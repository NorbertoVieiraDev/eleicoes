"""Download and preserve every reviewed BU package; convert CSV/headerless TXT to raw Parquet.
No cross-year semantic harmonization is performed. See docs/*/historical-data.md.
"""
import argparse,concurrent.futures,csv,hashlib,io,json,pathlib,re,shutil,subprocess,time,urllib.parse,zipfile
import duckdb
ROOT=pathlib.Path(__file__).resolve().parents[1]
VERSION=2

def sqlstr(value):return "'"+str(value).replace("'","''")+"'"
def digest(path,algorithm='sha512'):
    h=hashlib.new(algorithm)
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def fetch(url,path):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname!='cdn.tse.jus.br':raise ValueError('Unapproved official source URL')
    if path.exists() and path.stat().st_size:return
    part=path.with_name(path.name+'.part')
    subprocess.run(['curl','--fail','--silent','--show-error','--location','--retry','3','--retry-delay','2','--connect-timeout','30','--max-time','1800','--continue-at','-','--output',str(part),url],check=True)
    part.replace(path)

def schema(first_line,member):
    first=next(csv.reader([first_line],delimiter=';',quotechar='"'))
    if not first:raise ValueError('Empty first record')
    if first[0].lstrip('\ufeff')=='DT_GERACAO':
        if len(first)!=len(set(first)):raise ValueError('Duplicate source header names require explicit adapter')
        return True,first
    if re.fullmatch(r'\d{2}/\d{2}/\d{4}',first[0]):
        return False,[f'field_{i:03d}' for i in range(1,len(first)+1)]
    raise ValueError('Unrecognized source schema: '+member)

def repair_unescaped_quotes(line):
    """Escape quote marks inside quoted fields when they precede field content.

    Some 2020 source rows contain unescaped quote marks inside names. Repair
    only quote marks that cannot be a field terminator, and retain the literal
    quote in the parsed value.
    """
    out=[];quoted=False;field_content=False;repairs=0;i=0
    while i<len(line):
        ch=line[i]
        if not quoted:
            out.append(ch)
            if ch=='"':quoted=True;field_content=False
            elif ch==';':field_content=False
            elif ch not in '\r\n':field_content=True
            i+=1;continue
        if ch!='"':
            out.append(ch);field_content=True;i+=1;continue
        nxt=line[i+1] if i+1<len(line) else ''
        after=line[i+2] if i+2<len(line) else ''
        if nxt=='"':
            if after in (';','\r','\n',''):
                if field_content:
                    out.extend(('"','"','"'));repairs+=1
                else:out.extend(('"','"'))
                quoted=False;i+=2
            else:
                out.extend(('"','"'));i+=2
        elif nxt in (';','\r','\n',''):
            out.append(ch);quoted=False;i+=1
        else:
            out.extend(('"','"'));field_content=True;repairs+=1;i+=1
    return ''.join(out),repairs

def convert_member(c,z,member,r,out,source_sha,prefix=""):
    safe=re.sub(r'[^A-Za-z0-9_.-]','_',pathlib.PurePosixPath(member.filename).stem)
    name=r['filename'].removesuffix('.zip')+'__'+(hashlib.sha256(prefix.encode()).hexdigest()[:12]+'__' if prefix else '')+str(z.infolist().index(member))+'__'+safe
    scratch=out/(name+'.utf8.part')
    final=out/(name+'.parquet');part=out/(name+'.parquet.part')
    try:
        with io.TextIOWrapper(z.open(member),encoding='latin-1',newline='') as src:
            first_source_line=src.readline()
            if not first_source_line:
                return {'source_member':prefix+member.filename,'status':'empty_member','source_uncompressed_bytes':member.file_size,'rows':0}
            first_line,quote_repairs=repair_unescaped_quotes(first_source_line)
            has_header,columns=schema(first_line,member.filename)
            with scratch.open('w',encoding='utf-8',newline='') as dst:
                dst.write(first_line)
                for source_line in src:
                    normalized,count=repair_unescaped_quotes(source_line)
                    quote_repairs+=count;dst.write(normalized)
        # Historical raw exports retain empty strings. They are not the legacy 2026 analytical view.
        options="delim=';', header="+('true' if has_header else 'false')+", all_varchar=true, nullstr='', strict_mode=true, auto_detect=false, quote='\"', escape='\"', columns={"+','.join(sqlstr(n)+":'VARCHAR'" for n in columns)+'}, force_not_null=['+','.join(sqlstr(n) for n in columns)+']'
        query=f"SELECT *,{sqlstr(r['filename'])} source_package,{sqlstr(source_sha)} source_sha512 FROM read_csv({sqlstr(scratch)},{options})"
        c.execute(f'COPY ({query}) TO {sqlstr(part)} (FORMAT PARQUET,COMPRESSION ZSTD)')
        part.replace(final)
        source_query=f"SELECT * FROM read_csv({sqlstr(scratch)},{options})"
        # Compare unordered row multisets with two commutative fingerprints plus count.
        # Hashes are diagnostic; EXCEPT ALL can be requested separately for exact comparisons.
        names=','.join('"'+n.replace('"','""')+'"' for n in columns)
        fingerprint=f"count(*)::BIGINT n, sum(hash({names}))::VARCHAR fingerprint_sum, bit_xor(hash({names}))::VARCHAR fingerprint_xor"
        original=c.execute('SELECT '+fingerprint+' FROM ('+source_query+')').fetchone()
        prepared=c.execute('SELECT '+fingerprint+' FROM read_parquet('+sqlstr(final)+')').fetchone()
        if original!=prepared:raise ValueError('Source/Parquet row count or fingerprint mismatch')
        got=[x[0] for x in c.execute('DESCRIBE SELECT * FROM read_parquet('+sqlstr(final)+')').fetchall()]
        if got!=columns+['source_package','source_sha512']:raise ValueError('Output schema mismatch')
        rounds=[]; election_dates=[]; election_year_values=[]
        if 'NR_TURNO' in columns:rounds=[x[0] for x in c.execute('select distinct NR_TURNO from read_parquet('+sqlstr(final)+') order by 1').fetchall()]
        if 'DT_PLEITO' in columns:election_dates=[x[0] for x in c.execute('select distinct DT_PLEITO from read_parquet('+sqlstr(final)+') order by 1').fetchall()]
        if 'ANO_ELEICAO' in columns:election_year_values=[x[0] for x in c.execute('select distinct ANO_ELEICAO from read_parquet('+sqlstr(final)+') order by 1').fetchall()]
        return {'source_member':prefix+member.filename,'election_date_values':election_dates,'election_year_values':election_year_values,'status':'converted','source_uncompressed_bytes':member.file_size,'source_has_header':has_header,'columns':columns,'column_naming':'source_header' if has_header else 'ordinal_no_semantic_mapping','csv_unescaped_quote_repairs':quote_repairs,'rows':original[0],'logical_fingerprint_sum':original[1],'logical_fingerprint_xor':original[2],'fingerprint_comparison':'matched','parquet_file':str(final.relative_to(ROOT)),'parquet_bytes':final.stat().st_size,'parquet_sha512':digest(final),'round_values':rounds,'csv_empty_field_convention':'empty_string_retained','encoding_from':'latin-1','encoding_to':'utf-8','compression':'zstd'}
    finally:
        if scratch.exists():scratch.unlink()

def collect(r):
    start=time.time();partition='supplementary' if r['scope']=='supplementary' else f"round-{r['round']}"
    rawdir=ROOT/'data'/str(r['year'])/partition/'raw';rawdir.mkdir(parents=True,exist_ok=True)
    out=ROOT/'derived/history'/str(r['year'])/partition;out.mkdir(parents=True,exist_ok=True)
    raw=rawdir/r['filename'];meta=out/(r['filename']+'.json')
    if meta.exists():
        previous=json.loads(meta.read_text())
        if previous.get('pipeline_version') in {1,VERSION} and previous.get('status')=='converted' and previous.get('source_url')==r['url'] and previous.get('published_checksum_url')==r.get('checksum_url') and all((ROOT/x['parquet_file']).exists() for x in previous['members'] if x['status']=='converted'):
            print('RESUME',r['year'],r['filename'],flush=True);return previous
    result={'year':r['year'],'round':r['round'],'scope':r['scope'],'state':r['state'],'source_url':r['url'],'source_package':r['filename'],'pipeline_version':VERSION,'duckdb_version':duckdb.__version__,'members':[]}
    c=None
    try:
        if shutil.disk_usage(ROOT).free<20*1024**3:raise RuntimeError('Less than 20 GiB free; acquisition stopped to protect disk space')
        fetch(r['url'],raw)
        source_sha=digest(raw)
        result.update(source_sha512=source_sha,source_bytes=raw.stat().st_size)
        check=r.get('checksum_url')
        if check:
            cp=rawdir/check.rsplit('/',1)[-1];fetch(check,cp)
            algorithm='sha1' if check.endswith('.sha1') else 'sha512';length=40 if algorithm=='sha1' else 128
            candidates=re.findall(r'(?i)\b[0-9a-f]{'+str(length)+r'}\b',cp.read_text(encoding='utf-8-sig',errors='strict'))
            actual=source_sha if algorithm=='sha512' else digest(raw,algorithm)
            if len(candidates)!=1 or candidates[0].lower()!=actual:raise ValueError('Published '+algorithm+' mismatch')
            result.update(published_checksum_algorithm=algorithm,published_checksum=candidates[0].lower(),published_checksum_status='matched',published_checksum_url=check)
        else:result['published_checksum_status']='not_listed_in_catalog'
        c=duckdb.connect();c.execute("SET memory_limit='1GB'; SET threads=1");c.execute('SET temp_directory='+sqlstr(out/('spill-'+raw.stem)))
        result['nested_archives']=[]
        def visit(z,prefix='',depth=0):
            if depth>5:raise ValueError('Nested archive depth exceeds reviewed limit')
            found=0
            for m in z.infolist():
                if m.is_dir():continue
                suffix=pathlib.PurePosixPath(m.filename).suffix.lower()
                if suffix in {'.csv','.txt'} and not pathlib.PurePosixPath(m.filename).name.lower().startswith(('leiame','leia-me','readme','_leiame')):
                    result['members'].append(convert_member(c,z,m,r,out,source_sha,prefix));found+=1
                elif suffix=='.zip':
                    if m.file_size>256*1024*1024:raise ValueError('Nested ZIP exceeds 256 MiB in-memory limit; use streamed adapter')
                    data=z.read(m);inner={'name':prefix+m.filename,'sha512':hashlib.sha512(data).hexdigest(),'published_checksum_status':'not_present_in_parent'}
                    for ext,alg in [('.sha512','sha512'),('.sha1','sha1')]:
                        sibling=m.filename+ext
                        if sibling in z.namelist():
                            n=128 if alg=='sha512' else 40
                            values=re.findall(r'(?i)\b[0-9a-f]{'+str(n)+r'}\b',z.read(sibling).decode('utf-8-sig'))
                            if len(values)!=1 or hashlib.new(alg,data).hexdigest()!=values[0].lower():raise ValueError('Nested published checksum mismatch: '+m.filename)
                            inner.update(published_checksum_status='matched',published_checksum_algorithm=alg,published_checksum=values[0].lower());break
                    result['nested_archives'].append(inner)
                    with zipfile.ZipFile(io.BytesIO(data)) as nested:found+=visit(nested,prefix+m.filename+'::',depth+1)
            return found
        with zipfile.ZipFile(raw) as z:
            result['archive_members']=[{'name':m.filename,'bytes':m.file_size} for m in z.infolist()]
            if not visit(z):raise ValueError('No tabular CSV/TXT members found')
        result.update(status='converted',rows=sum(m['rows'] for m in result['members']),parquet_bytes=sum(m.get('parquet_bytes',0) for m in result['members']))
    except Exception as e:
        result.update(status='failed',error=type(e).__name__+': '+str(e).replace(str(ROOT),'<project>'))
    finally:
        if c:c.close()
    result['seconds']=round(time.time()-start,1)
    tmp=meta.with_suffix('.json.part');tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');tmp.replace(meta)
    print(json.dumps({k:result.get(k) for k in ['year','source_package','status','rows','parquet_bytes','error']},ensure_ascii=False),flush=True)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--year',type=int);ap.add_argument('--workers',type=int,default=2,choices=[1,2,3]);ap.add_argument('--include-2026',action='store_true',help='Create historical-format exports as well as existing 2026 outputs');a=ap.parse_args()
    inv=json.loads((ROOT/'data/catalog/bu-inventory.json').read_text());items=[r for r in inv['resources'] if (a.year is None or r['year']==a.year) and (a.include_2026 or r['year']!=2026)]
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for result in pool.map(collect,items):
            results.append(result)
            target=ROOT/'reports/history';target.mkdir(parents=True,exist_ok=True)
            temp=target/'conversion-records.json.part';temp.write_text(json.dumps({'pipeline_version':VERSION,'scope':'BU tabular packages found in official catalog; 2026 existing outputs tracked separately unless explicitly included','results':results},ensure_ascii=False,indent=2)+'\n');temp.replace(target/'conversion-records.json')
    print('FINISHED',len(results),'CONVERTED',sum(r['status']=='converted' for r in results),flush=True)
    raise SystemExit(0 if all(r['status']=='converted' for r in results) else 1)
