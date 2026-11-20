#!/usr/bin/env python3
"""Render 5 static 1080×1350 card news PNGs from CatchMICE news.json.
Never redraws or synthesizes mascots. Uses immutable cropped source artwork.
"""
import hashlib,json,re,sys,textwrap
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'social'/'drafts'
NAVY='#071642'; BLUE='#0755f1'; CREAM='#fffaf4'; MUTED='#61718b'
FONT='/usr/share/fonts/truetype/nanum/NanumSquareB.ttf'
if not Path(FONT).exists():
    import subprocess
    found=subprocess.getoutput('fc-match -f "%{file}" "NanumSquare"').strip(); FONT=found

def font(n):return ImageFont.truetype(FONT,n)
def rounded(d,xy,fill,rad=26,outline=None,width=2):d.rounded_rectangle(xy,radius=rad,fill=fill,outline=outline,width=width)
def fit_text(d,text,maxwidth,size=74,minsize=32):
    for n in range(size,minsize-1,-2):
        f=font(n)
        if d.textbbox((0,0),text,font=f)[2]<=maxwidth:return f
    return font(minsize)
def wrap(d,text,f,width):
    words=list(text.strip());lines=[];cur=''
    for c in words:
        if d.textbbox((0,0),cur+c,font=f)[2]>width and cur:lines.append(cur);cur=c
        else:cur+=c
    if cur:lines.append(cur)
    return lines

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
        d.text((112,y+39),f'{j+1:02}',font=font(45),fill=BLUE)
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
    data={'id':sid,'source_url':item['url'],'source':src,'title':title,'category':cat,'caption':caption,'character':role,'created_at':datetime.now().isoformat(),'status':'pending','pages':[f'{j:02d}.png' for j in range(1,6)]}
    (dest/'draft.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    return data

def main():
    src=ROOT/'news.json'
    if not src.exists():sys.exit('news.json must be copied to package root from homepage repo')
    items=json.loads(src.read_text(encoding='utf-8')).get('items',[])
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
