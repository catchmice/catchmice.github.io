#!/usr/bin/env python3
"""CatchMICE 데이터 매일 자동 업데이트.

매일 아침(KST 07:00) GitHub Actions에서 실행되어
  - `jobs.json` : 사람인(Saramin) 채용 검색 결과에서 MICE·컨벤션·전시·국제회의 공고를 모아 갱신
  - `news.json` : 국내 MICE 업계 매체 RSS에서 새 기사를 모아 기존 목록 뒤에 더함
합니다.

설계 원칙
  * 표준 라이브러리만 사용합니다. 외부 패키지, 유료 API, API 키가 필요 없습니다.
  * 수집에 실패하면 기존 데이터를 지우지 않습니다(안전 실패).
  * 사이트(`index.html`)가 읽는 스키마를 100% 그대로 유지합니다.
  * **사람이 정리해 둔 항목은 자동 실행이 지우거나 덮어쓰지 않습니다.**
    - `jobs.json` : 마감일(`YYYY-MM-DD`)이 지난 공고만 정리하고, 나머지는 필드까지 그대로 둡니다.
      같은 공고(URL 또는 회사+제목)는 RSS/사람인에서 다시 긁혀도 새 항목으로 덧붙이지 않습니다.
    - `news.json` : 기존 기사는 URL·제목 기준으로 중복 판정해 기존 요약(sum)을 그대로 살립니다.
      기사 날짜가 `NEWS_KEEP_DAYS`보다 오래된 것만 정리하고, 새 기사만 더합니다.
  * 예전처럼 `최신 15건`으로 통째로 잘라 내지 않습니다(기존 목록이 15건보다 많아도 유지).

사용법
    python3 scripts/update_data.py              # 실제 파일 갱신
    python3 scripts/update_data.py --dry-run    # 파일을 쓰지 않고 결과만 확인
    python3 scripts/update_data.py --jobs-only  # 채용공고만 갱신
    python3 scripts/update_data.py --news-only  # 뉴스만 갱신
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

try:  # Python 3.9+
    from zoneinfo import ZoneInfo

    KST = ZoneInfo("Asia/Seoul")
except Exception:  # pragma: no cover - tzdata가 없는 환경 대비
    KST = timezone(timedelta(hours=9))

REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_PATH = REPO_ROOT / "jobs.json"
NEWS_PATH = REPO_ROOT / "news.json"

USER_AGENT = "CatchMICE-daily-update/1.0 (+https://catchmice.github.io)"
HTTP_TIMEOUT = 25
HTTP_RETRIES = 2
POLITE_DELAY = 1.2  # 요청 사이 대기(초). 상대 서버에 부담을 주지 않기 위함

# ---------------------------------------------------------------------------
# 보관 정책
#   기존(사람이 정리한) 항목이 상한을 넘더라도 잘라 내지 않습니다.
#   상한은 '새로 더할 자리'를 정하는 값으로만 씁니다.
#   - jobs.json : 상한(MAX_JOBS)에 차면 마감이 지난 공고가 빠진 자리에만 새 공고를 담습니다.
#   - news.json : 기사 날짜 기준(NEWS_KEEP_DAYS)으로만 줄어들기 때문에, 상한에 가까워도
#                 MIN_NEW_ITEMS_PER_RUN 만큼은 새 기사를 더해 목록이 낡지 않게 합니다.
# ---------------------------------------------------------------------------

# jobs.json 총 보관 상한(사람이 고른 기존 항목은 항상 포함)
MAX_JOBS = 100
# 한 번 실행에서 새로 더하는 공고 수 상한(마감이 급한 공고부터)
MAX_NEW_JOBS_PER_RUN = 20

# news.json 총 보관 상한(기존 기사는 항상 포함)
MAX_NEWS = 40
# 한 번 실행에서 새로 더하는 기사 수 하한
MIN_NEW_ITEMS_PER_RUN = 5
# 이 기간(일)이 지난 기존 기사는 정리한다. 그 안의 기사는 개수와 상관없이 보존
# (RSS에서 새로 집을 때도 같은 기준을 써서, 담은 기사가 다음 실행에 곧바로 지워지는 일이 없게 한다)
NEWS_KEEP_DAYS = 10
NEWS_FIELDS = ("date", "cat", "source", "title", "sum", "url")

# ---------------------------------------------------------------------------
# 공통 유틸
# ---------------------------------------------------------------------------

_INVISIBLE = str.maketrans({"\u200b": "", "\u200c": "", "\u200d": "", "\ufeff": "", "\u00a0": " "})


def clean_text(value: str) -> str:
    """HTML 엔티티를 풀고 공백/보이지 않는 문자를 정리한다."""
    text = html_lib.unescape(value or "").translate(_INVISIBLE)
    return re.sub(r"\s+", " ", text).strip()


def strip_tags(value: str) -> str:
    return clean_text(re.sub(r"<[^>]+>", " ", value or ""))


def fetch(url: str, *, timeout: int = HTTP_TIMEOUT, retries: int = HTTP_RETRIES) -> str:
    """URL을 가져와 문자열로 돌려준다. 실패하면 RuntimeError."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
        "Accept-Encoding": "identity",
    }
    last_error: object = None
    for attempt in range(retries + 1):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                raw = response.read()
            break
        except (HTTPError, URLError, TimeoutError, OSError) as exc:  # noqa: PERF203
            last_error = exc
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    else:  # 모든 시도 실패
        raise RuntimeError(f"요청 실패: {url} ({last_error})")

    for encoding in (charset, "utf-8", "euc-kr"):
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError(f"{path.name}: items 배열이 없는 JSON")
    return data


def write_json(path: Path, payload: dict) -> None:
    """원자적으로 파일을 쓴다(중간에 죽어도 파일이 깨지지 않게)."""
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def today_kst() -> date:
    return datetime.now(KST).date()


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_url(url: str) -> str:
    """중복 판정용 URL 정규화(스킴/www/추적 파라미터/끝 슬래시 제거)."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in {"fbclid", "gclid", "oc", "hl", "gl", "ceid"}
    ]
    path = parts.path.rstrip("/")
    return urlunsplit(("https", netloc, path, urlencode(query_pairs), ""))


def normalize_title(title: str) -> str:
    """중복 판정용 제목 정규화(공백/기호/말머리 제거)."""
    text = re.sub(r"^\s*[\[(][^\])]{1,20}[\])]\s*", "", clean_text(title))
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


# ---------------------------------------------------------------------------
# 채용공고(jobs.json)
# ---------------------------------------------------------------------------

SARAMIN_SEARCH_URL = (
    "https://www.saramin.co.kr/zf_user/search/recruit"
    "?searchType=search&searchword={query}&recruitPageCount={count}&recruitPage=1"
)
SARAMIN_QUERIES = ("MICE", "컨벤션", "PCO", "국제회의", "전시기획", "행사기획")
SARAMIN_PAGE_COUNT = 100

# MICE 업계 공고로 볼 만한 표현 / 걸러낼 표현
JOB_INCLUDE_RE = re.compile(
    r"MICE|마이스|컨벤션|국제회의|PCO|전시|박람회|엑스포|EXPO|(?<!여)행사|이벤트|컨퍼런스|학회|포럼|심포지엄",
    re.IGNORECASE,
)
JOB_EXCLUDE_RE = re.compile(
    r"웨딩|예식|홀서빙|서빙|주방|조리|바리스타|파티셰|제과|뷔페|세척|설거지|알바|아르바이트 모집|연회|예약실|예약부|"
    r"시설관리|시설관리원|미화|청소|경비|주차|건축|건설|인테리어|토목|전기|설비|기계설계|캐드|CAD|"
    r"디자이너|디자인 담당|편집디자인|그래픽|웹디자인|UI|UX|퍼블리셔|영상편집|"
    r"개발자|프로그래머|엔지니어|반도체|물류|배송|운전|생산직|제조|공장|"
    r"요양|간병|장례|상조|콜센터|텔레마케팅|보험|학습지|방문판매|부동산|아파트|"
    r"경리|회계|총무|비서|인사담당|급식|간호|의료기사|약사|영양사",
    re.IGNORECASE,
)
# 제목에 붙는 마감 표시
JOB_CLOSED_RE = re.compile(r"\(마감\)|\[마감\]|마감된", re.IGNORECASE)

REGION_MAP = {
    "서울전체": "서울",
    "경기전체": "경기",
    "전남광주": "광주·전남",
    "경남울산": "울산·경남",
    "전북전주": "전북",
}


def _parse_deadline(text: str, today: date) -> str | None:
    """사람인 마감 표기를 `YYYY-MM-DD` 또는 `상시`로 바꾼다."""
    value = clean_text(text)
    if not value:
        return None
    if re.search(r"상시|채용시|수시|채용완료시", value):
        return "상시"
    if "오늘" in value:
        return today.isoformat()
    if "내일" in value:
        return (today + timedelta(days=1)).isoformat()

    match = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})", value)  # ~ 11/30(월)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        try:
            parsed = date(today.year, month, day)
        except ValueError:
            return None
        if parsed < today - timedelta(days=45):  # 연말·연초 공고는 다음 해로
            try:
                parsed = date(today.year + 1, month, day)
            except ValueError:
                return None
        return parsed.isoformat()

    match = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", value)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        except ValueError:
            return None
    return None


def _strip_company_tag(title: str, company: str) -> str:
    """제목 앞의 `[회사명]` 말머리를 회사명과 같을 때만 떼어 낸다."""
    match = re.match(r"^\s*[\[(]([^\])]{2,25})[\])]\s*", title)
    if not match:
        return title
    tag = re.sub(r"[^0-9A-Za-z가-힣]", "", match.group(1))
    name = re.sub(r"[^0-9A-Za-z가-힣]", "", company or "")
    if tag and name and (tag in name or name in tag):
        return title[match.end() :].strip()
    return title


def _clean_company(name: str) -> str:
    text = clean_text(name)
    text = re.sub(r"^[(（]주[)）]\s*", "", text)
    text = re.sub(r"^주식회사\s*", "", text)
    text = re.sub(r"^㈜\s*", "", text)
    text = re.sub(r"\s*(?:주식회사|[(（]주[)）]|㈜)$", "", text)
    return text.strip()


def _normalize_pay(raw: str) -> str:
    value = clean_text(raw)
    if not value:
        return ""
    value = re.sub(r"\s+만원", "만원", value)
    value = re.sub(r"(\d)\s+(\d{3})", r"\1,\2", value)
    return value


def parse_saramin(html_text: str, today: date) -> list[dict]:
    """사람인 검색 결과 HTML에서 공고를 뽑아 jobs.json 스키마로 변환한다."""
    jobs: list[dict] = []
    for block in re.split(r'<div class="item_recruit"', html_text)[1:]:
        idx_match = re.match(r'\s*value="(\d+)"', block)
        if not idx_match:
            continue
        rec_idx = idx_match.group(1)

        title_match = re.search(r'<h2 class="job_tit">(.*?)</h2>', block, re.S)
        if not title_match:
            continue
        title_html = title_match.group(1)
        # 사람인은 목록에서 제목을 잘라 보여준다. a 태그의 title 속성에 원문 제목이 있다.
        full_title_match = re.search(r'title="([^"]{4,})"', title_html)
        visible_title = strip_tags(title_html)
        title = clean_text(full_title_match.group(1)) if full_title_match else visible_title
        if len(title) < len(visible_title):
            title = visible_title

        company_match = re.search(r'<strong class="corp_name">(.*?)</strong>', block, re.S)
        company = _clean_company(strip_tags(company_match.group(1))) if company_match else ""

        date_match = re.search(r'<div class="job_date">\s*<span class="([^"]*)">(.*?)</span>', block, re.S)
        deadline = _parse_deadline(date_match.group(2), today) if date_match else None

        condition_match = re.search(r'<div class="job_condition">(.*?)</div>', block, re.S)
        condition = condition_match.group(1) if condition_match else ""
        place = ""
        career = ""
        employer = ""
        pay = ""
        spans = re.findall(r"<span>(.*?)</span>", condition, re.S)
        for index, span in enumerate(spans):
            plain = strip_tags(span)
            if index == 0 and "<a" in span:  # 첫 span은 지역(시/군/구 링크)
                place = " ".join(strip_tags(item) for item in re.findall(r"<a[^>]*>(.*?)</a>", span, re.S))
                place = clean_text(place)
                continue
            if re.search(r"학력|대졸|초대졸|고졸|중졸|석사|박사", plain):
                continue
            if re.search(r"만원|시급|일급|월급|연봉", plain):
                pay = _normalize_pay(plain)
                continue
            if re.search(r"정규직|계약직|기간제|아르바이트|알바|프리랜서|인턴|파견|병역|전임|위촉", plain):
                employer = plain
                continue
            if re.search(r"신입|경력", plain) and not career:
                career = plain

        if not title or not company:
            continue
        if JOB_CLOSED_RE.search(title):
            continue
        if JOB_EXCLUDE_RE.search(title) or JOB_EXCLUDE_RE.search(company):
            continue
        if not JOB_INCLUDE_RE.search(title):  # 제목 기준. 부서명만 MICE인 무관 공고는 거른다
            continue
        if deadline and _ISO_DATE.match(deadline) and deadline < today.isoformat():
            continue

        title = _strip_company_tag(title, company)
        region_token = place.split(" ")[0] if place else ""
        if region_token.endswith("전체"):
            region_token = region_token[: -len("전체")]
        region = REGION_MAP.get(region_token, region_token) or "전국"
        career_text = career
        if employer and employer not in career_text:
            career_text = f"{career_text} · {employer}" if career_text else employer

        jobs.append(
            {
                "company": company,
                "title": title,
                "region": region,
                "place": place or region,
                "career": career_text or "공고 확인",
                "newbie": bool(re.search(r"신입|경력무관", f"{career} {employer}")),
                "deadline": deadline or "상시",
                "pay": pay,
                "url": f"https://www.saramin.co.kr/zf_user/jobs/view?rec_idx={rec_idx}",
                "site": "사람인",
            }
        )
        jobs[-1]["_rec_idx"] = rec_idx
    return jobs


K_MICE_RSS = "https://k-mice.visitkorea.or.kr/micerss.kto?func_name=notiRecList"
K_MICE_REGION_RE = re.compile(r"서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주")


def fetch_kmice_fallback(today: date) -> list[dict]:
    """사람인 수집이 실패했을 때 쓰는 보조 소스(K-MICE 채용게시판 RSS)."""
    raw = fetch(K_MICE_RSS, timeout=20)
    jobs: list[dict] = []
    for item in re.findall(r"<item>(.*?)</item>", raw, re.S):
        title_match = re.search(r"<title>(.*?)</title>", item, re.S)
        link_match = re.search(r"<link>(.*?)</link>", item, re.S)
        date_match = re.search(r"<pubDate>(\d{8})", item)
        if not (title_match and link_match):
            continue
        title = strip_tags(title_match.group(1))
        if not title or "마감" in title:
            continue
        link = html_lib.unescape(link_match.group(1).strip())
        if link.startswith("/"):
            link = "https://k-mice.visitkorea.or.kr" + link
        posted = None
        if date_match:
            try:
                posted = datetime.strptime(date_match.group(1), "%Y%m%d").date()
            except ValueError:
                posted = None
        if posted and (today - posted).days > 120:
            continue
        region_token = K_MICE_REGION_RE.search(title)
        region = region_token.group(0) if region_token else "전국"
        jobs.append(
            {
                "company": title.split(" ")[0],
                "title": title,
                "region": region,
                "place": region,
                "career": "공고 확인",
                "newbie": "신입" in title or "인턴" in title,
                "deadline": "상시",
                "pay": "",
                "url": link,
                "site": "K-MICE 채용게시판",
            }
        )
    return jobs


def job_sort_key(job: dict) -> tuple:
    deadline = job.get("deadline") or ""
    company = job.get("company") or ""
    title = job.get("title") or ""
    if _ISO_DATE.match(deadline):
        return (0, deadline, company, title)
    if deadline == "상시":
        return (1, "", company, title)
    return (2, "", company, title)


def _new_slot_capacity(kept_count: int, total_cap: int, min_per_run: int, max_per_run: int) -> int:
    """기존 항목을 지키면서 새 항목에 내어줄 자리 수를 계산한다.

    기존 항목이 상한을 넘어도 자리가 0이 되지 않게 `min_per_run`을 하한으로 두고
    (뉴스처럼 기간으로만 소멸하는 목록에 사용), 한 번에 너무 많이 늘지 않게
    `max_per_run`을 둔다. 채용공고처럼 상한에서 순환하는 목록은 하한을 0으로 둔다.
    """
    return min(max(total_cap - kept_count, min_per_run), max_per_run)


def merge_jobs(existing: list[dict], scraped: list[dict], today: date, log) -> list[dict]:
    """기존(사람이 고른) 항목을 보존하면서 새 공고를 더한다.

    - 마감일이 지난 기존 공고만 정리하고, 남은 기존 공고는 필드까지 그대로 둔다.
    - 같은 공고(URL 또는 회사+제목)는 다시 긁혀도 새 항목으로 덧붙이지 않는다.
    """
    today_iso = today.isoformat()
    kept: list[dict] = []
    dropped_expired = 0
    for job in existing:
        deadline = str(job.get("deadline") or "")
        if _ISO_DATE.match(deadline) and deadline < today_iso:
            dropped_expired += 1
            continue
        kept.append({key: value for key, value in job.items() if not key.startswith("_")})

    seen_urls = {normalize_url(job.get("url", "")) for job in kept}
    seen_keys = {(normalize_title(job.get("company", "")), normalize_title(job.get("title", ""))) for job in kept}
    seen_rec = {job.get("_rec_idx") for job in kept if job.get("_rec_idx")}

    added: list[dict] = []
    for job in scraped:
        url_key = normalize_url(job.get("url", ""))
        title_key = (normalize_title(job.get("company", "")), normalize_title(job.get("title", "")))
        rec_idx = job.get("_rec_idx")
        if url_key in seen_urls or title_key in seen_keys or (rec_idx and rec_idx in seen_rec):
            continue
        seen_urls.add(url_key)
        seen_keys.add(title_key)
        if rec_idx:
            seen_rec.add(rec_idx)
        added.append({key: value for key, value in job.items() if not key.startswith("_")})

    # 기존 항목은 먼저 지키고, 남는 자리만큼만 새 공고를 담는다(새 공고는 마감이 급한 순)
    # 상한(MAX_JOBS)에 차면 마감이 지난 공고가 빠지면서 생긴 자리에만 새로 담는다.
    capacity = _new_slot_capacity(len(kept), MAX_JOBS, 0, MAX_NEW_JOBS_PER_RUN)
    added.sort(key=job_sort_key)
    if len(added) > capacity:
        log(f"  새 공고 {len(added)}건 중 마감이 급한 {capacity}건만 오늘치에 담습니다(나머지는 다음 실행에서 재수집).")
        added = added[:capacity]
    merged = kept + added
    merged.sort(key=job_sort_key)

    log(f"  기존 {len(existing)}건 중 {len(kept)}건 유지 (마감 지난 {dropped_expired}건 정리)")
    log(f"  새 공고 {len(added)}건 추가 → 총 {len(merged)}건")
    return merged


def update_jobs(today: date, dry_run: bool, log) -> bool:
    """jobs.json을 갱신한다. 성공적으로 채웠으면 True."""
    data = load_json(JOBS_PATH)
    existing = data["items"]

    scraped: list[dict] = []
    succeeded_sources = 0
    for query in SARAMIN_QUERIES:
        url = SARAMIN_SEARCH_URL.format(query=quote(query, safe=""), count=SARAMIN_PAGE_COUNT)
        try:
            html_text = fetch(url)
            found = parse_saramin(html_text, today)
            scraped.extend(found)
            succeeded_sources += 1
            log(f"  사람인 '{query}' 검색: {len(found)}건")
        except Exception as exc:  # noqa: BLE001 - 한 소스 실패가 전체를 막지 않게
            log(f"  ! 사람인 '{query}' 검색 실패: {exc}")
        time.sleep(POLITE_DELAY)

    if not scraped:
        log("  ! 사람인에서 쓸 만한 공고를 하나도 얻지 못했습니다. K-MICE 게시판으로 재시도합니다.")
        try:
            scraped = fetch_kmice_fallback(today)
            if scraped:
                succeeded_sources += 1
                log(f"  K-MICE 채용게시판: {len(scraped)}건")
        except Exception as exc:  # noqa: BLE001
            log(f"  ! K-MICE 채용게시판도 실패: {exc}")

    merged = merge_jobs(existing, scraped, today, log)
    if not merged:
        log("  ! 결과가 비어 있어 jobs.json을 건드리지 않습니다.")
        return False
    if succeeded_sources == 0:
        log("  ! 수집에 성공한 소스가 없어 jobs.json을 그대로 둡니다.")
        return False

    payload = {"updated": today.isoformat(), "items": merged}
    if dry_run:
        log("  (dry-run) jobs.json은 쓰지 않았습니다. 미리보기 3건:")
        for job in merged[:3]:
            log(f"    - {job['company']} | {job['title'][:40]} | {job['deadline']} | {job['region']}")
    else:
        write_json(JOBS_PATH, payload)
        log(f"  jobs.json 저장 완료 ({len(merged)}건, updated={payload['updated']})")
    return succeeded_sources > 0 or bool(merged)


# ---------------------------------------------------------------------------
# 뉴스(news.json)
# ---------------------------------------------------------------------------

NEWS_FEEDS = (
    # (출처 이름, RSS 주소, 제목에서 허용할 말머리 태그)
    ("KMJ", "https://www.kmjournal.net/rss/allArticle.xml", (r"^\s*\[(?:마이스|MICE)",)),  # 한국MICE저널
    ("호텔레스토랑", "https://www.hotelrestaurant.co.kr/rss/allArticle.xml", ()),
    ("여행신문", "https://www.traveltimes.co.kr/rss/allArticle.xml", ()),
    ("비즈월드", "https://www.bizwnews.com/rss/allArticle.xml", ()),
    ("디스커버리뉴스", "https://www.discoverynews.kr/rss/allArticle.xml", ()),
)

NEWS_INCLUDE_RE = re.compile(
    r"MICE|마이스|컨벤션|국제회의|PCO|전시회|전시산업|전시컨벤션|전시장|박람회|엑스포|"
    r"컨퍼런스|학술대회|국제행사|인센티브|전시·행사|전람회",
    re.IGNORECASE,
)
# 같은 매체 기사가 목록을 독점하지 않도록, 한 번에 한 매체에서 담는 최대 건수
MAX_NEWS_PER_SOURCE = 6

# 사이트(index.html)가 색을 지정해 둔 6개 카테고리만 사용한다
_REGION_RE = re.compile(r"서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주")
_AI_RE = re.compile(r"\bAI\b|인공지능|로봇|메타버스|디지털 전환|챗봇|빅데이터", re.IGNORECASE)
_BID_RE = re.compile(r"국제회의|국제행사|세계대회|ICCA|총회|G20|월드컵|올픽픽")
_CENTER_RE = re.compile(r"컨벤션센터|전시컨벤션센터|전시장")
_OPEN_RE = re.compile(r"개관|착공|준공|건립|신축|완공|문을 연다|리모델링")
_EVENT_RE = re.compile(r"개막|개최|열린다|열려|박람회|엑스포|전시회|페스티벌|아트페어|마켓|행사")

_BYLINE_RE = re.compile(r"^\s*\[[^\]]{2,40}\]\s*")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def classify_news(title: str, body: str) -> str:
    text = f"{title} {body}"
    if _AI_RE.search(title) or _AI_RE.search(body):
        return "AI×MICE"
    if _BID_RE.search(title) and re.search(r"유치|선정", f"{title} {body}"):
        return "국제회의 유치"
    if _CENTER_RE.search(text) and _OPEN_RE.search(text):
        return "신규 컨벤션센터"
    if _EVENT_RE.search(title) or _EVENT_RE.search(body):
        return "전시·행사 일정"
    if _REGION_RE.search(text):
        return "지역 MICE"
    return "국내 MICE"


def _sentences(text: str) -> list[str]:
    """문장 단위로 나눈다(끝이 잘린 문장은 제외)."""
    parts = re.findall(r"[^.!?]{2,}?[.!?](?=\s|$|[가-힣A-Za-z\"'“‘(])", text)
    return [part.strip() for part in parts]


def summarize(text: str, limit: int = 210) -> str:
    """기사 첫 문단에서 두 문장 정도를 뽑아 요약으로 쓴다."""
    body = strip_tags(text)
    body = _BYLINE_RE.sub("", body)
    body = re.sub(r"\[[^\]]{0,40}기자[^\]]*\]", " ", body)
    body = _EMAIL_RE.sub("", body)
    body = clean_text(body)
    if not body:
        return ""
    sentences = _sentences(body)
    for start in (0, 1):  # 앞부분이 인용문으로 시작하면 다음 문장부터 다시 시도
        picked: list[str] = []
        for sentence in sentences[start:]:
            if len(" ".join(picked + [sentence])) > limit:
                break
            picked.append(sentence)
            if len(picked) >= 2:
                break
        if picked and _quotes_balanced(" ".join(picked)):
            return " ".join(picked)

    clipped = body[:limit].rsplit(" ", 1)[0]
    return f"{clipped}…" if clipped else ""


def _quotes_balanced(text: str) -> bool:
    return text.count("“") == text.count("”") and text.count("‘") == text.count("’")


def _parse_feed_date(value: str) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    for fmt, length in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%dT%H:%M:%S", 19),
        ("%Y%m%d%H%M%S", 14),
        ("%Y-%m-%d", 10),
    ):
        try:
            return datetime.strptime(text[:length], fmt).date()
        except ValueError:
            continue
    try:  # RFC 822 (Tue, 17 Nov 2026 09:11:47 GMT)
        from email.utils import parsedate_to_datetime

        parsed = parsedate_to_datetime(text)
        return parsed.astimezone(KST).date() if parsed else None
    except Exception:  # noqa: BLE001
        return None


def parse_feed(xml_text: str, source: str, topic_tags: tuple = (), today: date | None = None) -> list[dict]:
    today = today or today_kst()
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", xml_text)
        root = ET.fromstring(cleaned)

    items: list[dict] = []
    for node in root.iter("item"):
        title = strip_tags(node.findtext("title") or "")
        link = (node.findtext("link") or "").strip()
        if not title or not link.startswith("http"):
            continue
        published = _parse_feed_date(node.findtext("pubDate") or "")
        if published is None:
            continue
        if published > today or (today - published).days > NEWS_KEEP_DAYS:
            continue

        summary_source = node.findtext("description") or ""
        body = summarize(summary_source)
        title_clean = re.sub(r"^\s*\[(?:마이스|MICE)\]\s*", "", title).strip()

        tagged = any(re.search(pattern, title) for pattern in topic_tags)
        if not tagged and not NEWS_INCLUDE_RE.search(title_clean):
            continue
        if re.search(r"부고|인사말|인사\b|동정|포토뉴스|오늘의 날씨|주간\s*행사", title_clean):
            continue

        items.append(
            {
                "date": published.isoformat(),
                "cat": classify_news(title_clean, body),
                "source": source,
                "title": title_clean,
                "sum": body,
                "url": link,
            }
        )
    return items


def _news_date(item: dict) -> date | None:
    text = str(item.get("date") or "").strip()
    if not _ISO_DATE.match(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def merge_news(existing: list[dict], scraped: list[dict], today: date, log) -> list[dict]:
    """기존 기사(사람이 다듬은 요약)를 보존하면서 새 기사만 더한다.

    - 기존 기사는 URL·제목 기준으로 중복을 걸러 내고, 필드(date·cat·source·title·sum·url)를
      그대로 살립니다. RSS에 다시 보여도 기존 요약을 덮어쓰지 않습니다.
    - 기사 날짜가 `NEWS_KEEP_DAYS`보다 오래된 기존 기사만 정리합니다.
    - 새 기사는 중복 없이 최신순으로 더하되, 한 번에 `MIN_NEW_ITEMS_PER_RUN` 이상은 들어오게 합니다.
    """
    kept: list[dict] = []
    dropped_old = 0
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()

    for item in existing:  # 기존(사람이 쓴) 항목이 우선
        title_key = normalize_title(str(item.get("title") or ""))
        if not title_key:
            continue
        url_key = normalize_url(str(item.get("url") or ""))
        if (url_key and url_key in seen_urls) or title_key in seen_titles:
            continue
        published = _news_date(item)
        if published is not None and (today - published).days > NEWS_KEEP_DAYS:
            dropped_old += 1
            continue
        if url_key:
            seen_urls.add(url_key)
        seen_titles.add(title_key)
        kept.append({key: item.get(key, "") for key in NEWS_FIELDS})

    # 새 기사 중복 제거(기존 목록과 겹치는 기사는 새로 더하지 않는다)
    fresh: list[dict] = []
    for item in sorted(scraped, key=lambda x: str(x.get("date") or ""), reverse=True):
        title_key = normalize_title(str(item.get("title") or ""))
        if not title_key:
            continue
        url_key = normalize_url(str(item.get("url") or ""))
        if (url_key and url_key in seen_urls) or title_key in seen_titles:
            continue
        if url_key:
            seen_urls.add(url_key)
        seen_titles.add(title_key)
        fresh.append({key: item.get(key, "") for key in NEWS_FIELDS})

    # 한 매체가 목록을 독점하지 않도록 매체별 상한을 두고, 남는 자리는 매체 상한을 풀어 채운다
    capacity = max(MAX_NEWS - len(kept), MIN_NEW_ITEMS_PER_RUN)
    per_source: dict[str, int] = {}
    picked: list[dict] = []
    overflow: list[dict] = []
    for entry in fresh:
        source = str(entry.get("source") or "")
        if per_source.get(source, 0) >= MAX_NEWS_PER_SOURCE:
            overflow.append(entry)
            continue
        per_source[source] = per_source.get(source, 0) + 1
        picked.append(entry)
        if len(picked) >= capacity:
            break
    else:
        picked.extend(overflow[: max(0, capacity - len(picked))])

    merged = kept + picked
    merged.sort(key=lambda item: (str(item.get("date") or ""), str(item.get("title") or "")), reverse=True)
    log(
        f"  기존 {len(existing)}건 중 {len(kept)}건 유지({NEWS_KEEP_DAYS}일 지난 기사 {dropped_old}건 정리)"
        f" + 새 기사 {len(picked)}건 → 총 {len(merged)}건"
    )
    return merged


def update_news(today: date, dry_run: bool, log) -> bool:
    data = load_json(NEWS_PATH)
    existing = data["items"]

    scraped: list[dict] = []
    succeeded_sources = 0
    for source, url, tags in NEWS_FEEDS:
        try:
            xml_text = fetch(url, timeout=20)
            found = parse_feed(xml_text, source, tags, today)
            scraped.extend(found)
            succeeded_sources += 1
            log(f"  {source} RSS: {len(found)}건")
        except Exception as exc:  # noqa: BLE001
            log(f"  ! {source} RSS 실패: {exc}")
        time.sleep(POLITE_DELAY)

    merged = merge_news(existing, scraped, today, log)
    if not merged:
        log("  ! 결과가 비어 있어 news.json을 건드리지 않습니다.")
        return False
    if succeeded_sources == 0:
        log("  ! 수집에 성공한 소스가 없어 news.json을 그대로 둡니다.")
        return False

    payload = {"updated": today.isoformat(), "items": merged}
    if dry_run:
        log("  (dry-run) news.json은 쓰지 않았습니다. 미리보기 3건:")
        for item in merged[:3]:
            log(f"    - {item['date']} [{item['cat']}] {item['title'][:40]} ({item['source']})")
    else:
        write_json(NEWS_PATH, payload)
        log(f"  news.json 저장 완료 ({len(merged)}건, updated={payload['updated']})")
    return succeeded_sources > 0 or bool(merged)


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CatchMICE 데이터(jobs.json, news.json) 매일 자동 업데이트")
    parser.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 결과만 확인합니다")
    parser.add_argument("--jobs-only", action="store_true", help="채용공고만 갱신합니다")
    parser.add_argument("--news-only", action="store_true", help="뉴스만 갱신합니다")
    args = parser.parse_args(argv)

    if args.jobs_only and args.news_only:
        parser.error("--jobs-only 와 --news-only 는 함께 쓸 수 없습니다")

    def log(message: str) -> None:
        print(message, flush=True)

    today = today_kst()
    log(f"[CatchMICE] 기준일 {today.isoformat()} (KST){' · dry-run' if args.dry_run else ''}")

    ok = True
    if not args.news_only:
        log("· 채용공고(jobs.json)")
        ok = update_jobs(today, args.dry_run, log) and ok
    if not args.jobs_only:
        log("· 뉴스(news.json)")
        ok = update_news(today, args.dry_run, log) and ok

    if not ok:
        log("! 모든 소스 수집에 실패했습니다. 기존 파일은 그대로 두었습니다.")
        return 1
    log("완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
