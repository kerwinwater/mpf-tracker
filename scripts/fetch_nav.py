#!/usr/bin/env python3
"""
Period return fetcher  —  fetch_nav.py  v2
=====================================================================
Fetches real short-period returns (1W / 1M / 3M / 6M) for all MPF
funds from the MPFA prices-and-performances API.

API endpoint (POST)
-------------------
  https://mfp.mpfa.org.hk/eng/information/fund/prices_and_performances.do

Form parameters tried (in order until one works):
  period=1W   → 1-week return
  period=1M   → 1-month return
  period=3M   → 3-month return
  period=6M   → 6-month return

The response is an HTML page containing a table with columns:
  Scheme / Fund Name / Fund Type / Return (%)

The script:
  1. Fetches 4 API responses (one per short period)
  2. Parses each HTML table → {normalised_name: return_pct}
  3. Matches by fund name to the existing funds.json
  4. Overwrites returns.oneWeek / oneMonth / threeMonths / sixMonths
  5. Saves updated funds.json  (1Y / 3Y / 5Y values are left intact)

Falls back to the cyr_25 proxy values already in funds.json whenever
the API call or name match fails.
"""

import argparse
import json
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

ROOT_DIR   = Path(__file__).parent.parent
FUNDS_FILE = ROOT_DIR / "public" / "data" / "funds.json"

BASE_URL = "https://mfp.mpfa.org.hk"

# Candidate API endpoints and parameter formats to try
API_CONFIGS = [
    # (url, param_key, period_values)
    (
        f"{BASE_URL}/eng/information/fund/prices_and_performances.do",
        "period",
        {"oneWeek": "1W", "oneMonth": "1M", "threeMonths": "3M", "sixMonths": "6M"},
    ),
    (
        f"{BASE_URL}/tch/information/fund/prices_and_performances.do",
        "period",
        {"oneWeek": "1W", "oneMonth": "1M", "threeMonths": "3M", "sixMonths": "6M"},
    ),
    # Alternative parameter name
    (
        f"{BASE_URL}/eng/information/fund/prices_and_performances.do",
        "returnPeriod",
        {"oneWeek": "1W", "oneMonth": "1M", "threeMonths": "3M", "sixMonths": "6M"},
    ),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type":    "application/x-www-form-urlencoded",
    "Connection":      "keep-alive",
    "Referer":         f"{BASE_URL}/eng/information/fund/prices_and_performances.jsp",
}


# ──────────────────────────────────────────────────────────────────────────────
# HTTP
# ──────────────────────────────────────────────────────────────────────────────

def make_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update(HEADERS)
    # Prime the session / get cookies
    try:
        sess.get(f"{BASE_URL}/eng/information/fund/prices_and_performances.jsp",
                 timeout=20)
    except Exception:
        pass
    return sess


def safe_post(sess, url, data: dict, retries=2) -> Optional[requests.Response]:
    for attempt in range(retries + 1):
        try:
            r = sess.post(url, data=data, timeout=40)
            log.debug("POST %s %s -> %d (%d bytes)",
                      url, data, r.status_code, len(r.content))
            return r
        except requests.RequestException as e:
            log.warning("POST attempt %d/%d: %s", attempt + 1, retries + 1, e)
            if attempt < retries:
                time.sleep(2 ** attempt)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Name normalisation for fuzzy matching
# ──────────────────────────────────────────────────────────────────────────────

def _norm(name: str) -> str:
    """Normalise a fund name for matching (lowercase, collapse spaces)."""
    return re.sub(r"\s+", " ", name.lower().strip())


def build_name_index(funds: list) -> dict[str, dict]:
    """Return {normalised_name: fund_dict} for all funds."""
    return {_norm(f["name"]): f for f in funds}


def fuzzy_match(api_name: str, index: dict[str, dict]) -> Optional[dict]:
    """Match an API fund name to the nearest fund in index."""
    norm = _norm(api_name)

    # Exact match
    if norm in index:
        return index[norm]

    # Substring match: API name contains our name or vice-versa
    for key, fund in index.items():
        if key in norm or norm in key:
            return fund

    return None


# ──────────────────────────────────────────────────────────────────────────────
# HTML table parser
# ──────────────────────────────────────────────────────────────────────────────

def parse_float(text: str) -> Optional[float]:
    t = text.replace("%", "").replace(",", "").replace("+", "").strip()
    if t in ("N/A", "NA", "n.a.", "n/a", "-", "--", ""):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def parse_period_table(html: str) -> dict[str, float]:
    """
    Parse an MPFA prices-and-performances response.

    Returns {fund_name: return_pct}.

    The table is expected to have columns like:
      Scheme | Fund Name | Fund Type | Return (%)
    or the Chinese equivalent.  We detect the "return" column by
    looking for "%" header keywords.
    """
    soup = BeautifulSoup(html, "lxml")
    results: dict[str, float] = {}

    for tbl in soup.find_all("table"):
        headers = []
        header_row = tbl.find("tr")
        if not header_row:
            continue
        for th in header_row.find_all(["th", "td"]):
            headers.append(th.get_text(strip=True).lower())

        if not headers:
            continue

        # Identify name column and return column
        name_col = None
        ret_col  = None
        for i, h in enumerate(headers):
            if any(k in h for k in ["fund name", "constituent fund",
                                     "基金名稱", "成分基金"]):
                name_col = i
            if any(k in h for k in ["%", "return", "回報", "performance",
                                     "表現", "升跌"]):
                ret_col = i

        # Fallback: last column is often the return
        if name_col is None:
            for i, h in enumerate(headers):
                if any(k in h for k in ["fund", "基金", "name", "名稱"]):
                    name_col = i
                    break
        if ret_col is None and headers:
            ret_col = len(headers) - 1

        if name_col is None or ret_col is None:
            continue

        row_count = 0
        for row in tbl.find_all("tr")[1:]:  # skip header
            cells = row.find_all(["td", "th"])
            if len(cells) <= max(name_col, ret_col):
                continue
            name = cells[name_col].get_text(strip=True)
            val  = parse_float(cells[ret_col].get_text(strip=True))
            if name and val is not None:
                results[name] = val
                row_count += 1

        if row_count > 10:
            log.debug("Parsed %d rows from table (name_col=%d ret_col=%d)",
                      row_count, name_col, ret_col)
            break  # found the right table

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Probe API to find working config
# ──────────────────────────────────────────────────────────────────────────────

def probe_api(sess) -> Optional[tuple]:
    """
    Try each API config until one returns >10 fund rows for a test period.
    Returns (url, param_key, period_map) or None.
    """
    for url, param_key, period_map in API_CONFIGS:
        test_period = list(period_map.values())[1]  # try 1M
        log.info("Probing API: POST %s  %s=%s", url, param_key, test_period)
        r = safe_post(sess, url, {param_key: test_period}, retries=1)
        if r is None:
            log.warning("No response from %s", url)
            continue
        if r.status_code != 200:
            log.warning("HTTP %d from %s", r.status_code, url)
            continue
        r.encoding = r.apparent_encoding or "utf-8"
        data = parse_period_table(r.text)
        if len(data) > 10:
            log.info("API probe success: %d funds returned  (url=%s param=%s)",
                     len(data), url, param_key)
            return (url, param_key, period_map)
        log.warning("Only %d rows parsed from %s — trying next config", len(data), url)

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Fetch MPFA period returns via API")
    ap.add_argument("--delay",   type=float, default=1.0,
                    help="Seconds between API calls (default 1.0)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse but do not write funds.json")
    args = ap.parse_args()

    log.info("=" * 60)
    log.info("fetch_nav.py v2  —  MPFA period-return API")
    log.info("=" * 60)

    # ── Load fund list ─────────────────────────────────────────────────────────
    if not FUNDS_FILE.exists():
        log.error("funds.json not found: %s", FUNDS_FILE)
        sys.exit(1)

    with open(FUNDS_FILE, encoding="utf-8") as fh:
        funds_data = json.load(fh)

    funds = funds_data.get("funds", [])
    if not funds:
        log.error("No funds in funds.json")
        sys.exit(1)

    log.info("Loaded %d funds from funds.json", len(funds))
    name_index = build_name_index(funds)

    # ── Find a working API config ──────────────────────────────────────────────
    sess = make_session()
    config = probe_api(sess)

    if config is None:
        log.error(
            "All API configs failed — short-period returns will remain as "
            "cyr_25 proxies.  Check the MPFA website for API changes."
        )
        sys.exit(1)

    api_url, param_key, period_map = config

    # ── Fetch each short period ────────────────────────────────────────────────
    # Map: mpf_period_key → return_data_dict
    period_results: dict[str, dict[str, float]] = {}

    for fund_key, api_period in period_map.items():
        log.info("Fetching %s (%s=%s)...", fund_key, param_key, api_period)
        r = safe_post(sess, api_url, {param_key: api_period})
        if r is None or r.status_code != 200:
            log.warning("SKIP %s — HTTP %s", fund_key,
                        r.status_code if r else "N/A")
            continue

        r.encoding = r.apparent_encoding or "utf-8"
        data = parse_period_table(r.text)
        if not data:
            log.warning("SKIP %s — 0 rows parsed", fund_key)
            continue

        period_results[fund_key] = data
        log.info("  %s: %d fund rows", fund_key, len(data))

        if args.delay > 0:
            time.sleep(args.delay)

    if not period_results:
        log.error("No period data fetched — aborting")
        sys.exit(1)

    # ── Apply returns to funds ─────────────────────────────────────────────────
    matched_total = 0
    match_counts  = {k: 0 for k in period_results}

    for fund in funds:
        for period_key, data in period_results.items():
            # Try exact → fuzzy match
            val = data.get(fund["name"])
            if val is None:
                hit = fuzzy_match(fund["name"], {_norm(n): v for n, v in data.items()
                                                  if isinstance(n, str)})
                # hit is a float if we reuse fuzzy_match incorrectly; re-do properly
                norm_data = {_norm(n): float(v) for n, v in data.items()
                             if isinstance(v, (int, float))}
                norm_key = _norm(fund["name"])
                val = norm_data.get(norm_key)
                if val is None:
                    for k, v in norm_data.items():
                        if k in norm_key or norm_key in k:
                            val = v
                            break

            if val is not None:
                fund["returns"][period_key] = round(val, 4)
                match_counts[period_key] = match_counts.get(period_key, 0) + 1

    # Recompute 1W from 1M if 1W not available
    for fund in funds:
        if "oneWeek" not in period_results and "oneMonth" in period_results:
            om = fund["returns"].get("oneMonth", 0)
            fund["returns"]["oneWeek"] = round(
                ((1 + om / 100) ** (7 / 30) - 1) * 100, 4
            )

    matched_total = min(match_counts.values()) if match_counts else 0
    log.info("Match summary:")
    for k, v in match_counts.items():
        log.info("  %-14s  %d / %d funds matched", k, v, len(funds))

    # ── Save funds.json ────────────────────────────────────────────────────────
    if not args.dry_run:
        hkt     = timezone(timedelta(hours=8))
        now_hkt = datetime.now(hkt)
        fetched_periods = list(period_results.keys())

        funds_data["lastUpdated"]    = datetime.now(timezone.utc).isoformat()
        funds_data["lastUpdatedHKT"] = now_hkt.strftime("%Y-%m-%d %H:%M HKT")
        funds_data["note"] = (
            f"mfp.mpfa.org.hk | {len(funds)} funds | "
            f"short-period returns from API ({', '.join(fetched_periods)}); "
            f"1Y/3Y/5Y from list page"
        )

        funds.sort(key=lambda f: f["returns"]["oneYear"], reverse=True)
        funds_data["funds"] = funds

        with open(FUNDS_FILE, "w", encoding="utf-8") as fh:
            json.dump(funds_data, fh, ensure_ascii=False, indent=2)
        log.info("funds.json saved (%d funds, %d periods updated)",
                 len(funds), len(period_results))

    log.info("Done.")


if __name__ == "__main__":
    main()
