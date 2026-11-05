#!/usr/bin/env python3
"""Create reproducible state-scoped Parquet files from canonical annual data.

The canonical source file is never changed. Each output retains every source row
and column for exactly one state_code value (plus a separate NULL shard). Only
row order and file boundaries change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re

import duckdb


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sha512(path: pathlib.Path) -> str:
    digest = hashlib.sha512()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=pathlib.Path, help="Annual canonical votes-YYYY.parquet or sections-YYYY.parquet")
    parser.add_argument("--output-dir", required=True, type=pathlib.Path, help="Directory for state-scoped Parquet files")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--sort-mode", choices=["required", "best-effort", "none"], default="required",
                        help="required preserves existing behavior; best-effort retries only sort resource failures without global sorting")
    parser.add_argument("--memory-limit", help="Optional DuckDB memory limit, e.g. 5GiB")
    parser.add_argument("--temp-dir", type=pathlib.Path, help="Optional external DuckDB spill directory")
    parser.add_argument("--max-temp-size", help="Optional spill limit, e.g. 3GiB")
    args = parser.parse_args()

    source = args.input.resolve()
    if not source.is_file():
        parser.error(f"input file does not exist: {source}")
    match = re.fullmatch(r"(votes|sections)-(20[0-9]{2})[.]parquet", source.name)
    if not match:
        parser.error("input filename must match votes-YYYY.parquet or sections-YYYY.parquet")
    kind, year = match.groups()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute(f"SET threads={max(1, args.threads)}")
    if args.memory_limit:
        con.execute(f"SET memory_limit={sql_string(args.memory_limit)}")
    if args.temp_dir:
        args.temp_dir.mkdir(parents=True, exist_ok=True)
        con.execute(f"SET temp_directory={sql_string(str(args.temp_dir.resolve()))}")
    if args.max_temp_size:
        con.execute(f"SET max_temp_directory_size={sql_string(args.max_temp_size)}")
    if args.sort_mode != "required":
        con.execute("SET preserve_insertion_order=false")
    source_sql = f"read_parquet({sql_string(str(source))})"
    columns = {row[0] for row in con.execute(f"DESCRIBE SELECT * FROM {source_sql}").fetchall()}
    if "state_code" not in columns:
        raise ValueError("source Parquet has no state_code column")

    value_columns = ["round", "office_code", "municipality_code", "zone_number", "section_number", "urn_number", "candidate_number"]
    order_by = ", ".join(quote_identifier(name) for name in value_columns if name in columns)
    vote_expr = "sum(votes)::HUGEINT" if "votes" in columns else "NULL::HUGEINT"
    null_vote_expr = "count(*) FILTER (WHERE votes IS NULL)" if "votes" in columns else "0::BIGINT"
    input_rows = con.execute(
        f"SELECT state_code, count(*)::BIGINT, {vote_expr}, {null_vote_expr} "
        f"FROM {source_sql} GROUP BY state_code ORDER BY state_code NULLS FIRST"
    ).fetchall()

    groups = []
    for state_code, row_count, vote_sum, null_vote_rows in input_rows:
        state = str(state_code).upper() if state_code is not None else "_NULL"
        if state != "_NULL" and not re.fullmatch(r"[A-Z0-9_-]{1,12}", state):
            raise ValueError(f"unsupported state_code for a safe filename: {state!r}")
        target = args.output_dir / f"{kind}-{year}-{state}.parquet"
        temporary = target.with_suffix(".parquet.part")
        predicate = '"state_code" IS NULL' if state_code is None else f'"state_code" IS NOT DISTINCT FROM {sql_string(str(state_code))}'
        sort_applied = bool(order_by) and args.sort_mode != "none"
        sort_sql = f" ORDER BY {order_by}" if sort_applied else ""
        def copy_sql(sort):
            return (
                f"COPY (SELECT * FROM {source_sql} WHERE {predicate}{sort}) "
                f"TO {sql_string(str(temporary))} (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
        try:
            con.execute(copy_sql(sort_sql))
        except duckdb.OutOfMemoryException:
            if args.sort_mode != "best-effort" or not sort_applied:
                raise
            # A failed sort is not a validated output. Retry the same rows and
            # columns in a streaming COPY; never suppress other failures.
            temporary.unlink(missing_ok=True)
            print(f"{target.name}: sort exceeded resources; retrying without global sort", flush=True)
            con.execute(copy_sql(""))
            sort_applied = False
        temporary.replace(target)

        check = con.execute(
            f"SELECT count(*)::BIGINT, {vote_expr}, {null_vote_expr} "
            f"FROM read_parquet({sql_string(str(target))})"
        ).fetchone()
        expected = (int(row_count), vote_sum, int(null_vote_rows))
        actual = (int(check[0]), check[1], int(check[2]))
        if expected != actual:
            target.unlink(missing_ok=True)
            raise ValueError(f"integrity check failed for {target.name}: expected {expected}, got {actual}")
        groups.append({
            "state_code": state_code,
            "output": target.name,
            "rows": int(row_count),
            "vote_sum": str(vote_sum) if vote_sum is not None else None,
            "null_vote_rows": int(null_vote_rows),
            "bytes": target.stat().st_size,
            "sha512": sha512(target),
            "sort_applied": sort_applied,
        })
        print(f"{target.name}: {row_count:,} rows; {target.stat().st_size:,} bytes", flush=True)

    if sum(group["rows"] for group in groups) != con.execute(f"SELECT count(*) FROM {source_sql}").fetchone()[0]:
        raise ValueError("state shard row counts do not sum to the canonical source row count")

    report = {
        "format_version": 1,
        "method": "DuckDB COPY of unchanged source columns, filtered by state_code; see sort_mode and each shard's sort_applied.",
        "sort_mode": args.sort_mode,
        "resources": {"threads": max(1, args.threads), "memory_limit": args.memory_limit,
                      "max_temp_size": args.max_temp_size},
        "source": source.name,
        "source_bytes": source.stat().st_size,
        "source_sha512": sha512(source),
        "source_rows": sum(group["rows"] for group in groups),
        "source_vote_sum": str(sum(int(group["vote_sum"] or 0) for group in groups)) if "votes" in columns else None,
        "shards": groups,
    }
    manifest = args.output_dir / f"manifest-{kind}-{year}.json"
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"manifest: {manifest}", flush=True)
    con.close()


if __name__ == "__main__":
    main()
