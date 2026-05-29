"""
네이버 뉴스에서 비상장 종목 관련 키워드를 검색하여
기업명과 언급 빈도를 추출하는 스크립트
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
from bs4 import BeautifulSoup
import json
import re
import time
import os
from datetime import datetime, timedelta
from collections import Counter
from urllib.parse import quote

KEYWORDS = [
    "IPO 지정감사",
    "상장 주관사선정",
    "상장 주관사계약",
    "상장 주간사선정",
    "상장 주간사계약",
    "프리IPO",
    "pre ipo",
    "pre-ipo",
    "VC 투자유치",
    "벤처캐피탈 투자유치",
    "투자유치 시리즈",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://search.naver.com/",
}

EXCLUDE_WORDS = {
    "네이버", "카카오", "삼성", "현대", "SK", "LG", "한화", "롯데",
    "뉴스", "기자", "관련", "투자", "상장", "기업", "회사", "시장",
    "올해", "지난해", "최근", "이번", "이날", "오늘", "내년",
    "대표", "사장", "회장", "이사", "서울", "한국", "국내",
    "스타트업", "사업", "기업가치", "코스닥", "코스피", "부터", "억원",
    "의장", "주관사", "주간사", "유치", "매각", "행사", "프리",
    "기업들", "관계자", "규모", "대상", "가능성", "작업", "공모",
    "중심", "월에", "이상", "성장", "지원하", "프로그램", "인프라",
    "관계", "있다", "자금", "분야", "네트워크", "계획", "지분",
    "방향", "기업에", "기업들에게", "투자유치", "인베스트먼트",
    "조원", "만원", "수준", "시리즈", "지정감사", "벤처캐피탈",
    "주식시장", "원화", "달러", "이후", "이전", "지금", "정도",
    "진행", "예정", "목표", "가치", "자체", "전략", "글로벌",
    "확대", "준비", "결정", "필요", "만큼", "때문", "상태",
    "시작", "추진", "완료", "전망", "환경", "기술", "과정",
    "코스닥상장", "상장사", "비상장", "투자사", "벤처", "펀드",
    # 외국 기업 (비상장 한국 종목 발굴 대상 아님)
    "앤트로픽", "오픈AI", "오픈에이아이", "스페이스X", "스페이스엑스",
    "레플릿", "엔비디아", "테슬라", "구글", "메타", "마이크로소프트",
    "아마존", "애플", "바이트댄스", "틱톡", "보스턴다이내믹스",
    "안트로픽", "딥시크", "미스트랄", "xAI", "퍼플렉시티",
    # 증권사/금융사/회계법인 (주관사로 언급되지만 발굴 대상 아님)
    "삼성증권", "한국투자증권", "미래에셋증권", "신영증권", "NH투자증권",
    "KB증권", "키움증권", "대신증권", "하나증권", "신한투자증권",
    "한국투자금융그룹", "삼일회계법인", "삼정회계법인", "안진회계법인",
    "한영회계법인", "딜로이트", "삼정KPMG", "한국거래소", "금융감독원",
    "한국투자", "미래에셋", "메리츠증권", "유진투자증권", "DB금융투자",
    "KB금융", "신한은행", "하나은행", "우리은행", "산업은행",
    # 기타 일반어/문맥어
    "투자자들", "감사인", "차익", "계약서", "절차", "코스닥시장",
    "매각주관사", "경연", "이번투자", "기반", "매출", "주식", "업계",
    "상품", "기관", "손잡", "차원", "단계", "단계까지", "단계부터프리",
    "성장세", "계약", "입찰제안요청서", "지분율", "금융그룹", "나스닥",
    "증권사", "영역", "한국거래소에", "한국거래소", "회사가", "업체",
    "영업이익", "기술특례", "공모가", "청구", "예심", "심사", "승인",
    "추천", "선정", "주주", "대주주", "최대주주", "임직원", "경영진",
    "투자자", "대표주관사", "이번투자라운드", "라운드", "거래", "캐피털",
    "빠짐없", "회째", "최대", "목표로", "개선", "속도", "중복", "고객",
    "기술성평", "단계부터", "금융", "후보물질", "전략적 인프라 파트너",
    "기술성", "평가", "실적", "수익", "사업부", "부문", "법인", "지주",
    "IPO", "ipo", "시리즈A", "시리즈B", "시리즈C", "시리즈D",
    "시리즈E", "시리즈F", "시리즈G", "프리IPO", "프리", "기업공개",
    # 외국 암호화폐 거래소/해외 기업 추가
    "바이낸스", "코인베이스", "UBS", "크레디트스위스", "골드만삭스",
    "JP모건", "모건스탠리", "블랙록", "소프트뱅크", "비전펀드",
    # 펀드/투자조합 (투자 주체 — 발굴 대상 아님)
    "국민성장펀드", "성장펀드", "모태펀드", "혁신펀드", "성장금융",
    # 대형 상장사/지주 (비상장 발굴 대상 아님)
    "AI", "삼성전자", "삼전", "SK하이닉스", "삼성", "SK", "SK바이오",
    "SK바이오팜", "LG", "LG에너지솔루션", "현대차", "기아", "포스코",
    "뉴욕증권거래소", "한국거래소", "나스닥", "코스피", "기보",
    "기술보증기금", "신용보증기금", "중진공", "중소벤처기업진흥공단",
    "한투금융", "한국투자금융", "한투AC", "한국금융", "KB금융",
    "KB금융그룹", "신한금융", "하나금융", "우리금융", "메리츠금융",
    # 외국 기업/인물
    "레플릿", "앤스로픽", "앤트로픽", "Keep", "방시혁", "송경한", "홍종철",
    "이재용", "정의선", "최태원", "구광모", "김범수", "이해진", "장병규",
    # 언론사
    "딜사이트경제TV", "국제신문", "시사저널이코노미", "중앙이코노미뉴스",
    "르몽드", "오늘의", "딜사이트", "이데일리", "더벨", "플래텀", "THE",
    # 일반 명사/문맥어 (제목 첫 토큰으로 자주 등장)
    "바이오", "반도체", "헬스케어", "상장재수", "삼수생", "상장속",
    "이유있", "트래픽", "수요예측", "하이닉스", "삼성파운드리",
    "샌프란시스코", "파운드리", "수요", "예측", "재수", "삼수",
    "올해도", "내년에", "사실상", "본격", "드디어", "마침내",
}

# 외국 기업 판별용 (영문 단독 또는 외국계 키워드)
FOREIGN_PATTERNS = ["X", "AI"]


def search_naver_news(keyword, pages=10):
    """네이버 뉴스 검색 결과에서 기사 제목과 내용을 가져옴.
    href 기준으로 그룹핑: 같은 href의 첫 텍스트=제목, 두번째=본문요약.
    빈 페이지가 나오면 조기 종료."""
    articles = []
    global_seen = set()

    for page in range(1, pages + 1):
        start = (page - 1) * 10 + 1
        url = f"https://search.naver.com/search.naver?where=news&query={quote(keyword)}&sort=1&ds=&de=&start={start}"
        page_new = 0
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # 외부 뉴스 링크(fender-ui)를 순서대로 수집
            by_href = {}  # href -> {"title":..., "desc":...}
            order = []
            for a_tag in soup.select("a"):
                classes = " ".join(a_tag.get("class", []))
                if "fender-ui" not in classes:
                    continue
                href = a_tag.get("href", "")
                text = a_tag.get_text(strip=True)
                if not href or "naver.com" in href or "search.naver" in href:
                    continue
                if len(text) < 8:
                    continue
                if href not in by_href:
                    by_href[href] = {"title": text, "desc": ""}
                    order.append(href)
                elif not by_href[href]["desc"] and text != by_href[href]["title"]:
                    by_href[href]["desc"] = text[:200]

            for href in order:
                if href in global_seen:
                    continue
                global_seen.add(href)
                page_new += 1
                articles.append({
                    "keyword": keyword,
                    "title": by_href[href]["title"],
                    "description": by_href[href]["desc"],
                    "link": href,
                    "source": "",
                    "date": "",
                })

        except Exception as e:
            print(f"  [오류] '{keyword}' 페이지 {page}: {e}")

        if page_new == 0:
            break  # 더 이상 새 기사 없음
        time.sleep(0.4)
    return articles


def extract_companies_from_title(title):
    """제목에서 기업명 후보 추출.
    핵심 패턴: 대괄호/따옴표 접두어 제거 후, 첫 쉼표 앞 토큰이 기업명.
    예) '[더벨]파블로항공, 150억 프리IPO...' -> '파블로항공'
        '레티널, 278억 원 규모 프리IPO 투자 유치' -> '레티널'
        '국민성장펀드, 퓨리오사AI·스마일게이트·SK바이오 등...' -> '국민성장펀드', '퓨리오사AI', '스마일게이트', 'SK바이오'
    """
    candidates = []

    # 0. 대괄호 안에 '회사명IPO' / '회사명 IPO' 형태로 갇힌 기업명 추출
    #    예) [에이엔에이치스트럭쳐IPO], [업스테이지 IPO엑스레이]
    for inner in re.findall(r'\[([^\]]+)\]', title):
        m = re.match(r'^([가-힣A-Za-z0-9]{2,20})\s*IPO', inner)
        if m:
            candidates.append(m.group(1))

    # 1. 선행 대괄호 접두어 제거: [더벨], [주간투자동향], [Who Is?] 등 (반복)
    t = re.sub(r'^\s*(?:\[[^\]]*\]\s*)+', '', title).strip()

    # 2. 선행 따옴표 구문 제거: '몸값 5조', "AI 글래스 광학기술" 등
    t = re.sub(r"^\s*['‘’\"“”][^'‘’\"“”]{1,30}['‘’\"“”]\s*", '', t).strip()

    if not t:
        return candidates

    # 3. 첫 쉼표(,) 앞 세그먼트 = 주체 기업
    has_comma = bool(re.search(r'[,，]', t))
    first_seg = re.split(r'[,，]', t)[0].strip()
    tokens = first_seg.split()
    if tokens:
        head = tokens[0]
        # 'SK' 'KT' 'CJ' 등 짧은 그룹명으로 시작하면 2어절 결합
        if len(head) <= 2 and re.match(r'^[A-Za-z가-힣]{1,2}$', head) and len(tokens) > 1:
            head = head + tokens[1]
        # ·로 연결된 토큰이면 통째로 넣지 않고 4번 분리 로직에 맡김
        if '·' not in head and 'ㆍ' not in head:
            # 쉼표가 없는 문장형 제목이면 첫 토큰에 조사가 붙어있을 수 있어 제거
            if not has_comma:
                head = strip_single_josa(head)
            candidates.append(head)

    # 4. · 또는 ㆍ 로 연결된 기업 나열 (퓨리오사AI·스마일게이트·SK바이오)
    for grp in re.findall(r'[가-힣A-Za-z0-9]{2,15}(?:[·ㆍ][가-힣A-Za-z0-9]{2,15})+', t):
        for part in re.split(r'[·ㆍ\-]', grp):
            part = strip_single_josa(part.strip(), safe=True)
            if part:
                candidates.append(part)

    # 5. 기업명 + (프리IPO/투자유치/상장/주관사 등) 바로 앞 토큰
    for m in re.findall(r'([가-힣A-Za-z0-9]{2,15})\s*(?:프리IPO|투자\s*유치|상장|기업공개|주관사|지정감사|시리즈[A-G])', t):
        candidates.append(strip_single_josa(m))

    # 인물명(직함이 바로 뒤따르는 후보) 제외
    candidates = [c for c in candidates if c and not is_person_name(c, title)]

    return candidates


# 인물 직함 (이 단어가 후보 바로 뒤에 오면 인물명으로 판단)
PERSON_TITLES = (
    "대표이사", "대표", "회장", "부회장", "의장", "사장", "부사장",
    "전무", "상무", "이사", "센터장", "본부장", "사업부장", "팀장",
    "소장", "원장", "박사", "교수", "연구원", "위원장", "위원",
    "장관", "차관", "청장", "위원회", "CEO", "CFO", "CTO", "COO",
    "창업자", "공동대표", "각자대표", "총괄", "지사장", "법인장",
)


# 한국 흔한 성씨 (인물명 판별용 — 기업명 오탐 방지)
SURNAMES = set("김이박최정강조윤장임한오서신권황안송류전홍고문양손배"
               "백허남심노하곽성차주우구민진지엄채원천방공현함변염여추"
               "도소석선설마길연위표명기반라왕금옥육인맹제모탁국어은편용예경봉")


def is_person_name(name, title):
    """제목에서 'name + 직함' 패턴이고 name이 한국 성씨로 시작하면 인물로 간주.
    (메가존·야놀자처럼 성씨가 아닌 사명은 직함 앞에 와도 보존)"""
    # 한국 인물명은 대부분 정확히 3글자 → 3글자 + 성씨 시작에만 적용
    if not re.match(r'^[가-힣]{3}$', name):
        return False
    if name[0] not in SURNAMES:
        return False
    pat = re.escape(name) + r'(?:\s|은|는|이|가|의|,)*\s*(?:' + "|".join(PERSON_TITLES) + r')'
    return bool(re.search(pat, title))


# 조사 세트: SAFE는 이/가 제외(넥스아이 등 사명 보호), FULL은 이/가 포함
JOSA_SAFE = ("으로", "에서", "은", "는", "을", "를",
             "의", "에", "와", "과", "도", "로", "만", "께")
JOSA_FULL = JOSA_SAFE + ("이", "가")


def strip_single_josa(token, safe=False):
    """토큰 끝의 단일 조사를 제거 (제거 후 2글자 이상 유지).
    safe=True면 이/가는 보존(사명 끝일 가능성)."""
    token = token.strip()
    josa_set = JOSA_SAFE if safe else JOSA_FULL
    for josa in sorted(josa_set, key=len, reverse=True):
        if token.endswith(josa) and len(token) - len(josa) >= 2:
            return token[:-len(josa)]
    return token


def extract_company_names(articles):
    """기사 제목 중심으로 기업명 후보를 추출"""
    company_counter = Counter()
    company_articles = {}

    for art in articles:
        # 제목 중심 추출 (정확도 높음)
        candidates = extract_companies_from_title(art["title"])

        seen_in_article = set()
        for name in candidates:
            name = clean_candidate(name)
            if not name or name in seen_in_article:
                continue
            seen_in_article.add(name)
            company_counter[name] += 1
            if name not in company_articles:
                company_articles[name] = []
            company_articles[name].append({
                "title": art["title"],
                "link": art["link"],
                "keyword": art["keyword"],
                "source": art["source"],
                "date": art["date"],
            })

    return company_counter, company_articles


# 후행 조사 (다음절만 — 단일 음절 조사는 실제 사명을 훼손하므로 제외)
TRAILING_JOSA = [
    "에서는", "에게서", "에서", "으로", "에게", "께서",
    "이라며", "이라고", "이라", "라며", "라고", "는", "은",
]


def clean_candidate(name):
    """추출된 후보에서 후행 조사를 제거하고 기업명이 아닌 것을 걸러냄"""
    # 선행/후행 기호(말줄임표, 따옴표, 가운뎃점, 하이픈 등) 제거
    name = name.strip(" '\"‘’“”·ㆍ.…-—~()[]<>")
    if len(name) < 2:
        return None

    # 하이픈/가운뎃점이 남아있으면 첫 토큰만 (KB금융-리벨리온 -> 처리는 호출부에서 분리됨)
    if "-" in name or "·" in name or "ㆍ" in name:
        return None

    # 다음절 후행 조사만 제거 (긴 것부터). 제거 후 최소 2글자 유지
    for josa in sorted(TRAILING_JOSA, key=len, reverse=True):
        if name.endswith(josa) and len(name) - len(josa) >= 2:
            name = name[:-len(josa)]
            break

    name = name.strip(" '\"‘’“”·.…-")
    if len(name) < 2:
        return None
    if name in EXCLUDE_WORDS:
        return None
    # 숫자만 / 숫자로 시작 / 숫자+단위 제외
    if re.match(r"^[0-9]", name):
        return None
    # 영문 1~2글자 단독 제외 (AI, THE 등 약어 노이즈)
    if re.match(r"^[A-Za-z]{1,3}$", name):
        return None
    return name


def main():
    print("=" * 60)
    print("네이버 뉴스 비상장 종목 키워드 검색")
    print(f"검색 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    all_articles = []
    keyword_stats = {}

    for kw in KEYWORDS:
        print(f"\n[검색] 키워드: '{kw}'...")
        articles = search_naver_news(kw, pages=10)
        print(f"   → {len(articles)}건 수집")
        all_articles.extend(articles)
        keyword_stats[kw] = len(articles)
        time.sleep(1)

    print(f"\n총 {len(all_articles)}건 기사 수집 완료")

    company_counter, company_articles = extract_company_names(all_articles)

    top_companies = company_counter.most_common(80)
    print(f"\n{'='*60}")
    print(f"기업 언급 빈도 TOP 80")
    print(f"{'='*60}")
    for i, (name, count) in enumerate(top_companies, 1):
        print(f"  {i:3d}. {name} ({count}회)")

    output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "keyword_stats": keyword_stats,
        "total_articles": len(all_articles),
        "top_companies": [
            {
                "name": name,
                "mention_count": count,
                "keywords": sorted(set(
                    a["keyword"] for a in company_articles.get(name, [])
                )),
                "articles": company_articles.get(name, [])[:5],
            }
            for name, count in top_companies
        ],
        "all_articles": all_articles,
    }

    out_path = os.path.join(output_dir, "news_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
