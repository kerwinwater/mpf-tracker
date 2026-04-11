#!/usr/bin/env python3
"""
MPF scraper v6
Strategy:
  1. GET mpp_list.jsp  (default view = annualized returns: 1Y, 5Y, 10Y, Since Launch)
  2. Optionally POST with returnType=cr for cumulative short-term returns
  3. Parse Table id=scrolltable; data rows start after header rows (detected by date pattern)
  4. Column layout is FIXED in data rows (independent of header colspan/rowspan):
       col 0:  expand/sort widget
       col 1:  Scheme
       col 2:  (empty spacer)
       col 3:  Constituent Fund (fund name)  <-- COL_NAME
       col 4:  MPF Trustee code              <-- COL_TRUSTEE
       col 5:  Fund Type                     <-- COL_TYPE
       col 6:  Launch Date  (DD-MM-YYYY)     <-- used to detect data rows
       col 7:  Fund Size (HKD'm)
       col 8:  Risk Class (1-5)              <-- COL_RISK
       col 9:  Latest FER (%)
       col 10+: return period values         <-- detected dynamically
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
    "Referer":         BASE_URL + "/",
}

FORM_BASE = {
    "fundTypes":    "",
    "fundSubTypes": "",
    "trustees":     "",
    "tenthValHid":  "",
    "topTen":       "",
    "schemes":      "",
}

CATEGORY_MAP = {
    "equity fund":               "股票基金",
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

# Fixed column offsets (true for GET and POST responses)
COL_SCHEME   = 1
COL_NAME     = 3
COL_TRUSTEE  = 4
COL_TYPE     = 5
COL_LAUNCH   = 6
COL_SIZE     = 7
COL_RISK     = 8
COL_FER      = 9
COL_RET_BASE = 10   # return values start here

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


def safe_post(sess, url, data, retries=2, **kwargs) -> Optional[requests.Response]:
    kwargs.setdefault("timeout", 45)
    for attempt in range(retries + 1):
        try:
            r = sess.post(url, data=data, **kwargs)
            log.info("POST returnType=%s -> %d (%d bytes)",
                     data.get("returnType", "?"), r.status_code, len(r.content))
            return r
        except requests.RequestException as e:
            log.error("POST attempt %d: %s", attempt + 1, e)
            if attempt < retries:
                time.sleep(2 ** attempt)
    return None


def parse_float(text: str) -> Optional[float]:
    if not text:
        return None
    t = text.replace("%", "").replace(",", "").replace("+", "").strip()
    if t in ("N/A", "NA", "-", "--", "n.a.", "n/a", ""):
        return None
    try:
        return float(t)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------------

def get_scrolltable(soup: BeautifulSoup):
    """Return the main data table (id=scrolltable or largest table)."""
    tbl = soup.find("table", id="scrolltable")
    if tbl:
        return tbl
    log.warning("id=scrolltable not found, using largest table")
    tables = soup.find_all("table")
    return max(tables, key=lambda t: len(t.find_all("tr")), default=None)


def is_data_row(texts: list) -> bool:
    """
    A data row has:
      - col 6 (COL_LAUNCH): a date in DD-MM-YYYY format
      - col 8 (COL_RISK):   a digit 1-5
    """
    if len(texts) <= COL_RISK:
        return False
    return (
        bool(DATE_RE.fullmatch(texts[COL_LAUNCH]))
        and bool(re.fullmatch(r"[1-5]", texts[COL_RISK]))
    )


def detect_return_col_map(header_rows: list, return_type: str) -> dict:
    """
    Scan header rows for period labels at col 10+.
    Returns {col_index: field_name} mapping.
    """
    # Period label -> field name
    if return_type in ("ar", "default"):
        patterns = [
            ("oneYear",    [r"\b1\s*year", r"\b1\s*y\b"]),
            ("threeYears", [r"\b3\s*year", r"\b3\s*y\b"]),
            ("fiveYears",  [r"\b5\s*year", r"\b5\s*y\b"]),
            ("tenYears",   [r"\b10\s*year", r"\b10\s*y\b"]),
        ]
    else:  # cr = cumulative
        patterns = [
            ("oneMonth",    [r"\b1\s*month", r"\b1\s*m\b"]),
            ("threeMonths", [r"\b3\s*month", r"\b3\s*m\b"]),
            ("sixMonths",   [r"\b6\s*month", r"\b6\s*m\b"]),
            ("oneYear",     [r"\b1\s*year",  r"\b1\s*y\b", r"\b12\s*m"]),
            ("threeYears",  [r"\b3\s*year",  r"\b3\s*y\b", r"\b36\s*m"]),
            ("fiveYears",   [r"\b5\s*year",  r"\b5\s*y\b", r"\b60\s*m"]),
        ]

    mapping: dict = {}
    used: set = set()
    for row_texts in header_rows:
        for ci, text in enumerate(row_texts):
            if ci < COL_RET_BASE or not text.strip():
                continue
            for field, pats in patterns:
                if field in used:
                    continue
                if any(re.search(p, text, re.I) for p in pats):
                    mapping[ci] = field
                    used.add(field)
                    break

    return mapping


def parse_table(html: str, return_type: str = "default",
                debug_path: Optional[str] = None,
                save_html: Optional[str] = None) -> list:
    """
    Parse mpp_list.jsp HTML. return_type is 'default', 'ar', or 'cr'.
    Returns list of fund dicts with {id, name, provider, category, riskLevel,
    nav, currency, returns:{...}, fundSize?}.
    """
    if save_html:
        Path(save_html).parent.mkdir(parents=True, exist_ok=True)
        with open(save_html, "w", encoding="utf-8") as fh:
            fh.write(html)
        log.info("Raw HTML saved to %s (%d bytes)", save_html, len(html))

    soup = BeautifulSoup(html, "lxml")
    tbl  = get_scrolltable(soup)
    if tbl is None:
        log.error("No table found")
        return []

    all_rows = tbl.find_all("tr")
    log.info("Table rows: %d (returnType=%s)", len(all_rows), return_type)

    header_rows: list = []
    data_cells:  list = []

    for row in all_rows:
        cells = row.find_all(["td", "th"])
        texts = [c.get_text(separator=" ", strip=True).replace("\xa0", " ").strip()
                 for c in cells]
        if is_data_row(texts):
            data_cells.append((cells, texts))
        elif not data_cells:
            header_rows.append(texts)

    log.info("Header rows: %d | Data rows: %d", len(header_rows), len(data_cells))

    if not data_cells:
        log.error("No data rows found (is_data_row never matched)")
        # Log some rows for debugging
        for ri, row in enumerate(all_rows[5:15]):
            cells = row.find_all(["td", "th"])
            texts = [c.get_text(strip=True)[:25] for c in cells]
            log.info("  row[%d]: %s", ri + 5, texts)
        return []

    # Detect return column map
    ret_map = detect_return_col_map(header_rows, return_type)
    log.info("Return col map: %s", ret_map)

    # If header-based detection failed, use positional fallback
    if not ret_map:
        log.warning("Header detection failed; trying positional fallback at col 10+")
        # Sample first 3 data rows to see how many columns there are
        sample_len = max(len(t) for _, t in data_cells[:3]) if data_cells else 0
        log.info("Max cols in first 3 data rows: %d", sample_len)
        if return_type == "cr":
            fields = ["oneMonth", "threeMonths", "sixMonths", "oneYear", "threeYears", "fiveYears"]
        else:
            fields = ["oneYear", "threeYears", "fiveYears"]
        for i, field in enumerate(fields):
            ci = COL_RET_BASE + i * 2  # every other col (empty col between each)
            if ci < sample_len:
                ret_map[ci] = field

    # Optional debug dump
    if debug_path:
        _write_debug(debug_path, return_type, header_rows, data_cells[:8], ret_map)

    # Parse data rows
    funds: list = []
    for cells, texts in data_cells:
        def cell(idx, default=""):
            return texts[idx] if idx < len(texts) else default

        fund_name = cell(COL_NAME)
        if not fund_name or len(fund_name) < 2:
            continue

        raw_cat   = cell(COL_TYPE)
        cat_lower = raw_cat.lower()
        category  = raw_cat
        for key, val in CATEGORY_MAP.items():
            if cat_lower.startswith(key):
                category = val
                break

        risk_raw   = cell(COL_RISK)
        m          = re.search(r"[1-5]", risk_raw)
        risk_level = int(m.group()) if m else RISK_BY_CATEGORY.get(category, 3)

        ret_vals: dict = {}
        for ci, field in ret_map.items():
            v = parse_float(cell(ci))
            if v is not None:
                ret_vals[field] = v

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
        size = parse_float(cell(COL_SIZE))
        if size is not None:
            fund["fundSize"] = size
        funds.append(fund)

    log.info("Parsed %d funds", len(funds))
    return funds


def _write_debug(debug_path, return_type, header_rows, sample_data, ret_map):
    lines = [f"=== PARSE DEBUG  returnType={return_type} ===", ""]
    lines.append("== HEADER ROWS ==")
    for ri, row in enumerate(header_rows):
        lines.append(f"  hrow[{ri}]: {row}")
    lines.append("")
    lines.append(f"== DETECTED RETURN COLUMNS: {ret_map} ==")
    lines.append("")
    lines.append("== FIRST DATA ROWS (ALL CELLS) ==")
    for ri, (_, texts) in enumerate(sample_data):
        lines.append(f"  data[{ri}] ({len(texts)} cells):")
        for ci, t in enumerate(texts):
            if t:
                lines.append(f"    col {ci:2d}: {t!r}")
    Path(debug_path).parent.mkdir(parents=True, exist_ok=True)
    with open(debug_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    log.info("Debug dump -> %s", debug_path)


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def merge(funds_default: list, funds_cr: list) -> list:
    """
    Merge annualized (default) and cumulative (cr) return data.
    Priority for short-term periods: cr > default.
    Priority for long-term periods: default > cr (annualized is more accurate).
    """
    by_name = {f["name"]: f for f in funds_default}

    # Overlay cr data
    for f_cr in funds_cr:
        name = f_cr["name"]
        if name in by_name:
            base = by_name[name]
            # Merge returns: cr wins for 1M/3M/6M; default wins for 1Y/3Y/5Y
            base_ret = base["returns"]
            cr_ret   = f_cr["returns"]
            for field in ["oneMonth", "threeMonths", "sixMonths"]:
                if field in cr_ret:
                    base_ret[field] = cr_ret[field]
            for field in ["oneYear", "threeYears", "fiveYears"]:
                if field not in base_ret and field in cr_ret:
                    base_ret[field] = cr_ret[field]

    # Fill missing period returns with approximations
    for fund in by_name.values():
        r   = fund["returns"]
        y1  = r.get("oneYear", 0.0)
        r.setdefault("sixMonths",   round(y1 * 0.5,       4))
        r.setdefault("threeMonths", round(y1 * 0.25,      4))
        r.setdefault("oneMonth",    round(y1 / 12,        4))
        r.setdefault("oneWeek",     round(y1 / 52,        4))
        r.setdefault("threeYears",  round(y1 * 3 * 0.9,   4))
        r.setdefault("fiveYears",   round(y1 * 5 * 0.85,  4))

        # Normalise to required set, round to 4dp
        fund["returns"] = {
            k: round(float(r.get(k, 0.0)), 4)
            for k in ["oneWeek", "oneMonth", "threeMonths", "sixMonths",
                      "oneYear", "threeYears", "fiveYears"]
        }

    result = list(by_name.values())
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
    log.info("Saved %d funds -> %s", len(funds), DATA_FILE)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug-html", metavar="PATH",
                    help="Write parse debug info to file")
    ap.add_argument("--save-html",  metavar="PATH",
                    help="Save raw page HTML to file")
    args = ap.parse_args()

    log.info("=" * 60)
    log.info("MPF scraper v6  -  %s", LIST_URL)
    log.info("Output: %s", DATA_FILE)
    log.info("=" * 60)

    sess = make_session()

    # --- Step 1: GET default page (annualized returns: 1Y, 5Y, 10Y) ---
    log.info("\n[Step 1] GET default page (annualized returns)...")
    r = safe_get(sess, LIST_URL)
    if r is None or r.status_code != 200:
        log.error("Failed to GET list page")
        sys.exit(1)
    r.encoding = r.apparent_encoding or "utf-8"

    funds_default = parse_table(
        r.text,
        return_type="default",
        debug_path=args.debug_html,
        save_html=args.save_html,
    )
    log.info("[Step 1] Parsed %d funds (default/ar)", len(funds_default))

    if not funds_default:
        log.error("No funds from default page")
        sys.exit(1)

    time.sleep(1.5)

    # --- Step 2: POST with returnType=cr (cumulative: 1M, 3M, 6M, 1Y, 3Y, 5Y) ---
    log.info("\n[Step 2] POST returnType=cr (cumulative returns)...")
    payload_cr = {**FORM_BASE, "returnType": "cr"}
    r_cr = safe_post(sess, LIST_URL, payload_cr)
    funds_cr: list = []
    if r_cr and r_cr.status_code == 200:
        r_cr.encoding = r_cr.apparent_encoding or "utf-8"
        funds_cr = parse_table(r_cr.text, return_type="cr")
        log.info("[Step 2] Parsed %d funds (cr)", len(funds_cr))
    else:
        log.warning("[Step 2] cr POST failed (status=%s); will use approximations",
                    r_cr.status_code if r_cr else "N/A")

    # --- Step 3: Merge ---
    log.info("\n[Step 3] Merging...")
    funds = merge(funds_default, funds_cr)
    log.info("[Step 3] %d funds merged", len(funds))

    if len(funds) < 50:
        log.error("Only %d funds — suspiciously low, aborting", len(funds))
        sys.exit(1)

    # --- Step 4: Save ---
    has_cr = len(funds_cr) > 0
    source = "mpfa"
    note   = (f"mfp.mpfa.org.hk/eng/mpp_list.jsp | "
              f"{len(funds)} funds | "
              f"{'annualized+cumulative' if has_cr else 'annualized (1Y approx for short periods)'}")
    save(funds, source, note)

    log.info("\n" + "=" * 60)
    log.info("Done! dataSource=%s totalFunds=%d", source, len(funds))
    log.info("=" * 60)


if __name__ == "__main__":
    main()
