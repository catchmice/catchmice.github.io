/** CatchMICE mobile approval dashboard, protected by Cloudflare Access.
 * Required env vars: REPO, ACCESS_AUD, ACCESS_TEAM, GITHUB_TOKEN (secret).
 * This code never stores Instagram credentials or displays GitHub credentials.
 */
const HEADERS = { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': "default-src 'none'; img-src https://catchmice.github.io; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self' https://catchmice.github.io; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" };
function decode64url(x) { const v = x.replace(/-/g,'+').replace(/_/g,'/'); return Uint8Array.from(atob(v.padEnd(Math.ceil(v.length/4)*4,'=')),c=>c.charCodeAt(0)); }
async function verifyAccess(token, env) {
  if (!token || !env.ACCESS_AUD || !env.ACCESS_TEAM) return false;
  const parts = token.split('.'); if (parts.length !== 3) return false;
  let header,payload;
  try { header=JSON.parse(new TextDecoder().decode(decode64url(parts[0]))); payload=JSON.parse(new TextDecoder().decode(decode64url(parts[1]))); } catch { return false; }
  const origin = `https://${env.ACCESS_TEAM}`;
  if (header.alg !== 'RS256' || !header.kid || payload.iss !== origin || ![payload.aud].flat().includes(env.ACCESS_AUD) || !payload.exp || payload.exp * 1000 <= Date.now()) return false;
  const resp=await fetch(`${origin}/cdn-cgi/access/certs`); if(!resp.ok)return false;
  const keys=await resp.json();const jwk=keys.keys?.find(k=>k.kid===header.kid);if(!jwk)return false;
  const key=await crypto.subtle.importKey('jwk',jwk,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);
  return crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,decode64url(parts[2]),new TextEncoder().encode(parts[0]+'.'+parts[1]));
}
function reply(text,status=200,type='text/plain; charset=utf-8') { return new Response(text,{status,headers:{...HEADERS,'Content-Type':type}}); }
function githubHeaders(env) { return {Authorization:`Bearer ${env.GITHUB_TOKEN}`,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'CatchMICE-Approval'}; }
async function getDraft(id,env){
  const uri=`https://api.github.com/repos/${env.REPO}/contents/social/drafts/${id}/draft.json`;
  const r=await fetch(uri,{headers:githubHeaders(env)});if(!r.ok)return null;
  const doc=await r.json(); if(doc.type !== 'file' || !doc.content) return null;
  try{ return JSON.parse(new TextDecoder().decode(decode64url(doc.content.replace(/\s/g,''))));} catch {return null;}
}
const html=`<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CatchMICE 승인함</title>
<style>*{box-sizing:border-box}body{font:16px/1.55 system-ui,sans-serif;background:#fdf9f5;color:#0b1a43;max-width:790px;margin:0 auto;padding:24px}h1{font-size:30px;margin-bottom:4px;color:#0558e8}p{margin-top:5px}label{display:block;font-weight:700;margin-top:28px}input{width:100%;padding:15px;border:2px solid #d6e1f4;border-radius:12px;font:inherit}button{cursor:pointer;border:0;border-radius:12px;background:#0755f1;color:#fff;font:700 16px system-ui;padding:15px 20px;margin-top:12px}button:disabled{opacity:.55;cursor:not-allowed}.sub{color:#51627b}.pages{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:20px 0}.pages img{width:100%;border-radius:11px;border:1px solid #dbe6f3}.caption{white-space:pre-wrap;background:#fff;border:1px solid #dce6f5;border-radius:12px;padding:16px;margin:14px 0}.warning{background:#fff2d6;border-radius:10px;padding:13px}.status{margin-top:16px;font-weight:700}</style>
<h1>CatchMICE 승인함</h1><p class="sub">카드뉴스 5장과 캡션을 확인한 후 승인해 주세요. 승인 전에는 게시되지 않습니다.</p>
<label for="id">초안 ID</label><input id="id" maxlength="12" placeholder="예: 12자리 영숫자" autocomplete="off"><button id="load">초안 보기</button>
<main id="output" aria-live="polite"></main>
<script>
const out=document.getElementById('output'); const btn=document.getElementById('load'); let current=null;
const idRule=/^[a-f0-9]{12}$/;
function message(t){const p=document.createElement('p');p.className='status';p.textContent=t;out.append(p)};
async function load(){const id=document.getElementById('id').value.trim();out.replaceChildren();current=null;
 if(!idRule.test(id)){message('12자리 초안 ID를 입력해 주세요.');return;}
 const r=await fetch('/api/drafts/'+id);if(!r.ok){message('초안을 불러오지 못했습니다.');return;}const d=await r.json();current=d;
 const h=document.createElement('h2');h.textContent=d.title;out.append(h);
 const gallery=document.createElement('div');gallery.className='pages';
 for(const name of d.pages){const img=document.createElement('img');img.src='https://catchmice.github.io/social/drafts/'+id+'/'+name;img.alt='카드뉴스 '+name;gallery.append(img);}out.append(gallery);
 const c=document.createElement('div');c.className='caption';c.textContent=d.caption;out.append(c);
 if(d.status!=='pending'){message('현재 초안 상태: '+d.status+' (게시 승인 불가)');return;}
 const p=document.createElement('p');p.className='warning';p.textContent='승인하면 GitHub 게시 작업이 시작됩니다. Instagram 계정에 공개될 수 있습니다.';out.append(p);
 const approve=document.createElement('button');approve.textContent='검토 완료 · 게시 승인';approve.onclick=async()=>{
  if(!confirm('이미지 5장과 캡션을 최종 확인했나요? 게시 작업을 요청합니다.'))return;
  approve.disabled=true;const res=await fetch('/api/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({draft_id:id})});message(res.ok?'게시 요청이 접수되었습니다. GitHub Actions에서 추가 승인/게시 상태를 확인하세요.':'게시 요청 실패: '+await res.text());
 };out.append(approve);
}
btn.onclick=load;const param=new URLSearchParams(location.search).get('draft');if(param&&idRule.test(param)){document.getElementById('id').value=param;load();}
</script></html>`;
export default {async fetch(req,env){
  if(!(await verifyAccess(req.headers.get('Cf-Access-Jwt-Assertion'),env)))return reply('Unauthorized',401);
  if(!env.GITHUB_TOKEN || !/^[-a-zA-Z0-9_.]+\/[-a-zA-Z0-9_.]+$/.test(env.REPO||''))return reply('Server configuration missing',503);
  const u=new URL(req.url);
  if(req.method==='GET' && u.pathname==='/')return reply(html,200,'text/html; charset=utf-8');
  const m=u.pathname.match(/^\/api\/drafts\/([a-f0-9]{12})$/);
  if(req.method==='GET'&&m){const draft=await getDraft(m[1],env);if(!draft || draft.id!==m[1])return reply('Not found',404);
    if(!Array.isArray(draft.pages)||draft.pages.length!==5||!draft.pages.every((x,i)=>x===String(i+1).padStart(2,'0')+'.png'))return reply('Malformed draft',422);
    return reply(JSON.stringify({id:draft.id,title:draft.title,status:draft.status,pages:draft.pages,caption:draft.caption}),200,'application/json; charset=utf-8');
  }
  if(req.method==='POST'&&u.pathname==='/api/approve'){
    if(req.headers.get('content-type')?.split(';')[0]!=='application/json')return reply('JSON only',415);
    // Same-site browser UI; browser cross-site POST is also blocked by Origin check.
    const origin=req.headers.get('Origin');if(origin!==u.origin)return reply('Invalid origin',403);
    let body;try{body=await req.json()}catch{return reply('Bad JSON',400)}
    const id=body?.draft_id;if(typeof id!=='string'||!/^[a-f0-9]{12}$/.test(id))return reply('Invalid draft ID',400);
    const d=await getDraft(id,env);
    if(!d||d.id!==id||d.status!=='pending'||!Array.isArray(d.pages)||d.pages.length!==5)return reply('Not a publishable draft',409);
    const api=`https://api.github.com/repos/${env.REPO}/actions/workflows/instagram-cards.yml/dispatches`;
    const r=await fetch(api,{method:'POST',headers:{...githubHeaders(env),'Content-Type':'application/json'},body:JSON.stringify({ref:'main',inputs:{action:'publish',draft_id:id}})});
    return reply(r.ok?'Requested':await r.text(),r.ok?202:502);
  }
  return reply('Not found',404);
}};
