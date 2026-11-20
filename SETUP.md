# CatchMICE 인스타그램 승인형 카드뉴스 — 설치 패키지

**상태:** 배포 전 소스코드. 기존 홈페이지 변경 없음. 사용자 승인 없이 게시하지 않음.

## 동작

1. 홈페이지의 `news.json`에서 이전에 초안으로 만든 적 없는 기사를 선택합니다.
2. Github Actions가 화·금 07:00 KST에 1080×1350 PNG 5장을 만듭니다(실제 시작은 GitHub 스케줄 지연 가능).
3. `social/drafts/<id>`를 GitHub Pages에 공개하여 카드뉴스 이미지 URL을 발행합니다.
4. Cloudflare Access로 인증된 **본인만** 승인 페이지에서 5장과 캡션을 확인하고 게시 워크플로를 호출합니다.
5. Instagram Login API의 Instagram 비즈니스 게시 권한으로 캐러셀을 게시하고 결과 상태를 기록합니다.

## 캐릭터 원본 고정

`assets/{micy,veny,exy,aily}.png`는 **사용자가 제공한 기자단 소개 카드뉴스의 각 캐릭터 구역을 그대로 자른 이미지**입니다. 재생성하지 않습니다. 이미지 배경이 포함된 스크린샷 크롭이므로 실제 브랜드용 배경 없는 투명 PNG를 확보하면 교체하는 것을 권장합니다. 원본 그림체와 얼굴을 다시 그리는 것은 금지합니다.

## GitHub에 올릴 것

패키지 파일을 `catchmice/catchmice.github.io` 루트에 병합합니다. 기존 `index.html`과 기존 `img`는 수정할 필요가 없습니다. **`news.json`은 기존 저장소 파일을 사용하며 패키지에는 포함하지 않았습니다.**

특히 `.github/workflows/instagram-cards.yml` 워크플로는 GitHub의 웹 편집기에서 직접 업로드해야 할 수 있습니다. 이 환경의 GitHub 커넥터는 `create_branch`에 403을 반환했습니다.

GitHub 저장소 Settings > Secrets and variables > Actions > Secrets에 아래를 추가하세요.

- `IG_ACCESS_TOKEN`: Meta Instagram Login으로 발급받은 실제 게시 권한 토큰
- `IG_USER_ID`: Instagram Professional Account 숫자 ID

GitHub Settings > Environments에서 `instagram-publishing` 환경을 만들어 **Required reviewers**를 설정하면 추가 2차 승인 안전장치가 됩니다. 플랜 및 공개 저장소 제약은 GitHub 설정에서 확인하세요.

Actions > CatchMICE Instagram approval > Run workflow > generate 로 첫 초안을 테스트하세요. `social/drafts/<id>` 이미지들이 GitHub Pages에서 열린 후 게시 승인 테스트를 진행하세요.

## 승인 버튼 설치 (Cloudflare Worker)

1. Cloudflare에서 Worker를 배포합니다. `worker/index.js`와 `worker/wrangler.toml` 사용.
2. Worker에 **Cloudflare Access 애플리케이션**을 걸어 본인의 이메일만 접근하도록 허용하세요.
3. `ACCESS_AUD`에 해당 Access App의 AUD, `ACCESS_TEAM`에 팀 도메인을 넣으세요.
4. Worker secret `GITHUB_TOKEN`에 **해당 repo Contents: Read 및 Actions: Write** 권한의 fine-grained GitHub PAT를 저장하세요. 브라우저 파일에 넣으면 안 됩니다.
5. 사용자 휴대폰에서 Worker URL 접속 → 초안 ID 입력 → 이미지·캡션 확인 → **승인하고 인스타그램 게시**.

## Meta 설정

Meta Developers에서 Instagram API with Instagram Login을 설정하고, `instagram_business_basic`, `instagram_business_content_publish` 권한을 사용하세요. 계정을 앱에 연결하고 사용자 ID 및 장기 액세스 토큰을 안전하게 저장하고 만료/갱신 정책을 마련하세요. 실제 계정에 대한 권한은 Meta 설정/앱 상태에 따라 다릅니다. 토큰을 채팅으로 공유하지 마세요.

## 중요한 제한

- **현재 패키지는 배포·Meta 인증·실게시 검증이 되지 않았습니다.**
- 승인 페이지는 Cloudflare Access 인증이 반드시 필요하며, Worker 접근 허용 범위를 전체 공개로 두면 안 됩니다.
- 초안의 이미지 및 원고는 GitHub Pages에 공개됩니다. 민감하거나 비공개 콘텐츠는 이 설계에서 사용하면 안 됩니다.
- 공개된 승인 버튼은 없고, Cloudflare Access 본인 인증 후에만 접속합니다.
- Meta API는 이미지가 공개 HTTPS URL로 접근 가능해야 합니다. Pages 배포 반영 시간을 확인하세요.
- AI 문장 생성 대신 `news.json`의 원문 요약을 템플릿에 배치한 **결정론적 MVP**입니다. 원문 대조와 사실 확인은 승인자가 해야 합니다. 4장 인사이트는 기사별 자동 심층 분석이 아닌 공통 실무 질문으로 표기합니다.
- 스케줄 작업은 07:00에 **시작**하며 08:00 이전 완료를 보장하지 않습니다.
- 승인 요청의 진위는 서버에서 확인합니다. 게시 상태 중복 방지는 draft 상태에 의존하므로 동시 요청/중복 실행에는 추가 락이나 GitHub Environment 승인 정책이 필요합니다.
- 실제 무인 운영 전 Meta 버전, 처리 대기 상태, 실패 재시도 및 토큰 만료 로직을 테스트하세요.
