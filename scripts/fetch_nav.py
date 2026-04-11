#!/usr/bin/env python3
"""
Daily NAV fetcher  —  fetch_nav.py  v3
=====================================================================
Fetches today's unit prices (NAV) for all MPF funds from the MPFA
daily price page, accumulates a rolling history, then computes real
period returns from the actual price data.

Data source
-----------
  https://mfp.mpfa.org.hk/tch/fund_price.jsp   (static HTML, no JS)

Expected table columns (Traditional Chinese):
  計劃名稱 | 成分基金名稱 | 基金類別 | 單位價格 | 貨幣 | 價格日期
  Scheme   | Fund Name   | Type    | NAV     | CCY  | Date

nav_history.json layout
-----------------------
{
  "lastUpdated": "2026-04-11",
  "dates":  ["2026-04-11", "2026-04-10", ...],   ← most-recent first
  "navs": {
    "fund-xxxx": [12.34, 12.30, ...]              ← aligned to dates[]
  }
}

Period return formulas (index 0 = today, index N = N trading days ago)
----------------------------------------------------------------------
  oneWeek     ≈ index where date ≤ today − 7 cal days
  oneMonth    ≈ index where date ≤ today − 30 cal days
  threeMonths ≈ index where date ≤ today − 90 cal days
  sixMonths   ≈ index where date ≤ today − 180 cal days
  oneYear     ≈ index where date ≤ today − 365 cal days
  threeYears  ≈ index where date ≤ today − 1095 cal days
  fiveYears   ≈ index where date ≤ today − 1825 cal days

Falls back to cyr_25 proxy values from funds.json for any period that
lacks sufficient history.
"""

import argparse
import json
import logging
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
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

ROOT_DIR   = Path(__file__).parent.parent
FUNDS_FILE = ROOT_DIR / "public" / "data" / "funds.json"
NAV_FILE   = ROOT_DIR / "public" / "data" / "nav_history.json"
MAX_DAYS   = 2000   # keep ~8 years

BASE_URL   = "https://mfp.mpfa.org.hk"

PRICE_URLS = [
    f"{BASE_URL}/tch/fund_price.jsp",
    f"{BASE_URL}/eng/fund_price.jsp",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Referer":         BASE_URL + "/tch/",
}

# Number of calendar days for each period
PERIOD_DAYS = {
    "oneWeek":     7,
    "oneMonth":    30,
    "threeMonths": 90,
    "sixMonths":   180,
    "oneYear":     365,
    "threeYears":  1095,
    "fiveYears":   1825,
}


# ──────────────────────────────────────────────────────────────────────────────
# HTTP
# ──────────────────────────────────────────────────────────────────────────────

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
            log.warning("GET %d/%d %s: %s", attempt + 1, retries + 1, url, e)
            if attempt < retries:
                time.sleep(2 ** attempt)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Page parser
# ──────────────────────────────────────────────────────────────────────────────

def _parse_price(text: str) -> Optional[float]:
    t = text.replace(",", "").strip()
    try:
        v = float(t)
        return v if 0.0001 < v < 1_000_000 else None
    except ValueError:
        return None


def _parse_date(text: str) -> Optional[str]:
    """Return YYYY-MM-DD from various date formats."""
    text = text.strip()
    # DD/MM/YYYY  or  DD-MM-YYYY
    m = re.match(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    # YYYY-MM-DD  or  YYYY/MM/DD
    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", text)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    # DD MMM YYYY  e.g. "11 Apr 2026"
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if m:
        months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
                  "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
        mo = months.get(m.group(2).lower())
        if mo:
            return f"{m.group(3)}-{mo:02d}-{int(m.group(1)):02d}"
    return None


# Column-header keywords → semantic role
_NAME_KEYS = ["fund name", "constituent fund", "成分基金", "基金名稱", "fund"]
_PRICE_KEYS = ["unit price", "nav", "單位價格", "price"]
_DATE_KEYS  = ["price date", "date", "日期", "價格日期"]
_SCHEME_KEYS = ["scheme", "計劃", "計劃名稱"]


def _col_role(header: str) -> str:
    h = header.lower()
    for k in _NAME_KEYS:
        if k in h:
            return "name"
    for k in _PRICE_KEYS:
        if k in h:
            return "price"
    for k in _DATE_KEYS:
        if k in h:
            return "date"
    for k in _SCHEME_KEYS:
        if k in h:
            return "scheme"
    return "other"


def parse_price_page(html: str) -> tuple[str, dict[str, float]]:
    """
    Returns (price_date_str, {raw_fund_name: nav_price}).
    price_date_str is 'YYYY-MM-DD' (today's date if not found in page).
    """
    soup = BeautifulSoup(html, "lxml")
    page_date: Optional[str] = None
    results: dict[str, float] = {}

    # Search for the date anywhere in visible text first
    for tag in soup.find_all(string=re.compile(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}")):
        d = _parse_date(tag.strip())
        if d:
            page_date = d
            break

    # Try each table
    for tbl in soup.find_all("table"):
        rows = tbl.find_all("tr")
        if len(rows) < 2:
            continue

        # Detect header row
        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True) for c in header_cells]
        roles   = [_col_role(h) for h in headers]

        if "name" not in roles:
            continue  # not a fund table

        name_col  = roles.index("name")
        price_col = roles.index("price") if "price" in roles else None
        date_col  = roles.index("date")  if "date"  in roles else None

        # If no price column found, try last numeric column
        if price_col is None:
            price_col = len(roles) - 1

        row_count = 0
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) <= name_col:
                continue
            name = cells[name_col].get_text(strip=True)
            if not name or len(name) < 3:
                continue

            if price_col < len(cells):
                price = _parse_price(cells[price_col].get_text(strip=True))
                if price:
                    results[name] = price
                    row_count += 1

            if date_col is not None and date_col < len(cells) and page_date is None:
                d = _parse_date(cells[date_col].get_text(strip=True))
                if d:
                    page_date = d

        if row_count > 10:
            log.info("Parsed %d NAV rows (name_col=%d price_col=%d)",
                     row_count, name_col, price_col)
            break  # correct table found

    if page_date is None:
        page_date = date.today().isoformat()

    return page_date, results


# ──────────────────────────────────────────────────────────────────────────────
# Name matching
# ──────────────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[\s\u3000\u00a0]+", " ", s).strip().lower()


def build_price_lookup(raw: dict[str, float]) -> dict[str, float]:
    """Return {normalised_name: price}."""
    return {_norm(k): v for k, v in raw.items()}


def match_fund(fund_name: str, lookup: dict[str, float]) -> Optional[float]:
    norm = _norm(fund_name)
    if norm in lookup:
        return lookup[norm]
    # Substring match
    for k, v in lookup.items():
        if k in norm or norm in k:
            return v
    return None


# ──────────────────────────────────────────────────────────────────────────────
# NAV history I/O
# ──────────────────────────────────────────────────────────────────────────────

def load_history() -> dict:
    if NAV_FILE.exists():
        try:
            with open(NAV_FILE, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {"lastUpdated": "", "dates": [], "navs": {}}


def save_history(hist: dict) -> None:
    NAV_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(NAV_FILE, "w", encoding="utf-8") as fh:
        json.dump(hist, fh, ensure_ascii=False, separators=(",", ":"))
    log.info("nav_history.json saved (%d dates, %d funds)",
             len(hist["dates"]), len(hist["navs"]))


# ──────────────────────────────────────────────────────────────────────────────
# Period return calculation
# ──────────────────────────────────────────────────────────────────────────────

def compute_returns(fund_id: str, hist: dict, fallback: dict) -> dict:
    """Compute period returns from history; fall back to existing values."""
    dates = hist["dates"]  # list of "YYYY-MM-DD", most-recent first
    navs  = hist["navs"].get(fund_id, [])

    if not navs or navs[0] is None:
        return fallback

    today_nav = navs[0]
    today_str = dates[0]
    today_dt  = date.fromisoformat(today_str)

    def _pct(days: int) -> Optional[float]:
        target = today_dt - timedelta(days=days)
        # Find latest date ≤ target
        for i, d_str in enumerate(dates):
            if date.fromisoformat(d_str) <= target:
                if i < len(navs) and navs[i] is not None and navs[i] > 0:
                    return round((today_nav / navs[i] - 1) * 100, 4)
                break
        return None

    result = {}
    for key, days in PERIOD_DAYS.items():
        v = _pct(days)
        result[key] = v if v is not None else fallback.get(key, 0.0)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Fetch MPFA daily NAV and compute returns")
    ap.add_argument("--save-html", metavar="PATH",
                    help="Save raw HTML of price page for diagnosis")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse but do not write output files")
    args = ap.parse_args()

    log.info("=" * 60)
    log.info("fetch_nav.py v3  —  MPFA daily NAV  %s", PRICE_URLS[0])
    log.info("=" * 60)

    # ── Load fund list ─────────────────────────────────────────────────────────
    if not FUNDS_FILE.exists():
        log.error("funds.json not found"); sys.exit(1)

    with open(FUNDS_FILE, encoding="utf-8") as fh:
        funds_data = json.load(fh)
    funds = funds_data.get("funds", [])
    log.info("Loaded %d funds from funds.json", len(funds))

    # ── Fetch price page ───────────────────────────────────────────────────────
    sess = make_session()
    html = None
    used_url = None

    for url in PRICE_URLS:
        r = safe_get(sess, url)
        if r and r.status_code == 200:
            r.encoding = r.apparent_encoding or "utf-8"
            html = r.text
            used_url = url
            log.info("Fetched %d bytes from %s", len(html), url)
            break
        else:
            log.warning("GET %s -> %s", url,
                        r.status_code if r else "connection error")

    if html is None:
        log.error("Could not fetch any NAV price page")
        sys.exit(1)

    if args.save_html:
        Path(args.save_html).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save_html).write_text(html[:200_000], encoding="utf-8")
        log.info("Saved HTML snippet -> %s", args.save_html)

    # ── Parse today's prices ───────────────────────────────────────────────────
    price_date, raw_prices = parse_price_page(html)
    log.info("Price date: %s  |  raw rows: %d", price_date, len(raw_prices))

    if len(raw_prices) < 10:
        # Diagnostic: print page structure hints
        soup = BeautifulSoup(html, "lxml")
        tables = soup.find_all("table")
        log.warning("Only %d price rows parsed — page has %d tables",
                    len(raw_prices), len(tables))
        for i, t in enumerate(tables[:5]):
            rows = t.find_all("tr")
            if rows:
                hdrs = [c.get_text(strip=True) for c in rows[0].find_all(["th","td"])]
                log.warning("  table[%d]: %d rows, headers=%s", i, len(rows), hdrs[:8])
        log.error("Insufficient data — aborting")
        sys.exit(1)

    lookup = build_price_lookup(raw_prices)

    # ── Load existing history ──────────────────────────────────────────────────
    hist = load_history()
    dates: list = hist.get("dates", [])
    nav_store: dict = hist.get("navs", {})

    # Insert today's prices (skip if date already present)
    if price_date in dates:
        log.info("Date %s already in history — updating prices only", price_date)
        idx = dates.index(price_date)
    else:
        dates.insert(0, price_date)
        idx = 0
        # Extend every fund's array by 1 at the front
        for fid in nav_store:
            nav_store[fid].insert(0, None)

    # Trim to MAX_DAYS
    if len(dates) > MAX_DAYS:
        dates = dates[:MAX_DAYS]
        nav_store = {k: v[:MAX_DAYS] for k, v in nav_store.items()}

    matched = 0
    for fund in funds:
        fid   = fund["id"]
        price = match_fund(fund["name"], lookup)
        if price is None:
            continue
        matched += 1

        if fid not in nav_store:
            nav_store[fid] = [None] * len(dates)
        if idx < len(nav_store[fid]):
            nav_store[fid][idx] = price
        else:
            # Pad and set
            nav_store[fid] += [None] * (idx - len(nav_store[fid]) + 1)
            nav_store[fid][idx] = price

    log.info("Matched %d / %d funds to today's prices", matched, len(funds))

    hist_out = {
        "lastUpdated": price_date,
        "dates":       dates,
        "navs":        nav_store,
    }

    if not args.dry_run:
        save_history(hist_out)

    # ── Compute returns & update funds.json ────────────────────────────────────
    updated = 0
    for fund in funds:
        fid = fund["id"]
        if fid not in nav_store:
            continue
        new_ret = compute_returns(fid, hist_out, fund.get("returns", {}))
        fund["returns"] = new_ret
        fund["nav"]     = nav_store[fid][0] if nav_store[fid] else fund.get("nav", 10.0)
        updated += 1

    log.info("Updated returns for %d funds", updated)

    if not args.dry_run:
        hkt = timezone(timedelta(hours=8))
        now_hkt = datetime.now(hkt)
        funds_data["lastUpdated"]    = datetime.now(timezone.utc).isoformat()
        funds_data["lastUpdatedHKT"] = now_hkt.strftime("%Y-%m-%d %H:%M HKT")
        funds_data["note"] = (
            f"mfp.mpfa.org.hk | {len(funds)} funds | "
            f"NAV from fund_price.jsp ({price_date}) | "
            f"history: {len(dates)} days | "
            f"returns computed from daily prices"
        )
        funds.sort(key=lambda f: f["returns"]["oneYear"], reverse=True)
        funds_data["funds"] = funds

        with open(FUNDS_FILE, "w", encoding="utf-8") as fh:
            json.dump(funds_data, fh, ensure_ascii=False, indent=2)
        log.info("funds.json saved")

    log.info("Done. matched=%d updated=%d history_days=%d",
             matched, updated, len(dates))


if __name__ == "__main__":
    main()
