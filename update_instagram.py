#!/usr/bin/env python3
"""Fetch the owner's latest Instagram media. Secrets never enter public files."""
import datetime as dt
import json, os, re, shutil, sys, tempfile
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'instagram'
VERSION = 'v26.0'
MAX_BYTES = 16 * 1024 * 1024

def api_json(path, token, params):
    url = 'https://graph.instagram.com/' + VERSION + '/' + path + '?' + urlencode(params)
    try:
        with urlopen(Request(url, headers={'Authorization':'Bearer '+token}), timeout=40) as r:
            return json.load(r)
    except HTTPError as e:
        # Do not print URLs, response bodies, request headers or token-bearing exceptions.
        raise RuntimeError('Instagram API request failed (HTTP '+str(e.code)+'). Check token, account ID and permissions.') from None
    except (URLError, ValueError, TimeoutError):
        raise RuntimeError('Instagram API could not be reached or returned invalid data.') from None

def stamp(value):
    return dt.datetime.fromisoformat(value.replace('Z','+00:00'))

def latest_posts(data):
    if not isinstance(data, list):
        raise RuntimeError('Instagram returned no valid media list.')
    try:
        posts = sorted(data, key=lambda p: stamp(p['timestamp']), reverse=True)[:3]
    except (KeyError, ValueError, TypeError):
        raise RuntimeError('Instagram media timestamps are missing or invalid.') from None
    for p in posts:
        if not re.fullmatch(r'[0-9]+', str(p.get('id',''))):
            raise RuntimeError('Invalid media identifier.')
        u = urlparse(p.get('permalink',''))
        if u.scheme != 'https' or u.hostname not in ('instagram.com','www.instagram.com') or not re.fullmatch(r'/(p|reel|tv)/[^/]+/?',u.path):
            raise RuntimeError('Invalid Instagram post link.')
    return posts

def image_url(post):
    return post.get('thumbnail_url') if post.get('media_type') == 'VIDEO' else post.get('media_url')

def download_image(url):
    if not isinstance(url,str):
        raise RuntimeError('One of the latest posts has no supported image or video thumbnail.')
    def allowed(u):
        p=urlparse(u);h=p.hostname or ''
        return p.scheme=='https' and (h.endswith('.cdninstagram.com') or h.endswith('.fbcdn.net') or h in ('cdninstagram.com','fbcdn.net'))
    if not allowed(url):
        raise RuntimeError('Unrecognized Instagram image host.')
    try:
        with urlopen(Request(url,headers={'User-Agent':'USJBusinessSocietySite/1.0'}), timeout=40) as r:
            if not allowed(r.url):
                raise RuntimeError('Image redirect used an unrecognized host.')
            kind=r.headers.get_content_type()
            extension={'image/jpeg':'jpg','image/png':'png','image/webp':'webp'}.get(kind)
            if not extension:
                raise RuntimeError('Unsupported image content type.')
            content=r.read(MAX_BYTES+1)
            if not content or len(content)>MAX_BYTES:
                raise RuntimeError('Image is empty or exceeds the download limit.')
            return extension,content
    except (HTTPError,URLError,TimeoutError):
        raise RuntimeError('An Instagram image could not be downloaded; the previous live feed is preserved.') from None

def update():
    token=os.environ.get('INSTAGRAM_ACCESS_TOKEN','').strip()
    user=os.environ.get('INSTAGRAM_ACCOUNT_ID','').strip()
    if not token or not re.fullmatch(r'[0-9]+',user):
        raise RuntimeError('Configure INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID in GitHub Actions secrets before enabling the workflow.')
    # Verify the connected account before publishing any media.
    profile=api_json(user,token,{'fields':'id,username'})
    if profile.get('username','').lower()!='usjbusiness':
        raise RuntimeError('The connected Instagram account is not @usjbusiness.')
    media=api_json(user+'/media',token,{'fields':'id,caption,media_type,media_url,thumbnail_url,permalink,timestamp','limit':50})
    posts=latest_posts(media.get('data'))
    OUT.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='instagram-',dir=OUT.parent))
    try:
        clean=[]
        for p in posts:
            ext,content=download_image(image_url(p));name=p['id']+'.'+ext
            (stage/name).write_bytes(content)
            clean.append({'id':p['id'],'caption':str(p.get('caption',''))[:2200],'mediaType':p.get('media_type','IMAGE'),'permalink':p['permalink'],'timestamp':p['timestamp'],'image':'assets/instagram/'+name})
        feed={'updatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'posts':clean}
        (stage/'feed.json').write_text(json.dumps(feed,ensure_ascii=False,indent=2)+'\n')
        if OUT.exists():shutil.rmtree(OUT)
        stage.rename(OUT)
        print('Instagram feed prepared: '+str(len(clean))+' latest posts. No credentials included in public output.')
    finally:
        if stage.exists():shutil.rmtree(stage)

if __name__=='__main__':
    try:update()
    except RuntimeError as e:
        print('Feed update stopped: '+str(e),file=sys.stderr);sys.exit(1)
