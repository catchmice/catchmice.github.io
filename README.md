# CatchMICE

MICE를 캐치하는 기자단 CatchMICE 웹사이트예요.
전시·컨벤션 일정, MICE 한입뉴스, 채용공고, 논문, 취업 가이드를 모아요.
서버·유료 API 없이 GitHub Pages에 올라가는 정적 사이트(HTML/CSS/JS + JSON)입니다.

- `index.html` 사이트 본체 (라우팅·렌더링·캐릭터 브리핑이 모두 이 파일 안에 있어요)
- `events.json`, `news.json`, `jobs.json`, `papers.json` 매일 업데이트되는 데이터
- `img/` 캐릭터 이미지, `icons/` 앱 아이콘
- `manifest.webmanifest`, `sw.js` 휴대폰 홈 화면 설치와 오프라인 보기
- `404.html` 없는 주소로 들어왔을 때 보여 주는 안내 페이지
- `scripts/update_data.py` 데이터 자동 수집 스크립트
- `scripts/daily-update.workflow.yml` 매일 아침 자동 실행 설정(아래 설명 참고)
- `package.json`, `capacitor.config.json`, `scripts/prepare-web.mjs` 앱(안드로이드·iOS) 빌드 설정
- `android/` 안드로이드 앱 프로젝트, `scripts/build-android-apk.workflow.yml` APK 자동 빌드
- `APP_SETUP.md` 앱 설치·빌드 안내(아래 "앱으로 설치하기" 참고)

## 앱으로 설치하기 (안드로이드 APK · iOS)

웹사이트는 그대로 GitHub Pages에서 돌고, **같은 파일로 폰에 설치하는 앱**도 만들 수 있어요.
[Capacitor](https://capacitorjs.com)로 감싸기 때문에 별도 서버나 유료 서비스가 필요 없습니다.

- **안드로이드 APK**: GitHub Actions 무료 러너에서 자동 빌드 → Actions 탭 Artifacts 에서 내려받아 설치
- **아이폰**: 같은 설정으로 맥에서 Xcode로 빌드 (`npx cap add ios && npx cap open ios`)
- 앱은 웹 파일을 **폰 안에 넣어 두고(번들)** 열어서 오프라인에서도 화면이 뜨고,
  온라인이면 1.5초 뒤 `https://catchmice.github.io` 의 최신 JSON으로 조용히 데이터를 갱신합니다.
- 앱 아이콘은 `icons/icon-512.png`(Micy)에서 만들어 넣었습니다.
- 앱 안에서는 서비스 워커(`sw.js`)를 끄고, `target="_blank"` 링크는 휴대폰 기본 브라우저로 엽니다.

처음 한 번만 해 두면 되는 준비(자동 빌드 켜기, APK 내려받기, iOS 빌드, 스토어 서명)는
**[`APP_SETUP.md`](APP_SETUP.md)** 에 순서대로 정리해 두었습니다.

## 화면 구성

아래쪽 6개 탭(홈·캘린더·동네·뉴스·채용·스터디)은 그대로이고, 그 안에서 화면이 바뀝니다.
`#home`, `#calendar`, `#walk`, `#news`, `#jobs`, `#ai`, `#papers`, `#guide`, `#crew` 주소를 그대로 쓸 수 있어요.
`#briefing`으로 들어오면 홈의 캐릭터 브리핑으로 바로 이동합니다.

## 캐릭터 일일 브리핑 & 질문하기 (2단계)

홈 화면 위쪽에 네 기자가 오늘 데이터를 정리해 주는 패널이 있어요.

- **Micy(채용 코치)** — 모집 중인 공고 수, 신입 가능 공고, 마감 7일 이내 공고, 지난 방문 뒤 새 공고
- **Veny(행사 가이드)** — 가장 가까운 행사 D-day, 7일 안에 열리는 행사, 사전등록이 열린 행사
- **Exy(뉴스 에디터)** — 최신 기사 수·분류 분포·헤드라인
- **Aily(준비 파트너)** — 취업 준비 8단계 진행률, 다음 할 일, 오늘의 AI 용어, 논문 수

빠른 질문 칩과 자유 입력으로 물어보면 **`jobs.json`·`news.json`·`events.json`·`papers.json`에 있는 항목만**으로
답합니다. 결과 카드는 해당 탭으로 이동하거나(채용·뉴스·논문) 행사 상세를 열고, 맞는 항목이 없으면
지어내지 않고 "전체 검색에서 찾기"로 안내합니다. 답변에는 항상 데이터 기준 날짜가 붙습니다.

### 내 맞춤 조건

브리핑 안의 **내 맞춤 조건**에서 지역(여러 개)·경력(무관/신입/경력)·관심 분야(PCO/전시/협회·공공/베뉴)를
고르면 Micy 브리핑과 "내 조건에 맞는 공고" 답변이 그 조건으로 좁혀집니다. 브라우저에만 저장됩니다.

### 3단계(AI API) 연동 지점

`index.html` 안의 `BADAPTER` 한 곳만 열려 있습니다. 키는 이 파일에 넣지 마세요.
어댑터가 없거나 실패하면 항상 위의 로컬 JSON 검색으로 답합니다.

```js
// 3단계에서 서버 프록시(권장)나 API를 붙일 때
window.CatchMICEAssistant.registerProvider(async (question, context) => {
  // context: {today, prefs, updated, jobs, events, news, papers, prep, applied}
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({question, context})
  });
  return {html: (await res.json()).html};   // .bans 안에 들어갈 HTML
});
```

그 밖에 `window.CatchMICEAssistant`는 `context()`(현재 데이터 스냅샷), `ask(q)`, `open("micy")`,
`hasProvider()`를 제공합니다. 어댑터를 지우려면 `registerProvider(null)`.

## 채용 트래커 (#jobs)

- 필터: **마감 임박(D-7)**, 신입 가능, 경력, **지원함**, 저장한 공고 + 지역
- 카드에서 **지원함**을 누르면 한 줄 메모를 남길 수 있고, `지원함` 표시·메모는 홈의 **내 지원·저장**에 모입니다.
- **캘린더** 버튼은 공고 마감일을 구글 캘린더에 하루 종일 일정으로 추가합니다(행사 카드와 같은 방식).
- 마감 지난 공고는 목록에서 자동으로 빠집니다.

## 취업 준비 8단계 (#guide)

`PREP` 배열의 8단계 체크리스트가 가이드 화면에 나옵니다. 체크하면 진행률 막대와 숫자가 바뀌고,
Aily 브리핑에도 바로 반영됩니다.

## 브라우저에 저장되는 값 (localStorage)

| 키 | 내용 |
| --- | --- |
| `cm_theme` | 화면 테마(system/light/dark) |
| `cm_saved2` | 저장한 행사·공고 |
| `cm_seen` | 지난 방문 때 본 항목(NEW 배지용) |
| `cm_prefs` | 내 맞춤 조건(지역·경력·관심 분야) |
| `cm_applied` | 지원함 표시 + 한 줄 메모 |
| `cm_prep` | 취업 준비 8단계 체크 |
| `cm_lessons` | AI 스터디에서 끝낸 레슨 |

서버로 보내지 않습니다. 브라우저 저장소를 지우면 함께 사라집니다.

## 오프라인·캐시 동작 (`sw.js`)

- 문서(HTML): **network-first** → 캐시 → 오프라인 안내
- `*.json` 데이터: **network-first** → 캐시 (매일 아침 갱신이 바로 보이도록)
- 이미지·아이콘·폰트: **stale-while-revalidate** (빠르게 보여 주고 뒤에서 갱신)
- 캐시 이름은 `catchmice-<VERSION>`이고, `VERSION`을 올리면 새 워커가 설치되면서 예전 캐시를 지웁니다.
  **index.html·이미지를 바꿔 배포할 때는 `sw.js`의 `VERSION`도 함께 올려 주세요.**

## 404

`404.html`은 CatchMICE 색·캐릭터로 만든 안내 페이지입니다. 5초 뒤 `/#home`으로 이동하고
바로 갈 수 있는 버튼(홈·한입뉴스·채용)도 있습니다.

## 데이터 자동 업데이트

`jobs.json`(채용공고)과 `news.json`(한입뉴스)은 GitHub Actions가 매일 아침 7시(KST)에
`scripts/update_data.py`를 돌려 새로 채워요. 유료 API나 별도 서버, 라이브러리 없이 표준 파이썬만 씁니다.

- **채용공고** — 사람인(Saramin)에서 MICE·컨벤션·PCO·국제회의·전시기획·행사기획 공고를 검색해
  회사·제목·지역·고용형태·마감일·급여를 `jobs.json` 스키마 그대로 담아요.
  웨딩홀·식음·시설관리·디자인 전용 같은 무관 공고와 마감이 지난 공고는 거르고,
  손으로 골라 둔 기존 공고는 마감 전까지 그대로 둡니다.
- **뉴스** — 한국MICE저널(KMJ), 호텔레스토랑, 여행신문, 비즈월드, 디스커버리뉴스의 RSS에서
  MICE·컨벤션·전시 관련 기사만 골라 최신 15건으로 정리해요(기사 첫 문단을 요약으로 사용).
- 수집에 실패하면 기존 파일을 지우지 않고 그대로 둡니다. 한 소스가 막혀도 나머지로 채워요.

### 직접 실행해 보기

```bash
python3 scripts/update_data.py            # 실제로 jobs.json, news.json 갱신
python3 scripts/update_data.py --dry-run  # 파일을 쓰지 않고 결과만 확인
python3 scripts/update_data.py --jobs-only
python3 scripts/update_data.py --news-only
```

### 수동으로 한 번 돌리기

GitHub 저장소 → **Actions** 탭 → **Daily data update** → **Run workflow** (브랜치 선택 후 실행).
바뀐 내용이 있을 때만 `jobs.json`, `news.json`을 커밋하고 푸시합니다.

### 자동 실행 켜기 (한 번만)

자동 실행 설정은 `scripts/daily-update.workflow.yml`에 들어 있어요.
GitHub에서 `.github/workflows/daily-update.yml` 파일을 새로 만들고 그 내용을 그대로 붙여 넣으면
다음 날 아침 7시부터 자동으로 돌기 시작합니다.
(작업 도구에 workflows 권한이 없어 이 경로로는 직접 올리지 못했어요. 웹에서 파일을 추가하면 바로 동작합니다.)
