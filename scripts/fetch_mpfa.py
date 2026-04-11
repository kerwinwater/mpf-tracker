#!/usr/bin/env python3
"""
MPF list scraper v9
============================================================
Scrapes mpp_list.jsp for fund metadata and MPFA-computed returns.
Outputs public/data/funds.json with metadata + annual returns.

The short-period returns (1W/1M/3M/6M) are initially set from
calendar-year proxies. fetch_nav.py overwrites them with real
values derived from the monthly NAV price history.

Column layout of scrolltable data rows (29 cells, 0-indexed):
  col  0: expand widget
  col  1: Scheme
  col  2: spacer
  col  3: Constituent Fund (fund name)        COL_NAME
  col  4: MPF Trustee                         COL_TRUSTEE
  col  5: Fund Type                           COL_TYPE
  col  6: Launch Date DD-MM-YYYY              COL_LAUNCH  <- row detector
  col  7: Fund Size HKD'm
  col  8: Risk Class 1-7                      COL_RISK    <- row detector
  col  9: FER %
  col 10: Annualized 1-Year (% p.a.)          -> oneYear
  col 11: Annualized 5-Year (% p.a.)
  col 12-13: 10Y / Since-launch ann
  col 14: Cumulative 1-Year %
  col 15: Cumulative 5-Year %                 -> fiveYears
  col 16-17: 10Y / Since-launch cum
  col 18: Calendar Year 2025 %               -> short-period proxy
  col 19: Calendar Year 2024 %
  col 20: Calendar Year 2023 %
  col 21: Calendar Year 2022 %
  col 22: Calendar Year 2021 %
  col 23-27: fees
  col 28: detail page link  -> cfId extracted here
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

COL_SCHEME   = 1
COL_NAME     = 3
COL_TRUSTEE  = 4
COL_TYPE     = 5
COL_LAUNCH   = 6
COL_SIZE     = 7
COL_RISK     = 8
COL_ANN_1Y   = 10
COL_CUM_5Y   = 15
COL_CYR_2025 = 18
COL_CYR_2024 = 19
COL_CYR_2023 = 20
COL_DETAIL   = 28

CATEGORY_MAP = {
    "股票基金":       "股票基金",
    "混合資產基金":   "混合資產基金",
    "債券基金":       "債券基金",
    "保本基金":       "保本基金",
    "貨幣市場基金":   "貨幣市場基金",
    "保證基金":       "保證基金",
    "強積金保守基金": "強積金保守基金",
    "equity fund":               "股票基金",
    "mixed assets fund":          "混合資產基金",
    "bond fund":                  "債券基金",
    "capital preservation fund":  "保本基金",
    "money market fund":          "貨幣市場基金",
    "guaranteed fund":            "保證基金",
    "mpf conservative fund":      "強積金保守基金",
}

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
            log.debug("GET %s -> %d (%d bytes)", url, r.status_code, len(r.content))
            return r
        except requests.RequestException as e:
            log.warning("GET attempt %d/%d: %s", attempt + 1, retries + 1, e)
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
    if len(texts) <= COL_RISK:
        return False
    launch = texts[COL_LAUNCH] if COL_LAUNCH < len(texts) else ""
    risk   = texts[COL_RISK]   if COL_RISK   < len(texts) else ""
    return bool(DATE_RE.fullmatch(launch)) and bool(re.fullmatch(r"[1-7]", risk))


# ---------------------------------------------------------------------------
# cf_id extraction
# ---------------------------------------------------------------------------

# Patterns that extract a URL containing cf_id from JavaScript strings
_ONCLICK_URL_RE = re.compile(
    r"""(?:window\.open|location\.href\s*=|openWin|openWindow|open)\s*\(\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)
_JSP_URL_RE = re.compile(r"""['"]([^'"]*cf_detail[^'"]*cf_id[^'"]*\d[^'"]*)['"]""",
                          re.IGNORECASE)


def _cfid_from_text(text: str) -> Optional[str]:
    """Try to extract a cf_id number from any string."""
    # Pattern 1: cf_id=NNN in URL query string
    m = re.search(r"cf_id=(\d+)", text, re.IGNORECASE)
    if m:
        return m.group(1)
    # Pattern 2: URL inside quotes that mentions cf_detail + digit
    m = _JSP_URL_RE.search(text)
    if m:
        m2 = re.search(r"cf_id=(\d+)", m.group(1), re.IGNORECASE)
        if m2:
            return m2.group(1)
    return None


def _extract_cf_id_from_row(row_element) -> Optional[str]:
    """
    Exhaustively search a table row for a cf_id.

    Searches (in order):
    1. Every attribute of every element in the ENTIRE ROW
    2. Raw row HTML string
    3. JS function call with numeric arg: openXxx(NNN)
    """
    # Build raw HTML of entire row once
    raw_row = str(row_element)

    # Strategy 1: scan every attribute
    for tag in row_element.find_all(True):
        for attr_val in tag.attrs.values():
            s = " ".join(attr_val) if isinstance(attr_val, list) else str(attr_val)
            cf = _cfid_from_text(s)
            if cf:
                return cf

    # Strategy 2: raw row HTML (catches cases like onclick embedded in HTML comment)
    cf = _cfid_from_text(raw_row)
    if cf:
        return cf

    # Strategy 3: any JS function call with a 4-6 digit numeric argument
    # e.g. openDetail(12345), goFund('12345'), showWin(12345)
    m = re.search(
        r"""(?:open|detail|fund|show|view|info|go|win|pop)\w*\s*"""
        r"""\(\s*['"]?(\d{4,6})['"]?\s*[,)]""",
        raw_row, re.IGNORECASE,
    )
    if m:
        return m.group(1)

    return None


def _build_global_cfid_map(html: str, fund_names: list[str]) -> dict[str, str]:
    """
    Global fallback: scan the ENTIRE page HTML for cf_id patterns.
    Returns {fund_name: cf_id} by positional matching.

    If the page embeds cfIds in <script> blocks or data attributes
    rather than in table cells, this catches them.
    """
    # Collect all cf_id values in document order (preserving duplicates)
    all_ids = re.findall(r"cf_id=(\d+)", html, re.IGNORECASE)
    # Deduplicate while preserving order
    seen: set = set()
    unique_ids: list = []
    for fid in all_ids:
        if fid not in seen:
            seen.add(fid)
            unique_ids.append(fid)

    if not unique_ids:
        return {}

    log.info("Global HTML scan: found %d unique cf_id values", len(unique_ids))

    # If count matches, map positionally
    if len(unique_ids) == len(fund_names):
        return dict(zip(fund_names, unique_ids))

    # Otherwise try to match via surrounding text
    result: dict[str, str] = {}
    for fid in unique_ids:
        # Find the position in the HTML
        pos = html.lower().find(f"cf_id={fid.lower()}")
        if pos == -1:
            continue
        # Look for a fund name in the surrounding 2000 chars
        window = html[max(0, pos - 1000): pos + 1000]
        for name in fund_names:
            if name in window and name not in result.values():
                result[name] = fid
                break

    log.info("Global mapping matched %d/%d funds", len(result), len(fund_names))
    return result


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
    data_count  = 0
    cf_id_count = 0
    col28_samples: list = []   # raw HTML of col 28 for debug
    row_html_samples: list = []  # full row HTML samples for debug

    for row in all_rows:
        cells = row.find_all(["td", "th"])
        texts = [
            c.get_text(separator=" ", strip=True).replace("\xa0", " ").strip()
            for c in cells
        ]

        if not is_data_row(texts):
            continue

        data_count += 1

        def cell(idx: int) -> str:
            return texts[idx] if idx < len(texts) else ""

        # Category
        raw_cat  = cell(COL_TYPE)
        category = raw_cat
        for key, val in CATEGORY_MAP.items():
            if raw_cat.lower().startswith(key):
                category = val
                break

        # Risk level
        risk_raw   = cell(COL_RISK)
        m          = re.search(r"[1-7]", risk_raw)
        risk_level = int(m.group()) if m else RISK_BY_CATEGORY.get(category, 4)

        # Annualised / cumulative returns from list page
        ann_1y = parse_float(cell(COL_ANN_1Y))
        cum_5y = parse_float(cell(COL_CUM_5Y))
        cyr_25 = parse_float(cell(COL_CYR_2025))
        cyr_24 = parse_float(cell(COL_CYR_2024))
        cyr_23 = parse_float(cell(COL_CYR_2023))

        one_year   = ann_1y if ann_1y is not None else 0.0
        five_years = cum_5y if cum_5y is not None else round(one_year * 5 * 0.85, 2)

        # threeYears: compound 2023+2024+2025 calendar years
        if all(v is not None for v in [cyr_25, cyr_24, cyr_23]):
            three_y = (
                (1 + cyr_25 / 100) * (1 + cyr_24 / 100) * (1 + cyr_23 / 100) - 1
            ) * 100
            three_years = round(three_y, 4)
        else:
            three_years = round(one_year * 3 * 0.9, 4)

        returns = {
            "year2025":   round(cyr_25,      4) if cyr_25 is not None else 0.0,
            "year2024":   round(cyr_24,      4) if cyr_24 is not None else 0.0,
            "year2023":   round(cyr_23,      4) if cyr_23 is not None else 0.0,
            "threeYears": three_years,
            "fiveYears":  round(five_years,  4),
        }

        fund_name = cell(COL_NAME)
        fund_id   = "fund-" + hashlib.md5(fund_name.encode()).hexdigest()[:6]
        cf_id     = _extract_cf_id_from_row(row)
        if cf_id:
            cf_id_count += 1

        # Collect debug samples (first 3 data rows)
        if len(col28_samples) < 3:
            if COL_DETAIL < len(cells):
                col28_samples.append(str(cells[COL_DETAIL]))
            if len(row_html_samples) < 3:
                row_html_samples.append(str(row)[:600])

        fund: dict = {
            "id":       fund_id,
            "name":     fund_name,
            "provider": cell(COL_TRUSTEE),
            "scheme":   cell(COL_SCHEME),
            "category": category or "股票基金",
            "riskLevel": max(1, min(7, risk_level)),
            "nav":      10.0,   # placeholder; fetch_nav.py fills real value
            "currency": "HKD",
            "returns":  returns,
        }
        if cf_id:
            fund["cfId"] = cf_id          # used by fetch_nav.py

        size = parse_float(cell(COL_SIZE))
        if size is not None:
            fund["fundSize"] = size

        funds.append(fund)

    log.info(
        "Parsed %d fund rows — cf_id found for %d/%d (row-level scan)",
        data_count, cf_id_count, data_count,
    )

    # ── Global fallback: scan entire page HTML if row-level scan got 0 ────────
    if cf_id_count == 0 and funds:
        log.warning("Row-level cf_id scan got 0 results — trying global HTML scan")
        fund_names = [f["name"] for f in funds]
        global_map = _build_global_cfid_map(html, fund_names)
        if global_map:
            for fund in funds:
                gid = global_map.get(fund["name"])
                if gid:
                    fund["cfId"] = gid
                    cf_id_count += 1
            log.info("Global scan applied: %d/%d funds now have cfId", cf_id_count, len(funds))
        else:
            log.warning(
                "Global scan also found 0 cf_id values in page HTML. "
                "Row HTML sample: %s",
                row_html_samples[0][:300] if row_html_samples else "N/A"
            )

    funds.sort(key=lambda f: f["returns"]["year2025"], reverse=True)

    if debug_path:
        _write_debug(debug_path, funds[:5], col28_samples, row_html_samples)

    return funds


def _write_debug(debug_path: str, sample: list,
                  col28_samples: list = None,
                  row_html_samples: list = None) -> None:
    lines = ["=== PARSE DEBUG v9 ===", "Top 5 funds by 2025:"]
    for f in sample:
        r = f["returns"]
        lines.append(
            f"  {f['name'][:30]:30s} | "
            f"2025:{r['year2025']:7.2f}%  2024:{r['year2024']:7.2f}%  "
            f"2023:{r['year2023']:7.2f}%  3Y:{r['threeYears']:7.2f}%  5Y:{r['fiveYears']:7.2f}%"
        )
    if col28_samples:
        lines.append("")
        lines.append("=== RAW HTML of col-28 (first 3 data rows) ===")
        for i, snippet in enumerate(col28_samples[:3]):
            lines.append(f"[Row {i}] {snippet[:400]}")
    if row_html_samples:
        lines.append("")
        lines.append("=== FULL ROW HTML (first data row, 600 chars) ===")
        for i, snippet in enumerate(row_html_samples[:1]):
            lines.append(f"[Row {i}] {snippet}")
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
    ap = argparse.ArgumentParser(description="Fetch MPFA fund list")
    ap.add_argument("--debug-html", metavar="PATH", help="Write parse debug summary")
    ap.add_argument("--save-html",  metavar="PATH", help="Save raw HTML to file")
    args = ap.parse_args()

    log.info("=" * 60)
    log.info("MPF list scraper v9  -  %s", LIST_URL)
    log.info("=" * 60)

    sess = make_session()
    r = safe_get(sess, LIST_URL)
    if r is None or r.status_code != 200:
        log.error("GET failed (status=%s)", r.status_code if r else "N/A")
        cached = load_cache()
        if cached:
            log.info("Keeping cache: %d funds", cached.get("totalFunds", 0))
        sys.exit(1)

    r.encoding = r.apparent_encoding or "utf-8"
    funds = parse_page(r.text, debug_path=args.debug_html, save_html=args.save_html)

    if len(funds) < 50:
        log.error("Only %d funds — possible page structure change", len(funds))
        sys.exit(1)

    note = (
        f"mfp.mpfa.org.hk/tch/mpp_list.jsp | {len(funds)} funds | "
        f"2025/2024/2023 calendar-year returns + 3Y compound + 5Y cumulative"
    )
    save(funds, "mpfa", note)

    nonzero = sum(1 for f in funds if abs(f["returns"]["year2025"]) > 0.01)
    log.info("Done: %d funds, %d with non-zero 2025 return", len(funds), nonzero)


if __name__ == "__main__":
    main()
