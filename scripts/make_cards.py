#!/usr/bin/env python3
"""Render 5 static 1080×1350 card news PNGs from CatchMICE news.json.
Never redraws or synthesizes mascots. Uses immutable cropped source artwork.

Korean text needs a Nanum (나눔) font. GitHub Actions' ubuntu-latest has no Korean
font by default, and a missing font used to fall back to DejaVu Sans and render
every Hangul syllable as "□". resolve_font() now picks the first font that really
contains Hangul glyphs, in this order:
  1. $CARD_FONT
  2. fonts vendored in this repo: assets/fonts/Nanum*.ttf   (works offline, in CI too)
  3. system fonts installed by the `fonts-nanum` package or a manual install
  4. fc-match for a Nanum family
  5. download from a pinned URL into .cache/fonts (last resort, needs network)
If none has Hangul, the script exits with an error instead of drawing "□".
"""
import hashlib,json,os,re,struct,subprocess,sys,textwrap
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'social'/'drafts'
FONT_DIR=ROOT/'assets'/'fonts'
NAVY='#071642'; BLUE='#0755f1'; CREAM='#fffaf4'; MUTED='#61718b'

# Weight-ordered preference: the card design was drawn for NanumSquare Bold.
FONT_NAMES=['NanumSquareB.ttf','NanumSquare_acB.ttf','NanumGothicBold.ttf','NanumGothic-Bold.ttf','NanumBarunGothicBold.ttf','NanumSquareRoundB.ttf','NanumSquareR.ttf','NanumGothic.ttf']
FONT_FC=['NanumSquare:bold','NanumSquare_ac:bold','NanumGothic:bold','NanumBarunGothic:bold','NanumSquareRound:bold']
FONT_URLS=[
 'https://cdn.jsdelivr.net/npm/fontpkg-nanum-square/NanumSquareB.ttf',
 'https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Bold.ttf',
]
FONT_FILE=None

def _cmap_ranges(path):
    """Return [(first,last), ...] code point ranges the font actually maps."""
    data=Path(path).read_bytes()
    if len(data)<12 or data[:4] not in (b'\x00\x01\x00\x00',b'true',b'OTTO'):raise ValueError('not a TrueType font')
    num=struct.unpack('>H',data[4:6])[0]
    cmap=None
    for i in range(num):
        rec=12+i*16
        if data[rec:rec+4]==b'cmap':cmap=struct.unpack('>I',data[rec+8:rec+12])[0];break
    if cmap is None:raise ValueError('no cmap')
    n=struct.unpack('>H',data[cmap+2:cmap+4])[0]
    best=None
    for i in range(n):
        rec=cmap+4+i*8
        pid,eid,off=struct.unpack('>HHI',data[rec:rec+8])
        score={(3,10):4,(0,6):4,(3,1):3,(0,4):3,(0,3):2,(3,0):1}.get((pid,eid),0)
        fmt=struct.unpack('>H',data[cmap+off:cmap+off+2])[0]
        if score and fmt in (4,12) and (best is None or score>best[0]):best=(score,cmap+off,fmt)
    if best is None:raise ValueError('no usable cmap subtable')
    _,s,fmt=best
    ranges=[]
    if fmt==4:
        segx2=struct.unpack('>H',data[s+6:s+8])[0];seg=segx2//2
        ends=struct.unpack(f'>{seg}H',data[s+14:s+14+segx2])
        starts=struct.unpack(f'>{seg}H',data[s+16+segx2:s+16+2*segx2])
        for a,b in zip(starts,ends):
            if a==0xFFFF:continue
            if b>=a:ranges.append((a,b))
    else:
        ng=struct.unpack('>I',data[s+12:s+16])[0]
        for g in range(ng):
            p=s+16+g*12
            a,b,_=struct.unpack('>III',data[p:p+12])
            if b>=a:ranges.append((a,b))
    return ranges

def _has_hangul(path):
    try:
        rs=_cmap_ranges(path)
    except Exception as e:
        print(f'[font] cmap 확인 실패({path}): {e}',file=sys.stderr)
        return True  # cannot verify: keep it as a candidate rather than lose the font
    def covers(cp):return any(a<=cp<=b for a,b in rs)
    # common syllables in the card copy + the space must really exist
    return all(covers(cp) for cp in (0xAC00,0xB098,0xD55C,0xAE00,0x20))

def _download_font():
    dest=FONT_DIR
    try:dest.mkdir(parents=True,exist_ok=True)
    except OSError:dest=ROOT/'.cache'/'fonts';dest.mkdir(parents=True,exist_ok=True)
    for url in FONT_URLS:
        target=dest/url.rsplit('/',1)[-1]
        if target.exists() and _has_hangul(target):return target
        print(f'[font] 내려받기 시도: {url}',file=sys.stderr)
        try:
            import urllib.request
            with urllib.request.urlopen(url,timeout=45) as r:target.write_bytes(r.read())
        except Exception as e:
            print(f'[font] 실패: {e}',file=sys.stderr)
            if target.exists():target.unlink()
            continue
        if target.stat().st_size>50000 and _has_hangul(target):return target
        if target.exists():target.unlink()
    return None

def resolve_font():
    cands=[]
    env=os.environ.get('CARD_FONT')
    if env:cands.append(Path(env))
    for n in FONT_NAMES:cands.append(FONT_DIR/n)
    for d in (Path('/usr/share/fonts/truetype/nanum'),Path('/usr/share/fonts/nanum'),Path('/usr/local/share/fonts'),Path.home()/'.fonts',Path('/usr/share/fonts')):
        if d.is_dir():
            for n in FONT_NAMES:cands.append(d/n)
    if FONT_DIR.is_dir():cands+=sorted(FONT_DIR.glob('Nanum*B*.ttf'))+sorted(FONT_DIR.glob('Nanum*.ttf'))
    for fam in FONT_FC:
        try:
            p=subprocess.run(['fc-match','-f','%{file}',fam],capture_output=True,text=True,timeout=20).stdout.strip()
        except Exception:p=''
        if p:cands.append(Path(p))
    seen=set()
    for c in cands:
        try:
            if c in seen:continue
            seen.add(c)
            if c.is_file() and c.stat().st_size>50000 and _has_hangul(c):
                print(f'[font] {c}',file=sys.stderr);return c
        except OSError:continue
    got=_download_font()
    if got and _has_hangul(got):
        print(f'[font] {got}',file=sys.stderr);return got
    sys.exit('[font] 한글 나눔폰트를 찾지 못했습니다. `sudo apt-get install -y fonts-nanum` 또는 assets/fonts/NanumSquareB.ttf 를 확인하세요. (한글이 □로 깨진 카드를 만들지 않도록 중단합니다.)')

def font(n):
    global FONT_FILE
    if FONT_FILE is None:FONT_FILE=resolve_font()
    return ImageFont.truetype(str(FONT_FILE),n)
def rounded(d,xy,fill,rad=26,outline=None,width=2):d.rounded_rectangle(xy,radius=rad,fill=fill,outline=outline,width=width)
def fit_text(d,text,maxwidth,size=74,minsize=32):
    for n in range(size,minsize-1,-2):
        f=font(n)
        if d.textbbox((0,0),text,font=f)[2]<=maxwidth:return f
    return font(minsize)
def _too_wide(d,t,f,width):return d.textbbox((0,0),t,font=f)[2]>width

def wrap(d,text,f,width):
    """Break on spaces (Korean 어절) so numbers and words stay whole;
    only an over-long word is split by character as a last resort."""
    out=[]
    for para in text.strip().split('\n'):
        cur=''
        for w in [w for w in para.split(' ') if w]:
            cand=f'{cur} {w}' if cur else w
            if d.textbbox((0,0),cand,font=f)[2]<=width:cur=cand;continue
            if cur:out.append(cur);cur=''
            while _too_wide(d,w,f,width) and len(w)>1:
                k=len(w)
                while k>1 and _too_wide(d,w[:k],f,width):k-=1
                out.append(w[:k]);w=w[k:]
            cur=w
        if cur:out.append(cur)
    return out

def lines(d,text,xy,f,width,fill=NAVY,leading=1.43,maxlines=None):
    chunks=wrap(d,text,f,width)
    if maxlines and len(chunks)>maxlines:
        chunks=chunks[:maxlines];chunks[-1]=chunks[-1].rstrip('…')+'…'
    y=xy[1]
    for t in chunks:
        d.text((xy[0],y),t,font=f,fill=fill,stroke_width=0)
        y+=int(f.size*leading)
    return y

def base(label,num):
    img=Image.new('RGB',(1080,1350),CREAM);d=ImageDraw.Draw(img)
    d.rounded_rectangle((34,34,1046,1316),radius=42,outline='#d0def7',width=4)
    d.text((82,75),'Catch',font=font(41),fill=NAVY);d.text((230,75),'MICE',font=font(41),fill=BLUE)
    d.text((84,123),f'기자단  |  {label}',font=font(24),fill=MUTED)
    d.text((920,82),f'{num:02d}/05',font=font(26),fill=MUTED)
    d.line((82,184,998,184),fill='#d8e4f7',width=3)
    return img,d

def mascot(img,key,xy,size):
    p=ROOT/'assets'/f'{key}.png'
    if not p.exists():return
    a=Image.open(p).convert('RGB');a.thumbnail(size,Image.Resampling.LANCZOS)
    mask=Image.new('L',a.size,0);md=ImageDraw.Draw(mask);md.rounded_rectangle((0,0,a.width-1,a.height-1),radius=24,fill=255)
    img.paste(a,xy,mask)

def render(item):
    raw=item['url'].encode('utf8'); sid=hashlib.sha256(raw).hexdigest()[:12]
    dest=OUT/sid;dest.mkdir(parents=True,exist_ok=True)
    prev={}
    if (dest/'draft.json').exists():
        try:prev=json.loads((dest/'draft.json').read_text(encoding='utf-8'))
        except ValueError:prev={}
    title=item['title'].strip();summary=(item.get('sum') or '').strip();cat=item.get('cat') or 'MICE 한입뉴스';src=item.get('source') or '원문 확인'
    role='aily' if ('AI' in title.upper() or '인공지능' in title) else 'veny' if any(t in title for t in ['지역','관광','컨벤션센터','유치','베뉴']) else 'exy' if any(t in title for t in ['전시','산업','기업','박람회']) else 'micy'
    pages=[]
    img,d=base(cat,1)
    rounded(d,(75,235,1005,329),'#eaf0ff',20)
    d.text((112,263),'MICE 한입뉴스  |  CatchMICE 기자단',font=font(33),fill=BLUE)
    lines(d,title,(90,405),fit_text(d,title,880,70,50),860,leading=1.35,maxlines=6)
    mascot(img,role,(675,840),(280,350))
    d.text((90,1200),'MICE를 캐치하는 기자단',font=font(31),fill=BLUE)
    pages.append(img)
    img,d=base('핵심 요약',2)
    d.text((90,280),'무슨 일이 있었나요?',font=font(61),fill=NAVY)
    rounded(d,(75,410,1005,990),'#eef3ff',36)
    lines(d,summary,(122,465),font(47),830,leading=1.55,maxlines=9)
    mascot(img,role,(755,1030),(210,220));pages.append(img)
    img,d=base('기사 맥락',3)
    d.text((90,280),'핵심 체크포인트',font=font(64),fill=NAVY)
    subs=re.split(r'(?<=[.!?。])\s+',summary)
    if len(subs)<2:
        subs=[summary[:max(30,len(summary)//2)],summary[max(30,len(summary)//2):]]
    for j,t in enumerate(subs[:3]):
        y=425+j*240
        rounded(d,(80,y,996,y+206),'#fff',30,outline='#d5e1f2',width=3)
        d.text((112,y+39),f'{j+1:02d}',font=font(45),fill=BLUE)
        lines(d,t.strip(),(205,y+34),font(38),744,maxlines=3)
    pages.append(img)
    img,d=base('실무 인사이트',4)
    d.text((85,270),'그래서 왜 중요한가?',font=font(66),fill=BLUE)
    rounded(d,(75,405,1005,905),'#eaf8f4',30)
    insight='MICE 실무에서는 이 소식이 행사 유치, 참가자 경험, 지역 산업과 어떤 연결점을 만드는지 살펴볼 필요가 있어요.'
    lines(d,insight,(120,482),font(49),820,leading=1.55,maxlines=7)
    rounded(d,(80,950,1000,1130),'#fff',25,outline='#b6dcd3')
    lines(d,'원문 내용과 실무적 해석을 구분해 확인해 주세요.',(113,982),font(35),840)
    pages.append(img)
    img,d=base('마무리',5)
    d.text((95,265),'한 번 더 캐치!',font=font(74),fill=BLUE)
    lines(d,title,(95,405),font(48),880,leading=1.45,maxlines=5)
    for j,key in enumerate(['micy','veny','exy','aily']): mascot(img,key,(95+(j%2)*460,745+(j//2)*220),(365,202))
    rounded(d,(155,1190,927,1274),BLUE,42);d.text((318,1208),'@catchmice',font=font(49),fill='white')
    pages.append(img)
    for j,im in enumerate(pages,1):im.save(dest/f'{j:02d}.png',optimize=True)
    caption=f"🐭 CatchMICE 기자단의 MICE 한입뉴스!\n\n{title}\n\n{summary}\n\n💡 그래서 왜 중요할까요?\nMICE 실무에서 어떤 변화로 이어질지 함께 살펴봐요.\n\n출처: {src}\n원문: {item['url']}\n\n#CatchMICE #MICE #전시컨벤션 #MICE한입뉴스"
    data={'id':sid,'source_url':item['url'],'source':src,'title':title,'category':cat,'caption':caption,'character':role,'created_at':prev.get('created_at') or datetime.now().isoformat(),'status':prev.get('status') or 'pending','pages':[f'{j:02d}.png' for j in range(1,6)]}
    (dest/'draft.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    return data

def _items():
    src=ROOT/'news.json'
    if not src.exists():sys.exit('news.json must be copied to package root from homepage repo')
    return json.loads(src.read_text(encoding='utf-8')).get('items',[])

def rerender(nid):
    """Re-draw an existing draft (or an article URL) with the current font/layout."""
    if nid.startswith('http'):url=nid
    else:
        p=OUT/nid/'draft.json'
        if not p.exists():sys.exit(f'no draft {nid}')
        url=json.loads(p.read_text(encoding='utf-8'))['source_url']
    for item in _items():
        if item.get('url')==url:
            d=render(item);print(json.dumps({'draft_id':d['id'],'title':d['title']},ensure_ascii=False));return
    sys.exit(f'not in news.json: {url}')

def main():
    if len(sys.argv)>1 and sys.argv[1] in ('--rerender','--url'):
        if len(sys.argv)<3:sys.exit('usage: make_cards.py --rerender <draft_id|source_url>')
        return rerender(sys.argv[2])
    items=_items()
    if not items:sys.exit('No news to render')
    used=set()
    for p in OUT.glob('*/draft.json'):
        try:used.add(json.loads(p.read_text())['source_url'])
        except (KeyError,ValueError):pass
    for item in items:
        if item.get('url') and item.get('title') and item['url'] not in used:
            d=render(item); print(json.dumps({'draft_id':d['id'],'title':d['title']},ensure_ascii=False));return
    print('NO_NEW_ARTICLES')
if __name__=='__main__':main()
