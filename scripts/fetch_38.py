# -*- coding: utf-8 -*-
"""38커뮤니케이션(www.38.co.kr) 비상장 데이터 수집.

38은 비상장 시세 정보가 가장 활발한 커뮤니티 사이트이나, 거래량은 노출되지 않는다.
대신 다음 두 가지를 정형화해 가져온다:
  1) 등락률 급등 종목 (시세표의 현재가/등락률)
  2) 주주동호회 활성도 (최근 게시글 수 = 종목별 커뮤니티 관심도)

주의: 38은 구형 SSL이라 SECLEVEL=1로 낮춰야 접속되며 인코딩은 euc-kr.
"""
import re
import ssl
import json
import os
from collections import Counter
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
import urllib3

urllib3.disable_warnings()

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.38.co.kr"


class _LegacySSLAdapter(HTTPAdapter):
    """38의 구형 TLS를 위해 보안 레벨을 낮춘 어댑터."""

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def _session():
    s = requests.Session()
    s.mount("https://", _LegacySSLAdapter())
    return s


def _get(s, url):
    r = s.get(url, headers=UA, timeout=15, verify=False)
    r.encoding = "euc-kr"
    return r.text


def _cells(tr):
    cs = [re.sub(r"<[^>]+>", "", x).replace("&nbsp;", "").strip()
          for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.DOTALL)]
    return [c for c in cs if c]


def _stock_url(code):
    return f"http://forum.38.co.kr/html/forum/board/?code={code}"


def fetch_gainers(s):
    """등락률 급등 종목. 38 비상장 시세표에서 현재가/등락률 파싱 후 상승률순 정렬."""
    print("38 등락률 급등 종목 수집중...")
    quotes = {}
    # 여러 시세 뷰를 합쳐 더 많은 종목 확보
    for o in ["", "?o=updown", "?o=time", "?o=38", "?o=ipo"]:
        try:
            html = _get(s, f"{BASE}/html/trade/price/price.php{o}")
        except Exception as e:
            print(f"  [경고] price.php{o}: {e}")
            continue
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL):
            m = re.search(r"code=([0-9A-Za-z]{6})", tr)
            if not m:
                continue
            code = m.group(1)
            if code in quotes:
                continue
            cs = _cells(tr)
            rate_cell = next((c for c in cs if "%" in c), None)
            name = next((c for c in cs if re.search(r"[가-힣]", c)
                         and "%" not in c and len(c) < 25), None)
            price = next((c for c in cs if re.match(r"^\d{1,3}(,\d{3})+$", c)), None)
            if not (rate_cell and name):
                continue
            rm = re.search(r"-?[0-9.]+", rate_cell)
            if not rm:
                continue
            quotes[code] = {
                "name": name,
                "code": code,
                "price": price or "",
                "change_pct": float(rm.group()),
                "platform": "38커뮤니케이션",
                "url": _stock_url(code),
            }
    gainers = sorted([q for q in quotes.values() if q["change_pct"] > 0],
                     key=lambda x: x["change_pct"], reverse=True)
    print(f"  38 급등 종목: {len(gainers)}종목 (전체 시세 {len(quotes)}종목 중)")
    return gainers


def fetch_community_activity(s):
    """주주동호회 활성도(인기 순위). 38이 직접 산출하는 비상장 동호회 실시간
    인기 랭킹(nostock_rank.js)을 가져온다. 배열 순서가 곧 인기 순위다.

    각 항목 형식: "종목명|종목코드|...|구분플래그"
    """
    print("38 주주동호회 인기 순위 수집중...")
    try:
        js = _get(s, f"{BASE}/html/forum/forum_list/nostock_rank.js")
    except Exception as e:
        print(f"  [오류] 동호회 인기 랭킹: {e}")
        return []

    active = []
    for i, raw in enumerate(re.findall(r'ranklist\[\d+\]\s*=\s*"([^"]*)";', js)):
        parts = raw.split("|")
        if len(parts) < 2 or not parts[0] or not parts[1]:
            continue
        name, code = parts[0], parts[1]
        active.append({
            "rank": i + 1,                 # 실시간 인기 순위 (1=최상위)
            "name": name,
            "code": code,
            "platform": "38커뮤니케이션",
            "url": _stock_url(code),
        })
    print(f"  38 동호회 인기 종목: {len(active)}종목")
    return active


def main():
    print("=" * 60)
    print("38커뮤니케이션 비상장 데이터 수집")
    print(f"수집 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    s = _session()
    gainers = fetch_gainers(s)
    active = fetch_community_activity(s)

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "gainers": gainers,
        "community_activity": active,
        "summary": {
            "gainer_count": len(gainers),
            "active_count": len(active),
        },
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "thirtyeight_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
