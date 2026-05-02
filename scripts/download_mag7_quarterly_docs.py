#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import quote_plus

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE = REPO_ROOT / "app" / "rag" / "data" / "raw"
BASE.mkdir(parents=True, exist_ok=True)

TICKERS = {
    "meta": "META",
    "msft": "MSFT",
    "tsla": "TSLA",
    "amzn": "AMZN",
    "aapl": "AAPL",
}

QUARTERS = [
    (2024, "q1"),
    (2024, "q2"),
    (2024, "q3"),
    (2024, "q4"),
    (2025, "q1"),
    (2025, "q2"),
    (2025, "q3"),
    (2025, "q4"),
]

USER_AGENT = "Mozilla/5.0"


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True, errors="ignore")


def curl(url: str) -> str:
    return run(["curl", "-L", "-sS", "-A", USER_AGENT, url])


def download(url: str, dest: Path) -> bool:
    try:
        subprocess.check_call(["curl", "-L", "-sS", "-A", USER_AGENT, url, "-o", str(dest)])
        if dest.stat().st_size < 1000:
            dest.unlink(missing_ok=True)
            return False
        with open(dest, "rb") as f:
            if f.read(4) != b"%PDF":
                dest.unlink(missing_ok=True)
                return False
        return True
    except Exception:
        dest.unlink(missing_ok=True)
        return False


def ddg_html(query: str) -> str:
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    return curl(url)


def extract_urls(html: str) -> list[str]:
    urls = re.findall(r'nofollow" class="result__a" href="([^"]+)"', html)
    if not urls:
        urls = re.findall(r'href="(https?://[^"]+)"', html)
    cleaned = []
    for u in urls:
        u = u.replace("&amp;", "&")
        if u.startswith("//"):
            u = "https:" + u
        cleaned.append(u)
    out = []
    seen = set()
    for u in cleaned:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def candidate_queries(company: str, ticker: str, year: int, quarter: str) -> list[tuple[str, str]]:
    qn = quarter.upper()
    fq = f"{year} {qn}"
    return [
        (f"{company} {fq} earnings transcript pdf", "earnings-transcript"),
        (f"{company} {fq} earnings call transcript pdf", "earnings-transcript"),
        (f"{company} {fq} earnings release pdf", "earnings-release"),
        (f"{company} {fq} investor presentation pdf", "investor-presentation"),
        (f"{company} {fq} shareholder deck pdf", "shareholder-deck"),
        (f"{ticker} {fq} quarterly results pdf", "quarterly-results"),
    ]


def interesting(url: str, year: int, quarter: str) -> bool:
    low = url.lower()
    if ".pdf" not in low:
        return False
    if str(year) not in low and f"fy{str(year)[2:]}" not in low:
        return False
    quarter_variant = quarter.replace("q", "quarter-")
    if quarter not in low and quarter.upper() not in url and quarter_variant not in low:
        # allow if keyword strong enough
        if not any(
            keyword in low
            for keyword in ["earn", "shareholder", "presentation", "results", "release"]
        ):
            return False
    return True


def main() -> None:
    for company, ticker in TICKERS.items():
        out_dir = BASE / company
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n== {company} ==")
        for year, quarter in QUARTERS:
            done = False
            for query, kind in candidate_queries(company, ticker, year, quarter):
                try:
                    html = ddg_html(query)
                except Exception:
                    continue
                for url in extract_urls(html):
                    if not interesting(url, year, quarter):
                        continue
                    filename = f"{year}-{quarter}-{kind}.pdf"
                    dest = out_dir / filename
                    if dest.exists():
                        done = True
                        break
                    if download(url, dest):
                        print("ok", filename, url)
                        done = True
                        break
                if done:
                    break
            if not done:
                print("miss", year, quarter)


if __name__ == "__main__":
    main()
