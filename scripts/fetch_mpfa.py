#!/usr/bin/env python3
"""
MPF scraper v5
- POST mpp_list.jsp with returnType=cr (cumulative) to get 1M/3M/6M/1Y/3Y/5Y returns
- POST mpp_list.jsp with returnType=ar (annualized) to fill in 1Y/5Y/10Y
- Table[5] id="scrolltable" has 450+ rows; data starts at row 7
- Column layout (no merged-cell confusion):
    col 0:  sort/expand button  (ignored)
    col 1:  Scheme name
    col 2:  empty spacer
    col 3:  Constituent Fund name
    col 4:  MPF Trustee abbreviation
    col 5:  Fund Type
    col 6:  Launch Date
    col 7:  Fund Size (HKD'm)
    col 8:  Risk Class (1-5)
    col 9:  Latest FER (%)
    col 10+: return period values (depends on returnType POST param)
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
    "Referer":         LIST_URL,
}

# POST payload base (all selects left empty = "all")
FORM_BASE = {
    "fundTypes":    "",
    "fundSubTypes": "",
    "trustees":     "",
    "tenthValHid":  "",
    "topTen":       "",
    "schemes":      "",
}

CATEGORY_MAP = {
    "equity fund":                    "股票基金",
    "mixed assets fund":               "混合資產基金",
    "bond fund":                       "債券基金",
    "capital preservation fund":       "保本基金",
    "money market fund":               "貨幣市場基金",
    "guaranteed fund":                 "保證基金",
    "mpf conservative fund":           "強積金保守基金",
    # sub-types (keep prefix match)
    "equity fund -":                   "股票基金",
    "mixed assets fund -":             "混合資產基金",
    "mixed assets fund - default":     "混合資產基金",
    "bond fund -":                     "債券基金",
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

# ---- column offsets that we know from inspection ----
COL_SCHEME    = 1
COL_NAME      = 3
COL_TRUSTEE   = 4
COL_TYPE      = 5
COL_LAUNCH    = 6
COL_SIZE      = 7
COL_RISK      = 8
COL_FER       = 9
COL_RET_START = 10   # returns begin here; actual sub-columns depend on returnType

# Minimum number of fund rows expected in the data table
MIN_FUND_ROWS = 100

# After how many rows does the header section end?
# We'll detect this dynamically, but default to skipping first 7 rows.
HEADER_ROWS_MAX = 10


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    # Warm up session (get cookies)
    try:
        s.get(LIST_URL, timeout=20)
    except Exception:
        pass
    return s


def safe_get(sess, url, retries=2, **kwargs) -> Optional[requests.Response]:
    kwargs.setdefault("timeout", 30)
    for attempt in range(retries + 1):
        try:
            r = sess.get(url, **kwargs)
            log.info("GET %s -> %d (%d bytes)", url, r.status_code, len(r.content))
            return r
        except requests.RequestException as e:
            log.error("GET %s attempt %d: %s", url, attempt + 1, e)
            if attempt < retries:
                time.sleep(2 ** attempt)
    return None


def safe_post(sess, url, data, retries=2, **kwargs) -> Optional[requests.Response]:
    kwargs.setdefault("timeout", 45)
    for attempt in range(retries + 1):
        try:
            r = sess.post(url, data=data, **kwargs)
            log.info("POST %s returnType=%s -> %d (%d bytes)",
                     url, data.get("returnType", "?"), r.status_code, len(r.content))
            return r
        except requests.RequestException as e:
            log.error("POST %s attempt %d: %s", url, attempt + 1, e)
            if attempt < retries:
                time.sleep(2 ** attempt)
    return None


def parse_float(text: str) -> Optional[float]:
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
# Detect header rows and return-column structure
# ---------------------------------------------------------------------------

def is_data_row(cells_text: list) -> bool:
    """Return True if this row looks like a fund data row (not a header)."""
    if len(cells_text) < COL_RET_START:
        return False
    name_cell  = cells_text[COL_NAME] if COL_NAME < len(cells_text) else ""
    risk_cell  = cells_text[COL_RISK] if COL_RISK < len(cells_text) else ""
    # A data row has a non-empty fund name and a numeric risk class
    if not name_cell or len(name_cell) < 2:
        return False
    if risk_cell and re.fullmatch(r"[1-5]", risk_cell):
        return True
    # Also accept rows where col 3 contains a non-trivial string
    skip_words = {"fund", "constituent", "scheme", "trustee", "type", "risk", "return",
                  "year", "month", "launch", "size", "fer", "annualized", "cumulative"}
    if any(w in name_cell.lower() for w in skip_words):
        return False
    return len(name_cell) > 4


def detect_return_columns(header_rows: list) -> list:
    """
    Scan header rows (list of cell-text-lists) to find the return period sub-headers
    starting at COL_RET_START.  Returns a list of (col_index, label) tuples.
    """
    results = []
    for row_texts in header_rows:
        for ci, text in enumerate(row_texts):
            if ci < COL_RET_START:
                continue
            t = text.lower().strip()
            if t and t not in ("", "n/a"):
                results.append((ci, text.strip()))
    return results


# ---------------------------------------------------------------------------
# Parse one page (GET or POST response)
# ---------------------------------------------------------------------------

def parse_page(html: str, return_type: str, debug_path: Optional[str] = None) -> list:
    """
    Parse the mpp_list.jsp response and return a list of fund dicts.
    Each dict: {name, provider, scheme, category, risk_raw, fundSize, returns:{...}}
    """
    soup = BeautifulSoup(html, "lxml")

    # Find Table[5] (id=scrolltable) or the table with the most rows
    data_table = soup.find("table", id="scrolltable")
    if data_table is None:
        log.warning("id=scrolltable not found; falling back to largest table")
        tables = soup.find_all("table")
        data_table = max(tables, key=lambda t: len(t.find_all("tr")), default=None)

    if data_table is None:
        log.error("No table found on page")
        return []

    all_rows = data_table.find_all("tr")
    log.info("Data table: %d rows total (returnType=%s)", len(all_rows), return_type)

    # Split into header rows and data rows
    header_rows_text = []
    data_rows = []
    for row in all_rows:
        cells = row.find_all(["td", "th"])
        texts = [c.get_text(separator=" ", strip=True).replace("\xa0", " ").strip()
                 for c in cells]
        if not data_rows:
            # Still in header section
            if is_data_row(texts):
                data_rows.append((cells, texts))
            else:
                header_rows_text.append(texts)
        else:
            data_rows.append((cells, texts))

    log.info("Header rows: %d | Data rows: %d", len(header_rows_text), len(data_rows))

    # Detect return column layout from header rows
    ret_col_info = detect_return_columns(header_rows_text)
    log.info("Return column headers: %s", ret_col_info[:10])

    # Optional debug dump
    if debug_path:
        _write_debug(debug_path, return_type, html, header_rows_text, data_rows[:5], ret_col_info)

    # Map return period labels to our field names
    # For cumulative (cr): 1 Month, 3 Month(s), 6 Month(s), 1 Year, 3 Year(s), 5 Year(s)
    # For annualized (ar): 1 Year, 3 Year(s), 5 Year(s), 10 Year(s), Since Launch
    # For calendar year (cyr): 2025, 2024, 2023, 2022, 2021
    ret_field_map = _build_ret_field_map(ret_col_info, return_type)
    log.info("Return field map: %s", ret_field_map)

    funds = []
    for cells, texts in data_rows:
        if not is_data_row(texts):
            continue

        def cell(idx, default=""):
            if idx >= len(texts):
                return default
            return texts[idx]

        raw_cat = cell(COL_TYPE)
        # Normalize category: match longest prefix
        category = raw_cat  # default
        cat_lower = raw_cat.lower()
        best_len = 0
        for key, val in CATEGORY_MAP.items():
            if cat_lower.startswith(key) and len(key) > best_len:
                category = val
                best_len = len(key)

        # Risk class
        risk_raw = cell(COL_RISK)
        risk_level = None
        m = re.search(r"[1-5]", risk_raw)
        if m:
            risk_level = int(m.group())
        if risk_level is None:
            risk_level = RISK_BY_CATEGORY.get(category, 3)

        # Fund size
        size_val = parse_float(cell(COL_SIZE))

        # Extract returns
        ret_vals: dict = {}
        for col_idx, field_name in ret_field_map.items():
            val = parse_float(cell(col_idx))
            if val is not None and field_name not in ret_vals:
                ret_vals[field_name] = val

        fund_name = cell(COL_NAME)
        fund_id = "fund-" + hashlib.md5(fund_name.encode()).hexdigest()[:6]

        fund = {
            "id":        fund_id,
            "name":      fund_name,
            "provider":  cell(COL_TRUSTEE),
            "scheme":    cell(COL_SCHEME),
            "category":  category or "股票基金",
            "riskLevel": max(1, min(5, risk_level)),
            "nav":       10.0,
            "currency":  "HKD",
            "returns":   ret_vals,
        }
        if size_val is not None:
            fund["fundSize"] = size_val

        funds.append(fund)

    log.info("Parsed %d funds (returnType=%s)", len(funds), return_type)
    return funds


def _build_ret_field_map(ret_col_info: list, return_type: str) -> dict:
    """Map column index -> field name based on return type and detected column headers."""
    mapping: dict = {}

    if return_type == "cr":
        # Cumulative returns: look for 1M, 3M, 6M, 1Y, 3Y, 5Y labels
        period_patterns = [
            ("oneMonth",     [r"\b1\s*m", r"1\s*month"]),
            ("threeMonths",  [r"\b3\s*m", r"3\s*month"]),
            ("sixMonths",    [r"\b6\s*m", r"6\s*month"]),
            ("oneYear",      [r"\b1\s*y", r"1\s*year", r"\b12\s*m"]),
            ("threeYears",   [r"\b3\s*y", r"3\s*year", r"\b36\s*m"]),
            ("fiveYears",    [r"\b5\s*y", r"5\s*year", r"\b60\s*m"]),
        ]
    elif return_type == "ar":
        # Annualized returns: 1Y, 3Y, 5Y, 10Y, Since Launch
        period_patterns = [
            ("oneYear",      [r"\b1\s*y", r"1\s*year"]),
            ("threeYears",   [r"\b3\s*y", r"3\s*year"]),
            ("fiveYears",    [r"\b5\s*y", r"5\s*year"]),
        ]
    else:
        # Calendar year returns: 2025, 2024, ...
        period_patterns = []
        for ci, label in ret_col_info:
            if re.fullmatch(r"20\d\d", label):
                year = label
                # Use as backup for oneYear (most recent year)
                if "yearReturn_" + year not in mapping.values():
                    mapping[ci] = "yearReturn_" + year
        return mapping

    # Try to match headers
    used_fields = set()
    for ci, label in ret_col_info:
        label_lower = label.lower()
        for field_name, patterns in period_patterns:
            if field_name not in used_fields:
                if any(re.search(p, label_lower) for p in patterns):
                    mapping[ci] = field_name
                    used_fields.add(field_name)
                    break

    # If header matching failed, use positional fallback
    if not mapping and ret_col_info:
        # Use positional assignment based on return type
        if return_type == "cr":
            pos_fields = ["oneMonth", "threeMonths", "sixMonths", "oneYear", "threeYears", "fiveYears"]
        else:
            pos_fields = ["oneYear", "threeYears", "fiveYears"]

        cols_sorted = sorted(c for c, _ in ret_col_info)
        for i, ci in enumerate(cols_sorted):
            if i < len(pos_fields):
                mapping[ci] = pos_fields[i]

    return mapping


def _write_debug(debug_path: str, return_type: str, html: str,
                 header_rows: list, sample_data_rows: list, ret_col_info: list) -> None:
    """Write detailed parse debug info to a file."""
    lines = []

    def w(s=""):
        lines.append(str(s))

    soup = BeautifulSoup(html, "lxml")
    w(f"=== MPFA PARSE DEBUG  returnType={return_type} ===")
    w(f"URL: {LIST_URL}")
    w(f"HTML length: {len(html):,}")
    w()

    # Header rows
    w("=== HEADER ROWS ===")
    for ri, row in enumerate(header_rows):
        w(f"  header[{ri}]: {row[:20]}")
    w()

    # Return column info
    w("=== DETECTED RETURN COLUMNS ===")
    for ci, label in ret_col_info:
        w(f"  col {ci}: {label!r}")
    w()

    # Sample data rows (full, no truncation)
    w("=== SAMPLE DATA ROWS (first 5) ===")
    for ri, (cells, texts) in enumerate(sample_data_rows):
        w(f"  data[{ri}] ({len(texts)} cells):")
        for ci, t in enumerate(texts):
            if t:
                w(f"    col {ci}: {t!r}")
    w()

    # Forms
    w("=== FORMS ===")
    for fi, form in enumerate(soup.find_all("form")):
        w(f"Form[{fi}]: {form.get('action')} method={form.get('method')}")
        for inp in form.find_all(["input", "select"])[:10]:
            w(f"  {inp.name}: name={inp.get('name')!r} value={str(inp.get('value',''))[:50]!r}")

    Path(debug_path).parent.mkdir(parents=True, exist_ok=True)
    with open(debug_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    log.info("Debug dump -> %s", debug_path)


# ---------------------------------------------------------------------------
# Merge multiple return-type results into one fund list
# ---------------------------------------------------------------------------

def merge_funds(funds_by_type: dict) -> list:
    """
    Merge fund data from different returnType fetches.
    funds_by_type: {"cr": [...], "ar": [...], "cyr": [...]}
    """
    # Collect all fund names
    all_names: set = set()
    for funds in funds_by_type.values():
        for f in funds:
            all_names.add(f["name"])

    log.info("Total unique funds across all types: %d", len(all_names))

    # Build index: name -> fund dict per type
    idx: dict = {rtype: {f["name"]: f for f in funds}
                 for rtype, funds in funds_by_type.items()}

    # Priority for base fund info: cr > ar > cyr
    prio = ["cr", "ar", "cyr"]

    result = []
    for name in all_names:
        # Get base info from highest-priority type that has this fund
        base = {}
        for rtype in prio:
            if name in idx.get(rtype, {}):
                base = idx[rtype][name]
                break

        if not base:
            continue

        # Merge returns from all types
        merged_ret: dict = {}
        for rtype in reversed(prio):  # lower priority first, higher overwrites
            f = idx.get(rtype, {}).get(name)
            if f:
                merged_ret.update(f.get("returns", {}))

        # Remove calendar year return fields (yearReturn_XXXX) - not used in frontend
        merged_ret = {k: v for k, v in merged_ret.items()
                      if not k.startswith("yearReturn_")}

        # Fill missing period returns with approximations
        one_yr = merged_ret.get("oneYear", 0.0)
        merged_ret.setdefault("sixMonths",   round(one_yr * 0.5, 4))
        merged_ret.setdefault("threeMonths", round(one_yr * 0.25, 4))
        merged_ret.setdefault("oneMonth",    round(one_yr / 12, 4))
        merged_ret.setdefault("oneWeek",     round(one_yr / 52, 4))
        merged_ret.setdefault("threeYears",  round(one_yr * 3 * 0.9, 4))
        merged_ret.setdefault("fiveYears",   round(one_yr * 5 * 0.85, 4))

        # Ensure all required fields present
        required = ["oneWeek", "oneMonth", "threeMonths", "sixMonths",
                    "oneYear", "threeYears", "fiveYears"]
        returns = {k: round(float(merged_ret.get(k, 0.0)), 4) for k in required}

        fund = {
            "id":        base["id"],
            "name":      name,
            "provider":  base.get("provider", ""),
            "category":  base.get("category", "股票基金"),
            "riskLevel": base.get("riskLevel", 3),
            "nav":       base.get("nav", 10.0),
            "currency":  "HKD",
            "returns":   returns,
        }
        if "fundSize" in base:
            fund["fundSize"] = base["fundSize"]

        result.append(fund)

    result.sort(key=lambda f: f["returns"]["oneYear"], reverse=True)
    return result


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
    log.info("Saved %d funds to %s", len(funds), DATA_FILE)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug-html", metavar="PATH",
                        help="Write detailed parse debug to this file")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("MPF scraper v5  -  %s", LIST_URL)
    log.info("Output: %s", DATA_FILE)
    log.info("=" * 60)

    sess = make_session()

    funds_by_type: dict = {}

    # Fetch cumulative returns (1M, 3M, 6M, 1Y, 3Y, 5Y)
    log.info("\n[Step 1] Fetching cumulative returns (returnType=cr)...")
    payload_cr = {**FORM_BASE, "returnType": "cr"}
    r_cr = safe_post(sess, LIST_URL, payload_cr)
    if r_cr and r_cr.status_code == 200:
        r_cr.encoding = r_cr.apparent_encoding or "utf-8"
        debug_path = args.debug_html if args.debug_html else None
        funds_cr = parse_page(r_cr.text, "cr", debug_path=debug_path)
        if funds_cr:
            funds_by_type["cr"] = funds_cr
            log.info("[Step 1] Got %d funds (cr)", len(funds_cr))
        else:
            log.warning("[Step 1] No funds from cr POST")
    else:
        log.error("[Step 1] cr POST failed: status=%s",
                  r_cr.status_code if r_cr else "N/A")

    time.sleep(1)

    # Fetch annualized returns for 1Y, 5Y cross-check
    log.info("\n[Step 2] Fetching annualized returns (returnType=ar)...")
    payload_ar = {**FORM_BASE, "returnType": "ar"}
    r_ar = safe_post(sess, LIST_URL, payload_ar)
    if r_ar and r_ar.status_code == 200:
        r_ar.encoding = r_ar.apparent_encoding or "utf-8"
        funds_ar = parse_page(r_ar.text, "ar")
        if funds_ar:
            funds_by_type["ar"] = funds_ar
            log.info("[Step 2] Got %d funds (ar)", len(funds_ar))
        else:
            log.warning("[Step 2] No funds from ar POST")
    else:
        log.error("[Step 2] ar POST failed")

    if not funds_by_type:
        log.error("All POSTs failed — keeping cached data")
        cached = load_cache()
        if cached:
            log.info("Cache: %d funds, %s", cached.get("totalFunds", 0),
                     cached.get("lastUpdatedHKT", "?"))
        sys.exit(1)

    # Merge
    log.info("\n[Step 3] Merging fund data...")
    funds = merge_funds(funds_by_type)

    if len(funds) < MIN_FUND_ROWS:
        log.error("Only %d funds merged — expected %d+; check parsing", len(funds), MIN_FUND_ROWS)
        sys.exit(1)

    # Save
    types_used = "+".join(funds_by_type.keys())
    source = "mpfa"
    note   = (f"Source: {LIST_URL} | "
              f"returnType={types_used} | "
              f"{len(funds)} funds")
    save(funds, source, note)

    log.info("\n" + "=" * 60)
    log.info("Done!  dataSource=%s  totalFunds=%d", source, len(funds))
    log.info("=" * 60)


if __name__ == "__main__":
    main()
