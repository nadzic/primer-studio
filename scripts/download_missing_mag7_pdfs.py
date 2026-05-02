#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import TypedDict
from urllib.parse import urljoin


class CompanyConfig(TypedDict):
    cik: int
    sec_slug: str
    extra_pages: list[str]


class RecentFilings(TypedDict):
    form: list[str]
    accessionNumber: list[str]
    primaryDocument: list[str]
    filingDate: list[str]


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE = REPO_ROOT / "app" / "rag" / "data" / "raw"
BASE.mkdir(parents=True, exist_ok=True)

COMPANIES: dict[str, CompanyConfig] = {
    "meta": {
        "cik": 1326801,
        "sec_slug": "meta",
        "extra_pages": [
            "https://investor.atmeta.com/financials/default.aspx",
            "https://investor.atmeta.com/investor-news/press-releases/default.aspx",
        ],
    },
    "msft": {
        "cik": 789019,
        "sec_slug": "msft",
        "extra_pages": [
            "https://www.microsoft.com/en-us/Investor/earnings/default.aspx",
            "https://www.microsoft.com/en-us/Investor/sec-filings.aspx",
        ],
    },
    "tsla": {
        "cik": 1318605,
        "sec_slug": "tsla",
        "extra_pages": [
            "https://ir.tesla.com/",
            "https://ir.tesla.com/sec-filings",
        ],
    },
    "amzn": {
        "cik": 1018724,
        "sec_slug": "amzn",
        "extra_pages": [
            "https://www.amazon.com/ir",
            "https://www.aboutamazon.com/news/company-news",
        ],
    },
    "aapl": {
        "cik": 320193,
        "sec_slug": "aapl",
        "extra_pages": [
            "https://investor.apple.com/investor-relations/default.aspx",
            "https://investor.apple.com/sec-filings/default.aspx",
        ],
    },
}

USER_AGENT = "Nik local research script nik@example.com"


def curl(url: str, dest: Path | None = None) -> str:
    cmd = [
        "curl",
        "-L",
        "-sS",
        "-A",
        USER_AGENT,
        url,
    ]
    if dest is not None:
        cmd.extend(["-o", str(dest)])
        subprocess.check_call(cmd)
        return ""
    return subprocess.check_output(cmd, text=True, errors="ignore")


def download_pdf(url: str, dest: Path) -> bool:
    try:
        curl(url, dest)
        if dest.stat().st_size < 1000:
            dest.unlink(missing_ok=True)
            return False
        with dest.open("rb") as f:
            if f.read(4) != b"%PDF":
                dest.unlink(missing_ok=True)
                return False
        return True
    except Exception:
        dest.unlink(missing_ok=True)
        return False


def sec_recent(cik: int) -> RecentFilings:
    txt = curl(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    return json.loads(txt)["filings"]["recent"]


def sec_html_url(cik: int, accession: str, primary_doc: str) -> str:
    accession_compact = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_compact}/{primary_doc}"


def print_to_pdf(url: str, out: Path) -> bool:
    chrome_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    chrome = next((p for p in chrome_candidates if Path(p).exists()), None)
    if not chrome:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        f"--print-to-pdf={out}",
        url,
    ]
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out.exists() and out.stat().st_size > 1000
    except Exception:
        out.unlink(missing_ok=True)
        return False


def scrape_pdf_links(page_url: str) -> list[str]:
    try:
        html = curl(page_url)
    except Exception:
        return []

    links = set()
    for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
        full = urljoin(page_url, href)
        if ".pdf" in full.lower():
            links.add(full)

    for direct in re.findall(r'https://[^"\']+?\.pdf(?:\?[^"\']*)?', html, re.I):
        links.add(direct)

    return sorted(links)


def maybe_interesting(pdf_url: str) -> bool:
    low = pdf_url.lower()
    if not any(y in low for y in ["2024", "2025", "fy24", "fy25", "q1", "q2", "q3", "q4"]):
        return False
    return any(
        k in low
        for k in [
            "earn",
            "quarter",
            "result",
            "release",
            "presentation",
            "supplemental",
            "shareholder",
            "annual",
            "10-k",
            "10-q",
        ]
    )


def main() -> None:
    for slug, cfg in COMPANIES.items():
        target = BASE / slug
        target.mkdir(parents=True, exist_ok=True)
        print(f"\n== {slug} ==")

        # 1) SEC filings as printed PDFs from official filing pages
        recent = sec_recent(cfg["cik"])
        seen = set()
        for form, acc, primary, date in zip(
            recent["form"],
            recent["accessionNumber"],
            recent["primaryDocument"],
            recent["filingDate"],
            strict=False,
        ):
            year = date[:4]
            if year not in {"2024", "2025"}:
                continue
            if form not in {"10-K", "10-Q"}:
                continue

            if form == "10-Q":
                month = int(date[5:7])
                q = 1 if month <= 4 else 2 if month <= 7 else 3
                filename = f"{slug}-{year}-q{q}-10q.pdf"
            else:
                filename = f"{slug}-{year}-10k.pdf"

            if filename in seen:
                continue
            seen.add(filename)

            out = target / filename
            if out.exists():
                print("skip", filename)
                continue

            filing_url = sec_html_url(cfg["cik"], acc, primary)
            ok = print_to_pdf(filing_url, out)
            print(("ok" if ok else "fail"), filename, filing_url)

        # 2) Try direct investor-relations PDFs
        count = 0
        for page in cfg["extra_pages"]:
            for pdf_url in scrape_pdf_links(page):
                if not maybe_interesting(pdf_url):
                    continue
                name = os.path.basename(pdf_url.split("?")[0])
                safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
                out = target / safe
                if out.exists():
                    continue
                if download_pdf(pdf_url, out):
                    print("ok", safe, pdf_url)
                    count += 1
                if count >= 8:
                    break
            if count >= 8:
                break


if __name__ == "__main__":
    main()
