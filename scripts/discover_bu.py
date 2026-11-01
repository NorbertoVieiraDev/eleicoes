"""Discover tabular BU ZIPs through the official CKAN catalog (not all TSE datasets)."""
import datetime,json,pathlib,re,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
QUERY='https://dadosabertos.tse.jus.br/api/3/action/package_search?q=boletim&rows=1000'

def inventory(payload,retrieved_on):
    result=payload['result']
    if len(result['results'])!=result['count']:raise ValueError('Catalog result truncated; implement pagination before collecting')
    resources=[];datasets=[]
    for d in result['results']:
        year=int(re.search(r'20\d\d',d['name']).group());supplementary='suplement' in d['name']
        datasets.append({'name':d['name'],'title':d['title'],'catalog_year':year,'license_id':d.get('license_id'),'license_url':d.get('license_url'),'metadata_modified':d.get('metadata_modified')})
        for r in d['resources']:
            url=r['url'];correction=None
            if '/buweb/' not in url.lower():continue
            if 'boletim de urna' in r['name'].lower() and url.endswith('.zip.sha512'):
                url=url.removesuffix('.sha512');correction='Catalog BU resource pointed to checksum; removed .sha512'
            if not url.lower().endswith('.zip'):continue
            name=url.rsplit('/',1)[-1];match=re.search(r'(?i)bweb_([12])t_([a-z]{2})_',name)
            checks=[x['url'] for x in d['resources'] if x['url'].lower() in {(url+'.sha512').lower(),(url+'.sha1').lower()}]
            resources.append({'dataset':d['name'],'dataset_url':'https://dadosabertos.tse.jus.br/dataset/'+d['name'],'year':year,'round':int(match[1]) if match else None,'scope':'supplementary' if supplementary else 'regular','state':match[2].upper() if match else None,'name':r['name'],'url':url,'catalog_url':r['url'],'catalog_correction':correction,'checksum_url':checks[0] if checks else None,'source_format':r.get('format'),'filename':name})
    if len({r['url'] for r in resources})!=len(resources):raise ValueError('Duplicate source ZIP URLs require review')
    return {'retrieved_on':retrieved_on,'query':QUERY,'matching_datasets':result['count'],'datasets':datasets,'resources':resources}

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as td:
        p=pathlib.Path(td)/'catalog.json'
        subprocess.run(['curl','--fail','--silent','--show-error','--location','--max-time','60',QUERY,'-o',str(p)],check=True)
        result=inventory(json.loads(p.read_text()),datetime.datetime.now(datetime.timezone.utc).date().isoformat())
    target=ROOT/'data/catalog/bu-inventory.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('DISCOVERED',len(result['resources']),'BU ZIP packages')
