#!/usr/bin/env python3
"""Refresh CatchMICE listings using the authorized public APIs."""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
G2B = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService02/getBidPblancListInfoServc02"
WORK24 = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210L01.do"
VOLUNTEER = "https://apis.data.go.kr/1741000/volunteerPartcptnService/getVltrSearchWordList"
EVENT = re.compile(r"전시|박람회|엑스포|EXPO|컨벤션|콘퍼런스|컨퍼런스|국제회의|페스티벌|축제|MICE|학술대회|포럼", re.I)
ROLE = re.compile(r"운영\s*(요원|인력|스태프|스텝|보조)|스태프|스텝|단기|아르바이트|서포터즈|통역|자원봉사|도슨트")
REGIONS = (
    ("서울", "서울"), ("경기도", "경기"), ("경기", "경기"), ("부산", "부산"),
    ("대구", "대구"), ("인천", "인천"), ("광주광역", "광주"), ("광주", "광주"),
    ("대전", "대전"), ("울산", "울산"), ("세종", "세종"), ("강원", "강원"),
    ("충청북", "충북"), ("충북", "충북"), ("충청남", "충남"), ("충남", "충남"),
    ("전라북", "전북"), ("전북", "전북"), ("전라남", "전남"), ("전남", "전남"),
    ("경상북", "경북"), ("경북", "경북"), ("경상남", "경남"), ("경남", "경남"),
    ("제주", "제주"), ("전국", "전국"),
)

def read_api(endpoint, params):
    # Deliberately avoid logging exceptions that may contain an authenticated URL.
    try:
        request = Request(endpoint + "?" + urlencode(params), headers={"User-Agent": "CatchMICE/1.0"})
        with urlopen(request, timeout=30) as response:
            return response.read()
    except Exception:
        raise RuntimeError("Source request failed. Check API approval, quota and availability.") from None

def iso_date(value):
    value = str(value or "").strip()
    candidate = re.match(r"^(\d{4})[-./]?(\d{2})[-./]?(\d{2})(?!\d)", value)
    if candidate:
        try:
            return date(*map(int, candidate.groups())).isoformat()
        except ValueError:
            pass
    return ""

def public_url(value, hosts):
    try:
        url = urlsplit(value or "")
        if url.scheme in {"http", "https"} and url.hostname in hosts and not url.username and not url.password:
            return url.geturl()
    except ValueError:
        pass
    return ""

def region(value):
    return next((name for prefix, name in REGIONS if (value or "").strip().startswith(prefix)), "기타")

def bid_category(title):
    if re.search(r"부스|홍보관|공동관|한국관|전시관", title) and re.search(r"시공|조성|설치|구축|운영|제작", title):
        return "부스·시설"
    if re.search(r"국제회의|학술대회|컨벤션|콘퍼런스|컨퍼런스|국제\s*(세미나|포럼)|정상회의|정상외교|포럼\s*개최", title):
        return "국제회의"
    if re.search(r"축제|페스티벌", title):
        return "축제"
    if re.search(r"박람회|엑스포|EXPO|전시|테크페어", title, re.I):
        return "전시·박람회"
    if re.search(r"행사\s*(기획|대행|운영|개최)|행사.{0,18}(운영|대행)|행사\s*용역", title):
        return "행사대행"
    return ""

def bid_number(row):
    number = str(row.get("bidNtceNo") or "").strip()
    order = str(row.get("bidNtceOrd") or "0").strip()
    return number + "-" + order.zfill(3) if number else ""

def normalize_bid(row):
    title = str(row.get("bidNtceNm") or "").strip()
    category = bid_category(title)
    number = bid_number(row)
    deadline = iso_date(row.get("bidClseDt"))
    if not (category and number and deadline):
        return None
    amount = str(row.get("asignBdgtAmt") or "").replace(",", "")
    return dict(title=title, org=row.get("dminsttNm") or row.get("ntceInsttNm") or "",
                type=category, region=region(row.get("dminsttAdrs")),
                budget=f"배정예산 {int(amount):,}원" if amount.isdecimal() and int(amount)>0 else "",
                posted=iso_date(row.get("bidNtceDt")), deadline=deadline,
                method=row.get("cntrctCnclsMthdNm") or "", no=number,
                url=public_url(row.get("bidNtceDtlUrl") or row.get("bidNtceUrl"),
                               {"www.g2b.go.kr","g2b.go.kr"}),
                src="나라장터", source_id=number.rsplit("-", 1)[0])

def bid_pages(key, today):
    # Use a seven-day window on every run to cover missed schedules and revisions.
    params = dict(serviceKey=unquote(key), type="json", inqryDiv="1",
                  inqryBgnDt=(today-timedelta(days=6)).strftime("%Y%m%d0000"),
                  inqryEndDt=today.strftime("%Y%m%d2359"), numOfRows=100)
    for page in range(1, 151):
        response = json.loads(read_api(G2B, dict(params,pageNo=page)))["response"]
        if str(response["header"]["resultCode"]) not in {"00", "0"}:
            raise RuntimeError("KONEPS returned an error.")
        body = response["body"]
        total = int(body["totalCount"])
        items = body.get("items") or []
        if isinstance(items, dict):
            items = items.get("item", [])
            if isinstance(items, dict):
                items = [items]
        if not isinstance(items,list) or (not items and total > (page-1)*100):
            raise RuntimeError("Incomplete KONEPS page.")
        yield from items
        if page*100 >= total:
            return
    raise RuntimeError("KONEPS pagination limit exceeded.")

def refresh_bids(previous, today):
    latest = {}
    for row in bid_pages(os.environ["G2B_SERVICE_KEY"], today):
        number = bid_number(row)
        if not number:
            continue
        identity, order = number.rsplit("-",1)
        if identity not in latest or order >= latest[identity][0]:
            latest[identity] = (order,row)
    existing = {bid_identity(item):item for item in previous}
    for identity, (order, row) in latest.items():
        old = existing.get(identity)
        old_order = str((old or {}).get("no") or "").rpartition("-")[2]
        if old_order.isdecimal() and old_order.zfill(3) > order:
            continue
        if "취소" in str(row.get("ntceKindNm") or "") or str(row.get("bidNtceNm") or "").startswith(("취소공고", "[취소]")):
            existing.pop(identity,None)
            continue
        new = normalize_bid(row)
        if new:
            if old and old.get("first_seen"):
                new["first_seen"] = old["first_seen"]
            existing[identity] = new
    return list(existing.values())

def bid_identity(item):
    return item.get("source_id") or re.sub(r"-\d{2,3}$","",item.get("no") or "") or item["url"]

def xml_page(endpoint, params, root_tag, total_path, items_path):
    root = ElementTree.fromstring(read_api(endpoint, params))
    if root.tag != root_tag:
        raise RuntimeError("Unexpected XML response from the source.")
    if root_tag=="response" and root.findtext("header/resultCode") not in {"00","0"}:
        raise RuntimeError("Volunteer API returned an error.")
    total = int(root.findtext(total_path))
    return total, root.findall(items_path)

def work24_listings(key):
    listings = {}
    for keyword in ("행사 운영요원","전시 스태프","박람회","전시회","서포터즈","행사 통역"):
        for employment in ("1","2"):
            for page in range(1, 11):
                params = dict(authKey=key,callTp="L",returnType="XML",startPage=page,
                              display=50,keyword=keyword,empTpGb=employment)
                total, rows = xml_page(WORK24, params, "wantedRoot", "total", "wanted")
                if not rows and total>(page-1)*50:
                    raise RuntimeError("Incomplete Work24 page.")
                for row in rows:
                    def value(name):
                        return (row.findtext(name) or "").strip()
                    title = value("title")
                    identity = value("wantedAuthNo")
                    url = public_url(value("wantedInfoUrl"),{"www.work24.go.kr","work24.go.kr","www.work.go.kr","m.work24.go.kr"})
                    deadline = iso_date(value("closeDt"))
                    if not (identity and url and deadline and ROLE.search(title)
                            and (EVENT.search(title) or "행사" in title)):
                        continue
                    kind = ("서포터즈·기자단" if "서포터즈" in title else
                            "통역·자원봉사" if "통역" in title else "스태프·운영요원")
                    listings[identity] = dict(title=title, org=value("company"), kind=kind,
                        region=region(value("region")), deadline=deadline, pay=value("sal"),
                        posted=iso_date(value("regDt")), url=url, src="고용24", source_id=identity)
                if page*50>=total:
                    break
            else:
                raise RuntimeError("Work24 pagination limit exceeded.")
    return list(listings.values())

def volunteer_listings(key, today):
    listings = {}
    for keyword in ("전시","박람회","축제","국제회의","서포터즈"):
        for page in range(1, 11):
            params=dict(serviceKey=unquote(key),pageNo=page,numOfRows=50,keyword=keyword,
                        schCateGu="all",progrmBgnde=today.strftime("%Y%m%d"),
                        progrmEndde=(today+timedelta(days=60)).strftime("%Y%m%d"))
            total, rows = xml_page(VOLUNTEER, params, "response", "body/totalCount", "body/items/item")
            if not rows and total>(page-1)*50:
                raise RuntimeError("Incomplete volunteer API page.")
            for row in rows:
                def value(name):
                    return (row.findtext(name) or "").strip()
                title=value("progrmSj")
                identity=value("progrmRegistNo")
                deadline=iso_date(value("noticeEndde"))
                end=iso_date(value("progrmEndde"))
                if not (identity.isdecimal() and EVENT.search(title)
                        and value("progrmSttusSe") in {"2","모집중","모집 중"}
                        and (deadline or end)):
                    continue
                url=public_url(value("url"),{"www.1365.go.kr","1365.go.kr"})
                if not url:
                    url="https://www.1365.go.kr/vols/P9210/partcptn/timeCptn.do?type=show&progrmRegistNo="+identity
                period=" ~ ".join(filter(None,(iso_date(value("progrmBgnde")),end)))
                listings[identity]=dict(title=title,org=value("nanmmbyNm"),region=region(value("actPlace")),
                    kind="서포터즈·기자단" if "서포터즈" in title else "통역·자원봉사",
                    period=period,deadline=deadline,active_until=end,url=url,
                    src="1365 자원봉사포털",source_id=identity)
            if page*50>=total:
                break
        else:
            raise RuntimeError("Volunteer API pagination limit exceeded.")
    return list(listings.values())

def refresh_staff(previous,today):
    results=previous
    successes=0
    sources=(
        ("WORK24_AUTH_KEY","고용24",work24_listings),
        ("VOLUNTEER_SERVICE_KEY","1365 자원봉사포털",lambda key: volunteer_listings(key,today)),
    )
    for secret, source, load in sources:
        if not os.environ.get(secret):
            continue
        try:
            fresh=load(os.environ[secret])
        except Exception:
            print(f"{source}: refresh failed; previous listings kept.",file=sys.stderr)
            continue
        old={item["source_id"]:item for item in results if item.get("src")==source and item.get("source_id")}
        for item in fresh:
            item["first_seen"]=old.get(item["source_id"],{}).get("first_seen") or today.isoformat()
        results=[item for item in results if item.get("src")!=source]+fresh
        successes+=1
    if not successes:
        raise RuntimeError("No staff source was refreshed.")
    return results

def keep_recent(items,today,snapshot):
    oldest=(today-timedelta(days=30)).isoformat()
    for item in items:
        if not item.get("first_seen") and not item.get("posted"):
            item["first_seen"]=snapshot or today.isoformat()
        deadline=iso_date(item.get("deadline"))
        active_until=iso_date(item.get("active_until"))
        if not deadline and not active_until:
            first=iso_date(item.get("first_seen")) or iso_date(item.get("posted")) or snapshot or today.isoformat()
            active_until=(date.fromisoformat(first)+timedelta(days=14)).isoformat()
            item["active_until"]=active_until
        if (deadline or active_until)>=oldest:
            yield item

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("feed",choices=("bids","staff"))
    feed=parser.parse_args().feed
    today=datetime.now(ZoneInfo("Asia/Seoul")).date()
    path=ROOT/f"{feed}.json"
    previous=json.loads(path.read_text(encoding="utf-8"))
    try:
        rows=(refresh_bids if feed=="bids" else refresh_staff)(previous["items"],today)
        rows=list(keep_recent(rows,today,iso_date(previous.get("updated"))))
        rows.sort(key=lambda item:(iso_date(item.get("deadline")) or "9999-12-31",item["title"]))
        payload={"updated":today.isoformat(),"items":rows}
        temp=path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        temp.replace(path)
    except Exception:
        print(f"{feed}: refresh failed; committed data was not replaced. Check configured API keys and their permissions.",file=sys.stderr)
        return 1
    print(f"{feed}: refreshed {len(rows)} listings")
    return 0

if __name__=="__main__":
    sys.exit(main())
