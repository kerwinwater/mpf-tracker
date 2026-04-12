#!/usr/bin/env python3
"""
fetch_aastocks.py — Scrape MPF fund data from aastocks.com
Data source: aastocks.com/tc/mpf/search.aspx (re-publishes MPFA/積金局 data)

Fields fetched: name, provider, category, price, 1Y/6M/3M/1M/YTD returns, expense ratio
"""
import json
import logging
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

BASE_URL = "http://www.aastocks.com/tc/mpf/search.aspx"
START_URL = BASE_URL + "?tab=1&s=3&o=1&sp=&t=1&r=1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Referer": "http://www.aastocks.com/tc/mpf/",
}

# Header keyword → field name (checked in order, first match wins)
COLUMN_KEYWORDS: list[tuple[str, list[str]]] = [
    ("name",         ["基金名稱", "名稱", "成分基金"]),
    ("provider",     ["受託人", "保薦人", "管理公司"]),
    ("category",     ["類別", "基金類別", "類型"]),
    ("price",        ["價格", "NAV", "單位價格", "資產淨值"]),
    ("oneYear",      ["1年", "一年", "12個月"]),
    ("sixMonths",    ["6個月", "六個月", "半年"]),
    ("threeMonths",  ["3個月", "三個月", "季"]),
    ("oneMonth",     ["1個月", "一個月", "月"]),
    ("ytd",          ["本年迄今", "今年迄今", "YTD"]),
    ("expenseRatio", ["開支比率", "費用比率", "管理費"]),
]


def detect_column(text: str) -> str | None:
    t = text.strip()
    for field, keywords in COLUMN_KEYWORDS:
        if any(kw in t for kw in keywords):
            return field
    return None


def parse_number(raw: str) -> float:
    """'+1.23%' → 1.23 | '-0.5' → -0.5 | 'N/A' → 0.0"""
    v = raw.strip()
    if not v or v in ("N/A", "--", "-", "n.a.", "N.A.", "—", "－", "NA"):
        return 0.0
    v = v.replace("%", "").replace("+", "").replace(",", "").strip()
    try:
        return round(float(v), 4)
    except ValueError:
        return 0.0


def cell_text(tag) -> str:
    return tag.get_text(separator=" ", strip=True)


def fetch_soup(session: requests.Session, url: str) -> tuple[BeautifulSoup, str]:
    r = session.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
    r.raise_for_status()
    # Detect encoding — aastocks may declare ISO-8859-1 but serve UTF-8 / Big5
    if r.encoding and r.encoding.lower() in ("iso-8859-1", "windows-1252"):
        r.encoding = r.apparent_encoding or "utf-8"
    log.info("GET %s → HTTP %d (%d chars)", url, r.status_code, len(r.text))
    return BeautifulSoup(r.text, "lxml"), r.text


def get_aspnet_fields(soup: BeautifulSoup) -> dict:
    fields = {}
    for name in (
        "__VIEWSTATE",
        "__VIEWSTATEGENERATOR",
        "__EVENTVALIDATION",
        "__EVENTTARGET",
        "__EVENTARGUMENT",
    ):
        inp = soup.find("input", {"name": name})
        if inp:
            fields[name] = inp.get("value", "")
    return fields


def find_main_table(soup: BeautifulSoup):
    """Return the table with the most data rows (≥4 <td> per row)."""
    best, best_count = None, 0
    for tbl in soup.find_all("table"):
        count = sum(1 for tr in tbl.find_all("tr") if len(tr.find_all("td")) >= 4)
        if count > best_count:
            best, best_count = tbl, count
    log.info("Main table: %d data rows", best_count)
    return best


def parse_table(soup: BeautifulSoup) -> list[dict]:
    """Parse fund rows from soup → list of fund dicts."""
    funds: list[dict] = []
    tbl = find_main_table(soup)
    if not tbl:
        log.error("No suitable table found")
        return funds

    rows = tbl.find_all("tr")

    # ── Detect header row ────────────────────────────────────────────────
    col_map: dict[str, int] = {}
    header_idx = 0
    for i, row in enumerate(rows[:10]):
        cells = row.find_all(["th", "td"])
        if len(cells) < 4:
            continue
        texts = [cell_text(c) for c in cells]
        mapped = {detect_column(t): j for j, t in enumerate(texts) if detect_column(t)}
        if len(mapped) >= 3:
            col_map = mapped
            header_idx = i
            log.info("Header row %d → col_map: %s", i, col_map)
            log.info("Header texts: %s", texts)
            break

    if not col_map:
        # Fallback: fixed order used on aastocks MPF search tab=1
        log.warning("Header not detected; using fallback column order")
        col_map = {
            "name": 0, "category": 1, "price": 2,
            "oneYear": 3, "sixMonths": 4, "threeMonths": 5,
            "oneMonth": 6, "ytd": 7, "expenseRatio": 8,
        }
        # Log first 3 rows for debugging
        for row in rows[:3]:
            log.warning("  %s", [cell_text(c) for c in row.find_all(["th", "td"])])

    # ── Parse data rows ──────────────────────────────────────────────────
    def get(texts, field, default=""):
        idx = col_map.get(field)
        if idx is None or idx >= len(texts):
            return default
        return texts[idx] or default

    for row in rows[header_idx + 1:]:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        texts = [cell_text(c) for c in cells]

        name = get(texts, "name").strip()
        if not name or len(name) < 2 or name in ("-", "N/A"):
            continue

        fund: dict = {
            "id":           "",           # set after dedup
            "name":         name,
            "provider":     get(texts, "provider", ""),
            "category":     get(texts, "category", "其他"),
            "price":        parse_number(get(texts, "price", "0")),
            "expenseRatio": parse_number(get(texts, "expenseRatio", "0")),
            "returns": {
                "oneYear":     parse_number(get(texts, "oneYear",     "0")),
                "sixMonths":   parse_number(get(texts, "sixMonths",   "0")),
                "threeMonths": parse_number(get(texts, "threeMonths", "0")),
                "oneMonth":    parse_number(get(texts, "oneMonth",    "0")),
                "ytd":         parse_number(get(texts, "ytd",         "0")),
            },
        }
        funds.append(fund)

    return funds


def fetch_all_pages(session: requests.Session) -> list[dict]:
    """Fetch page 1, then follow ASP.NET PostBack pagination if present."""
    all_funds: list[dict] = []

    log.info("Fetching page 1: %s", START_URL)
    soup, html = fetch_soup(session, START_URL)
    page1 = parse_table(soup)
    log.info("Page 1: %d funds", len(page1))
    all_funds.extend(page1)

    # ── Pagination via ASP.NET PostBack ──────────────────────────────────
    aspnet = get_aspnet_fields(soup)
    postback_links = re.findall(r"__doPostBack\('([^']+)','([^']*)'\)", html)
    # Only follow numeric page jumps (e.g. event_argument = "2", "3", …)
    page_triggers = [
        (tgt, arg) for tgt, arg in postback_links
        if arg.isdigit() and int(arg) > 1
    ]
    log.info("Pagination triggers: %d", len(page_triggers))

    seen_names = {f["name"] for f in all_funds}

    for event_target, event_arg in page_triggers[:10]:   # safety cap
        log.info("PostBack page %s (target=%s)", event_arg, event_target)
        post_data = {
            **aspnet,
            "__EVENTTARGET":   event_target,
            "__EVENTARGUMENT": event_arg,
        }
        try:
            r2 = session.post(
                START_URL,
                data=post_data,
                headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            soup2 = BeautifulSoup(r2.text, "lxml")
            page_funds = parse_table(soup2)
            new = [f for f in page_funds if f["name"] not in seen_names]
            log.info("  PostBack page %s: %d funds (%d new)", event_arg, len(page_funds), len(new))
            all_funds.extend(new)
            seen_names.update(f["name"] for f in new)
        except Exception as exc:
            log.warning("  PostBack failed: %s", exc)

    return all_funds


def main() -> None:
    out_path = Path("public/data/funds.json")
    session = requests.Session()

    funds = fetch_all_pages(session)

    if not funds:
        log.error("No funds parsed — aborting")
        sys.exit(1)

    # Deduplicate by name (keep first occurrence)
    seen: set[str] = set()
    unique: list[dict] = []
    for f in funds:
        if f["name"] not in seen:
            seen.add(f["name"])
            unique.append(f)
    funds = unique
    log.info("Unique funds: %d", len(funds))

    # Sort by 1-year return descending
    funds.sort(key=lambda f: f["returns"]["oneYear"], reverse=True)

    # Assign IDs
    for i, f in enumerate(funds, 1):
        f["id"] = f"aa_{i:04d}"

    hkt = timezone(timedelta(hours=8))
    now_hkt = datetime.now(hkt)

    output = {
        "lastUpdated":    now_hkt.isoformat(),
        "lastUpdatedHKT": now_hkt.strftime("%Y-%m-%d %H:%M HKT"),
        "totalFunds":     len(funds),
        "dataSource":     "aastocks",
        "note":           "aastocks.com/tc/mpf — 數據轉載自積金局",
        "funds":          funds,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Written → %s", out_path)

    # ── Summary ──────────────────────────────────────────────────────────
    nonzero = sum(1 for f in funds if f["returns"]["oneYear"] != 0.0)
    print(f"\ntotalFunds    : {len(funds)}")
    print(f"lastUpdatedHKT: {now_hkt.strftime('%Y-%m-%d %H:%M HKT')}")
    print(f"non-zero 1Y   : {nonzero}")
    print("\nTop 5 (1Y return):")
    for f in funds[:5]:
        r = f["returns"]
        print(
            f"  {f['name'][:35]:35s}"
            f" | 1Y:{r['oneYear']:6.2f}%"
            f" 6M:{r['sixMonths']:6.2f}%"
            f" 3M:{r['threeMonths']:6.2f}%"
            f" 1M:{r['oneMonth']:6.2f}%"
            f" YTD:{r['ytd']:6.2f}%"
        )


if __name__ == "__main__":
    main()
