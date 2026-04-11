#!/usr/bin/env python3
"""
fetch_nav.py  v4
=====================================================================
Two-phase strategy to get real short-period MPF returns:

Phase 1 — cfId discovery  (runs only when cf_id_map.json is missing
          or has fewer than 200 entries)
  Scan cf_detail.jsp?cf_id=1..CF_ID_MAX concurrently.
  For each HTTP-200 response, extract the fund name.
  Save to public/data/cf_id_map.json  {cf_id: fund_name}.

Phase 2 — period return fetch  (every run)
  For each cf_id in cf_id_map, fetch cf_detail.jsp and parse the
  return table (週/月 rows).  Match by name to funds.json.
  Overwrite the short-period returns in funds.json.

cf_detail.jsp URL
-----------------
  https://mfp.mpfa.org.hk/tch/cf_detail.jsp?cf_id=<N>

Expected HTML structure of the return table (Traditional Chinese):
  <table>
    <tr><td>回報</td><td>%</td>…</tr>
    <tr><td>1週</td><td>+1.23</td>…</tr>
    <tr><td>1個月</td><td>+2.34</td>…</tr>
    …
  </table>

(Actual column layout is discovered dynamically.)
"""

import argparse
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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

ROOT_DIR     = Path(__file__).parent.parent
FUNDS_FILE   = ROOT_DIR / "public" / "data" / "funds.json"
CF_MAP_FILE  = ROOT_DIR / "public" / "data" / "cf_id_map.json"

BASE_URL     = "https://mfp.mpfa.org.hk"
DETAIL_URL   = f"{BASE_URL}/tch/cf_detail.jsp"

CF_ID_MIN    = 1
CF_ID_MAX    = 2000
SCAN_WORKERS = 8          # concurrent scan workers
MAP_MIN_SIZE = 200        # re-scan if map has fewer entries than this
FETCH_DELAY  = 0.3        # seconds between phase-2 fetches

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

# Period label → returns dict key
PERIOD_MAP = {
    "1週":   "oneWeek",   "1星期": "oneWeek",   "一週":  "oneWeek",
    "1week": "oneWeek",   "1 week": "oneWeek",
    "1個月": "oneMonth",  "一個月": "oneMonth",  "1month": "oneMonth",
    "1 month": "oneMonth",
    "3個月": "threeMonths", "三個月": "threeMonths",
    "3months": "threeMonths", "3 months": "threeMonths",
    "6個月": "sixMonths",  "六個月": "sixMonths",
    "6months": "sixMonths",  "6 months": "sixMonths",
    "1年":   "oneYear",   "一年":  "oneYear",   "1year": "oneYear",
    "1 year": "oneYear",
    "3年":   "threeYears", "三年": "threeYears",
    "5年":   "fiveYears",  "五年": "fiveYears",
}

SHORT_PERIODS = {"oneWeek", "oneMonth", "threeMonths", "sixMonths"}


# ──────────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ──────────────────────────────────────────────────────────────────────────────

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _get(sess, cf_id: int, timeout=15) -> Optional[requests.Response]:
    url = f"{DETAIL_URL}?cf_id={cf_id}"
    try:
        r = sess.get(url, timeout=timeout)
        return r
    except requests.RequestException:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# HTML parsing
# ──────────────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", s).strip()


def extract_fund_name(html: str) -> Optional[str]:
    """Extract the fund name from a cf_detail.jsp page."""
    soup = BeautifulSoup(html, "lxml")

    # Strategy 1: look for <title> or <h1>/<h2> containing fund keywords
    for tag in soup.find_all(["title", "h1", "h2", "h3"]):
        t = _norm(tag.get_text())
        if len(t) > 4 and any(k in t for k in ["基金", "Fund", "fund"]):
            # strip site name suffix
            t = re.split(r"[-–|]", t)[0].strip()
            if len(t) > 4:
                return t

    # Strategy 2: first <td> or <th> in the first table that looks like a name
    for tbl in soup.find_all("table"):
        for row in tbl.find_all("tr")[:3]:
            for cell in row.find_all(["td", "th"]):
                t = _norm(cell.get_text())
                if 5 < len(t) < 80 and any(k in t for k in ["基金", "Fund"]):
                    return t

    return None


def parse_float(text: str) -> Optional[float]:
    t = text.replace("%", "").replace(",", "").replace("+", "").strip()
    if t in ("N/A", "NA", "n.a.", "n/a", "-", "--", ""):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def parse_returns(html: str) -> dict[str, float]:
    """
    Parse period returns from a cf_detail.jsp page.

    Looks for a table whose rows have (period_label, return_pct) pattern.
    Returns {period_key: float_pct}.
    """
    soup = BeautifulSoup(html, "lxml")
    results: dict[str, float] = {}

    for tbl in soup.find_all("table"):
        tbl_results: dict[str, float] = {}
        for row in tbl.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            label = _norm(cells[0].get_text()).lower()
            # Match against known period labels (try both cols 1 and last)
            period_key = None
            for raw_label, key in PERIOD_MAP.items():
                if raw_label.lower() in label:
                    period_key = key
                    break
            if period_key is None:
                continue
            # Try col 1, then last col
            for col_idx in (1, len(cells) - 1):
                val = parse_float(cells[col_idx].get_text())
                if val is not None:
                    tbl_results[period_key] = val
                    break

        if len(tbl_results) >= 2:
            results.update(tbl_results)

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1 — cfId discovery
# ──────────────────────────────────────────────────────────────────────────────

def scan_cf_ids(cf_id_range: range, workers: int = SCAN_WORKERS) -> dict[str, str]:
    """
    Concurrently probe cf_id values.
    Returns {cf_id_str: fund_name} for valid (HTTP 200) pages.
    """
    found: dict[str, str] = {}

    def probe(cf_id: int) -> tuple[int, Optional[str]]:
        sess = make_session()
        r = _get(sess, cf_id)
        if r is None or r.status_code != 200:
            return cf_id, None
        r.encoding = r.apparent_encoding or "utf-8"
        name = extract_fund_name(r.text)
        return cf_id, name

    total = len(cf_id_range)
    done  = 0
    log.info("Scanning cf_id %d–%d with %d workers …",
             cf_id_range.start, cf_id_range.stop - 1, workers)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(probe, i): i for i in cf_id_range}
        for fut in as_completed(futures):
            done += 1
            cf_id, name = fut.result()
            if name:
                found[str(cf_id)] = name
                log.info("  cfId=%-5d  %s", cf_id, name[:60])
            if done % 200 == 0:
                log.info("  Progress: %d/%d  found=%d", done, total, len(found))

    log.info("Scan complete: %d valid cfIds found out of %d probed",
             len(found), total)
    return found


# ──────────────────────────────────────────────────────────────────────────────
# Name matching
# ──────────────────────────────────────────────────────────────────────────────

def _norm_match(s: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", s.lower())


def build_fund_index(funds: list) -> dict[str, dict]:
    return {_norm_match(f["name"]): f for f in funds}


def match_to_fund(api_name: str, index: dict[str, dict]) -> Optional[dict]:
    key = _norm_match(api_name)
    if key in index:
        return index[key]
    # Substring
    for k, f in index.items():
        if k in key or key in k:
            return f
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="fetch_nav.py v4 — cfId scan + detail fetch")
    ap.add_argument("--force-scan", action="store_true",
                    help="Force re-scan even if cf_id_map.json already has data")
    ap.add_argument("--max-cf-id",  type=int, default=CF_ID_MAX)
    ap.add_argument("--workers",    type=int, default=SCAN_WORKERS)
    ap.add_argument("--delay",      type=float, default=FETCH_DELAY)
    ap.add_argument("--dry-run",    action="store_true")
    args = ap.parse_args()

    log.info("=" * 60)
    log.info("fetch_nav.py v4  —  cfId scan + period return fetch")
    log.info("=" * 60)

    # ── Load funds ─────────────────────────────────────────────────────────────
    with open(FUNDS_FILE, encoding="utf-8") as fh:
        funds_data = json.load(fh)
    funds = funds_data["funds"]
    fund_index = build_fund_index(funds)
    log.info("Loaded %d funds", len(funds))

    # ── Load / build cfId map ──────────────────────────────────────────────────
    cf_map: dict[str, str] = {}
    if CF_MAP_FILE.exists() and not args.force_scan:
        try:
            cf_map = json.loads(CF_MAP_FILE.read_text(encoding="utf-8"))
            log.info("Loaded cf_id_map.json: %d entries", len(cf_map))
        except Exception:
            cf_map = {}

    if len(cf_map) < MAP_MIN_SIZE or args.force_scan:
        log.info("Running Phase 1: cfId discovery (1–%d)", args.max_cf_id)
        new_map = scan_cf_ids(range(CF_ID_MIN, args.max_cf_id + 1), args.workers)
        cf_map.update(new_map)
        if not args.dry_run:
            CF_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
            CF_MAP_FILE.write_text(
                json.dumps(cf_map, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            log.info("cf_id_map.json saved: %d entries", len(cf_map))
    else:
        log.info("Phase 1 skipped (map has %d entries)", len(cf_map))

    if not cf_map:
        log.error("cf_id map is empty — cannot fetch returns"); sys.exit(1)

    # ── Phase 2: fetch period returns ─────────────────────────────────────────
    log.info("Phase 2: fetching period returns for %d funds", len(cf_map))
    sess     = make_session()
    matched  = 0
    enriched = 0
    no_data  = 0

    for i, (cf_id_str, map_name) in enumerate(cf_map.items()):
        r = _get(sess, int(cf_id_str))
        if r is None or r.status_code != 200:
            log.debug("SKIP cfId=%s (%s)", cf_id_str, map_name[:30])
            no_data += 1
            if args.delay:
                time.sleep(args.delay)
            continue

        r.encoding = r.apparent_encoding or "utf-8"
        returns = parse_returns(r.text)

        # Try to match to a fund
        fund = match_to_fund(map_name, fund_index)
        if fund is None:
            # Also try name extracted fresh from this page
            fresh_name = extract_fund_name(r.text)
            if fresh_name:
                fund = match_to_fund(fresh_name, fund_index)

        if fund is None:
            log.debug("No fund match for cfId=%s name=%s", cf_id_str, map_name[:40])
            no_data += 1
        else:
            matched += 1
            short = {k: v for k, v in returns.items() if k in SHORT_PERIODS}
            if short:
                fund["returns"].update(short)
                enriched += 1
                if enriched <= 5:
                    log.info("  cfId=%-5s  %-40s  1W=%.2f%%  1M=%.2f%%",
                             cf_id_str, fund["name"][:40],
                             fund["returns"].get("oneWeek", 0),
                             fund["returns"].get("oneMonth", 0))

        if i % 100 == 99:
            log.info("Phase 2 progress: %d/%d  matched=%d  enriched=%d",
                     i + 1, len(cf_map), matched, enriched)

        if args.delay:
            time.sleep(args.delay)

    log.info("Phase 2 done: matched=%d  enriched=%d  no_data=%d",
             matched, enriched, no_data)

    if enriched == 0:
        log.warning("0 funds enriched — short-period returns unchanged (proxy values kept)")

    # ── Save funds.json ────────────────────────────────────────────────────────
    if not args.dry_run:
        hkt = timezone(timedelta(hours=8))
        now_hkt = datetime.now(hkt)
        funds_data["lastUpdated"]    = datetime.now(timezone.utc).isoformat()
        funds_data["lastUpdatedHKT"] = now_hkt.strftime("%Y-%m-%d %H:%M HKT")
        funds_data["note"] = (
            f"mfp.mpfa.org.hk | {len(funds)} funds | "
            f"short-period from cf_detail.jsp ({enriched} enriched); "
            f"1Y/3Y/5Y from list page"
        )
        funds.sort(key=lambda f: f["returns"]["oneYear"], reverse=True)
        funds_data["funds"] = funds
        with open(FUNDS_FILE, "w", encoding="utf-8") as fh:
            json.dump(funds_data, fh, ensure_ascii=False, indent=2)
        log.info("funds.json saved")

    log.info("Done.")


if __name__ == "__main__":
    main()
