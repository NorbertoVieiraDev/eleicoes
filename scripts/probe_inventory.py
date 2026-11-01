"""Read-only size/availability probe of reviewed official source URLs."""
import concurrent.futures,json,pathlib,re,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
def probe(r):
    x=dict(r)
    result=subprocess.run(['curl','--silent','--show-error','--head','--location','--max-time','45','--connect-timeout','15',r['url']],capture_output=True,text=True)
    codes=re.findall(r'HTTP/\S+ (\d{3})',result.stdout)
    lengths=re.findall(r'(?im)^content-length:\s*(\d+)',result.stdout)
    x['head_status']=int(codes[-1]) if codes else None
    x['head_bytes']=int(lengths[-1]) if lengths else None
    if result.returncode:x['head_error']=result.stderr.strip()
    print(r['year'],r['filename'],x['head_status'],x['head_bytes'],flush=True)
    return x
if __name__=='__main__':
    p=ROOT/'data/catalog/bu-inventory.json';d=json.loads(p.read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:d['resources']=list(pool.map(probe,d['resources']))
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    print('TOTAL_BYTES',sum(x.get('head_bytes') or 0 for x in d['resources']),'PACKAGES',len(d['resources']),flush=True)
