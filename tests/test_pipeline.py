"""Synthetic integration tests: no network and no real voter/candidate records."""
import contextlib, csv, hashlib, importlib.util, io, json, pathlib, sys, tempfile, unittest, zipfile
import duckdb
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepare',ROOT/'scripts/prepare.py')
prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)

class PreparationTests(unittest.TestCase):
    def fixture(self,root,bad_checksum=False,bad_votes=False):
        name='bweb_1t_ZZ_fixture.zip';d=root/'data/2026/round-1';raw=d/'raw';raw.mkdir(parents=True)
        row={
          'ANO_ELEICAO':'2026','NR_TURNO':'1','CD_ELEICAO':'6257','CD_PLEITO':'3220','SG_UF':'ZZ',
          'CD_MUNICIPIO':'12','NM_MUNICIPIO':'LOCALIDADE SINTÉTICA','NR_ZONA':'1','NR_SECAO':'2',
          'NR_LOCAL_VOTACAO':'1015','CD_CARGO_PERGUNTA':'1','DS_CARGO_PERGUNTA':'Presidente',
          'CD_TIPO_VOTAVEL':'1','DS_TIPO_VOTAVEL':'Nominal','NR_VOTAVEL':'10','NM_VOTAVEL':'TESTE A',
          'NR_PARTIDO':'10','SG_PARTIDO':'TESTE','QT_VOTOS':'3','QT_APTOS':'10',
          'QT_COMPARECIMENTO':'5','QT_ABSTENCOES':'5','NR_URNA_EFETIVADA':'000123',
          'DS_SECOES_AGREGADAS':'3 / 4','DT_EMISSAO_BU':'2026-10-04 17:00:00','DT_BU_RECEBIDO':'2026-10-04 18:00:00'}
        other={**row,'NR_VOTAVEL':'20','NM_VOTAVEL':'TESTE B','QT_VOTOS':'bad' if bad_votes else '2'}
        text=io.StringIO();w=csv.DictWriter(text,fieldnames=list(row),delimiter=';');w.writeheader();w.writerows([row,other])
        with zipfile.ZipFile(raw/name,'w') as z:z.writestr('fixture.csv',text.getvalue().encode('latin-1'))
        digest=hashlib.sha512((raw/name).read_bytes()).hexdigest()
        (d/'manifest.json').write_text(json.dumps({'round':1,'resources':[{'url':'https://cdn.tse.jus.br/'+name,'sha512':'0'*128 if bad_checksum else digest}]}))
        return name

    def run_fixture(self,root,name):
        before_root,before_argv=prepare.ROOT,sys.argv
        try:
            prepare.ROOT=root;sys.argv=['prepare.py','--year','2026','--only',name]
            with contextlib.redirect_stdout(io.StringIO()):prepare.main()
        finally:prepare.ROOT=before_root;sys.argv=before_argv

    def test_preserves_votes_identifiers_and_deduplicates_turnout_grain(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);name=self.fixture(root);self.run_fixture(root,name)
            c=duckdb.connect();p=next((root/'derived').rglob('*.sections.parquet'))
            r=c.execute('select vote_rows,votes,eligible_min,turnout_min,duplicate_vote_keys,aggregated_sections from read_parquet(?)',[str(p)]).fetchone()
            self.assertEqual(r,(2,5,10,5,0,'3 / 4'))
            raw=next(p.parent.glob('bweb*fixture.parquet'))
            c.execute('create view f as '+prepare.fact_sql('read_parquet('+prepare.quote(raw)+')'))
            self.assertEqual(c.execute('select municipality_code,zone_number,section_number,urn_number,municipality_name from f limit 1').fetchone(),('00012','0001','0002','000123','LOCALIDADE SINTÉTICA'))
            self.assertEqual(c.execute('select sum(votes) from f').fetchone()[0],5)
            c.close()

    def test_checksum_mismatch_stops_preparation(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);name=self.fixture(root,bad_checksum=True)
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):self.run_fixture(root,name)
            self.assertFalse(list((root/'derived').rglob('*.parquet')))

    def test_non_numeric_votes_are_not_silently_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);name=self.fixture(root,bad_votes=True)
            with self.assertRaises(duckdb.ConversionException):self.run_fixture(root,name)
            self.assertFalse(list((root/'derived').rglob('*.json')))

if __name__=='__main__':unittest.main()
