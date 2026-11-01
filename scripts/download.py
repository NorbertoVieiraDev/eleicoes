"""Download official BU ZIPs listed in reviewed per-year/per-round manifests."""
import argparse, concurrent.futures, hashlib, json, pathlib, subprocess, urllib.parse
ROOT=pathlib.Path(__file__).resolve().parents[1]

def sha512(path):
    h=hashlib.sha512()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

def download(entry):
    directory,r=entry
    u=urllib.parse.urlsplit(r['url'])
    if u.scheme!='https' or u.hostname!='cdn.tse.jus.br':raise ValueError('Unapproved source host')
    name=pathlib.PurePosixPath(u.path).name
    if not name.endswith('.zip') or '/' in name:raise ValueError('Expected ZIP filename')
    directory.mkdir(parents=True,exist_ok=True)
    final=directory/name;partial=directory/(name+'.part')
    if not final.exists():
        subprocess.run(['curl','--fail','--silent','--show-error','--location','--retry','3','--connect-timeout','30','--max-time','1800','--continue-at','-','--output',str(partial),r['url']],check=True)
        if sha512(partial)!=r['sha512']:raise ValueError('Checksum mismatch: '+name)
        partial.replace(final)
    elif sha512(final)!=r['sha512']:
        raise ValueError('Existing file checksum mismatch; retained for investigation: '+name)
    print('VERIFIED',name,flush=True)
    return name

def main():
    p=argparse.ArgumentParser();p.add_argument('--year',required=True,type=int);p.add_argument('--round',choices=[1,2],type=int);a=p.parse_args()
    entries=[]
    for path in sorted((ROOT/'data'/str(a.year)).glob('round-*/manifest.json')):
        m=json.loads(path.read_text())
        if a.round and m['round']!=a.round:continue
        entries.extend((path.parent/'raw',r) for r in m['resources'])
    if not entries:p.error('No reviewed manifest for the selected year/round')
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        names=list(pool.map(download,entries))
    print('VERIFIED PACKAGES',len(names))

if __name__=='__main__':main()
