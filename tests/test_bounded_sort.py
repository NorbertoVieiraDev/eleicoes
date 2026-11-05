import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

import duckdb

spec=importlib.util.spec_from_file_location('bounded_sort',Path(__file__).parents[1]/'scripts/sort_partition_bounded.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BoundedSortTests(unittest.TestCase):
    def test_exact_rows_schema_duplicates_nulls_and_sort_order(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'votes-2024-SP.parquet';con=duckdb.connect()
            con.execute(f"COPY (SELECT * FROM (VALUES (2,'0002','B',5,'repeated-url','sha',NULL,'pkg'),(1,'0001','A',NULL,'repeated-url','sha',NULL,'pkg'),(1,'0001','A',NULL,'repeated-url','sha',NULL,'pkg'),(1,'0001','C',0,'other-url',NULL,'file','pkg')) AS x(round,municipality_code,candidate_number,votes,source_url,source_sha512,source_member,source_package)) TO '{source}' (FORMAT PARQUET)")
            digest=hashlib.sha512(source.read_bytes()).hexdigest()
            report=module.sort_partition(source,root/'sorted',digest,'0'*128)
            target=root/'sorted'/report['output']
            self.assertEqual(report['rows'],4)
            self.assertEqual(report['vote_sum'],'5')
            for a,b in [(source,target),(target,source)]:
                self.assertEqual(con.execute(f"SELECT count(*) FROM (SELECT * FROM read_parquet('{a}') EXCEPT ALL SELECT * FROM read_parquet('{b}'))").fetchone()[0],0)
            self.assertEqual(con.execute(f"SELECT round,municipality_code,candidate_number FROM read_parquet('{target}')").fetchall(),[(1,'0001','A'),(1,'0001','A'),(1,'0001','C'),(2,'0002','B')])
            self.assertEqual(hashlib.sha512(source.read_bytes()).hexdigest(),digest)
            con.close()

    def test_dictionary_keys_keep_lexical_order_and_nulls_last(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'votes-2024-SP.parquet';con=duckdb.connect()
            con.execute(f"COPY (SELECT * FROM (VALUES ('2',1), (NULL,2), ('10',3)) AS x(candidate_number,votes)) TO '{source}' (FORMAT PARQUET)")
            digest=hashlib.sha512(source.read_bytes()).hexdigest()
            r=module.sort_partition(source,root/'sorted',digest,'0'*128)
            target=root/'sorted'/r['output']
            self.assertEqual(con.execute(f"SELECT candidate_number FROM read_parquet('{target}')").fetchall(),[('10',),('2',),(None,)])
            con.close()

    def test_input_identity_is_required_before_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'votes-2024-SP.parquet';source.write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'SHA-512 mismatch'):
                module.sort_partition(source,root/'sorted','0'*128,'0'*128)
            self.assertFalse((root/'sorted').exists())


if __name__=='__main__':unittest.main()
