# CatchMICE 앱 (3단계) — 안드로이드 APK · iOS

웹사이트(`https://catchmice.github.io`)는 **지금 그대로 GitHub Pages에서 돌아갑니다.**
이 단계는 같은 HTML·CSS·JS·JSON 파일을 **[Capacitor](https://capacitorjs.com) 7.6.10** 으로 감싸서
안드로이드·아이폰에 설치되는 진짜 앱으로 만드는 설정입니다. 서버도, 유료 서비스도 쓰지 않습니다.

- 안드로이드 APK: **GitHub Actions 무료 러너에서 자동 빌드** (내 컴퓨터에 안드로이드 SDK 없어도 됨)
- iOS: 같은 설정으로 **맥에서 Xcode로 빌드** (아래 6번)

---

## 1. 파일 구조

| 경로 | 무엇 |
| --- | --- |
| `package.json` | Capacitor 의존성과 `npm run` 명령 모음 |
| `capacitor.config.json` | 앱 이름 `CatchMICE`, 앱 ID `io.github.catchmice.app`, 웹 폴더 `www` |
| `scripts/prepare-web.mjs` | 사이트 실행 파일만 골라 `www/` 로 깨끗하게 복사 (`npm run prepare:web`) |
| `scripts/make-android-icons.py` | `icons/icon-512.png`(Micy)에서 런처 아이콘·스플래시 생성 |
| `scripts/build-android-apk.workflow.yml` | APK 자동 빌드 워크플로 (2번에서 GitHub에 붙여 넣음) |
| `android/` | 실제 안드로이드 Gradle 프로젝트 (Capacitor CLI가 만든 것) |
| `www/` | 빌드할 때마다 새로 만들어지는 웹 번들 — **커밋하지 않습니다** (`.gitignore`) |

`android/` 는 한 번 만들어 두면 계속 씁니다. `appId`·앱 이름·버전을 바꾸지 않는 한 다시 만들 필요가 없어요.

---

## 2. 앱은 웹사이트를 어떻게 담나 (기본: 번들 + 최신 데이터)

기본 설정은 **앱 안에 웹 파일을 넣어 두는 방식(번들)** 입니다.

1. 앱을 열면 폰 안에 들어 있는 `www/` 파일로 바로 화면이 뜹니다 → **인터넷이 없어도 열립니다.**
2. 화면이 뜬 뒤 1.5초 뒤에 `https://catchmice.github.io/*.json` 을 한 번 확인해서,
   앱에 들어 있는 데이터보다 **더 새 데이터가 있으면 조용히 바꿔 끼웁니다.**
   (온라인일 때만, 실패하면 그대로 번들 데이터를 씁니다. 매일 아침 자동 갱신되는 JSON이 앱에도 반영됩니다.)
3. 앱 자체(HTML/CSS/JS)를 새로 배포하려면 **새 APK를 빌드해서 다시 설치**하면 됩니다.

### 항상 최신 웹사이트를 보여 주고 싶다면 (`server.url`)

`capacitor.config.json` 에 아래를 더하면 앱이 GitHub Pages를 직접 불러옵니다. 웹을 고치면 앱도 즉시 바뀝니다.

```json
"server": {
  "androidScheme": "https",
  "url": "https://catchmice.github.io",
  "cleartext": false
}
```

- 장점: 앱을 다시 설치하지 않아도 항상 최신
- 단점: **인터넷이 없으면 빈 화면**, 첫 실행이 느림, 스토어 심사에서 "웹사이트를 담은 앱"으로 반려될 수 있음
- 지금은 **번들 방식(기본값)을 권장**합니다. 필요할 때만 위 블록을 넣고 다시 빌드하세요.

### 앱 안에서 달라지는 동작 (`index.html` 수정 3곳)

- 앱 감지: `window.CM_NATIVE` (Capacitor `isNativePlatform()`)
- **서비스 워커는 앱에서 끕니다.** (`sw.js` 는 브라우저 전용) 앱은 번들 파일을 그대로 쓰고, 화면 갱신은 APK로 합니다.
  → 웹뷰 캐시가 오래된 화면을 붙잡는 문제가 없습니다.
- `target="_blank"` 링크(기사 원문·채용공고·지도 등)는 웹뷰에 새 창이 없어 눌러도 반응이 없습니다.
  앱에서는 이런 링크를 **휴대폰 기본 브라우저로** 엽니다.

---

## 3. 자동 빌드 켜기 (GitHub 웹에서 1분, 한 번만)

보안 설정 때문에 이 저장소의 연결 앱은 `.github/workflows/` 경로에 파일을 **직접 올릴 수 없습니다**
(`refusing to allow a GitHub App to create or update workflow`). 대신 웹에서 붙여 넣으면 바로 켜집니다.

1. GitHub 저장소 → **Add file** → **Create new file**
2. 파일 이름에 `.github/workflows/build-android-apk.yml` 입력
3. `scripts/build-android-apk.workflow.yml` 파일 내용을 **전부 복사해서** 붙여 넣기
4. **Commit changes** (main 브랜치에 커밋)

끝입니다. 이제 다음부터는

- **Actions** 탭 → 왼쪽 **Android APK build** → **Run workflow** → 실행 (손으로 빌드)
- 또는 `main` 에 웹 파일(`index.html`, `*.json`, `icons/`, `img/`, `android/` 등)이 올라오면 **자동 빌드**

빌드 시간은 5~7분이고, GitHub 무료 한도(월 2,000분) 안에서 충분합니다.
Gradle 캐시를 쓰기 때문에 두 번째 빌드부터는 3분 안쪽으로 줄어듭니다.

> 매일 데이터 갱신(`Daily data update`)도 같은 방법으로 한 번 켜 주세요.
> 파일: `scripts/daily-update.workflow.yml` → 경로: `.github/workflows/daily-update.yml`

---

## 4. APK 내려받아 폰에 설치하기

1. **Actions** 탭 → **Android APK build** → 맨 위 성공한 실행(초록 체크) 클릭
2. 페이지 아래 **Artifacts** → **`CatchMICE-debug-apk`** 클릭 (zip 파일이 받아집니다)
3. 압축을 풀면 **`app-debug.apk`**
4. 폰으로 옮겨서(카톡 나에게 보내기·USB·구글 드라이브 등) 눌러 설치
   - "출처를 알 수 없는 앱 설치" 안내가 뜨면 **허용**을 눌러 주세요 (직접 만든 APK라 그렇습니다)
   - 안드로이드 6.0 이상에서 설치됩니다
5. 홈 화면에 **Micy 아이콘**과 `CatchMICE` 이름으로 앱이 생깁니다

**알아 둘 점**

- 이 APK는 **디버그(테스트용)** 입니다. 스토어에 올릴 때는 8번(서명)을 참고하세요.
- 새 버전은 **APK를 다시 설치(덮어쓰기)** 하면 됩니다. 저장한 공고·지원함 메모·체크리스트는 그대로 남습니다.
- Play 스토어 배포용 빌드는 릴리스 서명이 필요합니다 (8번).
- 안드로이드는 서명이 다른 APK 위에 설치하지 못하므로, 서명을 바꾸면 앱을 지우고 다시 설치해야 합니다.

---

## 5. 내 컴퓨터에서 빌드하기 (선택)

필요한 것: **Node.js 20 이상**, **JDK 21**, 안드로이드 SDK(Android Studio에 포함)

```bash
npm install
npm run prepare:web          # www/ 생성
npx cap sync android         # www → android/app/src/main/assets/public 복사
npm run build:android        # = cap sync + ./gradlew assembleDebug
# 결과: android/app/build/outputs/apk/debug/app-debug.apk
```

Android Studio에서 열어서 실행하려면:

```bash
npx cap open android
```

웹만 고쳤을 때는 `npm run sync:android` 만 다시 돌려 주세요.

---

## 6. iOS(아이폰)는 맥에서

이 저장소에는 **`ios/` 폴더를 넣지 않았습니다.** 리눅스·CI에서는 iOS 파일을 제대로 만들 수 없고,
맥에서 한 번만 만들면 되기 때문입니다. Capacitor 설정(`capacitor.config.json`)은 이미 iOS용 값까지 들어 있어서
맥에서 아래 세 줄이면 끝납니다.

```bash
npm install
npm run prepare:web
npm run add:ios        # ios/ 폴더 생성 (Xcode 프로젝트)
npx cap open ios       # Xcode 열기 → 실기기 또는 시뮬레이터 실행
```

- 무료 Apple ID로도 실기기에 7일간 설치해 볼 수 있습니다(팀 서명 선택).
- 앱스토어에 올리려면 유료 Apple Developer Program(연 $99)이 필요합니다.
- `ios/` 를 만든 뒤로는 `npm run sync:android` 대신 `npx cap sync` 를 쓰면 안드로이드·iOS가 함께 갱신됩니다.
- iOS 13 이상을 지원합니다.

---

## 7. 이름·아이콘·버전 바꾸기

| 바꾸고 싶은 것 | 하는 일 |
| --- | --- |
| 앱 아이콘 | `icons/icon-512.png` 를 같은 이름으로 교체 → `python3 scripts/make-android-icons.py` (pillow 필요) |
| 앱 이름 | `capacitor.config.json` 의 `appName`, `android/app/src/main/res/values/strings.xml` 의 `app_name`, `title_activity_main` |
| 앱 ID | `capacitor.config.json` 의 `appId`, `android/app/build.gradle` 의 `applicationId`·`namespace` (**스토어에 올린 뒤에는 못 바꿉니다**) |
| 버전 | `android/app/build.gradle` 의 `versionCode`(정수, 올라가기만 함) / `versionName`(사람이 보는 버전) |

아이콘을 바꾸면 `scripts/make-android-icons.py` 를 다시 돌려 런처 아이콘 5종·원형 아이콘·어댑티브
foreground·스플래시 11종이 함께 갱신됩니다. (앱 아이콘 배경색도 아이콘 모서리 색으로 자동 설정)

---

## 8. 나중에 Play 스토어에 올릴 때 (릴리스 서명)

지금 워크플로는 `assembleDebug`(디버그 APK)만 만듭니다. 스토어에는 **서명된 AAB(또는 APK)** 가 필요합니다.

1. 서명 키 만들기 (한 번만, 잃어버리면 앱 업데이트 불가 — 꼭 백업)
   ```bash
   keytool -genkey -v -keystore catchmice-release.keystore -alias catchmice \
     -keyalg RSA -keysize 2048 -validity 10000
   ```
2. GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions** 에 아래 4개 등록
   `KEYSTORE_BASE64`(keystore를 base64로), `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`
3. `android/app/build.gradle` 에 `signingConfigs.release` 를 추가하고 워크플로에서
   `./gradlew bundleRelease` 로 AAB를 만들어 업로드
4. 워크플로 YAML에 디코딩 스텝 추가: `echo "$KEYSTORE_BASE64" | base64 -d > android/release.keystore`

`*.keystore`, `*.jks`, `keystore.properties` 는 `.gitignore` 에 이미 들어 있어 실수로 커밋되지 않습니다.

---

## 9. 잘 안 될 때

| 증상 | 원인 / 해결 |
| --- | --- |
| 워크플로 파일을 올릴 때 `refusing to allow a GitHub App ... workflows` | 이 저장소의 연결 앱에 workflows 권한이 없습니다. 3번처럼 **GitHub 웹에서** 파일을 만드세요. |
| `npm ci` 실패 | `package-lock.json` 이 커밋되어 있는지 확인 |
| Gradle `SDK location not found` / `compileSdk 35` 없음 | 러너에 SDK 35를 설치하는 스텝이 이미 들어 있습니다. 그래도 실패하면 `local.properties` 대신 `ANDROID_SDK_ROOT` 를 확인 |
| `invalid source release: 21` | JDK 21이 아닙니다. 워크플로는 `setup-java` 21을 씁니다 (Capacitor 7 Android는 Java 21로 컴파일) |
| 앱 화면이 하얗게만 나옴 | `www/` 가 비었거나 `cap sync` 를 건너뜀 → `npm run sync:android` |
| 앱에서 기사·공고 링크가 안 열림 | `target="_blank"` 링크 처리(2번 마지막 항목)가 들어 있는지 확인 |
| 데이터가 안 바뀜 | 앱은 번들 데이터로 먼저 뜹니다. 온라인이면 1.5초 뒤 최신 JSON으로 갱신되고, 안 되면 APK를 새로 빌드하세요. |
