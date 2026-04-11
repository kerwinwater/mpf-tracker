#!/usr/bin/env python3
"""
MPF scraper v4 - scrapes mpp_list.jsp directly
1. GET https://mfp.mpfa.org.hk/eng/mpp_list.jsp
2. Parse table: name, trustee, type, risk, fund size, annual returns 2021-2025
3. Follow each fund's detail link for period-based returns
4. Save to public/data/funds.json
"""

import json
import hashlib
import logging
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

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
LIST_URL = f"{BASE_URL}/eng/mpp_list.jsp"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Referer":         BASE_URL + "/",
}

CATEGORY_MAP = {
    "equity fund":                "股票基金",
    "mixed assets fund":          "混合資產基金",
    "bond fund":                  "債券基金",
    "capital preservation fund":  "保本基金",
    "money market fund":          "貨幣市場基金",
    "guaranteed fund":            "保證基金",
    "mpf conservative fund":      "強積金保守基金",
}

RISK_BY_CATEGORY = {
    "股票基金":       5,
    "混合資產基金":   3,
    "債券基金":       2,
    "保本基金":       1,
    "貨幣市場基金":   1,
    "保證基金":       1,
    "強積金保守基金": 1,
}

# Regex patterns to match period labels on the detail page
PERIOD_PATTERNS = [
    ("oneWeek",      [r"1\s*week", r"weekly", r"1\s*w\b"]),
    ("oneMonth",     [r"1\s*month", r"1\s*m\b", r"monthly"]),
    ("threeMonths",  [r"3\s*month", r"3\s*m\b"]),
    ("sixMonths",    [r"6\s*month", r"6\s*m\b", r"half\s*year"]),
    ("oneYear",      [r"1\s*year", r"1\s*y\b", r"12\s*month", r"annualised"]),
    ("threeYears",   [r"3\s*year", r"3\s*y\b", r"36\s*month"]),
    ("fiveYears",    [r"5\s*year", r"5\s*y\b", r"60\s*month"]),
]

# Max number of detail page fetches (to stay within GitHub Actions 20-min limit)
MAX_DETAIL_FETCHES = 600
DETAIL_DELAY       = 0.35  # seconds between requests


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def safe_get(sess, url, retries=2, **kwargs) -> Optional[requests.Response]:
    kwargs.setdefault("timeout", 25)
    for attempt in range(retries + 1):
        try:
            r = sess.get(url, **kwargs)
            log.info("GET %s -> HTTP %d (%d bytes)", url, r.status_code, len(r.content))
            return r
        except requests.RequestException as e:
            log.error("GET %s -> attempt %d FAILED: %s", url, attempt + 1, e)
            if attempt < retries:
                time.sleep(2 ** attempt)
    return None


def parse_float(text: str) -> Optional[float]:
    """Parse '12.34%' or '-5.67' or 'N/A' into float or None."""
    if not text:
        return None
    text = text.replace("%", "").replace(",", "").replace("+", "").strip()
    if text in ("N/A", "NA", "-", "--", "n.a.", "n/a", ""):
        return None
    try:
        return float(text)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Step 1: Parse the main list page
# ---------------------------------------------------------------------------

def parse_list_page(html: str) -> list:
    """
    Parse mpp_list.jsp.
    Expected columns (case-insensitive):
      Scheme | Constituent Fund | MPF Trustee | Fund Type |
      Launch Date | Fund Size (HKD'm) | Risk Class | Latest FER (%) |
      2025 | 2024 | 2023 | 2022 | 2021 | Details
    Returns list of raw fund dicts.
    """
    soup = BeautifulSoup(html, "lxml")

    log.info("Page title: %s", soup.title.string.strip() if soup.title else "N/A")

    all_tables = soup.find_all("table")
    log.info("Tables on page: %d", len(all_tables))

    # Dump first few tables for debugging
    for ti, tbl in enumerate(all_tables[:4]):
        rows = tbl.find_all("tr")
        log.info("  table[%d]: %d rows", ti, len(rows))
        for row in rows[:3]:
            cells = row.find_all(["th", "td"])
            log.info("    row: %s", [c.get_text(strip=True)[:25] for c in cells[:8]])

    funds = []

    for tbl_idx, tbl in enumerate(all_tables):
        rows = tbl.find_all("tr")
        if len(rows) < 3:
            continue

        # Find the header row (must mention "fund" or a year like "2024")
        header_idx = None
        header_texts = []
        for ri, row in enumerate(rows[:5]):
            cells = row.find_all(["th", "td"])
            texts = [c.get_text(strip=True).lower() for c in cells]
            joined = " ".join(texts)
            if "fund" in joined or "constituent" in joined or "2024" in joined:
                header_idx = ri
                header_texts = texts
                break

        if header_idx is None:
            continue

        log.info("Using table[%d] with %d rows, header at row %d",
                 tbl_idx, len(rows), header_idx)
        log.info("Header cells: %s", header_texts[:12])

        # Build column index map
        col = {}
        for ci, h in enumerate(header_texts):
            h = h.strip()
            if "constituent" in h:
                col.setdefault("name", ci)
            elif "fund" in h and "name" not in col and "type" not in h:
                col.setdefault("name", ci)
            elif "trustee" in h:
                col["trustee"] = ci
            elif "type" in h:
                col["type"] = ci
            elif "risk" in h:
                col["risk"] = ci
            elif "size" in h:
                col["size"] = ci
            elif "fer" in h:
                col["fer"] = ci
            elif "scheme" in h:
                col.setdefault("scheme", ci)
            elif re.fullmatch(r"20\d\d", h):
                col[h] = ci

        log.info("Column map: %s", col)

        if "name" not in col:
            log.info("No 'name' column found in table[%d], skipping", tbl_idx)
            continue

        # Parse data rows
        for row in rows[header_idx + 1:]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            def cell(key, default=""):
                idx = col.get(key)
                if idx is None or idx >= len(cells):
                    return default
                return cells[idx].get_text(separator=" ", strip=True).replace("\xa0", " ").strip()

            name = cell("name")
            if not name or len(name) < 2:
                continue

            # Skip rows that look like sub-headers
            if name.lower() in ("constituent fund", "fund name", "name"):
                continue

            # Find detail link: last <a> in the row, or any link in a "Details" cell
            detail_url = None
            for c in reversed(cells):
                a_tag = c.find("a", href=True)
                if a_tag:
                    href = a_tag["href"].strip()
                    if href and href != "#" and "javascript" not in href.lower():
                        detail_url = urljoin(LIST_URL, href)
                        break

            annual = {}
            for col_key, ci in col.items():
                if re.fullmatch(r"20\d\d", col_key):
                    val = parse_float(cell(col_key))
                    if val is not None:
                        annual[col_key] = val

            raw_category = cell("type")
            category = CATEGORY_MAP.get(raw_category.lower(), raw_category)

            fund = {
                "name":       name,
                "provider":   cell("trustee"),
                "scheme":     cell("scheme"),
                "category":   category or "股票基金",
                "risk_raw":   cell("risk"),
                "fundSize":   parse_float(cell("size")),
                "detail_url": detail_url,
                "annual":     annual,
            }
            funds.append(fund)

        if funds:
            log.info("Parsed %d funds from table[%d]", len(funds), tbl_idx)
            break  # Use first table that yielded funds

    return funds


# ---------------------------------------------------------------------------
# Step 2: Parse detail page for period-based returns
# ---------------------------------------------------------------------------

def parse_detail_page(html: str, fund_name: str = "") -> dict:
    """
    Parse a fund detail page to extract period-based returns.
    Looks for a table with rows like:  "1 Week | 0.23%"
    Returns dict: {"oneWeek": 0.23, "oneMonth": 1.5, ...}
    """
    soup = BeautifulSoup(html, "lxml")
    returns = {}

    for tbl in soup.find_all("table"):
        for row in tbl.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            label = cells[0].get_text(strip=True).lower()

            # Find first cell with a numeric/% value
            val = None
            for c in cells[1:]:
                txt = c.get_text(strip=True)
                if txt and (
                    "%" in txt
                    or re.search(r"-?\d+\.\d+", txt)
                    or re.search(r"-?\d+", txt)
                ):
                    val = parse_float(txt)
                    if val is not None:
                        break

            if val is None:
                continue

            for period_key, patterns in PERIOD_PATTERNS:
                if period_key not in returns:
                    if any(re.search(p, label, re.I) for p in patterns):
                        returns[period_key] = val
                        break

    if returns:
        log.info("  %s -> periods: %s", fund_name[:35], list(returns.keys()))
    else:
        soup2 = BeautifulSoup(html, "lxml")
        log.warning("  %s -> no period returns found", fund_name[:35])
        log.info("  Detail page title: %s",
                 soup2.title.string.strip() if soup2.title else "N/A")
        all_tbls = soup2.find_all("table")
        log.info("  Tables: %d", len(all_tbls))
        for ti, tbl in enumerate(all_tbls[:3]):
            rows = tbl.find_all("tr")
            for ri, row in enumerate(rows[:4]):
                cells = row.find_all(["td", "th"])
                log.info("    tbl[%d] row[%d]: %s",
                         ti, ri, [c.get_text(strip=True)[:20] for c in cells[:5]])

    return returns


# ---------------------------------------------------------------------------
# Step 3: Derive fallback period returns from annual data
# ---------------------------------------------------------------------------

def derive_returns(annual: dict, fetched: dict) -> dict:
    """
    Fill in missing period returns using annual calendar year data.
    """
    r = dict(fetched)  # start with whatever we fetched

    years_sorted = sorted(annual.keys(), reverse=True)  # ["2025","2024",...]

    # oneYear: use most recent full-year return
    if "oneYear" not in r:
        for yr in ["2024", "2025", "2023"]:
            if yr in annual:
                r["oneYear"] = annual[yr]
                break

    # threeYears: cumulative compound of last 3 annual returns
    if "threeYears" not in r:
        ys = years_sorted[:3]
        if len(ys) >= 2:
            cum = 1.0
            for y in ys:
                cum *= 1 + annual[y] / 100
            r["threeYears"] = round((cum - 1) * 100, 2)

    # fiveYears: cumulative compound of last 5 annual returns
    if "fiveYears" not in r:
        ys = years_sorted[:5]
        if len(ys) >= 3:
            cum = 1.0
            for y in ys:
                cum *= 1 + annual[y] / 100
            r["fiveYears"] = round((cum - 1) * 100, 2)

    # Short-period fallbacks: rough fractions of oneYear
    one_yr = r.get("oneYear", 0.0)
    if "sixMonths" not in r:
        r["sixMonths"] = round(one_yr * 0.5, 2)
    if "threeMonths" not in r:
        r["threeMonths"] = round(one_yr * 0.25, 2)
    if "oneMonth" not in r:
        r["oneMonth"] = round(one_yr / 12, 2)
    if "oneWeek" not in r:
        r["oneWeek"] = round(one_yr / 52, 2)

    return r


# ---------------------------------------------------------------------------
# Step 4: Build final fund list
# ---------------------------------------------------------------------------

def build_fund_list(raw_funds: list, period_map: dict) -> list:
    """Merge list-page data with detail-page period returns."""
    funds = []

    for raw in raw_funds:
        name     = raw["name"]
        category = raw.get("category", "股票基金") or "股票基金"

        # Risk level from Risk Class column
        risk_raw = raw.get("risk_raw", "").strip()
        risk_level = None
        m = re.search(r"\d", risk_raw)
        if m:
            risk_level = int(m.group())
        if risk_level is None:
            risk_level = RISK_BY_CATEGORY.get(category, 3)
        risk_level = max(1, min(5, risk_level))

        fetched  = period_map.get(name, {})
        annual   = raw.get("annual", {})
        rets_raw = derive_returns(annual, fetched)

        returns = {
            "oneWeek":     round(float(rets_raw.get("oneWeek",     0.0)), 4),
            "oneMonth":    round(float(rets_raw.get("oneMonth",    0.0)), 4),
            "threeMonths": round(float(rets_raw.get("threeMonths", 0.0)), 4),
            "sixMonths":   round(float(rets_raw.get("sixMonths",   0.0)), 4),
            "oneYear":     round(float(rets_raw.get("oneYear",     0.0)), 4),
            "threeYears":  round(float(rets_raw.get("threeYears",  0.0)), 4),
            "fiveYears":   round(float(rets_raw.get("fiveYears",   0.0)), 4),
        }

        fund_id = "fund-" + hashlib.md5(name.encode()).hexdigest()[:6]
        fund = {
            "id":        fund_id,
            "name":      name,
            "provider":  raw.get("provider", ""),
            "category":  category,
            "riskLevel": risk_level,
            "nav":       10.0,
            "currency":  "HKD",
            "returns":   returns,
        }
        if raw.get("fundSize") is not None:
            fund["fundSize"] = raw["fundSize"]

        funds.append(fund)

    funds.sort(key=lambda f: f["returns"]["oneYear"], reverse=True)
    return funds


# ---------------------------------------------------------------------------
# Persistence helpers
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
    log.info("Saved %d funds to %s", len(funds), DATA_FILE)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=" * 60)
    log.info("MPF scraper v4  -  %s", LIST_URL)
    log.info("Output: %s", DATA_FILE)
    log.info("=" * 60)

    sess = make_session()

    # ---- Step 1: Fetch list page ----
    log.info("\n[Step 1] Fetching fund list page...")
    r = safe_get(sess, LIST_URL)
    if r is None or r.status_code != 200:
        log.error("Failed to load list page (status=%s)", r.status_code if r else "N/A")
        cached = load_cache()
        if cached:
            log.info("Keeping cached data from %s", cached.get("lastUpdatedHKT"))
        sys.exit(1)

    r.encoding = r.apparent_encoding or "utf-8"
    raw_funds = parse_list_page(r.text)

    if not raw_funds:
        log.error("No funds parsed - check page structure above")
        log.info("Keeping cached data (if any)")
        cached = load_cache()
        if cached:
            log.info("Cache: %d funds, %s", cached.get("totalFunds", 0),
                     cached.get("lastUpdatedHKT", "?"))
        sys.exit(1)

    log.info("[Step 1] Done: %d raw funds", len(raw_funds))

    # ---- Step 2: Fetch detail pages ----
    log.info("\n[Step 2] Fetching detail pages for period returns...")
    period_map: dict = {}

    # Deduplicate by URL (some funds might share a detail page)
    url_to_names: dict = {}
    for fund in raw_funds:
        url = fund.get("detail_url")
        if url:
            url_to_names.setdefault(url, []).append(fund["name"])

    log.info("Unique detail URLs: %d (capped at %d)", len(url_to_names), MAX_DETAIL_FETCHES)

    fetched_count   = 0
    period_coverage = 0

    for url, names in list(url_to_names.items())[:MAX_DETAIL_FETCHES]:
        r2 = safe_get(sess, url)
        if r2 and r2.status_code == 200:
            r2.encoding = r2.apparent_encoding or "utf-8"
            rets = parse_detail_page(r2.text, names[0])
            for n in names:
                period_map[n] = rets
            if rets:
                period_coverage += len(names)
        else:
            log.warning("  Skipping %s (status=%s)", url, r2.status_code if r2 else "N/A")

        fetched_count += 1
        if fetched_count < len(url_to_names):
            time.sleep(DETAIL_DELAY)

        if fetched_count % 50 == 0:
            log.info("  Progress: %d/%d detail pages", fetched_count, len(url_to_names))

    log.info("[Step 2] Done: fetched %d detail pages, period data for %d funds",
             fetched_count, period_coverage)

    # ---- Step 3: Build final list ----
    log.info("\n[Step 3] Building fund list...")
    funds = build_fund_list(raw_funds, period_map)

    if not funds:
        log.error("Empty fund list after merge")
        sys.exit(1)

    # ---- Step 4: Save ----
    has_real_periods = period_coverage > 0
    source = "mpfa" if has_real_periods else "mpfa_annual_only"
    note   = (
        f"Source: {LIST_URL} | "
        f"{len(funds)} funds | "
        f"period data for {period_coverage} funds"
    )
    save(funds, source, note)

    log.info("\n" + "=" * 60)
    log.info("Done!  dataSource=%s  totalFunds=%d", source, len(funds))
    log.info("=" * 60)


if __name__ == "__main__":
    main()
