#!/usr/bin/env python3
"""Sort a verified state shard with dictionary-coded trace fields and bounded batches.

Only row order and Parquet encoding change. Repeated strings are not
carried through the external sort; they are reconstructed exactly before writing.
Requires the optional requirements-partition.txt dependencies.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import duckdb
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

SORT = ['round', 'office_code', 'municipality_code', 'zone_number', 'section_number', 'urn_number', 'candidate_number']


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def identifier(value):
    return '"' + value.replace('"', '""') + '"'


def sha512(path):
    digest = hashlib.sha512()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def sort_partition(source, output_dir, expected_sha512, canonical_sha512):
    if not re.fullmatch(r'[a-f0-9]{128}', canonical_sha512):
        raise ValueError('Expected the canonical SHA-512 identity')
    source = Path(source).resolve()
    output_dir = Path(output_dir).resolve()
    if not re.fullmatch(r'(votes|sections)-\d{4}-([A-Z]{2}|_NULL)\.parquet', source.name):
        raise ValueError('Expected an existing state shard filename')
    if sha512(source) != expected_sha512:
        raise ValueError('Input SHA-512 mismatch')
    output_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute('SET threads=1')
    con.execute("SET memory_limit='6GiB'")
    con.execute(f'SET temp_directory={literal(output_dir / "spill")}')
    con.execute("SET max_temp_directory_size='3GiB'")
    con.execute('SET preserve_insertion_order=false')
    relation = f'read_parquet({literal(source)})'
    schema = con.execute(f'SELECT * FROM {relation} LIMIT 0').fetch_arrow_table().schema
    columns = schema.names
    dictionaries = {}
    aliases = {}
    projection = []
    joins = []
    for index, name in enumerate(columns):
        q = 's.' + identifier(name)
        is_string = pa.types.is_string(schema.field(name).type) or pa.types.is_large_string(schema.field(name).type)
        values = con.execute(f'SELECT DISTINCT {identifier(name)} FROM {relation} ORDER BY {identifier(name)} NULLS LAST LIMIT 1000001').fetchall() if is_string else []
        if values and len(values) <= 1000000:
            values = [row[0] for row in values]
            dictionaries[name] = pa.array(values, type=schema.field(name).type)
            alias = f'__dictionary_{index}'
            if alias in columns:
                raise ValueError('Unexpected dictionary alias collision')
            aliases[name] = alias
            table_name = f'__dictionary_table_{index}'
            con.register(table_name, pa.table({'id': pa.array(range(len(values)), type=pa.int32()),
                                             'value': dictionaries[name]}))
            joins.append(f'LEFT JOIN {identifier(table_name)} d{index} ON {q} IS NOT DISTINCT FROM d{index}.value')
            projection.append(f'd{index}.id AS {identifier(alias)}')
        else:
            projection.append(q)
    keys = [name for name in SORT if name in columns]
    if not keys:
        raise ValueError('No supported sort keys')
    # Ordered dictionary IDs preserve the exact ASC / NULLS LAST key order.
    # Dictionary IDs are plain join columns, so unused raw strings are pruned before sorting.
    con.execute("SET disabled_optimizers='join_order'")
    compact = f'SELECT {",".join(projection)} FROM {relation} s ' + ' '.join(joins)
    sql = compact + ' ORDER BY ' + ','.join(identifier(aliases.get(k,k)) for k in keys)
    temporary = output_dir / (source.stem + '-sorted.parquet.part')
    try:
        reader = con.execute(sql).fetch_record_batch(rows_per_batch=122880)
        with pq.ParquetWriter(temporary, schema, compression='zstd', use_dictionary=True, write_statistics=True) as writer:
            for batch in reader:
                arrays = []
                for name in columns:
                    values = batch.column(batch.schema.get_field_index(aliases.get(name, name)))
                    if name in aliases:
                        if values.null_count:
                            raise ValueError(f'Unmapped trace value: {name}')
                        values = pc.take(dictionaries[name], values)
                    arrays.append(values)
                writer.write_batch(pa.RecordBatch.from_arrays(arrays, schema=schema), row_group_size=122880)
        # Streaming logical diagnostics cover all values without a huge raw-row hash table.
        hashes = 'hash(' + ','.join(identifier(name) for name in columns) + ')'
        measures = f'count(*),bit_xor({hashes}),sum({hashes})::HUGEINT'
        if 'votes' in columns:
            measures += ',sum(votes)::HUGEINT,count(*) FILTER (WHERE votes IS NULL)'
        before = con.execute(f'SELECT {measures} FROM {relation}').fetchone()
        after_relation = f'read_parquet({literal(temporary)})'
        after = con.execute(f'SELECT {measures} FROM {after_relation}').fetchone()
        if before != after:
            raise ValueError('Row-count/value-fingerprint/vote diagnostics mismatch')
        if con.execute(f'DESCRIBE SELECT * FROM {relation}').fetchall() != con.execute(f'DESCRIBE SELECT * FROM {after_relation}').fetchall():
            raise ValueError('Schema mismatch')
        if sha512(source) != expected_sha512:
            raise ValueError('Input changed during generation')
        output_sha512 = sha512(temporary)
        target = output_dir / (source.stem + '-sorted-' + output_sha512[:12] + '.parquet')
        if target.exists() and sha512(target) != output_sha512:
            raise ValueError('Output identity collision')
        temporary.replace(target)
        report = {'format_version': 1, 'source': source.name, 'source_sha512': expected_sha512,
                  'canonical_source_sha512': canonical_sha512, 'output': target.name,
                  'sha512': output_sha512, 'bytes': target.stat().st_size, 'rows': before[0],
                  'globally_sorted': True, 'sort_keys': keys,
                  'dictionary_cardinalities': {name: len(values) for name, values in dictionaries.items()},
                  'row_value_fingerprint_xor': str(before[1]), 'row_value_fingerprint_sum': str(before[2]),
                  'vote_sum': str(before[3]) if 'votes' in columns else None,
                  'null_vote_rows': before[4] if 'votes' in columns else None,
                  'validation': 'Schema, source/output SHA-512, row/vote counts and two logical all-column hash aggregates; fingerprints are diagnostics, not a collision-free multiset proof.'}
        manifest = output_dir / ('manifest-' + source.stem + '-sorted.json')
        metadata_tmp = manifest.with_suffix('.json.tmp')
        metadata_tmp.write_text(json.dumps(report, indent=2) + '\n')
        metadata_tmp.replace(manifest)
        return report
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--expected-input-sha512', required=True)
    parser.add_argument('--canonical-sha512', required=True)
    args = parser.parse_args()
    print(json.dumps(sort_partition(args.input, args.output_dir, args.expected_input_sha512, args.canonical_sha512), indent=2))


if __name__ == '__main__':
    main()
