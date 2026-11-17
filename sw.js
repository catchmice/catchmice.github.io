/* CatchMICE service worker (Step 2)
   - 문서(navigate): network-first → 캐시 → 오프라인 안내
   - *.json 데이터: network-first → 캐시 (매일 아침 갱신이 바로 보이도록)
   - 정적 자산(img/css/js/icon/font): stale-while-revalidate (빠르게 보여주고 뒤에서 갱신)
   - VERSION을 올리면 activate에서 예전 캐시를 자동으로 지웁니다.
   ※ 배포할 때 index.html·이미지가 바뀌면 아래 VERSION 숫자를 함께 올려 주세요.
*/
const VERSION = "v3-2026-11-17";
const CACHE = "catchmice-" + VERSION;
const OFFLINE_HTML = "404.html";

const CORE = [
  "./",
  "index.html",
  "manifest.webmanifest",
  "404.html",
  "img/hero.jpg",
  "img/micy.jpg",
  "img/veny.jpg",
  "img/exy.jpg",
  "img/aily.jpg",
  "img/crew-who.jpg",
  "img/crew-lineup.jpg",
  "icons/icon-192.png",
  "icons/icon-512.png"
];

const FONT_HOSTS = ["fonts.googleapis.com", "fonts.gstatic.com"];

self.addEventListener("install", e => {
  e.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    // 한 파일이 없어도 설치는 계속되게 (addAll은 하나만 실패해도 전부 실패)
    await Promise.all(CORE.map(url => cache.add(new Request(url, { cache: "reload" })).catch(() => {})));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k.indexOf("catchmice-") === 0 && k !== CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener("message", e => {
  if (e.data === "SKIP_WAITING" || (e.data && e.data.type === "SKIP_WAITING")) self.skipWaiting();
});

const isJson = u => /\.json$/i.test(u.pathname);
const isAsset = u => /\.(?:css|m?js|png|jpe?g|gif|svg|webp|avif|ico|woff2?|ttf|otf)$/i.test(u.pathname);

async function store(req, res) {
  try {
    if (res && res.ok && res.type !== "opaque") {
      const cache = await caches.open(CACHE);
      await cache.put(req, res.clone());
    }
  } catch (err) { /* 저장 실패는 무시: 다음 요청에서 다시 시도 */ }
}

async function networkFirst(req) {
  try {
    const res = await fetch(req);
    if (res && res.ok) store(req, res);
    return res;
  } catch (err) {
    const hit = await caches.match(req, { ignoreSearch: true });
    if (hit) return hit;
    throw err;
  }
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // 구글 폰트: 내용이 바뀌지 않으므로 캐시 우선
  if (FONT_HOSTS.indexOf(url.hostname) >= 0) {
    e.respondWith((async () => {
      const hit = await caches.match(req);
      if (hit) return hit;
      const res = await fetch(req);
      store(req, res);
      return res;
    })().catch(() => Response.error()));
    return;
  }

  if (url.origin !== self.location.origin) return;
  if (url.pathname.endsWith("/sw.js")) return;

  // 앱 문서: 늘 새 HTML을 먼저 시도 (업데이트가 바로 반영)
  if (req.mode === "navigate") {
    e.respondWith((async () => {
      try {
        const res = await fetch(req);
        if (res && res.ok) store(req, res);
        return res;
      } catch (err) {
        const hit = await caches.match(req, { ignoreSearch: true });
        if (hit) return hit;
        const shell = await caches.match("index.html");
        if (shell) return shell;
        const off = await caches.match(OFFLINE_HTML);
        if (off) return off;
        return new Response("오프라인 상태예요. 연결되면 다시 열어 주세요.", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } });
      }
    })());
    return;
  }

  // 데이터 JSON: network-first, 실패하면 캐시본
  if (isJson(url)) {
    e.respondWith((async () => {
      try {
        return await networkFirst(req);
      } catch (err) {
        const hit = await caches.match(req, { ignoreSearch: true });
        if (hit) return hit;
        return new Response("[]", { status: 503, headers: { "Content-Type": "application/json; charset=utf-8" } });
      }
    })());
    return;
  }

  // 정적 자산: stale-while-revalidate
  if (isAsset(url)) {
    e.respondWith((async () => {
      const cache = await caches.open(CACHE);
      const hit = await cache.match(req);
      const net = fetch(req).then(res => { if (res && res.ok) cache.put(req, res.clone()); return res; }).catch(() => null);
      if (hit) return hit;
      const res = await net;
      if (res) return res;
      return new Response("", { status: 504 });
    })());
    return;
  }

  // 그 밖의 같은 출처 요청
  e.respondWith((async () => {
    const hit = await caches.match(req);
    if (hit) return hit;
    try {
      const res = await fetch(req);
      if (res && res.ok) store(req, res);
      return res;
    } catch (err) {
      return new Response("", { status: 504 });
    }
  })());
});
