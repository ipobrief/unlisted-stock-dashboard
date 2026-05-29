"""
모든 데이터 소스를 순차적으로 수집하는 통합 스크립트
"""
import subprocess
import sys
import os
import json
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)


def run_script(name):
    path = os.path.join(SCRIPT_DIR, name)
    print(f"\n{'='*60}")
    print(f"실행: {name}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, path],
        capture_output=False,
        text=True,
        cwd=PROJECT_DIR,
    )
    return result.returncode == 0


def merge_data():
    """수집된 데이터를 data.js로 병합"""
    news_path = os.path.join(PROJECT_DIR, "news_data.json")
    thevc_path = os.path.join(PROJECT_DIR, "thevc_data.json")
    platform_path = os.path.join(PROJECT_DIR, "platform_data.json")

    merged = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "news": {},
        "thevc": {},
        "platforms": {},
    }

    for path, key in [(news_path, "news"), (thevc_path, "thevc"), (platform_path, "platforms")]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                merged[key] = json.load(f)

    out_path = os.path.join(PROJECT_DIR, "data.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("const DASHBOARD_DATA = ")
        json.dump(merged, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    print(f"\n통합 데이터 저장: {out_path}")


def main():
    print("=" * 60)
    print("비상장 종목 서치 - 전체 데이터 수집")
    print(f"시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    scripts = [
        "fetch_naver_news.py",
        "fetch_thevc.py",
        "fetch_platforms.py",
    ]

    results = {}
    for script in scripts:
        success = run_script(script)
        results[script] = "성공" if success else "실패"

    merge_data()

    print(f"\n{'='*60}")
    print("수집 결과 요약")
    print(f"{'='*60}")
    for script, status in results.items():
        print(f"  {script}: {status}")
    print(f"\n완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
