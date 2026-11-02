"""Download and verify inventoried TSE result archives from 2000–2010."""
import argparse,concurrent.futures,hashlib,json,pathlib,shutil,subprocess,time,urllib.parse,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]

def sha512(path):
    h=hashlib.sha512()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def download(resource):
    parsed=urllib.parse.urlsplit(resource['url'])
    if parsed.scheme!='https' or parsed.hostname!='cdn.tse.jus.br':raise ValueError('Unapproved source host')
    rawdir=ROOT/'data'/str(resource['year'])/'results'/'raw';rawdir.mkdir(parents=True,exist_ok=True)
    path=rawdir/resource['filename'];meta=rawdir/(resource['filename']+'.json')
    if path.exists() and path.stat().st_size:
        with zipfile.ZipFile(path) as z:
            bad=z.testzip()
            if bad:raise ValueError('Existing archive CRC failed: '+bad)
    else:
        part=path.with_name(path.name+'.part')
        if shutil.disk_usage(ROOT).free<20*1024**3:raise RuntimeError('Less than 20 GiB free; acquisition stopped')
        subprocess.run(['curl','--http1.1','--fail','--silent','--show-error','--location','--retry','3','--retry-delay','2','--connect-timeout','30','--max-time','1800','--continue-at','-','--output',str(part),resource['url']],check=True)
        with zipfile.ZipFile(part) as z:
            bad=z.testzip()
            if bad:raise ValueError('Downloaded archive CRC failed: '+bad)
        part.replace(path)
    digest=sha512(path)
    record={**resource,'download_status':'verified','source_sha512':digest,'source_bytes':path.stat().st_size,'catalog_hash_status':'not_published','downloaded_on':time.strftime('%Y-%m-%d',time.gmtime())}
    tmp=meta.with_suffix(meta.suffix+'.part');tmp.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');tmp.replace(meta)
    return {'year':resource['year'],'filename':resource['filename'],'scope':resource['scope'],'bytes':path.stat().st_size,'status':'verified'}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--workers',type=int,default=3,choices=(1,2,3,4));a=ap.parse_args()
    inventory=json.loads((ROOT/'data/catalog/legacy-results-2000-2010.json').read_text())
    results=[];failures=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(download,r):r for r in inventory['resources']}
        for f in concurrent.futures.as_completed(futures):
            r=futures[f]
            try:
                x=f.result();results.append(x);print(json.dumps(x,ensure_ascii=False),flush=True)
            except Exception as e:
                failure={'year':r['year'],'filename':r['filename'],'status':'failed','error':type(e).__name__+': '+str(e)};failures.append(failure);print(json.dumps(failure,ensure_ascii=False),flush=True)
    target=ROOT/'reports/history';target.mkdir(parents=True,exist_ok=True)
    report={'scope':'Official TSE result-by-section and section-detail archives, catalog cycles 2000–2010','resource_count':len(inventory['resources']),'verified':len(results),'failed':len(failures),'results':sorted(results,key=lambda x:(x['year'],x['filename'])),'failures':failures}
    (target/'legacy-results-downloads.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('FINISHED',len(results),'VERIFIED',len(failures),'FAILED')
    raise SystemExit(bool(failures))
