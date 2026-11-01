"""Lossless BU CSV -> Parquet, section/office profiles, and queryable DuckDB views."""
import argparse, hashlib, io, json, pathlib, re, time, zipfile
import duckdb
ROOT = pathlib.Path(__file__).resolve().parents[1]

def quote(value):
    return "'" + str(value).replace("'", "''") + "'"

def fact_sql(source):
    # Keep electoral codes as text; numeric identifiers are not measures.
    return f"""SELECT cast(ANO_ELEICAO as integer) election_year,
      cast(NR_TURNO as integer) round, CD_ELEICAO election_id, CD_PLEITO event_id,
      SG_UF state, lpad(CD_MUNICIPIO,5,'0') municipality_code, NM_MUNICIPIO municipality_name,
      lpad(NR_ZONA,4,'0') zone_number, lpad(NR_SECAO,4,'0') section_number,
      NR_LOCAL_VOTACAO voting_location, CD_CARGO_PERGUNTA office_code, DS_CARGO_PERGUNTA office_name,
      CD_TIPO_VOTAVEL votable_type, DS_TIPO_VOTAVEL votable_type_name,
      NR_VOTAVEL votable_number, NM_VOTAVEL votable_name, NR_PARTIDO party_number, SG_PARTIDO party,
      cast(QT_VOTOS as bigint) votes, cast(QT_APTOS as bigint) eligible,
      cast(QT_COMPARECIMENTO as bigint) turnout, cast(QT_ABSTENCOES as bigint) abstentions,
      NR_URNA_EFETIVADA urn_number, DS_SECOES_AGREGADAS aggregated_sections,
      DT_EMISSAO_BU bu_issued_at, DT_BU_RECEBIDO bu_received_at,
      source_package, source_sha512
      FROM {source}"""

KEY = 'election_year, round, election_id, event_id, state, municipality_code, zone_number, section_number, office_code'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--year',type=int,required=True)
    ap.add_argument('--raw-dir',type=pathlib.Path,help='Optional existing flat ZIP directory; originals are never moved')
    ap.add_argument('--only',help='Process one package filename, for diagnostics')
    a=ap.parse_args()
    if a.year!=2026:
        ap.error('Only the 2026 schema is validated. Add a reviewed schema adapter for other years.')
    out=ROOT/'derived'/str(a.year);out.mkdir(parents=True,exist_ok=True)
    c=duckdb.connect();c.execute("SET memory_limit='2GB'; SET threads=2")
    c.execute('SET temp_directory='+quote(out/'spill'))
    manifests=sorted((ROOT/'data'/str(a.year)).glob('round-*/manifest.json'))
    expected=[]
    for manifest in manifests:
        m=json.loads(manifest.read_text())
        for r in m['resources']:
            name=r['url'].rsplit('/',1)[-1]
            if a.only and a.only!=name:continue
            raw=(a.raw_dir or manifest.parent/'raw')/name
            folder=out/manifest.parent.name;folder.mkdir(exist_ok=True)
            stem=name.removesuffix('.zip')
            parquet=folder/(stem+'.parquet'); sections=folder/(stem+'.sections.parquet')
            metadata=folder/(stem+'.json')
            expected.append((r,parquet,sections,metadata))
            if all(x.exists() for x in (parquet,sections,metadata)):
                old=json.loads(metadata.read_text())
                if old['source_sha512']==r['sha512'] and old.get('pipeline_version')==1:
                    print('RESUME',name,flush=True);continue
            start=time.time()
            h=hashlib.sha512()
            with raw.open('rb') as f:
                for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=r['sha512']:raise ValueError('Source checksum mismatch: '+name)
            scratch=folder/(stem+'.utf8.csv.part')
            try:
                with zipfile.ZipFile(raw) as z:
                    members=[n for n in z.namelist() if n.lower().endswith('.csv')]
                    if len(members)!=1:raise ValueError('Expected exactly one CSV: '+name)
                    with io.TextIOWrapper(z.open(members[0]),encoding='latin-1',newline='') as src, scratch.open('w',encoding='utf-8',newline='') as dst:
                        for chunk in iter(lambda:src.read(4*1024*1024),''):dst.write(chunk)
                # Preserve every source column as text, with explicit lineage.
                sql=f"SELECT *, {quote(name)} source_package, {quote(r['sha512'])} source_sha512 FROM read_csv({quote(scratch)}, delim=';', header=true, all_varchar=true, nullstr='', strict_mode=true)"
                tmp=parquet.with_suffix('.parquet.part')
                c.execute(f'COPY ({sql}) TO {quote(tmp)} (FORMAT PARQUET, COMPRESSION ZSTD)')
                tmp.replace(parquet)
                c.execute('CREATE OR REPLACE TEMP VIEW f AS '+fact_sql(f'read_parquet({quote(parquet)})'))
                section_tmp=sections.with_suffix('.parquet.part')
                # Materialize the result directly to avoid depending on relation introspection.
                relation=c.sql(f"""SELECT {KEY}, any_value(municipality_name) municipality_name,
                  any_value(office_name) office_name, count(*) vote_rows, sum(votes)::BIGINT votes,
                  min(eligible) eligible_min,max(eligible) eligible_max,min(turnout) turnout_min,max(turnout) turnout_max,
                  min(abstentions) abstentions_min,max(abstentions) abstentions_max,
                  count(distinct urn_number) urn_variants,any_value(urn_number) urn_number,
                  count(distinct aggregated_sections) aggregation_variants,any_value(aggregated_sections) aggregated_sections,
                  count(*)-count(distinct (votable_type,votable_number,party_number)) duplicate_vote_keys,
                  count(*) filter(where votes<0) negative_vote_rows,count(distinct voting_location) location_variants
                  FROM f GROUP BY {KEY}""")
                relation.write_parquet(str(section_tmp),compression='zstd');section_tmp.replace(sections)
                n=c.execute('select count(*) from f').fetchone()[0]
                metadata.write_text(json.dumps({'pipeline_version':1,'source_package':name,'source_sha512':r['sha512'],'rows':n,'parquet_bytes':parquet.stat().st_size,'seconds':round(time.time()-start,1)},indent=2)+'\n')
                print('PREPARED',name,n,'rows',round(time.time()-start,1),'s',flush=True)
            finally:
                if scratch.exists():scratch.unlink()
    if a.only:return
    if len(expected)!=56:raise ValueError('Expected 56 package resources for 2026')
    for r,p,s,m in expected:
        if not all(x.exists() for x in (p,s,m)):raise ValueError('Missing prepared package '+r['url'])
    c.close()
    db=duckdb.connect(str(out/'elections.duckdb'))
    db.execute("SET memory_limit='2GB'; SET threads=2")
    db.execute('SET temp_directory='+quote(out/'spill'))
    paths='['+','.join(quote(p) for _,p,_,_ in expected)+']'
    db.execute('CREATE OR REPLACE VIEW raw_bu AS SELECT * FROM read_parquet('+paths+')')
    db.execute('CREATE OR REPLACE VIEW votes AS '+fact_sql('raw_bu'))
    paths='['+','.join(quote(s) for _,_,s,_ in expected)+']'
    db.execute('CREATE OR REPLACE VIEW section_office AS SELECT * FROM read_parquet('+paths+')')
    db.execute("""CREATE OR REPLACE VIEW section_quality AS SELECT *,
      eligible_min=eligible_max AND turnout_min=turnout_max AND abstentions_min=abstentions_max
        AND urn_variants=1 AND aggregation_variants=1 AND location_variants=1 metadata_consistent,
      eligible_min=turnout_min+abstentions_min turnout_balances,
      votes=turnout_min*(CASE WHEN office_code='5' AND round=1 THEN 2 ELSE 1 END) ballots_balance
      FROM section_office""")
    db.execute("""CREATE OR REPLACE TABLE coverage AS SELECT election_year,round,election_id,event_id,state,office_code,office_name,
      count(*) section_office_records,count(distinct municipality_code) municipalities,
      sum(vote_rows)::BIGINT vote_rows,sum(votes)::BIGINT votes,
      sum(CASE WHEN metadata_consistent THEN eligible_min END)::BIGINT eligible,
      sum(CASE WHEN metadata_consistent THEN turnout_min END)::BIGINT turnout,
      count(*) filter(where NOT metadata_consistent) metadata_conflicts,
      count(*) filter(where NOT turnout_balances) turnout_imbalances,
      count(*) filter(where NOT ballots_balance) ballot_imbalances,
      sum(duplicate_vote_keys)::BIGINT duplicate_vote_keys,
      sum(negative_vote_rows)::BIGINT negative_vote_rows
      FROM section_quality GROUP BY ALL""")
    db.execute("""CREATE OR REPLACE TABLE candidate_municipality AS SELECT election_year,round,election_id,event_id,state,
      municipality_code,municipality_name,office_code,office_name,votable_type,votable_type_name,
      votable_number,votable_name,party_number,party,sum(votes)::BIGINT votes
      FROM votes WHERE try_cast(office_code as integer)>0 AND try_cast(votable_type as integer)>0 GROUP BY ALL""")
    db.execute("""CREATE OR REPLACE TABLE candidate_state AS SELECT election_year,round,election_id,event_id,state,
      office_code,office_name,votable_type,votable_type_name,votable_number,votable_name,party_number,party,
      sum(votes)::BIGINT votes FROM candidate_municipality GROUP BY ALL""")
    db.execute("""CREATE OR REPLACE TABLE candidates AS SELECT DISTINCT election_year,round,election_id,
      CASE WHEN office_code='1' THEN 'BR' ELSE state END constituency,office_code,office_name,
      votable_number,votable_name,party_number,party FROM candidate_state WHERE votable_type='1'""")
    db.execute("""CREATE OR REPLACE TABLE territories AS SELECT DISTINCT state,municipality_code,municipality_name,
      CASE WHEN state='ZZ' THEN NULL ELSE 'BR' END country_code FROM candidate_municipality""")
    db.execute("""CREATE OR REPLACE TABLE section_aliases AS
      SELECT DISTINCT election_year,round,election_id,event_id,state,municipality_code,zone_number,office_code,
        section_number principal_section_number, section_number query_section_number, false is_aggregated
      FROM section_office WHERE try_cast(office_code as integer)>0
      UNION
      SELECT DISTINCT election_year,round,election_id,event_id,state,municipality_code,zone_number,office_code,
        section_number principal_section_number, lpad(trim(alias),4,'0') query_section_number, true is_aggregated
      FROM section_office, unnest(string_split(aggregated_sections,'/')) AS members(alias)
      WHERE try_cast(office_code as integer)>0 AND regexp_full_match(trim(alias),'[0-9]{1,4}')
        AND lpad(trim(alias),4,'0')<>section_number""")
    report=ROOT/'reports'/str(a.year);report.mkdir(parents=True,exist_ok=True)
    for table in ['coverage','candidate_state','territories']:
        db.execute(f'COPY (SELECT * FROM {table} ORDER BY ALL) TO {quote(report/(table+".csv"))} (HEADER, DELIMITER \';\')')
    summary={'packages':len(expected),'source_rows':sum(json.loads(m.read_text())['rows'] for _,_,_,m in expected),'parquet_bytes':sum(p.stat().st_size for _,p,_,_ in expected)}
    for table in ['section_office','candidates','territories','candidate_municipality']:
        summary[table+'_rows']=db.execute('SELECT count(*) FROM '+table).fetchone()[0]
    summary['checks']=dict(zip(['metadata_conflicts','turnout_imbalances','ballot_imbalances','duplicate_vote_keys','negative_vote_rows'], db.execute('select sum(metadata_conflicts),sum(turnout_imbalances),sum(ballot_imbalances),sum(duplicate_vote_keys),sum(negative_vote_rows) from coverage').fetchone()))
    summary['null_keys_or_measures']=db.execute("select count(*) from votes where election_year is null or round is null or election_id is null or event_id is null or state is null or municipality_code is null or zone_number is null or section_number is null or office_code is null or votable_type is null or votable_number is null or votes is null or eligible is null or turnout is null or abstentions is null").fetchone()[0]
    summary['invalid_source_identity_or_code_width']=db.execute("select count(*) from raw_bu where ANO_ELEICAO<>'2026' or SG_UF<>regexp_extract(source_package,'bweb_[12]t_([A-Z]{2})_',1) or NR_TURNO<>regexp_extract(source_package,'bweb_([12])t_',1) or not regexp_full_match(CD_MUNICIPIO,'[0-9]{1,5}') or not regexp_full_match(NR_ZONA,'[0-9]{1,4}') or not regexp_full_match(NR_SECAO,'[0-9]{1,4}')").fetchone()[0]
    summary['source_placeholder_rows']=db.execute("select count(*) from votes where try_cast(office_code as integer)<=0 or try_cast(votable_type as integer)<=0").fetchone()[0]
    summary['observed_sections_by_round']=[dict(zip(['round','source_sections','contest_sections'],row)) for row in db.execute("select round,count(distinct(state,municipality_code,zone_number,section_number)),count(distinct(state,municipality_code,zone_number,section_number)) filter(where try_cast(office_code as integer)>0) from section_office group by round order by round").fetchall()]
    summary['aggregation_alias_conflicts']=db.execute("select count(*) from (select election_id,state,municipality_code,zone_number,office_code,query_section_number from section_aliases group by all having count(distinct principal_section_number)>1)").fetchone()[0]
    summary['unparsed_aggregation_values']=db.execute("select count(*) from section_office where aggregated_sections is not null and aggregated_sections not in ('#NULO#','-1','') and not regexp_full_match(aggregated_sections,'[0-9]{1,4}( * /? *[0-9]{1,4})*')").fetchone()[0]
    summary['limitations']=['Published packages only; independent expected-section roster reconciliation pending.','BU votes are not judicially adjusted official totalization.','Country mapping for overseas and IBGE map code crosswalk pending.','Candidate names are BU display names, not necessarily full registered names.']
    (report/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    db.close();print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
