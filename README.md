# CatchMICE

MICE를 캐치하는 기자단 CatchMICE 웹사이트예요.
전시·컨벤션 일정, MICE 한입뉴스, 채용공고, 논문, 취업 가이드를 모아요.

- `index.html` 사이트 본체
- `events.json`, `news.json`, `jobs.json`, `papers.json` 매일 업데이트되는 데이터
- `img/` 캐릭터 이미지, `icons/` 앱 아이콘
- `manifest.webmanifest`, `sw.js` 휴대폰 홈 화면 설치와 오프라인 보기
- `scripts/update_data.py` 데이터 자동 수집 스크립트
- `scripts/daily-update.workflow.yml` 매일 아침 자동 실행 설정(아래 설명 참고)

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
