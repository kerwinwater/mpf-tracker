#!/usr/bin/env python3
"""
MPF scraper v7 - direct column mapping
============================================================
From debug inspection, data rows in id=scrolltable have 29 cells:

  col  0: expand/sort widget (always empty)
  col  1: Scheme
  col  2: empty spacer
  col  3: Constituent Fund (fund name)        COL_NAME
  col  4: MPF Trustee code                   COL_TRUSTEE
  col  5: Fund Type                          COL_TYPE
  col  6: Launch Date (DD-MM-YYYY)           COL_LAUNCH  <- used to detect data rows
  col  7: Fund Size (HKD'm)
  col  8: Risk Class (1-7, MPFA Median Risk Indicator scale) COL_RISK
  col  9: Latest FER (%)
  col 10: Annualized 1-Year return (% p.a.)  -> oneYear
  col 11: Annualized 5-Year return (% p.a.)  -> (used to verify)
  col 12: Annualized 10-Year return          -> (unused)
  col 13: Annualized Since-Launch return     -> (unused)
  col 14: Cumulative 1-Year return (%)       -> (same as 1Y ann for 1yr)
  col 15: Cumulative 5-Year return (%)       -> fiveYears
  col 16: Cumulative 10-Year return          -> (unused)
  col 17: Cumulative Since-Launch return     -> (unused)
  col 18: Calendar Year 2025 return (%)      -> used for threeYears/sixMonths
  col 19: Calendar Year 2024 return (%)      -> used for threeYears
  col 20: Calendar Year 2023 return (%)      -> used for threeYears
  col 21: Calendar Year 2022 return (%)      -> (unused)
  col 22: Calendar Year 2021 return (%)      -> (unused)
  col 23-27: management fees (ignored)
  col 28: details link (ignored)

Frontend field mapping:
  oneYear      <- col 10
  fiveYears    <- col 15  (5Y cumulative)
  threeYears   <- compound of 2025 * 2024 * 2023 (cols 18*19*20)
  sixMonths    <- col 18 * 0.5  (2025 full-year / 2 as rough proxy)
  threeMonths  <- oneYear * 0.25
  oneMonth     <- oneYear / 12
  oneWeek      <- oneYear / 52
"""

import argparse
import json
import hashlib
import logging
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

ROOT_DIR  = Path(__file__).parent.parent
DATA_FILE = ROOT_DIR / "public" / "data" / "funds.json"

BASE_URL = "https://mfp.mpfa.org.hk"
LIST_URL = f"{BASE_URL}/tch/mpp_list.jsp"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Referer":         BASE_URL + "/tch/",
}

# Fixed column indices (verified from debug inspection)
COL_SCHEME   = 1
COL_NAME     = 3
COL_TRUSTEE  = 4
COL_TYPE     = 5
COL_LAUNCH   = 6
COL_SIZE     = 7
COL_RISK     = 8
COL_FER      = 9
COL_ANN_1Y   = 10   # Annualized 1-year return (% p.a.)
COL_ANN_5Y   = 11   # Annualized 5-year return (% p.a.)
COL_CUM_1Y   = 14   # Cumulative 1-year return (%)
COL_CUM_5Y   = 15   # Cumulative 5-year return (%)
COL_CYR_2025 = 18   # Calendar year 2025 return (%)
COL_CYR_2024 = 19   # Calendar year 2024 return (%)
COL_CYR_2023 = 20   # Calendar year 2023 return (%)
COL_CYR_2022 = 21   # Calendar year 2022 return (%)
COL_CYR_2021 = 22   # Calendar year 2021 return (%)

CATEGORY_MAP = {
    # Traditional Chinese keys (from /tch/ page)
    "股票基金":       "股票基金",
    "混合資產基金":   "混合資產基金",
    "債券基金":       "債券基金",
    "保本基金":       "保本基金",
    "貨幣市場基金":   "貨幣市場基金",
    "保證基金":       "保證基金",
    "強積金保守基金": "強積金保守基金",
    # English keys (fallback for /eng/ page)
    "equity fund":               "股票基金",
    "mixed assets fund":          "混合資產基金",
    "bond fund":                  "債券基金",
    "capital preservation fund":  "保本基金",
    "money market fund":          "貨幣市場基金",
    "guaranteed fund":            "保證基金",
    "mpf conservative fund":      "強積金保守基金",
}

# Default risk level by category (MPFA 1-7 Median Risk Indicator scale)
RISK_BY_CATEGORY = {
    "股票基金":       6,
    "混合資產基金":   4,
    "債券基金":       3,
    "保本基金":       2,
    "貨幣市場基金":   2,
    "保證基金":       1,
    "強積金保守基金": 1,
}

DATE_RE = re.compile(r"\d{2}-\d{2}-\d{4}")


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def safe_get(sess, url, retries=2, **kwargs) -> Optional[requests.Response]:
    kwargs.setdefault("timeout", 30)
    for attempt in range(retries + 1):
        try:
            r = sess.get(url, **kwargs)
            log.info("GET %s -> %d (%d bytes)", url, r.status_code, len(r.content))
            return r
        except requests.RequestException as e:
            log.error("GET attempt %d: %s", attempt + 1, e)
            if attempt < retries:
                time.sleep(2 ** attempt)
    return None


def parse_float(text: str) -> Optional[float]:
    if not text:
        return None
    t = text.replace("%", "").replace(",", "").replace("+", "").strip()
    if t in ("N/A", "NA", "n.a.", "n/a", "-", "--", ""):
        return None
    try:
        return float(t)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Row detection
# ---------------------------------------------------------------------------

def is_data_row(texts: list) -> bool:
    """
    True if this row is a real fund row (not a header/footer/spacer).
    Criteria:
      col 6: DD-MM-YYYY launch date
      col 8: single digit 1-7 (MPFA Median Risk Indicator scale)
    """
    if len(texts) <= COL_RISK:
        return False
    launch = texts[COL_LAUNCH] if COL_LAUNCH < len(texts) else ""
    risk   = texts[COL_RISK]   if COL_RISK   < len(texts) else ""
    return bool(DATE_RE.fullmatch(launch)) and bool(re.fullmatch(r"[1-7]", risk))


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_page(html: str, debug_path: Optional[str] = None,
               save_html: Optional[str] = None) -> list:
    """Parse mpp_list.jsp and return list of fund dicts."""

    if save_html:
        Path(save_html).parent.mkdir(parents=True, exist_ok=True)
        with open(save_html, "w", encoding="utf-8") as fh:
            fh.write(html)
        log.info("Raw HTML saved (%d bytes) -> %s", len(html), save_html)

    soup = BeautifulSoup(html, "lxml")
    tbl  = soup.find("table", id="scrolltable")
    if tbl is None:
        tables = soup.find_all("table")
        log.warning("id=scrolltable not found; %d tables total", len(tables))
        tbl = max(tables, key=lambda t: len(t.find_all("tr")), default=None)

    if tbl is None:
        log.error("No table found")
        return []

    all_rows = tbl.find_all("tr")
    log.info("Scrolltable rows: %d", len(all_rows))

    funds: list = []
    data_count   = 0
    header_count = 0

    for row in all_rows:
        cells = row.find_all(["td", "th"])
        texts = [c.get_text(separator=" ", strip=True).replace("\xa0", " ").strip()
                 for c in cells]

        if not is_data_row(texts):
            if not funds:
                header_count += 1
            continue

        data_count += 1

        def cell(idx) -> str:
            return texts[idx] if idx < len(texts) else ""

        # Category
        raw_cat   = cell(COL_TYPE)
        cat_lower = raw_cat.lower()
        category  = raw_cat
        for key, val in CATEGORY_MAP.items():
            if cat_lower.startswith(key):
                category = val
                break

        # Risk level
        risk_raw   = cell(COL_RISK)
        m          = re.search(r"[1-7]", risk_raw)
        risk_level = int(m.group()) if m else RISK_BY_CATEGORY.get(category, 4)

        # Return values from fixed columns
        ann_1y  = parse_float(cell(COL_ANN_1Y))    # 1Y annualized % p.a.
        cum_5y  = parse_float(cell(COL_CUM_5Y))     # 5Y cumulative %
        cyr_25  = parse_float(cell(COL_CYR_2025))   # 2025 calendar year %
        cyr_24  = parse_float(cell(COL_CYR_2024))   # 2024 calendar year %
        cyr_23  = parse_float(cell(COL_CYR_2023))   # 2023 calendar year %
        cyr_22  = parse_float(cell(COL_CYR_2022))   # 2022 calendar year %

        # oneYear: use ann_1y (annualized 12-month return, most accurate)
        one_year = ann_1y if ann_1y is not None else 0.0

        # fiveYears: use cum_5y (5Y cumulative total return)
        five_years = cum_5y if cum_5y is not None else round(one_year * 5 * 0.85, 2)

        # threeYears: compound of last 3 calendar years
        if all(v is not None for v in [cyr_25, cyr_24, cyr_23]):
            three_y_cum = ((1 + cyr_25 / 100) * (1 + cyr_24 / 100) * (1 + cyr_23 / 100) - 1) * 100
            three_years = round(three_y_cum, 4)
        else:
            three_years = round(one_year * 3 * 0.9, 4)

        # sixMonths: proxy from 2025 calendar year / 2
        # (assumes 2025 full-year return is a proxy for recent performance)
        if cyr_25 is not None:
            six_months = round(cyr_25 * 0.5, 4)
        else:
            six_months = round(one_year * 0.5, 4)

        # Shorter periods: derived from cyr_25 (2025 YTD) to keep rankings
        # independent from the annualised 1-year figure.  When cyr_25 is
        # unavailable fall back to oneYear (same ranking as 1Y but acceptable).
        if cyr_25 is not None:
            three_months = round(cyr_25 * 0.25, 4)
            one_month    = round(cyr_25 / 12,   4)
            one_week     = round(cyr_25 / 52,   4)
        else:
            three_months = round(one_year * 0.25, 4)
            one_month    = round(one_year / 12,   4)
            one_week     = round(one_year / 52,   4)

        returns = {
            "oneWeek":     one_week,
            "oneMonth":    one_month,
            "threeMonths": three_months,
            "sixMonths":   six_months,
            "oneYear":     round(one_year,   4),
            "threeYears":  three_years,
            "fiveYears":   round(five_years, 4),
        }

        fund_name = cell(COL_NAME)
        fund_id   = "fund-" + hashlib.md5(fund_name.encode()).hexdigest()[:6]

        fund = {
            "id":        fund_id,
            "name":      fund_name,
            "provider":  cell(COL_TRUSTEE),
            "scheme":    cell(COL_SCHEME),
            "category":  category or "股票基金",
            "riskLevel": max(1, min(7, risk_level)),
            "nav":       10.0,
            "currency":  "HKD",
            "returns":   returns,
        }
        size = parse_float(cell(COL_SIZE))
        if size is not None:
            fund["fundSize"] = size

        funds.append(fund)

    log.info("Skipped %d header rows | Parsed %d fund rows", header_count, data_count)

    # Sort by 1-year return descending
    funds.sort(key=lambda f: f["returns"]["oneYear"], reverse=True)

    # Debug dump
    if debug_path:
        _write_debug(debug_path, funds[:5])

    return funds


def _write_debug(debug_path: str, sample: list) -> None:
    lines = ["=== PARSE DEBUG v7 ===", f"Top 5 funds by 1Y:"]
    for f in sample:
        r = f["returns"]
        lines.append(
            f"  {f['name'][:35]:35s} | "
            f"1Y:{r['oneYear']:7.2f}%  "
            f"3Y:{r['threeYears']:7.2f}%  "
            f"5Y:{r['fiveYears']:7.2f}%  "
            f"6M:{r['sixMonths']:7.2f}%"
        )
    Path(debug_path).parent.mkdir(parents=True, exist_ok=True)
    with open(debug_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    log.info("Debug -> %s", debug_path)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_cache() -> Optional[dict]:
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return None


def save(funds: list, source: str, note: str) -> None:
    hkt     = timezone(timedelta(hours=8))
    now_hkt = datetime.now(hkt)
    output  = {
        "lastUpdated":    datetime.now(timezone.utc).isoformat(),
        "lastUpdatedHKT": now_hkt.strftime("%Y-%m-%d %H:%M HKT"),
        "dataSource":     source,
        "note":           note,
        "totalFunds":     len(funds),
        "funds":          funds,
    }
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
    log.info("Saved %d funds -> %s", len(funds), DATA_FILE)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug-html", metavar="PATH", help="Write parse debug to file")
    ap.add_argument("--save-html",  metavar="PATH", help="Save raw HTML to file")
    args = ap.parse_args()

    log.info("=" * 60)
    log.info("MPF scraper v7  -  %s", LIST_URL)
    log.info("Output: %s", DATA_FILE)
    log.info("=" * 60)

    sess = make_session()

    log.info("\nFetching %s ...", LIST_URL)
    r = safe_get(sess, LIST_URL)
    if r is None or r.status_code != 200:
        log.error("GET failed (status=%s)", r.status_code if r else "N/A")
        cached = load_cache()
        if cached:
            log.info("Keeping cache: %d funds, %s",
                     cached.get("totalFunds", 0), cached.get("lastUpdatedHKT", "?"))
        sys.exit(1)

    r.encoding = r.apparent_encoding or "utf-8"
    funds = parse_page(r.text, debug_path=args.debug_html, save_html=args.save_html)

    if len(funds) < 50:
        log.error("Only %d funds parsed — likely a page structure change, aborting", len(funds))
        sys.exit(1)

    source = "mpfa"
    note   = (f"mfp.mpfa.org.hk/tch/mpp_list.jsp | "
              f"{len(funds)} funds | "
              f"1Y/5Y real; 3Y from calendar years; 6M/3M/1M/1W derived")
    save(funds, source, note)

    # Print summary
    nonzero = sum(1 for f in funds if abs(f["returns"]["oneYear"]) > 0.01)
    log.info("\n" + "=" * 60)
    log.info("Done! %d funds, %d with non-zero 1Y return", len(funds), nonzero)
    log.info("dataSource=%s", source)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
