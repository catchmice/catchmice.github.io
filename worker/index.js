/** Cloudflare Worker approval gateway.
 * Put this Worker behind Cloudflare Access policy limited to your own identity.
 * Requires Access auth; NEVER put GITHUB_TOKEN in static site or frontend.
 * Secrets: GITHUB_TOKEN; Vars: REPO=catchmice/catchmice.github.io,
 * ACCESS_AUD=<Cloudflare Access application AUD>, ACCESS_TEAM=<team>.cloudflareaccess.com
 */
async function verifyAccess(jwt,env){
  if(!jwt || !env.ACCESS_AUD || !env.ACCESS_TEAM)return false;
  const [h,p,s]=jwt.split('.');if(!h||!p||!s)return false;
  function decode(v){const b=v.replace(/-/g,'+').replace(/_/g,'/');return Uint8Array.from(atob(b.padEnd(Math.ceil(b.length/4)*4,'=')),c=>c.charCodeAt(0));}
  let header,payload;
  try{header=JSON.parse(new TextDecoder().decode(decode(h)));payload=JSON.parse(new TextDecoder().decode(decode(p)));}catch{return false;}
  if(header.alg!=='RS256' || !header.kid || payload.iss!==`https://${env.ACCESS_TEAM}` || ![].concat(payload.aud||[]).includes(env.ACCESS_AUD) || payload.exp*1000<Date.now())return false;
  const keys=await fetch(`https://${env.ACCESS_TEAM}/cdn-cgi/access/certs`).then(r=>r.json());
  const jwk=keys.keys?.find(k=>k.kid===header.kid);if(!jwk)return false;
  const key=await crypto.subtle.importKey('jwk',jwk,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);
  return crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,decode(s),new TextEncoder().encode(h+'.'+p));
}
export default {async fetch(req,env){
  const origin=new URL(req.url).origin;
  const htmlHeaders={'Content-Type':'text/html; charset=UTF-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
  if(!(await verifyAccess(req.headers.get('Cf-Access-Jwt-Assertion'),env)))return new Response('Unauthorized', {status:401});
  if(req.method==='GET'){
    const html=`<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CatchMICE 승인함</title><style>body{font-family:system-ui;background:#fffaf4;color:#06153e;max-width:720px;margin:25px auto;padding:20px}h1{color:#0755f1}input{padding:14px;font-size:16px;width:90%}button{background:#0755f1;border:0;color:white;padding:15px 22px;border-radius:12px;font-size:16px;margin:10px 8px 0 0}img{width:44%;border-radius:10px;margin:2%}p{line-height:1.7}</style><h1>CatchMICE 승인함</h1><p>메일이나 예약 작업에서 받은 초안 ID를 입력해 주세요. 5장 미리보기와 캡션 확인 후 승인할 수 있어요.</p><input id="id" placeholder="초안 ID (예: 12자리 영숫자)"><button onclick="load()">미리보기</button><div id="output"></div><script>
const out=document.querySelector('#output');let draft;
async function load(){const id=document.querySelector('#id').value.trim();if(!/^[a-f0-9]{12}$/.test(id)){out.textContent='올바른 12자리 초안 ID를 입력하세요';return;}const base='https://catchmice.github.io/social/drafts/'+id+'/';try{const r=await fetch(base+'draft.json?x='+Date.now());if(!r.ok)throw Error('초안을 찾지 못했어요');draft=await r.json();if(draft.id!==id)throw Error('초안 ID 오류');out.replaceChildren();let t=document.createElement('h2');t.textContent=draft.title;out.append(t);for(const page of draft.pages){const img=document.createElement('img');img.src=base+page;img.alt='카드뉴스';out.append(img)}let c=document.createElement('p');c.textContent=draft.caption;c.style.whiteSpace='pre-wrap';out.append(c);if(draft.status==='published'){out.append('이미 게시되었습니다');return;}let btn=document.createElement('button');btn.textContent='승인하고 인스타그램 게시';btn.onclick=approve;out.append(btn)}catch(e){out.textContent=String(e)}}
async function approve(){if(!draft||!confirm('5장의 이미지와 캡션을 확인했나요? 승인하면 공개 게시 작업이 시작됩니다.'))return;const r=await fetch('/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({draft_id:draft.id})});out.append(document.createElement('p')).textContent=r.ok?'게시 요청을 전달했습니다. GitHub Actions 실행 결과를 확인하세요.':'승인 실패: '+await r.text()}
</script></html>`;return new Response(html,{headers:htmlHeaders});
  }
  if(req.method==='POST'){
    if(req.headers.get('content-type')?.split(';')[0]!=='application/json')return new Response('JSON required',{status:415});
    let id;try{id=(await req.json()).draft_id}catch{return new Response('Bad JSON',{status:400})}
    if(!/^[a-f0-9]{12}$/.test(id))return new Response('Bad draft',{status:400});
    if(!env.GITHUB_TOKEN||!env.REPO)return new Response('Not configured',{status:503});
    // Verify existence and state at the canonical repository rather than trusting the browser.
    const file=await fetch(`https://api.github.com/repos/${env.REPO}/contents/social/drafts/${id}/draft.json`,{headers:{Authorization:`Bearer ${env.GITHUB_TOKEN}`,Accept:'application/vnd.github.raw+json','User-Agent':'catchmice-approval'}});
    if(!file.ok)return new Response('Draft not found',{status:404});
    const d=await file.json();if(d.id!==id || d.status!=='pending')return new Response('Draft not pending',{status:409});
    const resp=await fetch(`https://api.github.com/repos/${env.REPO}/actions/workflows/instagram-cards.yml/dispatches`,{method:'POST',headers:{Authorization:`Bearer ${env.GITHUB_TOKEN}`,Accept:'application/vnd.github+json','User-Agent':'catchmice-approval','Content-Type':'application/json'},body:JSON.stringify({ref:'main',inputs:{action:'publish',draft_id:id}})});
    return new Response(resp.ok?'Publish workflow dispatched':await resp.text(),{status:resp.ok?202:502});
  }
  return new Response('Method Not Allowed',{status:405});
}};
