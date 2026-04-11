#!/usr/bin/env python3
"""
NAV history fetcher  —  fetch_nav.py
=====================================================================
Fetches monthly unit-price history for every fund that has a cfId in
funds.json.  Stores the history in public/data/nav_history.json and
then overwrites the returns in funds.json with values computed from
the actual price data.

Data source
-----------
  https://mfp.mpfa.org.hk/tch/cf_detail.jsp?cf_id=<N>

The page contains a "歷史單位價格" (historical unit price) section
with a table whose rows look like:
  <tr>
    <td>2026-03</td>          ← month  (YYYY-MM  or  MM/YYYY)
    <td>12.3456</td>          ← unit price
    <td>…</td>                ← possible extra cols (ignored)
  </tr>

Period return formulas  (index 0 = most-recent month)
------------------------------------------------------
  oneMonth    = nav[0]/nav[1]  - 1
  threeMonths = nav[0]/nav[3]  - 1
  sixMonths   = nav[0]/nav[6]  - 1
  oneYear     = nav[0]/nav[12] - 1
  threeYears  = nav[0]/nav[36] - 1   (cumulative, not annualised)
  fiveYears   = nav[0]/nav[60] - 1   (cumulative, not annualised)
  oneWeek     = (1 + oneMonth)^(7/30) - 1   (estimated)

Falls back to the MPFA-proxy values from funds.json whenever there
are not enough history points.

nav_history.json layout
-----------------------
{
  "lastUpdated": "2026-04",
  "months":  ["2026-04", "2026-03", ...],   # most-recent first
  "navs": {
    "fund-41a382": [12.34, 12.20, 11.95, ...]
  }
}
"""

import argparse
import json
import logging
import math
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

ROOT_DIR      = Path(__file__).parent.parent
FUNDS_FILE    = ROOT_DIR / "public" / "data" / "funds.json"
NAV_FILE      = ROOT_DIR / "public" / "data" / "nav_history.json"
MAX_MONTHS    = 72      # keep up to 6 years of history

BASE_URL      = "https://mfp.mpfa.org.hk"
DETAIL_URL    = f"{BASE_URL}/tch/cf_detail.jsp"

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

# ──────────────────────────────────────────────────────────────────────────────
# HTTP helpers
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
            return r
        except requests.RequestException as e:
            log.warning("GET attempt %d/%d %s: %s", attempt + 1, retries + 1, url, e)
            if attempt < retries:
                time.sleep(2 ** attempt)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# NAV page parser
# ──────────────────────────────────────────────────────────────────────────────

# Month normaliser: accepts "2026-03", "03/2026", "2026/03", "Mar-2026", etc.
_MONTH_PATTERNS = [
    re.compile(r"^(\d{4})[/-](\d{1,2})$"),           # 2026-03  or  2026/03
    re.compile(r"^(\d{1,2})[/-](\d{4})$"),           # 03/2026  or  03-2026
    re.compile(r"^(\d{4})年(\d{1,2})月$"),            # 2026年03月
]

def _normalise_month(raw: str) -> Optional[str]:
    raw = raw.strip()
    for pat in _MONTH_PATTERNS:
        m = pat.match(raw)
        if m:
            a, b = m.group(1), m.group(2)
            if len(a) == 4:
                return f"{a}-{int(b):02d}"
            else:
                return f"{b}-{int(a):02d}"
    return None


def _parse_nav_price(raw: str) -> Optional[float]:
    t = raw.replace(",", "").strip()
    try:
        v = float(t)
        return v if 0.001 < v < 1_000_000 else None
    except ValueError:
        return None


def parse_detail_page(html: str) -> list[tuple[str, float]]:
    """
    Returns a list of (month_str, nav_price) sorted most-recent-first.
    month_str is 'YYYY-MM'.
    """
    soup = BeautifulSoup(html, "lxml")

    results: dict[str, float] = {}

    # Strategy 1 – find every <table> and scan for rows with (month, price)
    for tbl in soup.find_all("table"):
        rows = tbl.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            texts = [c.get_text(separator=" ", strip=True).replace("\xa0", " ").strip()
                     for c in cells]
            if len(texts) < 2:
                continue
            month = _normalise_month(texts[0])
            if month is None:
                # try column 1 as month (some layouts swap)
                month = _normalise_month(texts[1])
                price_raw = texts[0] if month else None
            else:
                price_raw = texts[1]

            if month and price_raw:
                price = _parse_nav_price(price_raw)
                if price:
                    results[month] = price

    # Strategy 2 – look for "最新單位價格" label + nearby value (current month)
    for tag in soup.find_all(string=re.compile(r"最新單位價格|單位價格")):
        parent = tag.parent
        # check siblings / parent for a numeric value
        for sibling in list(parent.next_siblings)[:4]:
            raw = getattr(sibling, "get_text", lambda **_: str(sibling))(
                separator=" ", strip=True
            )
            price = _parse_nav_price(raw.replace(",", "").strip())
            if price:
                now_month = datetime.now(timezone.utc).strftime("%Y-%m")
                results.setdefault(now_month, price)
                break

    if not results:
        return []

    # Sort most-recent first
    sorted_pairs = sorted(results.items(), key=lambda kv: kv[0], reverse=True)
    return sorted_pairs


# ──────────────────────────────────────────────────────────────────────────────
# Period return calculations
# ──────────────────────────────────────────────────────────────────────────────

def compute_returns(navs: list[float], fallback: dict) -> dict:
    """
    navs: list of NAV values, index 0 = most-recent month.
    fallback: existing returns dict from funds.json (used if history too short).
    """
    def pct(n: int) -> Optional[float]:
        if len(navs) > n and navs[n] and navs[0]:
            return round((navs[0] / navs[n] - 1) * 100, 4)
        return None

    one_month    = pct(1)
    three_months = pct(3)
    six_months   = pct(6)
    one_year     = pct(12)
    three_years  = pct(36)
    five_years   = pct(60)

    # 1W estimated from 1M via compound
    if one_month is not None:
        one_week = round(((1 + one_month / 100) ** (7 / 30) - 1) * 100, 4)
    else:
        one_week = None

    # Build result, falling back to existing values where we lack history
    def use(computed, key):
        if computed is not None:
            return computed
        return fallback.get(key, 0.0)

    return {
        "oneWeek":     use(one_week,    "oneWeek"),
        "oneMonth":    use(one_month,   "oneMonth"),
        "threeMonths": use(three_months,"threeMonths"),
        "sixMonths":   use(six_months,  "sixMonths"),
        "oneYear":     use(one_year,    "oneYear"),
        "threeYears":  use(three_years, "threeYears"),
        "fiveYears":   use(five_years,  "fiveYears"),
    }


# ──────────────────────────────────────────────────────────────────────────────
# NAV history JSON I/O
# ──────────────────────────────────────────────────────────────────────────────

def load_nav_history() -> dict:
    if NAV_FILE.exists():
        try:
            with open(NAV_FILE, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {"lastUpdated": "", "months": [], "navs": {}}


def save_nav_history(history: dict) -> None:
    NAV_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(NAV_FILE, "w", encoding="utf-8") as fh:
        json.dump(history, fh, ensure_ascii=False, separators=(",", ":"))
    log.info("nav_history.json saved (%d months, %d funds)",
             len(history["months"]), len(history["navs"]))


def merge_fund_history(existing_navs: list[float],
                       existing_months: list[str],
                       new_pairs: list[tuple[str, float]],
                       master_months: list[str]) -> list[float]:
    """
    Merge new price data into the aligned master months array.
    Returns a new list aligned to master_months (None for missing months).
    """
    # Build a dict from existing data
    hist: dict[str, float] = {}
    for m, v in zip(existing_months, existing_navs):
        if v is not None:
            hist[m] = v
    # Overwrite / add new data
    for month, price in new_pairs:
        hist[month] = price
    # Align to master_months
    return [hist.get(m) for m in master_months]


# ──────────────────────────────────────────────────────────────────────────────
# Main logic
# ──────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Fetch MPFA monthly NAV history")
    ap.add_argument("--delay",    type=float, default=0.7,
                    help="Seconds between detail page requests (default 0.7)")
    ap.add_argument("--max-funds", type=int, default=0,
                    help="Stop after N funds (0 = all, for testing)")
    ap.add_argument("--dry-run",  action="store_true",
                    help="Parse but do not write output files")
    ap.add_argument("--fund-id",  metavar="FUND_ID",
                    help="Process only this fund ID (for debugging)")
    args = ap.parse_args()

    # ── Load fund list ─────────────────────────────────────────────────────────
    if not FUNDS_FILE.exists():
        log.error("funds.json not found: %s", FUNDS_FILE)
        sys.exit(1)

    with open(FUNDS_FILE, encoding="utf-8") as fh:
        funds_data = json.load(fh)

    funds = funds_data.get("funds", [])
    funds_with_cf = [f for f in funds if f.get("cfId")]
    log.info("funds.json: %d total, %d with cfId", len(funds), len(funds_with_cf))

    if not funds_with_cf:
        log.error("No funds have cfId — run fetch_mpfa.py first")
        sys.exit(1)

    if args.fund_id:
        funds_with_cf = [f for f in funds_with_cf if f["id"] == args.fund_id]
        if not funds_with_cf:
            log.error("Fund ID %s not found", args.fund_id)
            sys.exit(1)

    if args.max_funds:
        funds_with_cf = funds_with_cf[:args.max_funds]

    # ── Load existing NAV history ──────────────────────────────────────────────
    history = load_nav_history()

    # ── Build / extend master months list ─────────────────────────────────────
    # We'll collect all months from new scrapes and merge with existing
    master_months_set: set[str] = set(history.get("months", []))
    new_data: dict[str, list[tuple[str, float]]] = {}   # fund_id -> pairs

    sess = make_session()
    ok_count = 0
    fail_count = 0

    log.info("Fetching NAV history for %d funds (delay=%.1fs)...", len(funds_with_cf), args.delay)

    for i, fund in enumerate(funds_with_cf):
        cf_id     = fund["cfId"]
        fund_id   = fund["id"]
        fund_name = fund["name"]

        url = f"{DETAIL_URL}?cf_id={cf_id}"
        r   = safe_get(sess, url)

        if r is None or r.status_code != 200:
            log.warning("[%d/%d] SKIP %s (cf_id=%s, status=%s)",
                        i + 1, len(funds_with_cf), fund_name[:30], cf_id,
                        r.status_code if r else "N/A")
            fail_count += 1
        else:
            r.encoding = r.apparent_encoding or "utf-8"
            pairs = parse_detail_page(r.text)
            if pairs:
                new_data[fund_id] = pairs
                for month, _ in pairs:
                    master_months_set.add(month)
                ok_count += 1
                log.debug("[%d/%d] OK  %s — %d months", i + 1, len(funds_with_cf),
                          fund_name[:30], len(pairs))
            else:
                log.warning("[%d/%d] NODATA %s (cf_id=%s)",
                            i + 1, len(funds_with_cf), fund_name[:30], cf_id)
                fail_count += 1

        if i % 50 == 49:
            log.info("Progress: %d/%d  (ok=%d fail=%d)",
                     i + 1, len(funds_with_cf), ok_count, fail_count)

        if args.delay > 0 and i < len(funds_with_cf) - 1:
            time.sleep(args.delay)

    log.info("Fetch done: ok=%d  fail=%d", ok_count, fail_count)

    if not new_data:
        log.error("No NAV data retrieved — aborting")
        sys.exit(1)

    # ── Build master months array (sorted most-recent first, capped) ──────────
    master_months = sorted(master_months_set, reverse=True)[:MAX_MONTHS]
    log.info("Master months: %d  (%s … %s)",
             len(master_months),
             master_months[0] if master_months else "?",
             master_months[-1] if master_months else "?")

    # ── Merge histories ────────────────────────────────────────────────────────
    old_months = history.get("months", [])
    old_navs   = history.get("navs",   {})

    merged_navs: dict = {}
    for fund in funds_with_cf:
        fund_id = fund["id"]
        existing_vals   = old_navs.get(fund_id, [])
        existing_months = old_months[: len(existing_vals)]
        new_pairs       = new_data.get(fund_id, [])
        merged           = merge_fund_history(
            existing_vals, existing_months, new_pairs, master_months
        )
        # Only store if we have at least one real value
        if any(v is not None for v in merged):
            merged_navs[fund_id] = merged

    # Preserve history for funds we didn't re-fetch this run (max_funds / fund_id mode)
    if args.max_funds or args.fund_id:
        for fid, vals in old_navs.items():
            if fid not in merged_navs:
                # realign to new master_months
                hist_dict = {m: v for m, v in zip(old_months, vals) if v is not None}
                merged_navs[fid] = [hist_dict.get(m) for m in master_months]

    history_out = {
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m"),
        "months":      master_months,
        "navs":        merged_navs,
    }

    if not args.dry_run:
        save_nav_history(history_out)

    # ── Update funds.json returns ──────────────────────────────────────────────
    nav_updated = 0
    for fund in funds:
        fund_id  = fund["id"]
        nav_list = merged_navs.get(fund_id)
        if not nav_list:
            continue

        # Get non-None navs in order (most-recent first)
        clean_navs = [v for v in nav_list if v is not None]
        if not clean_navs:
            continue

        fund["nav"] = clean_navs[0]

        new_returns = compute_returns(clean_navs, fund.get("returns", {}))
        fund["returns"]    = new_returns
        fund["navSource"]  = "monthly_history"
        nav_updated += 1

    log.info("Updated returns for %d/%d funds from NAV history", nav_updated, len(funds))

    if not args.dry_run:
        hkt     = timezone(timedelta(hours=8))
        now_hkt = datetime.now(hkt)
        funds_data["lastUpdated"]    = datetime.now(timezone.utc).isoformat()
        funds_data["lastUpdatedHKT"] = now_hkt.strftime("%Y-%m-%d %H:%M HKT")
        funds_data["note"] = (
            f"mfp.mpfa.org.hk | {len(funds)} funds | "
            f"returns computed from monthly NAV history | "
            f"nav_history: {len(merged_navs)} funds × {len(master_months)} months"
        )

        # Re-sort by 1Y return descending
        funds.sort(key=lambda f: f["returns"]["oneYear"], reverse=True)
        funds_data["funds"] = funds

        with open(FUNDS_FILE, "w", encoding="utf-8") as fh:
            json.dump(funds_data, fh, ensure_ascii=False, indent=2)
        log.info("funds.json updated (%d funds)", len(funds))

    log.info("Done. nav_updated=%d  ok=%d  fail=%d", nav_updated, ok_count, fail_count)


if __name__ == "__main__":
    main()
