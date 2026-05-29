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
                rec = seen.get(name) or {
                    "name": name,
                    "code": code,
                    "price": str(price) if price is not None else "",
                    "change": (f"{adp} ({adpct}%)" if adp is not None else ""),
                    "change_pct": str(adpct) if adpct is not None else "",
                    "visit": it.get("visit_count", 0),
                    "category": it.get("business_category", ""),
                    "platform": "서울거래소",
                    "ranks": [],
                }
                rec["ranks"].append(label)
                seen[name] = rec
        stocks = list(seen.values())
        print(f"  서울거래소: {len(stocks)}종목 (인기/거래량/상승/시총 통합)")

    except Exception as e:
        print(f"  [오류] 서울거래소: {e}")

    return stocks


def fetch_naver_unlisted():
    """네이버페이 비상장 종목 데이터 수집"""
    print("\n네이버페이 비상장 데이터 수집중...")
    stocks = []

    try:
        # 네이버페이 비상장 메인 페이지
        url = "https://m.stock.naver.com/domestic/private/rising"
        resp = requests.get(url, headers=HEADERS, timeout=15)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            # JSON 데이터가 script 태그에 포함되어 있을 수 있음
            scripts = soup.select("script")
            for script in scripts:
                text = script.string or ""
                if "stockName" in text or "itemCode" in text:
                    try:
                        import re
                        json_match = re.search(r'\[{.*?}\]', text, re.DOTALL)
                        if json_match:
                            data = json.loads(json_match.group())
                            for item in data:
                                if isinstance(item, dict):
                                    stocks.append({
                                        "name": item.get("stockName", item.get("name", "")),
                                        "code": item.get("itemCode", item.get("code", "")),
                                        "price": str(item.get("closePrice", item.get("price", ""))),
                                        "change": str(item.get("compareToPreviousClosePrice", "")),
                                        "volume": str(item.get("accumulatedTradingVolume", "")),
                                        "platform": "네이버페이",
                                    })
                    except (json.JSONDecodeError, Exception):
                        continue

        # API 시도
        if not stocks:
            api_url = "https://m.stock.naver.com/api/stock/private/rising"
            resp2 = requests.get(api_url, headers={
                **HEADERS,
                "Accept": "application/json",
            }, timeout=15)
            if resp2.status_code == 200:
                try:
                    data = resp2.json()
                    items = data if isinstance(data, list) else data.get("stocks", data.get("result", []))
                    for item in items:
                        if isinstance(item, dict):
                            stocks.append({
                                "name": item.get("stockName", item.get("name", "")),
                                "code": item.get("itemCode", item.get("code", "")),
                                "price": str(item.get("closePrice", "")),
                                "change": str(item.get("compareToPreviousClosePrice", "")),
                                "volume": str(item.get("accumulatedTradingVolume", "")),
                                "changeRate": str(item.get("fluctuationsRatio", "")),
                                "platform": "네이버페이",
                            })
                except json.JSONDecodeError:
                    pass

        print(f"  네이버페이 비상장: {len(stocks)}종목")

    except Exception as e:
        print(f"  [오류] 네이버페이: {e}")

    return stocks


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

    print(f"\n{'='*60}")
    print(f"수집 결과 요약")
    print(f"  K-OTC: {len(kotc_stocks)}종목")
    print(f"  서울거래소: {len(seoul_stocks)}종목")
    print(f"  네이버페이: {len(naver_stocks)}종목")
    print(f"  거래량 급증: {len(volume_spikes)}종목")

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "kotc": kotc_stocks,
        "seoul_exchange": seoul_stocks,
        "naver_unlisted": naver_stocks,
        "all_stocks": all_stocks,
        "volume_spikes": volume_spikes[:30],
        "summary": {
            "kotc_count": len(kotc_stocks),
            "seoul_count": len(seoul_stocks),
            "naver_count": len(naver_stocks),
            "total": len(all_stocks),
            "volume_spike_count": len(volume_spikes),
        }
    }

    output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(output_dir, "platform_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
