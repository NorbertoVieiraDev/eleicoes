"""Snapshot official TSE section-result archives for 2000–2010 elections."""
import datetime,json,pathlib,re,subprocess,tempfile,urllib.parse

ROOT=pathlib.Path(__file__).resolve().parents[1]
YEARS=(2000,2002,2004,2006,2008,2010)
API='https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-{year}'
DATASET='https://dadosabertos.tse.jus.br/dataset/resultados-{year}'

def inventory(payloads,retrieved_on):
    datasets=[];resources=[]
    for year,payload in sorted(payloads.items()):
        if not payload.get('success'):raise ValueError(f'CKAN package_show failed for {year}')
        d=payload['result'];datasets.append({'name':d['name'],'title':d['title'],'year':year,'dataset_url':DATASET.format(year=year),'license_id':d.get('license_id'),'license_url':d.get('license_url'),'metadata_modified':d.get('metadata_modified')})
        for r in d.get('resources',[]):
            url=r.get('url','');parsed=urllib.parse.urlsplit(url);low=url.lower()
            if parsed.scheme!='https' or parsed.hostname!='cdn.tse.jus.br':continue
            if '/votacao_secao/' in low:kind='section_votes'
            elif '/detalhe_votacao_secao/' in low:kind='section_totals'
            else:continue
            filename=urllib.parse.unquote(parsed.path.rsplit('/',1)[-1])
            suffix=re.search(r'_(BR|ZZ|VT|[A-Z]{2})\.zip$',filename,re.I)
            area=suffix.group(1).upper() if suffix else 'ALL'
            if area=='BR':scope='national';include=False;reason='National presidential package overlaps the state-level voting-by-section files; retained for audit only.'
            else:
                scope={'ZZ':'overseas','VT':'transit','ALL':'all_states'}.get(area,'state')
                include=True;reason=None
            resources.append({'resource_id':r.get('id'),'dataset':d['name'],'dataset_url':DATASET.format(year=year),'year':year,'resource_name':r.get('name'),'resource_description':r.get('description'),'resource_format':r.get('format'),'resource_hash':r.get('hash') or None,'kind':kind,'scope':scope,'area_code':None if area in {'ALL','BR'} else area,'canonical_include':include,'canonical_exclusion_reason':reason,'url':url,'filename':filename,'catalog_created':r.get('created'),'catalog_last_modified':r.get('last_modified'),'catalog_size':r.get('size')})
    if not resources:raise ValueError('No official section-result archives found')
    if len({r['url'] for r in resources})!=len(resources):raise ValueError('Duplicate official source URLs require review')
    return {'retrieved_on':retrieved_on,'api_endpoints':[API.format(year=y) for y in YEARS],'dataset_count':len(datasets),'resource_count':len(resources),'datasets':datasets,'resources':resources}

if __name__=='__main__':
    payloads={}
    with tempfile.TemporaryDirectory() as td:
        for year in YEARS:
            p=pathlib.Path(td)/f'{year}.json';url=API.format(year=year)
            subprocess.run(['curl','--fail','--silent','--show-error','--location','--max-time','60',url,'-o',str(p)],check=True)
            payloads[year]=json.loads(p.read_text())
    result=inventory(payloads,datetime.datetime.now(datetime.timezone.utc).date().isoformat())
    target=ROOT/'data/catalog/legacy-results-2000-2010.json';target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('DISCOVERED',result['resource_count'],'official ZIP resources across',result['dataset_count'],'election datasets')
