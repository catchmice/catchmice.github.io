"""3단계 웹 번들 스모크 테스트 (헤드리스 Chromium)

준비물(선택): pip install playwright && python3 -m playwright install chromium
실행:  cd <repo> && npm run prepare:web
       python3 -m http.server 8123 --directory www &
       python3 scripts/smoke-test-app.py http://127.0.0.1:8123/
GitHub Actions(APK 빌드)는 이 파일을 실행하지 않습니다. 앱을 고쳤을 때 손으로 확인하는 용도입니다.

1) 일반 브라우저: 화면 렌더링 + 콘솔 오류 없음 + 서비스 워커 등록
2) Capacitor 네이티브 흉내(window.Capacitor 주입): CM_NATIVE=true, 서비스 워커 미등록,
   target=_blank 외부 링크 클릭이 기본 동작(페이지 이동)을 막는지
"""
import json
import os
import sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8123/"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else "/tmp"  # 스크린샷 저장 폴더

# 캐시에 headless shell 이 없을 수 있어 설치된 chromium 실행 파일을 직접 지정
CHROME = os.path.expanduser("~/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome")
LAUNCH = {"executable_path": CHROME} if os.path.exists(CHROME) else {}

failures = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        failures.append(msg)


def run(pw, native: bool):
    label = "네이티브 앱" if native else "일반 브라우저"
    print(f"\n=== {label} ===")
    browser = pw.chromium.launch(**LAUNCH)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    errors = []
    if native:
        ctx.add_init_script(
            "window.Capacitor={isNativePlatform:()=>true,getPlatform:()=>'android',Plugins:{}};"
        )
    page = ctx.new_page()
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until="load")
    page.wait_for_timeout(2500)

    info = page.evaluate(
        """() => ({
            native: !!window.CM_NATIVE,
            standalone: !!window.CM_STANDALONE,
            title: document.title,
            tabs: document.querySelectorAll('nav.tabbar a, nav.tabbar button').length,
            cards: document.querySelectorAll('.card').length
        })"""
    )
    print("  화면:", json.dumps(info, ensure_ascii=False))

    check(info["native"] is native, f"CM_NATIVE == {native}")
    check(info["tabs"] >= 5, "탭 바 렌더링")
    check(info["cards"] > 3, f"카드 렌더링 ({info['cards']}개)")

    # 번들 JSON 4종이 화면에 실제로 그려지는지 (탭마다 카드 개수)
    counts = {}
    for hash_, sel in [("#jobs", ".job"), ("#news", ".news"), ("#papers", ".paper"), ("#calendar", ".card")]:
        page.evaluate(f"location.hash='{hash_}'"); page.wait_for_timeout(400)
        counts[hash_] = page.evaluate(f"document.querySelectorAll('{sel}').length")
    print("  항목 수:", json.dumps(counts))
    check(all(v > 0 for v in counts.values()), f"번들 JSON 4종 렌더링 {counts}")

    regs = page.evaluate(
        "async () => ('serviceWorker' in navigator) ? (await navigator.serviceWorker.getRegistrations()).length : -1"
    )
    if native:
        check(regs == 0, f"앱에서는 서비스 워커 등록 안 함 (registrations={regs})")
    else:
        check(regs >= 1, f"브라우저에서는 서비스 워커 등록 (registrations={regs})")

    if native:
        # 외부 target=_blank 링크 클릭 → 우리 핸들러가 가로채 시스템 브라우저로 넘기는지
        res = page.evaluate(
            """() => {
                window.__opened = [];
                const orig = window.open;
                window.open = (u, t) => { window.__opened.push([u, t]); return {closed: false}; };
                const a = document.querySelector('a[target="_blank"][href^="http"]');
                if (!a) return {err: 'no-link'};
                const ev = new MouseEvent('click', {bubbles: true, cancelable: true, view: window});
                a.dispatchEvent(ev);
                window.open = orig;
                return {prevented: ev.defaultPrevented, opened: window.__opened, href: a.getAttribute('href')};
            }"""
        )
        print("  링크 가로채기:", json.dumps(res, ensure_ascii=False)[:220])
        check(res.get("err") != "no-link", "외부 _blank 링크 존재")
        check(res.get("prevented") is True, "외부 _blank 링크 기본 동작 차단")
        check(bool(res.get("opened")), "시스템 브라우저(_system)로 열기 요청")

    # 화면 이동(탭) 확인
    for hash, name in [("#jobs", "채용"), ("#news", "뉴스"), ("#calendar", "캘린더")]:
        page.evaluate(f"location.hash='{hash}'")
        page.wait_for_timeout(500)
        body = page.inner_text("main")
        check(len(body) > 200, f"{name} 화면 렌더링 ({len(body)}자)")

    check(not errors, f"콘솔 오류 없음 {'- ' + ' | '.join(errors[:3]) if errors else ''}")
    page.screenshot(path=f"{SHOTS}/step3_{'native' if native else 'web'}.png")
    browser.close()


with sync_playwright() as pw:
    run(pw, native=False)
    run(pw, native=True)

print("\n" + ("✗ 실패: " + ", ".join(failures) if failures else "✓ 모든 검사 통과"))
sys.exit(1 if failures else 0)
