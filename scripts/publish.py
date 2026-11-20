#!/usr/bin/env python3
"""Publish approved public GitHub Pages URLs to Instagram Business via Instagram Login API.
Runs ONLY after an authenticated approval workflow dispatch.
"""
import json,os,sys,time,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def api(path, data=None):
    url='https://graph.instagram.com/'+os.environ.get('IG_API_VERSION','v24.0')+'/'+path
    payload={**(data or {}),'access_token':os.environ['IG_ACCESS_TOKEN']}
    req=urllib.request.Request(url,data=urllib.parse.urlencode(payload).encode(),method='POST')
    with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)
def main():
    did=os.environ['DRAFT_ID']
    if not did or any(c not in '0123456789abcdef' for c in did):sys.exit('Invalid draft id')
    folder=ROOT/'social'/'drafts'/did
    draft=json.loads((folder/'draft.json').read_text(encoding='utf-8'))
    if draft['id']!=did:sys.exit('Mismatch')
    if draft.get('status')=='published':sys.exit('Already published')
    base='https://catchmice.github.io/social/drafts/'+did+'/'
    ig=os.environ['IG_USER_ID']; children=[]
    for name in draft['pages']:
        result=api(f'{ig}/media',{'image_url':base+name,'is_carousel_item':'true'})
        children.append(result['id'])
    carousel=api(f'{ig}/media',{'media_type':'CAROUSEL','children':','.join(children),'caption':draft['caption']})
    # Meta may process container asynchronously
    for attempt in range(20):
        try:
            post=api(f'{ig}/media_publish',{'creation_id':carousel['id']});break
        except Exception:
            if attempt==19:raise
            time.sleep(8)
    draft['status']='published';draft['instagram_media_id']=post['id']
    (folder/'draft.json').write_text(json.dumps(draft,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PUBLISHED',post['id'])
if __name__=='__main__':main()
