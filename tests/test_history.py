"""Historical raw-conversion regression tests, using synthetic source archives."""
import contextlib,hashlib,importlib.util,io,json,pathlib,tempfile,unittest,zipfile
import duckdb
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('history',ROOT/'scripts/collect_history.py')
history=importlib.util.module_from_spec(spec);spec.loader.exec_module(history)

class HistoryTests(unittest.TestCase):
    def run_source(self,content,member='fixture.csv',nested=False,corrupt_checksum=False):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=pathlib.Path(temp.name)
        raw=root/'data/2012/round-1/raw';raw.mkdir(parents=True)
        archive=raw/'fixture.zip'
        with zipfile.ZipFile(archive,'w') as z:
            if nested:
                data=io.BytesIO()
                with zipfile.ZipFile(data,'w') as inner:inner.writestr(member,content.encode('latin-1'))
                blob=data.getvalue();z.writestr('event/inner.zip',blob)
                z.writestr('event/inner.zip.sha512',('0'*128 if corrupt_checksum else hashlib.sha512(blob).hexdigest())+'  inner.zip')
            else:z.writestr(member,content.encode('latin-1'))
        r={'year':2012,'round':1,'scope':'regular','state':'AC','url':'https://cdn.tse.jus.br/fixture.zip','filename':'fixture.zip','checksum_url':None}
        before=history.ROOT
        try:
            history.ROOT=root
            with contextlib.redirect_stdout(io.StringIO()):result=history.collect(r)
        finally:history.ROOT=before
        return root,result

    def test_header_and_empty_strings_accents_and_duplicates_are_preserved(self):
        content='"DT_GERACAO";"SG_ UF";"NAME";"EMPTY"\n"01/01/2012";"AC";"JOÃO; TESTE";""\n"01/01/2012";"AC";"JOÃO; TESTE";""\n'
        root,result=self.run_source(content)
        self.assertEqual(result['status'],'converted');m=result['members'][0]
        self.assertEqual(m['rows'],2);self.assertEqual(m['fingerprint_comparison'],'matched')
        c=duckdb.connect();rows=c.execute('select "SG_ UF",NAME,EMPTY from read_parquet(?)',[str(root/m['parquet_file'])]).fetchall();c.close()
        self.assertEqual(rows,[('AC','JOÃO; TESTE',''),('AC','JOÃO; TESTE','')])

    def test_headerless_first_record_is_data_and_fields_are_positional(self):
        root,result=self.run_source('"01/01/2012";"0001";"3"\n"01/01/2012";"0002";"4"\n',member='fixture.txt')
        m=result['members'][0];self.assertEqual(m['column_naming'],'ordinal_no_semantic_mapping');self.assertEqual(m['rows'],2)
        c=duckdb.connect();rows=c.execute('select field_002 from read_parquet(?) order by 1',[str(root/m['parquet_file'])]).fetchall();c.close()
        self.assertEqual(rows,[('0001',),('0002',)])

    def test_unescaped_quotes_in_candidate_name_are_repaired_and_recorded(self):
        content='"DT_GERACAO";"NR_VOTAVEL";"NM_VOTAVEL"\n"18/11/2020";"17024";"ZÉ "APENAS PAPAI""\n'
        root,result=self.run_source(content)
        self.assertEqual(result['status'],'converted');m=result['members'][0]
        self.assertGreater(m['csv_unescaped_quote_repairs'],0)
        c=duckdb.connect();rows=c.execute('select NM_VOTAVEL from read_parquet(?)',[str(root/m['parquet_file'])]).fetchall();c.close()
        self.assertEqual(rows,[('ZÉ "APENAS PAPAI"',)])

    def test_nested_archives_and_published_inner_checksum(self):
        root,result=self.run_source('DT_GERACAO;NR_TURNO\n01/01/2012;1\n',nested=True)
        self.assertEqual(result['status'],'converted');self.assertEqual(result['nested_archives'][0]['published_checksum_status'],'matched')
        self.assertIn('inner.zip::fixture.csv',result['members'][0]['source_member'])

    def test_bad_nested_checksum_blocks_conversion(self):
        root,result=self.run_source('DT_GERACAO;NR_TURNO\n01/01/2012;1\n',nested=True,corrupt_checksum=True)
        self.assertEqual(result['status'],'failed');self.assertIn('checksum mismatch',result['error']);self.assertFalse(list((root/'derived').rglob('*.parquet')))

    def test_unrecognized_schema_is_not_guessed(self):
        _,result=self.run_source('unknown;header\n1;2\n')
        self.assertEqual(result['status'],'failed');self.assertIn('Unrecognized source schema',result['error'])

if __name__=='__main__':unittest.main()
