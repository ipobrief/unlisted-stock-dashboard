"""
thevc.kr에서 스타트업 투자 데이터를 수집하는 스크립트
- 최근 투자/M&A 내역
- 시리즈C 이상 기업 리스트
- 조회수 랭킹
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
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

STAGE_FILTERS = ["Series C", "Series D", "Series E", "Series F", "Series G", "Pre-IPO", "IPO"]


def fetch_homepage_data():
    """thevc.kr 홈페이지에서 최근 투자/M&A, 조회수 랭킹 데이터 수집"""
    print("thevc.kr 홈페이지 데이터 수집중...")
    url = "https://thevc.kr/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        investments = []
        ranking = []

        # 투자/M&A 테이블
        inv_rows = soup.select("div.home-recent-investment tbody tr, div.investment-table tbody tr")
        if not inv_rows:
            inv_rows = soup.select("table tbody tr")

        for row in inv_rows:
            cols = row.select("td")
            if len(cols) >= 5:
                date_el = cols[0]
                company_el = cols[1].select_one("a")
                stage_el = cols[3] if len(cols) > 3 else None
                amount_el = cols[4] if len(cols) > 4 else None
                investor_el = cols[5] if len(cols) > 5 else None

                investments.append({
                    "date": date_el.get_text(strip=True) if date_el else "",
                    "company": company_el.get_text(strip=True) if company_el else cols[1].get_text(strip=True),
                    "link": "https://thevc.kr" + company_el["href"] if company_el and company_el.get("href") else "",
                    "stage": stage_el.get_text(strip=True) if stage_el else "",
                    "amount": amount_el.get_text(strip=True) if amount_el else "",
                    "investor": investor_el.get_text(strip=True) if investor_el else "",
                })

        # 조회수 랭킹 (Vue 렌더라 API 직접 호출). 기간: DATE/WEEK/MONTH
        try:
            api = "https://thevc.kr/api/interaction/hits/organizations/rankings/ALL"
            rr = requests.get(api, headers={**HEADERS, "Referer": "https://thevc.kr/",
                                            "Accept": "application/json"}, timeout=15)
            rr.raise_for_status()
            data = rr.json()
            # 주간(WEEK) 조회수 랭킹 사용 (없으면 DATE)
            rows = data.get("WEEK") or data.get("DATE") or []
            for it in rows:
                name = it.get("name", "")
                slug = it.get("profilePage", "")
                if not name:
                    continue
                ranking.append({
                    "name": name,
                    "hits": it.get("count", 0),
                    "type": it.get("type", ""),
                    "link": f"https://thevc.kr/{slug}" if slug else "",
                })
        except Exception as e:
            print(f"  [경고] 조회수 랭킹 API: {e}")

        print(f"  투자 내역: {len(investments)}건, 랭킹: {len(ranking)}개")
        return investments, ranking

    except Exception as e:
        print(f"  [오류] 홈페이지 수집 실패: {e}")
        return [], []


def clean_company_name(raw_name):
    """'플렛지한국계 · 비상장' -> '플렛지'"""
    import re
    name = re.split(r'한국계|외국계|·|비상장|상장', raw_name)[0].strip()
    return name if name else raw_name.strip()


def fetch_recent_investments(pages=3):
    """최근 투자/M&A 데이터 수집 (투자/M&A 탭)"""
    print("\n최근 투자/M&A 데이터 수집중...")
    all_items = []

    for page in range(1, pages + 1):
        url = f"https://thevc.kr/browse/investments?page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            rows = soup.select("table tbody tr")
            for row in rows:
                cols = row.select("td")
                if len(cols) < 16:
                    continue

                texts = [c.get_text(strip=True) for c in cols]

                # td[1]: 날짜+보도자료, td[3]: 단계, td[4]: 금액
                # td[6]: 기업명, td[8]: 분류, td[12]: 분야, td[15]: 투자자
                import re
                date_raw = texts[1]
                date_match = re.match(r'(\d{4}-\d{2}-\d{2})', date_raw)
                date = date_match.group(1) if date_match else ""
                press_a = cols[1].select_one("a")
                press_link = press_a.get("href", "") if press_a else ""

                company_a = cols[6].select_one("a")
                company_raw = company_a.get_text(strip=True) if company_a else texts[6]
                company_name = clean_company_name(company_raw)
                href = company_a.get("href", "") if company_a else ""
                company_link = "https://thevc.kr" + href if href.startswith("/") else href

                investor_a = cols[15].select_one("a")
                investor = investor_a.get_text(strip=True) if investor_a else texts[15]

                all_items.append({
                    "date": date,
                    "company": company_name,
                    "link": company_link,
                    "press_link": press_link,
                    "sector": texts[12] if len(texts) > 12 else "",
                    "stage": texts[3] if len(texts) > 3 else "",
                    "amount": texts[4] if len(texts) > 4 else "",
                    "investor": clean_company_name(investor),
                })

            print(f"  페이지 {page}: {len(rows)}건")
        except Exception as e:
            print(f"  [오류] 페이지 {page}: {e}")
        time.sleep(1)

    return all_items


def fetch_startups_by_stage(stages=None, pages=3):
    """특정 투자 단계의 스타트업 리스트 수집"""
    if stages is None:
        stages = STAGE_FILTERS

    print(f"\n스타트업 탐색 (필터: {', '.join(stages)})...")
    all_startups = []

    stage_param = "&".join([f"latest_round[]={s.replace(' ', '+')}" for s in stages])

    for page in range(1, pages + 1):
        url = f"https://thevc.kr/browse/startups?{stage_param}&page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            rows = soup.select("table tbody tr")
            for row in rows:
                cols = row.select("td")
                if len(cols) < 10:
                    continue

                texts = [c.get_text(strip=True) for c in cols]

                # td[1]: 기업명, td[2]: 회사상태, td[3]: 분류
                # td[4]: 설립일, td[5]: 고용인원, td[9]: 기술
                # td[14]: 총자본금, td[17]: 최근라운드, td[18]: 최근투자단계
                # td[20]: 투자자
                company_a = cols[1].select_one("a")
                company_raw = company_a.get_text(strip=True) if company_a else texts[1]
                company_name = clean_company_name(company_raw)
                href = company_a.get("href", "") if company_a else ""
                company_link = "https://thevc.kr" + href if href.startswith("/") else href

                stage = texts[18] if len(texts) > 18 else ""
                investors_text = texts[20] if len(texts) > 20 else ""

                # 투자자 수 파싱
                import re
                investor_count = len(re.findall(r'회', investors_text))

                all_startups.append({
                    "name": company_name,
                    "link": company_link,
                    "status": texts[2] if len(texts) > 2 else "",
                    "category": texts[3] if len(texts) > 3 else "",
                    "founded": texts[4][:10] if len(texts) > 4 else "",
                    "employees": texts[5][:10] if len(texts) > 5 else "",
                    "sector": texts[9] if len(texts) > 9 else "",
                    "latest_stage": stage,
                    "investors": investors_text[:80],
                    "investor_count": investor_count,
                })

            print(f"  페이지 {page}: {len(rows)}건")
        except Exception as e:
            print(f"  [오류] 페이지 {page}: {e}")
        time.sleep(1)

    return all_startups


def main():
    print("=" * 60)
    print("THE VC 데이터 수집")
    print(f"수집 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. 홈페이지 데이터
    home_investments, ranking = fetch_homepage_data()

    # 2. 최근 투자/M&A
    recent_investments = fetch_recent_investments(pages=3)

    # 3. 시리즈C 이상 스타트업
    series_c_plus = fetch_startups_by_stage(STAGE_FILTERS, pages=5)

    # 시리즈C 이상 중 주요 투자 단계별 분류
    stage_groups = {}
    for s in series_c_plus:
        stage = "기타"
        for sf in STAGE_FILTERS:
            if sf.lower() in s.get("raw_text", "").lower() or sf.lower() in " ".join(s.get("tags", [])).lower():
                stage = sf
                break
        if stage not in stage_groups:
            stage_groups[stage] = []
        stage_groups[stage].append(s)

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "home_investments": home_investments[:20],
        "ranking": ranking[:20],
        "recent_investments": recent_investments,
        "series_c_plus": series_c_plus,
        "stage_summary": {k: len(v) for k, v in stage_groups.items()},
        "total_series_c_plus": len(series_c_plus),
    }

    output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(output_dir, "thevc_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")
    print(f"시리즈C 이상 기업: {len(series_c_plus)}개")
    print(f"최근 투자 내역: {len(recent_investments)}건")


if __name__ == "__main__":
    main()
