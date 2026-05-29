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
    """K-OTC 종목 리스트 및 시세 수집"""
    print("K-OTC 데이터 수집중...")
    stocks = []

    try:
        # K-OTC 시세 페이지
        url = "https://www.k-otc.or.kr/JISQ020000/JISQ020000.do"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        rows = soup.select("table tbody tr")
        for row in rows:
            cols = row.select("td")
            if len(cols) < 5:
                continue
            texts = [c.get_text(strip=True) for c in cols]
            name_el = row.select_one("a")
            stocks.append({
                "name": name_el.get_text(strip=True) if name_el else texts[0],
                "code": texts[1] if len(texts) > 1 else "",
                "price": texts[2] if len(texts) > 2 else "",
                "change": texts[3] if len(texts) > 3 else "",
                "volume": texts[4] if len(texts) > 4 else "",
                "platform": "K-OTC",
            })
        print(f"  K-OTC: {len(stocks)}종목")

    except Exception as e:
        print(f"  [오류] K-OTC: {e}")

    # K-OTC BB (비상장 장외시장)
    try:
        url2 = "https://www.k-otc.or.kr/JISQ030000/JISQ030000.do"
        resp2 = requests.get(url2, headers=HEADERS, timeout=15)
        resp2.raise_for_status()
        soup2 = BeautifulSoup(resp2.text, "lxml")

        rows2 = soup2.select("table tbody tr")
        for row in rows2:
            cols = row.select("td")
            if len(cols) < 5:
                continue
            texts = [c.get_text(strip=True) for c in cols]
            name_el = row.select_one("a")
            stocks.append({
                "name": name_el.get_text(strip=True) if name_el else texts[0],
                "code": texts[1] if len(texts) > 1 else "",
                "price": texts[2] if len(texts) > 2 else "",
                "change": texts[3] if len(texts) > 3 else "",
                "volume": texts[4] if len(texts) > 4 else "",
                "platform": "K-OTC BB",
            })
        print(f"  K-OTC BB 추가: {len(rows2)}종목")

    except Exception as e:
        print(f"  [오류] K-OTC BB: {e}")

    return stocks


def fetch_seoulexchange():
    """서울거래소 비상장 종목 데이터 수집"""
    print("\n서울거래소 비상장 데이터 수집중...")
    stocks = []

    try:
        # 서울거래소 비상장 API
        url = "https://www.seoulexchange.kr/api/stock/list"
        resp = requests.get(url, headers={
            **HEADERS,
            "Accept": "application/json",
        }, timeout=15)

        if resp.status_code == 200:
            try:
                data = resp.json()
                items = data if isinstance(data, list) else data.get("data", data.get("list", []))
                for item in items:
                    if isinstance(item, dict):
                        stocks.append({
                            "name": item.get("name", item.get("stockName", item.get("companyName", ""))),
                            "code": item.get("code", item.get("stockCode", "")),
                            "price": str(item.get("price", item.get("currentPrice", ""))),
                            "change": str(item.get("change", item.get("changePrice", ""))),
                            "volume": str(item.get("volume", item.get("tradeVolume", ""))),
                            "platform": "서울거래소",
                        })
            except json.JSONDecodeError:
                pass

        if not stocks:
            # HTML 페이지에서 수집 시도
            url2 = "https://www.seoulexchange.kr/stocks"
            resp2 = requests.get(url2, headers=HEADERS, timeout=15)
            if resp2.status_code == 200:
                soup = BeautifulSoup(resp2.text, "lxml")
                rows = soup.select("table tbody tr, div.stock-item, li.stock-item")
                for row in rows:
                    cols = row.select("td, span, div.value")
                    if len(cols) >= 3:
                        texts = [c.get_text(strip=True) for c in cols]
                        name_el = row.select_one("a")
                        stocks.append({
                            "name": name_el.get_text(strip=True) if name_el else texts[0],
                            "price": texts[1] if len(texts) > 1 else "",
                            "change": texts[2] if len(texts) > 2 else "",
                            "volume": texts[3] if len(texts) > 3 else "",
                            "platform": "서울거래소",
                        })

        print(f"  서울거래소: {len(stocks)}종목")

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


def identify_volume_spikes(stocks, threshold=2.0):
    """거래량 급증 종목 식별 (평균 대비 threshold배 이상)"""
    volume_stocks = []
    for s in stocks:
        vol_str = s.get("volume", "").replace(",", "").replace(" ", "")
        try:
            vol = int(vol_str) if vol_str else 0
        except ValueError:
            vol = 0
        if vol > 0:
            volume_stocks.append({**s, "volume_int": vol})

    if not volume_stocks:
        return []

    avg_vol = sum(s["volume_int"] for s in volume_stocks) / len(volume_stocks)
    spikes = [s for s in volume_stocks if s["volume_int"] > avg_vol * threshold]
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
