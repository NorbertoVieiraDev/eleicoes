import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

import duckdb

spec = importlib.util.spec_from_file_location('partition_canonical', Path(__file__).parents[1] / 'scripts/partition_canonical.py')
partition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(partition)


class PartitionResourceTests(unittest.TestCase):
    def run_partition(self, mode, failure=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'votes-2024.parquet'
            output = root / 'shards'
            con = duckdb.connect()
            con.execute(f"COPY (SELECT * FROM (VALUES ('AC', 2024, 1, '001', 'A', 3), ('SP', 2024, 1, '002', 'B', 5), ('SP', 2024, 1, '002', 'B', 5), ('SP', 2024, 2, '003', 'C', NULL), (NULL, 2024, 1, '004', 'D', 0)) AS x(state_code, election_year, round, municipality_code, candidate_number, votes)) TO '{source}' (FORMAT PARQUET)")
            con.close()
            digest = hashlib.sha512(source.read_bytes()).hexdigest()
            real_connect = duckdb.connect
            attempts = []
            failed = False

            class Connection:
                def __init__(self):
                    self.raw = real_connect()

                def execute(self, sql, *args, **kwargs):
                    nonlocal failed
                    if sql.startswith('COPY ') and "IS NOT DISTINCT FROM 'SP'" in sql:
                        sorted_copy = ' ORDER BY ' in sql
                        attempts.append(sorted_copy)
                        if failure is not None and sorted_copy and not failed:
                            failed = True
                            temporary = Path(re.search(r" TO '([^']+)'", sql)[1])
                            temporary.write_bytes(b'unvalidated partial output')
                            raise failure('simulated resource or IO failure')
                        if failed and not sorted_copy:
                            temporary = Path(re.search(r" TO '([^']+)'", sql)[1])
                            self_test.assertFalse(temporary.exists(), 'failed output must be removed before retry')
                    return self.raw.execute(sql, *args, **kwargs)

                def __getattr__(self, name):
                    return getattr(self.raw, name)

            self_test = self
            argv = ['partition_canonical.py', '--input', str(source), '--output-dir', str(output),
                    '--sort-mode', mode, '--threads', '1', '--memory-limit', '256MiB',
                    '--temp-dir', str(root / 'spill'), '--max-temp-size', '128MiB']
            with patch.object(sys, 'argv', argv), patch.object(partition.duckdb, 'connect', side_effect=Connection), contextlib.redirect_stdout(io.StringIO()):
                partition.main()
            report = json.loads((output / 'manifest-votes-2024.json').read_text())
            self.assertEqual(report['source_rows'], 5)
            self.assertEqual(report['source_vote_sum'], '13')
            self.assertEqual(hashlib.sha512(source.read_bytes()).hexdigest(), digest)
            con = real_connect()
            original = f"read_parquet('{source}')"
            derived = f"read_parquet('{output}/votes-2024-*.parquet')"
            self.assertEqual(con.execute(f'DESCRIBE SELECT * FROM {original}').fetchall(), con.execute(f'DESCRIBE SELECT * FROM {derived}').fetchall())
            for left, right in [(original, derived), (derived, original)]:
                self.assertEqual(con.execute(f'SELECT count(*) FROM (SELECT * FROM {left} EXCEPT ALL SELECT * FROM {right})').fetchone()[0], 0)
            con.close()
            return report, attempts

    def test_default_required_sort_retains_rows_and_schema(self):
        report, attempts = self.run_partition('required')
        self.assertEqual(attempts, [True])
        self.assertTrue(all(s['sort_applied'] for s in report['shards']))

    def test_best_effort_retries_only_resource_failure(self):
        report, attempts = self.run_partition('best-effort', duckdb.OutOfMemoryException)
        self.assertEqual(attempts, [True, False])
        self.assertFalse(next(s['sort_applied'] for s in report['shards'] if s['state_code'] == 'SP'))
        self.assertTrue(all(s['sort_applied'] for s in report['shards'] if s['state_code'] != 'SP'))

    def test_required_sort_propagates_resource_failure(self):
        with self.assertRaises(duckdb.OutOfMemoryException):
            self.run_partition('required', duckdb.OutOfMemoryException)

    def test_best_effort_does_not_hide_other_failures(self):
        with self.assertRaises(duckdb.IOException):
            self.run_partition('best-effort', duckdb.IOException)

    def test_unsorted_mode_retains_values_and_duplicate_rows(self):
        report, attempts = self.run_partition('none')
        self.assertEqual(attempts, [False])
        self.assertFalse(any(s['sort_applied'] for s in report['shards']))


if __name__ == '__main__':
    unittest.main()
