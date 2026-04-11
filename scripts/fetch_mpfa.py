#!/usr/bin/env python3
"""
MPF 強積金基金數據爬蟲 v2
=====================================

數據來源：積金局基金表現平台 mfp.mpfa.org.hk
目標頁面：https://mfp.mpfa.org.hk/eng/information/fund/prices_and_performances.jsp

運作流程：
1. 訪問 MPFA 績效頁面，建立 Session 取得 Cookie
2. 逐一抓取 7 個回報時段（1W/1M/3M/6M/1Y/3Y/5Y）
3. 解析 HTML 表格，動態識別欄位位置
4. 合併所有時段數據，寫入 public/data/funds.json
5. 失敗時保留快取，確保網站不中斷

使用：
    python3 scripts/fetch_mpfa.py

依賴：
    pip install requests beautifulsoup4 lxml
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

import requests
from bs4 import BeautifulSoup

# ─── 日誌設定 ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ─── 路徑設定 ─────────────────────────────────────────────────────────────────
ROOT_DIR  = Path(__file__).parent.parent
DATA_FILE = ROOT_DIR / "public" / "data" / "funds.json"   # ← 輸出到 public/ 供前端讀取

# ─── MPFA 網站設定（英文版） ──────────────────────────────────────────────────
BASE_URL  = "https://mfp.mpfa.org.hk"

# 英文版績效頁面
PERF_PAGE = f"{BASE_URL}/eng/information/fund/prices_and_performances.jsp"
PERF_API  = f"{BASE_URL}/eng/information/fund/prices_and_performances.do"

# 備用：繁體中文版（如英文版失敗）
PERF_PAGE_TCH = f"{BASE_URL}/tch/information/fund/prices_and_performances.jsp"
PERF_API_TCH  = f"{BASE_URL}/tch/information/fund/prices_and_performances.do"

# 模擬 Chrome 瀏覽器標頭
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Cache-Control":   "no-cache",
}

# 7 個回報時段（MPFA 參數 → JSON key）
PERIODS = {
    "1W": "oneWeek",
    "1M": "oneMonth",
    "3M": "threeMonths",
    "6M": "sixMonths",
    "1Y": "oneYear",
    "3Y": "threeYears",
    "5Y": "fiveYears",
}

# 類別名稱標準化（英文 → 繁中）
CATEGORY_MAP = {
    # 英文
    "Equity Fund":                "股票基金",
    "Mixed Assets Fund":          "混合資產基金",
    "Bond Fund":                  "債券基金",
    "Capital Preservation Fund":  "保本基金",
    "Money Market Fund":          "貨幣市場基金",
    "Guaranteed Fund":            "保證基金",
    "MPF Conservative Fund":      "強積金保守基金",
    # 繁中（MPFA 有時混用）
    "股票基金":       "股票基金",
    "混合資產基金":   "混合資產基金",
    "債券基金":       "債券基金",
    "保本基金":       "保本基金",
    "貨幣市場基金":   "貨幣市場基金",
    "保證基金":       "保證基金",
    "強積金保守基金": "強積金保守基金",
}

# 依類別推算風險等級
RISK_BY_CATEGORY = {
    "股票基金":       5,
    "混合資產基金":   3,
    "債券基金":       2,
    "保本基金":       1,
    "貨幣市場基金":   1,
    "保證基金":       1,
    "強積金保守基金": 1,
}


# ─── Session 管理 ─────────────────────────────────────────────────────────────

def create_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update(HEADERS)
    return sess


def init_session(sess: requests.Session, page_url: str, api_url: str) -> bool:
    """
    訪問績效頁面取得 JSESSIONID Cookie。
    MPFA 是 JSP 應用，必須先建立 session 才能 POST 查詢。
    """
    log.info(f"連接 MPFA 網站：{page_url}")
    try:
        r = sess.get(page_url, timeout=30)
        r.raise_for_status()
        cookies = list(sess.cookies.keys())
        log.info(f"✅ 連接成功 HTTP {r.status_code}，Cookies: {cookies}")
        return True
    except requests.exceptions.RequestException as e:
        log.error(f"❌ 連接失敗：{e}")
        return False


# ─── 數據抓取 ─────────────────────────────────────────────────────────────────

def fetch_period(
    sess: requests.Session,
    api_url: str,
    page_url: str,
    lang: str,
    period_code: str,
    max_retries: int = 3,
) -> Optional[str]:
    """
    POST 請求抓取指定時段的基金回報 HTML 表格。

    MPFA POST 參數：
      period    → 時段代碼 (1W/1M/3M/6M/1Y/3Y/5Y)
      sortBy    → 排序欄位（fundName / rtnPct）
      sortOrder → asc / desc
      fundType  → 基金類別（空白 = 全部）
      trusteeId → 受託人（空白 = 全部）
      pageNo    → 頁碼（1 起）
      pageSize  → 每頁筆數（設 9999 取得全部）
    """
    payload = {
        "lang":        lang,
        "sortBy":      "fundName",
        "sortOrder":   "asc",
        "period":      period_code,
        "fundType":    "",
        "trusteeId":   "",
        "pageNo":      "1",
        "pageSize":    "9999",
    }
    extra_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer":       page_url,
        "Origin":        BASE_URL,
        "X-Requested-With": "XMLHttpRequest",
    }

    for attempt in range(1, max_retries + 1):
        try:
            r = sess.post(api_url, data=payload, headers=extra_headers, timeout=45)
            r.raise_for_status()
            r.encoding = "utf-8"

            body = r.text
            if len(body) < 300:
                log.warning(f"  ⚠️  {period_code}: 回應太短 ({len(body)} bytes)，第 {attempt} 次")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                return None

            log.info(f"  ✅ {period_code}: HTTP {r.status_code}，{len(body):,} bytes")
            return body

        except requests.exceptions.Timeout:
            log.warning(f"  ⚠️  {period_code}: 逾時，第 {attempt}/{max_retries} 次")
        except requests.exceptions.RequestException as e:
            log.warning(f"  ⚠️  {period_code}: 第 {attempt}/{max_retries} 次失敗 — {e}")

        if attempt < max_retries:
            time.sleep(2 ** attempt)

    log.error(f"  ❌ {period_code}: {max_retries} 次重試後仍失敗")
    return None


# ─── HTML 解析 ────────────────────────────────────────────────────────────────

# 識別不同語言的欄位名稱
HEADER_PATTERNS = {
    "name":     [r"fund\s*name", r"基金名稱", r"name"],
    "type":     [r"fund\s*type", r"基金類別", r"類別", r"type"],
    "trustee":  [r"trustee", r"受託人", r"provider"],
    "return":   [r"return", r"回報", r"rtn\s*%", r"%"],
    "nav":      [r"nav", r"net\s*asset", r"資產淨值", r"unit\s*price"],
}


def detect_columns(headers: list[str]) -> dict[str, int]:
    """
    動態偵測表格各欄的位置。
    MPFA 網頁改版時欄位順序可能改變，此函數自動適應。
    """
    result = {}
    for col_key, patterns in HEADER_PATTERNS.items():
        for i, h in enumerate(headers):
            h_lower = h.lower().strip()
            if any(re.search(p, h_lower) for p in patterns):
                if col_key not in result:  # 取第一個匹配
                    result[col_key] = i
    return result


def parse_fund_table(html: str, period_key: str) -> dict:
    """
    解析 MPFA 回應的 HTML 表格，提取基金數據。

    策略：
    1. 找到包含基金數據的 <table>（嘗試多種選擇器）
    2. 解析 <thead> 偵測欄位位置
    3. 逐行讀取 <tbody> 的基金數據
    """
    soup = BeautifulSoup(html, "lxml")
    funds: dict = {}

    # ── 找到目標表格 ──────────────────────────────────────────────────────────
    table = None

    # 策略 1：找有 class 含 "fund" 或 "result" 的 table
    for cls_pat in [r"fund", r"result", r"list", r"table"]:
        table = soup.find("table", class_=re.compile(cls_pat, re.I))
        if table:
            break

    # 策略 2：找有 id 含 "fund" 或 "result" 的 table
    if not table:
        for id_pat in [r"fund", r"result", r"list"]:
            table = soup.find("table", id=re.compile(id_pat, re.I))
            if table:
                break

    # 策略 3：取最大的表格（行數最多）
    if not table:
        tables = soup.find_all("table")
        if tables:
            table = max(tables, key=lambda t: len(t.find_all("tr")))

    if not table:
        log.warning(f"  ⚠️  {period_key}: 找不到任何表格")
        return {}

    # ── 解析表頭 ──────────────────────────────────────────────────────────────
    thead = table.find("thead")
    header_row = thead.find("tr") if thead else table.find("tr")

    if not header_row:
        log.warning(f"  ⚠️  {period_key}: 找不到表頭")
        return {}

    raw_headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
    col_map = detect_columns(raw_headers)
    log.debug(f"  欄位對照：{col_map}（原始標頭：{raw_headers}）")

    # 最少需要名稱欄，其他可缺省
    name_col    = col_map.get("name",    0)
    type_col    = col_map.get("type",    1)
    trustee_col = col_map.get("trustee", 2)
    return_col  = col_map.get("return",  3)
    nav_col     = col_map.get("nav",    -1)

    # ── 解析數據行 ────────────────────────────────────────────────────────────
    tbody = table.find("tbody") or table
    rows  = tbody.find_all("tr")
    data_rows = [r for r in rows if r.find("td")]

    log.info(f"  📊 {period_key}: 找到 {len(data_rows)} 行數據")

    def cell(cells: list, idx: int) -> str:
        if idx < 0 or idx >= len(cells):
            return ""
        return cells[idx].get_text(separator=" ", strip=True).replace("\xa0", "").strip()

    for row in data_rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        name     = cell(cells, name_col)
        category = cell(cells, type_col)
        provider = cell(cells, trustee_col)

        # 找回報率欄：從 return_col 往後找第一個能 parse 成 float 的
        return_val = None
        for ci in range(return_col, min(return_col + 4, len(cells))):
            raw = cell(cells, ci).replace("%", "").replace(",", "").strip()
            try:
                return_val = float(raw)
                break
            except ValueError:
                continue

        if return_val is None:
            log.debug(f"    跳過（無回報數據）：{name!r}")
            continue

        if not name:
            continue

        # NAV
        nav_val = 0.0
        if nav_col >= 0:
            raw_nav = cell(cells, nav_col).replace(",", "").strip()
            try:
                nav_val = float(raw_nav)
            except ValueError:
                pass

        category_zh = CATEGORY_MAP.get(category, category) or "股票基金"

        if name not in funds:
            funds[name] = {
                "category": category_zh,
                "provider": provider,
                "nav":      nav_val,
            }
        funds[name][period_key] = return_val

    return funds


# ─── 數據合併 ─────────────────────────────────────────────────────────────────

def merge_all_periods(all_data: dict[str, dict]) -> list:
    """
    把各時段的基金數據合併成完整的基金列表。

    輸入格式：{ "oneWeek": {基金名: {...}}, "oneMonth": {基金名: {...}}, ... }
    輸出格式：[{id, name, provider, category, riskLevel, nav, returns: {...}}]
    """
    all_names: set = set()
    for period_funds in all_data.values():
        all_names.update(period_funds.keys())

    log.info(f"合併後共 {len(all_names)} 個唯一基金")

    funds = []
    for name in sorted(all_names):
        # 從任何有數據的時段取得基本資訊
        base: dict = {}
        for period_funds in all_data.values():
            if name in period_funds:
                base = period_funds[name]
                break

        category = base.get("category", "股票基金")
        provider = base.get("provider", "")
        nav      = base.get("nav", 10.0)

        # 各時段回報（缺失的設為 0）
        returns: dict = {}
        for period_key in PERIODS.values():
            val = 0.0
            for period_funds in all_data.values():
                if name in period_funds and period_key in period_funds[name]:
                    val = period_funds[name][period_key]
                    break
            returns[period_key] = round(float(val), 4)

        fund_id = f"fund-{hashlib.md5(name.encode()).hexdigest()[:6]}"

        funds.append({
            "id":        fund_id,
            "name":      name,
            "provider":  provider,
            "category":  category,
            "riskLevel": RISK_BY_CATEGORY.get(category, 3),
            "nav":       round(float(nav), 4) if nav else 10.0,
            "currency":  "HKD",
            "returns":   returns,
        })

    # 按一年回報降序排列
    funds.sort(key=lambda f: f["returns"].get("oneYear", 0), reverse=True)
    return funds


# ─── 檔案讀寫 ─────────────────────────────────────────────────────────────────

def load_cache() -> Optional[dict]:
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save(funds: list, source: str, note: str) -> None:
    hkt_tz  = timezone(timedelta(hours=8))
    now_hkt = datetime.now(hkt_tz)

    output = {
        "lastUpdated":    datetime.now(timezone.utc).isoformat(),
        "lastUpdatedHKT": now_hkt.strftime("%Y-%m-%d %H:%M HKT"),
        "dataSource":     source,
        "note":           note,
        "totalFunds":     len(funds),
        "funds":          funds,
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info(f"✅ 已寫入 {DATA_FILE}")
    log.info(f"   {len(funds)} 個基金 | 來源：{source} | {now_hkt.strftime('%Y-%m-%d %H:%M HKT')}")


# ─── 主程式 ───────────────────────────────────────────────────────────────────

def run_scraper(sess: requests.Session, page_url: str, api_url: str, lang: str) -> dict:
    """執行爬蟲，回傳各時段數據字典。"""
    all_data: dict = {}
    failed: list   = []

    for code, key in PERIODS.items():
        html = fetch_period(sess, api_url, page_url, lang, code)
        if html:
            parsed = parse_fund_table(html, key)
            if parsed:
                all_data[key] = parsed
                log.info(f"  ✅ {code}: {len(parsed)} 個基金")
            else:
                log.warning(f"  ⚠️  {code}: 解析到 0 個基金")
                failed.append(code)
        else:
            failed.append(code)

        time.sleep(1.5)  # 避免請求過於頻繁

    if failed:
        log.warning(f"失敗時段：{failed}")

    return all_data


def main():
    log.info("=" * 60)
    log.info("🚀 MPF 基金數據爬蟲 v2 啟動")
    log.info(f"   輸出檔案：{DATA_FILE}")
    log.info("=" * 60)

    sess = create_session()

    # ── 嘗試英文版 ──────────────────────────────────────────────────────────
    log.info("\n─── 嘗試英文版 MPFA ───")
    if init_session(sess, PERF_PAGE, PERF_API):
        all_data = run_scraper(sess, PERF_PAGE, PERF_API, "eng")
    else:
        all_data = {}

    # ── 如英文版失敗，嘗試繁體中文版 ────────────────────────────────────────
    if not all_data:
        log.info("\n─── 英文版失敗，嘗試繁體中文版 ───")
        sess2 = create_session()
        if init_session(sess2, PERF_PAGE_TCH, PERF_API_TCH):
            all_data = run_scraper(sess2, PERF_PAGE_TCH, PERF_API_TCH, "tch")

    # ── 評估結果 ─────────────────────────────────────────────────────────────
    if not all_data:
        log.warning("⚠️  所有版本均失敗，使用快取數據")
        cached = load_cache()
        if cached:
            log.info(f"📋 快取數據保留（{cached.get('lastUpdatedHKT', '未知時間')}）")
            sys.exit(0)
        else:
            log.error("❌ 無快取，爬取失敗")
            sys.exit(1)

    # ── 合併數據 ─────────────────────────────────────────────────────────────
    log.info(f"\n合併 {len(all_data)} 個時段的數據...")
    funds = merge_all_periods(all_data)

    if not funds:
        log.error("❌ 合併後基金列表為空")
        sys.exit(1)

    # ── 決定數據來源標籤 ──────────────────────────────────────────────────────
    total_periods = len(PERIODS)
    got_periods   = len(all_data)

    if got_periods == total_periods:
        source = "mpfa"
        note   = "數據來源：積金局基金表現平台 mfp.mpfa.org.hk（完整數據）"
    else:
        source = "mpfa_partial"
        note   = (
            f"數據來源：積金局基金表現平台 mfp.mpfa.org.hk"
            f"（{got_periods}/{total_periods} 個時段成功）"
        )

    # ── 儲存 ─────────────────────────────────────────────────────────────────
    save(funds, source, note)

    log.info("\n" + "=" * 60)
    log.info("🎉 爬蟲完成！")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
