"""
비상장 거래 플랫폼에서 종목 데이터를 수집하는 스크립트
- K-OTC (한국금융투자협회)
- 서울거래소 비상장 (구 서울거래 비상장)
- 네이버페이 비상장
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
from bs4 import BeautifulSoup
import json
import time
import os
from urllib.parse import quote
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_kotc():
    """K-OTC 순위 데이터 수집 (거래대금/거래량/상승률/시가총액 상위).
    공식 API: POST https://www.k-otc.or.kr/public/api (MainService.getMainTradeRank)
    """
    print("K-OTC 데이터 수집중...")
    stocks = []
    api = "https://www.k-otc.or.kr/public/api"
    headers = {**HEADERS, "Content-Type": "application/json",
               "Referer": "https://www.k-otc.or.kr/public/main"}
    # idx: 1=거래대금상위, 2=거래량상위, 3=상승률상위, 4=시가총액상위
    idx_label = {"1": "거래대금", "2": "거래량", "3": "상승률", "4": "시가총액"}
    seen = {}
    for idx, label in idx_label.items():
        try:
            body = {"class": "MainService", "method": "getMainTradeRank",
                    "param": {"idx": idx}}
            resp = requests.post(api, headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            contents = resp.json().get("contents", [])
            for it in contents:
                code = it.get("SHORTCD", "")
                name = it.get("KOREANSHTNM", "")
                if not name:
                    continue
                price = it.get("LASTCOT")
                diff = it.get("BEFOREDAYCMP")
                sign = it.get("INDECREASE", "")  # 등락 방향
                change = ""
                if diff is not None:
                    arrow = "-" if sign in ("2", "5", "-") and idx != "4" else ""
                    # INDECREASE: 보통 1/2 상승, 4/5 하락. 부호 불명확시 그대로 표기
                    change = f"{diff}"
                vol = it.get("TRADEACMQTY")
                rec = seen.get(code) or {
                    "name": name, "code": code,
                    "price": str(price) if price is not None else "",
                    "change": str(diff) if diff is not None else "",
                    "volume": str(vol) if vol is not None else "",
                    "amount": str(it.get("TRADEACMAMT", "")),
                    "platform": "K-OTC",
                    "url": "https://www.k-otc.or.kr/public/item/presentPrice",
                    "ranks": [],
                }
                rec["ranks"].append(label)
                # 가격/거래량이 비어있던 경우 채움
                if not rec["price"] and price is not None:
                    rec["price"] = str(price)
                if not rec["volume"] and vol is not None:
                    rec["volume"] = str(vol)
                seen[code] = rec
        except Exception as e:
            print(f"  [오류] K-OTC {label}: {e}")
        time.sleep(0.3)

    stocks = list(seen.values())
    print(f"  K-OTC: {len(stocks)}종목 (거래대금/거래량/상승률/시가총액 상위 통합)")
    return stocks


def fetch_seoulexchange():
    """서울거래소 비상장 종목 데이터 수집.
    홈페이지 HTML에 박힌 STOCK_TAB_DATA(JSON) 활용
    (탭: popular/volume/rising/marketcap).
    """
    print("\n서울거래소 비상장 데이터 수집중...")
    import re
    stocks = []
    tab_label = {"volume": "거래량", "rising": "상승", "popular": "인기", "marketcap": "시총"}
    try:
        resp = requests.get("https://www.seoulexchange.kr/", headers=HEADERS, timeout=15)
        resp.raise_for_status()
        m = re.search(r'STOCK_TAB_DATA\s*=\s*(\{.*?\})\s*;', resp.text, re.DOTALL)
        if not m:
            print("  [경고] 서울거래소: STOCK_TAB_DATA를 찾지 못함")
            return stocks

        data = json.loads(m.group(1))
        seen = {}
        for tab, label in tab_label.items():
            for it in data.get(tab, []):
                name = it.get("display_name", "")
                if not name:
                    continue
                code = it.get("short_isin", "")
                price = it.get("current_price")
                adp = it.get("advance_decline_price")
                adpct = it.get("advance_decline_percentage")
                key = it.get("annotated_display_key", "")
                rec = seen.get(name) or {
                    "name": name,
                    "code": code,
                    "price": str(price) if price is not None else "",
                    "change": (f"{adp} ({adpct}%)" if adp is not None else ""),
                    "change_pct": str(adpct) if adpct is not None else "",
                    "visit": it.get("visit_count", 0),
                    "category": it.get("business_category", ""),
                    "platform": "서울거래소",
                    "url": (f"https://www.seoulexchange.kr/stocks/{quote(key)}/" if key else "https://www.seoulexchange.kr/"),
                    "ranks": [],
                }
                rec["ranks"].append(label)
                seen[name] = rec
        stocks = list(seen.values())
        print(f"  서울거래소: {len(stocks)}종목 (인기/거래량/상승/시총 통합)")

    except Exception as e:
        print(f"  [오류] 서울거래소: {e}")

    return stocks


# 증권플러스(네이버) 비상장 랭킹 카테고리 -> 라벨
NAVER_CAT_LABEL = {
    "GENERAL_HIGH_VOLUME_STOCKS": "거래량",
    "POPULAR_STOCKS": "인기",
    "HIGH_CHANGE_RATE_STOCKS": "상승률",
    "READY_TO_IPO": "상장준비",
    "HIGH_ESTIMATED_MARKET_CAP": "시총",
    "SALES_REVENUE_INCREASE": "매출상승",
}


def fetch_naver_volume(code):
    """네이버 비상장 개별 종목 페이지의 최근 거래량(주) 추출.
    https://ustock.naver.com/stock/{code} 의 dailyPriceHistories[0].quantity.
    """
    import re
    if not code:
        return None
    try:
        url = f"https://ustock.naver.com/stock/{code}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
        if not m:
            return None
        d = json.loads(m.group(1))
        for q in d["props"]["pageProps"]["dehydratedState"]["queries"]:
            if q.get("queryKey", [None])[0] == "dailyPriceHistories":
                rows = (q.get("state", {}).get("data") or {}).get("dailyPriceHistories") or []
                if rows:
                    return rows[0].get("quantity")
        return None
    except Exception as e:
        print(f"    [경고] 거래량 보강 실패({code}): {e}")
        return None


def fetch_naver_unlisted():
    """네이버 비상장(증권플러스) 랭킹 데이터 수집.
    https://ustock.naver.com/stock/rank 의 __NEXT_DATA__(React Query)에서 추출.
    카테고리: 거래량/인기/상승률/상장준비/예상시총/매출상승
    """
    import re
    print("\n네이버 비상장(증권플러스) 데이터 수집중...")
    seen = {}
    ready_to_ipo = []
    revenue_up = []

    try:
        url = "https://ustock.naver.com/stock/rank"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
        if not m:
            print("  [경고] 네이버 비상장: __NEXT_DATA__ 없음")
            return []
        d = json.loads(m.group(1))
        categories = d["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]

        for cat in categories:
            label = NAVER_CAT_LABEL.get(cat.get("type"), cat.get("name", ""))
            for r in cat.get("rows", []):
                name = r.get("stockName", "")
                if not name:
                    continue
                code = r.get("stockCode", "")
                price = r.get("currentPrice")
                rate = r.get("changeRate")
                rec = seen.get(code) or {
                    "name": name,
                    "code": code,
                    "price": str(price) if price is not None else "",
                    "change_pct": str(rate) if rate is not None else "",
                    "board_count": r.get("boardCount", 0),
                    "ipo_badge": r.get("displayIpoBadge", False),
                    "platform": "네이버비상장",
                    "url": f"https://ustock.naver.com/stock/{code}" if code else "https://ustock.naver.com/stock/rank",
                    "ranks": [],
                }
                if label not in rec["ranks"]:
                    rec["ranks"].append(label)
                if not rec["price"] and price is not None:
                    rec["price"] = str(price)
                if not rec["change_pct"] and rate is not None:
                    rec["change_pct"] = str(rate)
                seen[code] = rec

                # 특수 카테고리 별도 보관
                stock_url = f"https://ustock.naver.com/stock/{code}" if code else "https://ustock.naver.com/stock/rank"
                if cat.get("type") == "READY_TO_IPO":
                    ready_to_ipo.append({
                        "name": name, "code": code,
                        "ipo_state": r.get("ipoState", ""),
                        "base_date": (r.get("baseDate") or "")[:10],
                        "rank": r.get("rank"),
                        "url": stock_url,
                    })
                elif cat.get("type") == "SALES_REVENUE_INCREASE":
                    revenue_up.append({
                        "name": name, "code": code,
                        "revenue_rate": r.get("revenueRaiseRate"),
                        "rank": r.get("rank"),
                        "url": stock_url,
                    })

        stocks = list(seen.values())

        # 거래량 랭킹에 든 종목은 개별 종목 페이지에서 최근 거래량(주) 보강
        vol_targets = [s for s in stocks if "거래량" in s.get("ranks", [])]
        print(f"  네이버 거래량 보강중... ({len(vol_targets)}종목)")
        for s in vol_targets:
            v = fetch_naver_volume(s.get("code", ""))
            if v is not None:
                s["volume"] = str(v)
            time.sleep(0.2)

        # 부가 정보를 함수 속성으로 전달
        fetch_naver_unlisted.ready_to_ipo = ready_to_ipo
        fetch_naver_unlisted.revenue_up = sorted(
            revenue_up, key=lambda x: (x.get("revenue_rate") or 0), reverse=True)
        print(f"  네이버 비상장: {len(stocks)}종목 "
              f"(상장준비 {len(ready_to_ipo)}, 매출상승 {len(revenue_up)})")
        return stocks

    except Exception as e:
        print(f"  [오류] 네이버 비상장: {e}")
        fetch_naver_unlisted.ready_to_ipo = []
        fetch_naver_unlisted.revenue_up = []
        return []


def identify_volume_spikes(stocks):
    """거래량 급증(상위) 종목 식별.
    각 플랫폼의 '거래량' 상위 랭킹에 든 종목을 모으고,
    숫자 거래량이 있으면 그 값으로 정렬한다.
    """
    spikes = []
    for s in stocks:
        ranks = s.get("ranks", [])
        if "거래량" not in ranks:
            continue
        vol_str = str(s.get("volume", "")).replace(",", "").replace(" ", "")
        try:
            vol = int(vol_str) if vol_str else 0
        except ValueError:
            vol = 0
        spikes.append({**s, "volume_int": vol})

    spikes.sort(key=lambda x: x["volume_int"], reverse=True)
    return spikes


def main():
    print("=" * 60)
    print("비상장 거래 플랫폼 데이터 수집")
    print(f"수집 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    kotc_stocks = fetch_kotc()
    seoul_stocks = fetch_seoulexchange()
    naver_stocks = fetch_naver_unlisted()

    all_stocks = kotc_stocks + seoul_stocks + naver_stocks
    volume_spikes = identify_volume_spikes(all_stocks)

    ready_to_ipo = getattr(fetch_naver_unlisted, "ready_to_ipo", [])
    revenue_up = getattr(fetch_naver_unlisted, "revenue_up", [])

    print(f"\n{'='*60}")
    print(f"수집 결과 요약")
    print(f"  K-OTC: {len(kotc_stocks)}종목")
    print(f"  서울거래소: {len(seoul_stocks)}종목")
    print(f"  네이버 비상장: {len(naver_stocks)}종목")
    print(f"  거래량 급증: {len(volume_spikes)}종목")
    print(f"  상장준비 기업: {len(ready_to_ipo)}개")
    print(f"  매출 급증 기업: {len(revenue_up)}개")

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "kotc": kotc_stocks,
        "seoul_exchange": seoul_stocks,
        "naver_unlisted": naver_stocks,
        "all_stocks": all_stocks,
        "volume_spikes": volume_spikes[:30],
        "ready_to_ipo": ready_to_ipo,
        "revenue_up": revenue_up,
        "summary": {
            "kotc_count": len(kotc_stocks),
            "seoul_count": len(seoul_stocks),
            "naver_count": len(naver_stocks),
            "total": len(all_stocks),
            "volume_spike_count": len(volume_spikes),
            "ready_to_ipo_count": len(ready_to_ipo),
            "revenue_up_count": len(revenue_up),
        }
    }

    output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(output_dir, "platform_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
