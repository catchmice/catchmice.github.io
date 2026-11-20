#!/usr/bin/env python3
"""Publishes a single approved 5-image carousel using Instagram Graph API.
GitHub Actions must gate this file behind the instagram-publishing environment.
"""
import json, os, re, sys, time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
GRAPH='https://graph.instagram.com/' + os.getenv('IG_API_VERSION','v24.0')

def api(path,payload):
    token=os.environ['IG_ACCESS_TOKEN']
    url=GRAPH+'/'+path
    req=Request(url,data=urlencode({**payload,'access_token':token}).encode('utf-8'),method='POST')
    with urlopen(req,timeout=90) as response:
        return json.load(response)

def main():
    did=os.environ.get('DRAFT_ID','')
    if not re.fullmatch(r'[a-f0-9]{12}',did):sys.exit('Invalid draft ID')
    folder=ROOT/'social'/'drafts'/did
    draft=json.loads((folder/'draft.json').read_text(encoding='utf-8'))
    if draft.get('id')!=did or draft.get('status')!='pending':sys.exit('Draft not pending or mismatch')
    pages=draft.get('pages')
    if pages != [f'{i:02}.png' for i in range(1,6)]:sys.exit('Five ordered PNGs required')
    for page in pages:
        if not (folder/page).is_file():sys.exit('Missing PNG '+page)
    caption=draft.get('caption')
    if not isinstance(caption,str) or not caption.strip():sys.exit('Caption missing')
    user=os.environ['IG_USER_ID']
    base=f'https://catchmice.github.io/social/drafts/{did}/'
    children=[]
    for page in pages:
        media=api(user+'/media',{'image_url':base+page,'is_carousel_item':'true'})
        children.append(media['id'])
    carousel=api(user+'/media',{'media_type':'CAROUSEL','children':','.join(children),'caption':caption})
    # Publish retries limited to media preparation; do not retry after confirmed publishing.
    for attempt in range(15):
        try:
            published=api(user+'/media_publish',{'creation_id':carousel['id']})
            break
        except Exception:
            if attempt==14:raise
            time.sleep(8)
    draft['status']='published'
    draft['instagram_media_id']=published['id']
    (folder/'draft.json').write_text(json.dumps(draft,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Instagram carousel published:', published['id'])

if __name__=='__main__':main()
