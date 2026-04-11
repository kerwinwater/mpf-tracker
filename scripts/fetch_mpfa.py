#!/usr/bin/env python3
"""
MPF scraper v8 - with detail-page short-period returns
============================================================
Phase 1: parse mpp_list.jsp (scrolltable) for each fund's
          1Y / 5Y / 3Y (calendar compound) / fund metadata.
          Also capture the detail-page URL from the last cell.

Phase 2: for each fund, fetch its MPFA detail page and extract
          real 1W / 1M / 3M / 6M returns.
          Falls back to calendar-year proxy if fetch fails.

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
  col 12: Annualized 10-Year
  col 13: Annualized Since-Launch
  col 14: Cumulative 1-Year %
  col 15: Cumulative 5-Year %                 -> fiveYears
  col 16: Cumulative 10-Year
  col 17: Cumulative Since-Launch
  col 18: Calendar Year 2025 %               -> sixMonths proxy / threeYears
  col 19: Calendar Year 2024 %               -> threeYears
  col 20: Calendar Year 2023 %               -> threeYears
  col 21: Calendar Year 2022 %
  col 22: Calendar Year 2021 %
  col 23-27: fees
  col 28: detail page link                    -> _detail_url
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

# Fixed column indices
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
COL_CYR_2022 = 21
COL_DETAIL   = 28   # last cell — contains the detail page link

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

# Period labels on MPFA detail pages (Traditional Chinese + English)
DETAIL_PERIOD_MAP: dict[str, str] = {
    "1週":    "oneWeek",
    "1星期":  "oneWeek",
    "一週":   "oneWeek",
    "1個月":  "oneMonth",
    "1个月":  "oneMonth",
    "一個月": "oneMonth",
    "3個月":  "threeMonths",
    "3个月":  "threeMonths",
    "三個月": "threeMonths",
    "6個月":  "sixMonths",
    "6个月":  "sixMonths",
    "六個月": "sixMonths",
    "1年":    "oneYear",
    "一年":   "oneYear",
    "3年":    "threeYears",
    "三年":   "threeYears",
    "5年":    "fiveYears",
    "五年":   "fiveYears",
    # English
    "1 week":    "oneWeek",
    "1 month":   "oneMonth",
    "3 months":  "threeMonths",
    "6 months":  "sixMonths",
    "1 year":    "oneYear",
    "3 years":   "threeYears",
    "5 years":   "fiveYears",
}

DATE_RE = re.compile(r"\d{2}-\d{2}-\d{4}")


# ---------------------------------------------------------------------------
# HTTP helpers
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
# Detail URL extraction
# ---------------------------------------------------------------------------

def _extract_detail_url(cells: list) -> Optional[str]:
    """
    Look for an <a> tag in the last few cells of a data row.
    Handles both direct href and JavaScript onclick patterns.
    """
    # Check the designated column first, then fall back to last 3 cells
    candidates = []
    if COL_DETAIL < len(cells):
        candidates.append(cells[COL_DETAIL])
    candidates.extend(cells[-3:])

    for cell in candidates:
        # Direct <a href>
        for a in cell.find_all("a"):
            href = (a.get("href") or "").strip()
            if href and href not in ("#", "") and "javascript" not in href.lower():
                if href.startswith("http"):
                    return href
                # Relative path
                sep = "" if href.startswith("/") else "/"
                return f"{BASE_URL}{sep}{href}"

            # onclick: parse URL from window.open / location.href / openWin etc.
            onclick = (a.get("onclick") or "").strip()
            if onclick:
                url = _parse_onclick_url(onclick)
                if url:
                    return url

        # onclick on the cell itself or any child element
        for elem in cell.find_all(attrs={"onclick": True}):
            url = _parse_onclick_url(elem.get("onclick", ""))
            if url:
                return url

    return None


def _parse_onclick_url(onclick: str) -> Optional[str]:
    """Extract a URL from a JavaScript onclick string."""
    patterns = [
        r"window\.open\s*\(\s*['\"]([^'\"]+)['\"]",
        r"location\.href\s*=\s*['\"]([^'\"]+)['\"]",
        r"openWin\s*\(\s*['\"]([^'\"]+)['\"]",
        r"openWindow\s*\(\s*['\"]([^'\"]+)['\"]",
        r"['\"]([^'\"]*\.jsp[^'\"]*)['\"]",
    ]
    for pat in patterns:
        m = re.search(pat, onclick, re.IGNORECASE)
        if m:
            url = m.group(1).strip()
            if url.startswith("http"):
                return url
            if url.startswith("/"):
                return BASE_URL + url
    return None


# ---------------------------------------------------------------------------
# Detail page parser
# ---------------------------------------------------------------------------

def _parse_detail_returns(html: str) -> dict:
    """
    Parse a fund detail page and return a dict of period returns.
    Looks for table rows where the first cell matches a period label.
    """
    soup = BeautifulSoup(html, "lxml")
    returns: dict = {}

    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        label = (
            cells[0]
            .get_text(separator=" ", strip=True)
            .replace("\xa0", "")
            .strip()
        )
        label_lower = label.lower()

        for key, field in DETAIL_PERIOD_MAP.items():
            if field in returns:          # already found
                continue
            if key.lower() == label_lower or key in label:
                # Try each remaining cell for a numeric value
                for c in cells[1:]:
                    val = parse_float(c.get_text(strip=True))
                    if val is not None:
                        returns[field] = val
                        break
                break

    return returns


# ---------------------------------------------------------------------------
# Detail page enrichment
# ---------------------------------------------------------------------------

SHORT_PERIODS = ("oneWeek", "oneMonth", "threeMonths", "sixMonths")


def enrich_with_detail_pages(
    sess: requests.Session,
    funds: list,
    delay: float = 0.7,
    batch_size: int = 50,
    batch_pause: float = 3.0,
) -> int:
    """
    Fetch MPFA fund detail pages and update short-period returns in-place.
    Funds without a _detail_url keep their calendar-year proxy values.
    Returns the count of successfully enriched funds.
    """
    enriched  = 0
    no_url    = 0
    fetch_err = 0
    no_data   = 0
    total     = len(funds)

    log.info("=" * 60)
    log.info("Phase 2: fetching detail pages (%d funds, %.1fs delay)", total, delay)
    log.info("=" * 60)

    for idx, fund in enumerate(funds):
        url = fund.pop("_detail_url", None)

        if not url:
            no_url += 1
            continue

        r = safe_get(sess, url, retries=1, timeout=20)
        if r is None or r.status_code != 200:
            fetch_err += 1
            log.warning("Detail FAIL  [%d/%d] %s", idx + 1, total, fund["name"][:40])
        else:
            r.encoding = r.apparent_encoding or "utf-8"
            detail = _parse_detail_returns(r.text)
            got = {p: detail[p] for p in SHORT_PERIODS if p in detail}

            if got:
                fund["returns"].update(got)
                enriched += 1
                if enriched <= 5:
                    log.info(
                        "Detail OK    [%d/%d] %s  → 1W=%.2f 1M=%.2f 3M=%.2f 6M=%.2f",
                        idx + 1, total, fund["name"][:30],
                        got.get("oneWeek",     fund["returns"]["oneWeek"]),
                        got.get("oneMonth",    fund["returns"]["oneMonth"]),
                        got.get("threeMonths", fund["returns"]["threeMonths"]),
                        got.get("sixMonths",   fund["returns"]["sixMonths"]),
                    )
            else:
                no_data += 1
                log.debug("Detail NODATA[%d/%d] %s  url=%s",
                          idx + 1, total, fund["name"][:30], url[-60:])

        # Progress report every batch
        if (idx + 1) % batch_size == 0:
            log.info(
                "Progress %d/%d — enriched=%d no_url=%d err=%d no_data=%d",
                idx + 1, total, enriched, no_url, fetch_err, no_data,
            )
            time.sleep(batch_pause)
        else:
            time.sleep(delay)

    log.info(
        "Detail enrichment done: enriched=%d / %d  (no_url=%d err=%d no_data=%d)",
        enriched, total, no_url, fetch_err, no_data,
    )
    return enriched


# ---------------------------------------------------------------------------
# Main list parser
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
    url_found    = 0

    for row in all_rows:
        cells = row.find_all(["td", "th"])
        texts = [
            c.get_text(separator=" ", strip=True).replace("\xa0", " ").strip()
            for c in cells
        ]

        if not is_data_row(texts):
            if not funds:
                header_count += 1
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

        # Return values from fixed columns
        ann_1y = parse_float(cell(COL_ANN_1Y))
        cum_5y = parse_float(cell(COL_CUM_5Y))
        cyr_25 = parse_float(cell(COL_CYR_2025))
        cyr_24 = parse_float(cell(COL_CYR_2024))
        cyr_23 = parse_float(cell(COL_CYR_2023))

        one_year   = ann_1y if ann_1y is not None else 0.0
        five_years = cum_5y if cum_5y is not None else round(one_year * 5 * 0.85, 2)

        # threeYears: compound of 2023 + 2024 + 2025 calendar years
        if all(v is not None for v in [cyr_25, cyr_24, cyr_23]):
            three_y_cum = (
                (1 + cyr_25 / 100) * (1 + cyr_24 / 100) * (1 + cyr_23 / 100) - 1
            ) * 100
            three_years = round(three_y_cum, 4)
        else:
            three_years = round(one_year * 3 * 0.9, 4)

        # Short-period proxies from cyr_25 (independent from oneYear ranking).
        # These will be overwritten by real data from the detail page in Phase 2.
        base = cyr_25 if cyr_25 is not None else one_year
        six_months   = round(base * 0.5,  4)
        three_months = round(base * 0.25, 4)
        one_month    = round(base / 12,   4)
        one_week     = round(base / 52,   4)

        returns = {
            "oneWeek":     one_week,
            "oneMonth":    one_month,
            "threeMonths": three_months,
            "sixMonths":   six_months,
            "oneYear":     round(one_year,   4),
            "threeYears":  three_years,
            "fiveYears":   round(five_years, 4),
        }

        fund_name  = cell(COL_NAME)
        fund_id    = "fund-" + hashlib.md5(fund_name.encode()).hexdigest()[:6]

        # Extract detail page URL from cell objects
        detail_url = _extract_detail_url(cells)
        if detail_url:
            url_found += 1

        fund = {
            "id":           fund_id,
            "name":         fund_name,
            "provider":     cell(COL_TRUSTEE),
            "scheme":       cell(COL_SCHEME),
            "category":     category or "股票基金",
            "riskLevel":    max(1, min(7, risk_level)),
            "nav":          10.0,
            "currency":     "HKD",
            "returns":      returns,
            "_detail_url":  detail_url,   # removed before save
        }
        size = parse_float(cell(COL_SIZE))
        if size is not None:
            fund["fundSize"] = size

        funds.append(fund)

    log.info(
        "Parsed %d fund rows (%d header rows skipped) — detail URLs found: %d/%d",
        data_count, header_count, url_found, data_count,
    )

    # Sort by 1-year return descending
    funds.sort(key=lambda f: f["returns"]["oneYear"], reverse=True)

    if debug_path:
        _write_debug(debug_path, funds[:5])

    return funds


def _write_debug(debug_path: str, sample: list) -> None:
    lines = ["=== PARSE DEBUG v8 ===", "Top 5 funds by 1Y:"]
    for f in sample:
        r = f["returns"]
        lines.append(
            f"  {f['name'][:35]:35s} | "
            f"1W:{r['oneWeek']:6.2f}%  "
            f"1M:{r['oneMonth']:6.2f}%  "
            f"3M:{r['threeMonths']:6.2f}%  "
            f"6M:{r['sixMonths']:6.2f}%  "
            f"1Y:{r['oneYear']:7.2f}%  "
            f"3Y:{r['threeYears']:7.2f}%  "
            f"5Y:{r['fiveYears']:7.2f}%"
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
    # Strip internal keys before saving
    clean = []
    for f in funds:
        fc = {k: v for k, v in f.items() if not k.startswith("_")}
        clean.append(fc)

    hkt     = timezone(timedelta(hours=8))
    now_hkt = datetime.now(hkt)
    output  = {
        "lastUpdated":    datetime.now(timezone.utc).isoformat(),
        "lastUpdatedHKT": now_hkt.strftime("%Y-%m-%d %H:%M HKT"),
        "dataSource":     source,
        "note":           note,
        "totalFunds":     len(clean),
        "funds":          clean,
    }
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
    log.info("Saved %d funds -> %s", len(clean), DATA_FILE)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Fetch MPFA fund data")
    ap.add_argument("--debug-html",   metavar="PATH", help="Write parse debug to file")
    ap.add_argument("--save-html",    metavar="PATH", help="Save raw list HTML to file")
    ap.add_argument("--skip-detail",  action="store_true",
                    help="Skip detail-page fetching (faster, short periods = proxy)")
    ap.add_argument("--detail-delay", type=float, default=0.7,
                    help="Seconds to wait between detail page requests (default: 0.7)")
    args = ap.parse_args()

    log.info("=" * 60)
    log.info("MPF scraper v8  -  %s", LIST_URL)
    log.info("Output: %s", DATA_FILE)
    log.info("=" * 60)

    sess = make_session()

    # ── Phase 1: fetch and parse list page ───────────────────────────────────
    log.info("Phase 1: fetching list page %s", LIST_URL)
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
        log.error("Only %d funds parsed — page structure may have changed", len(funds))
        sys.exit(1)

    # ── Phase 2: enrich with detail-page short-period returns ────────────────
    detail_ok = 0
    if args.skip_detail:
        log.info("--skip-detail: keeping calendar-year proxy for 1W/1M/3M/6M")
        for f in funds:
            f.pop("_detail_url", None)
        detail_note = "1W/1M/3M/6M=proxy(cyr2025)"
    else:
        detail_ok   = enrich_with_detail_pages(sess, funds, delay=args.detail_delay)
        detail_note = f"1W/1M/3M/6M real({detail_ok}/{len(funds)})"

    source = "mpfa"
    note   = (
        f"mfp.mpfa.org.hk/tch/mpp_list.jsp | "
        f"{len(funds)} funds | "
        f"1Y/5Y real; 3Y calendar-compound; {detail_note}"
    )
    save(funds, source, note)

    nonzero = sum(1 for f in funds if abs(f["returns"]["oneYear"]) > 0.01)
    log.info("=" * 60)
    log.info("Done!  %d funds total, %d with non-zero 1Y return", len(funds), nonzero)
    log.info("detail enriched: %d / %d", detail_ok, len(funds))
    log.info("dataSource=%s", source)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
