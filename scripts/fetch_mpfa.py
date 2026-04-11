#!/usr/bin/env python3
"""
MPF 強積金基金數據爬蟲
=====================================

從積金局基金表現平台 (mfp.mpfa.org.hk) 抓取所有基金的回報數據。

運作流程：
1. 訪問 MPFA 主頁，建立 Session 並取得 Cookie
2. 逐一爬取 7 個回報時段（1週/1月/3月/6月/1年/3年/5年）
3. 解析 HTML 表格，提取基金名稱、類別、受託人、回報率
4. 合併所有時段的回報數據到同一個基金記錄
5. 寫入 data/funds.json，供 Next.js 構建時讀取
6. 如果抓取失敗，保留上次的成功數據（不覆蓋）

使用方式：
    python3 scripts/fetch_mpfa.py

依賴：
    pip install requests beautifulsoup4 lxml
"""

import json
import os
import re
import sys
import time
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ─── 設定日誌 ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ─── 路徑設定 ─────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
DATA_FILE = ROOT_DIR / "data" / "funds.json"

# ─── MPFA 網站設定 ────────────────────────────────────────────────────────────
BASE_URL = "https://mfp.mpfa.org.hk"

# 使用繁體中文版本（數據更完整）
PERF_PAGE = f"{BASE_URL}/tch/information/fund/prices_and_performances.jsp"
PERF_API  = f"{BASE_URL}/tch/information/fund/prices_and_performances.do"

# 模擬真實 Chrome 瀏覽器的標頭（避免 WAF 封鎖）
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Cache-Control": "no-cache",
}

# 7 個回報時段：MPFA 參數名稱 → 我們的 JSON key
PERIODS = {
    "1W":  "oneWeek",
    "1M":  "oneMonth",
    "3M":  "threeMonths",
    "6M":  "sixMonths",
    "1Y":  "oneYear",
    "3Y":  "threeYears",
    "5Y":  "fiveYears",
}

# 基金類別對照表（MPFA 英文 → 繁體中文）
CATEGORY_MAP = {
    "Equity Fund":                "股票基金",
    "Mixed Assets Fund":          "混合資產基金",
    "Bond Fund":                  "債券基金",
    "Capital Preservation Fund":  "保本基金",
    "Money Market Fund":          "貨幣市場基金",
    "Guaranteed Fund":            "保證基金",
    "MPF Conservative Fund":      "強積金保守基金",
    # 中文版對照
    "股票基金":                    "股票基金",
    "混合資產基金":                "混合資產基金",
    "債券基金":                    "債券基金",
    "保本基金":                    "保本基金",
    "貨幣市場基金":                "貨幣市場基金",
    "保證基金":                    "保證基金",
    "強積金保守基金":              "強積金保守基金",
}

# 風險等級對照（依基金類別推算）
RISK_BY_CATEGORY = {
    "股票基金":      5,
    "混合資產基金":  3,
    "債券基金":      2,
    "保本基金":      1,
    "貨幣市場基金":  1,
    "保證基金":      1,
    "強積金保守基金": 1,
}


# ─── Session 管理 ─────────────────────────────────────────────────────────────

def create_session() -> requests.Session:
    """建立帶有持久 Cookie 的 HTTP Session"""
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def get_session_cookie(session: requests.Session) -> bool:
    """
    步驟 1：訪問 MPFA 主頁，取得 Session Cookie
    MPFA 網站使用 JSP Session，必須先訪問主頁才能查詢數據
    """
    log.info("步驟 1：連接 MPFA 網站，取得 Session Cookie...")
    try:
        resp = session.get(PERF_PAGE, timeout=30)
        resp.raise_for_status()
        cookies = dict(session.cookies)
        log.info(f"✅ 連接成功，HTTP {resp.status_code}，Cookie: {list(cookies.keys())}")
        return True
    except requests.exceptions.Timeout:
        log.error("❌ 連接逾時（30秒）")
        return False
    except requests.exceptions.ConnectionError as e:
        log.error(f"❌ 連接失敗：{e}")
        return False
    except requests.exceptions.HTTPError as e:
        log.error(f"❌ HTTP 錯誤：{e}")
        return False


# ─── 數據抓取 ─────────────────────────────────────────────────────────────────

def fetch_period_data(
    session: requests.Session,
    period_code: str,
    retry: int = 3,
) -> Optional[str]:
    """
    步驟 2：抓取指定時段的基金回報數據

    MPFA 使用 POST 請求查詢不同時段的回報：
    - period=1W → 1週回報
    - period=1M → 1個月回報
    - period=1Y → 1年回報
    等等

    參數：
        session: 帶有 Cookie 的 HTTP Session
        period_code: 時段代碼（"1W", "1M", "3M", "6M", "1Y", "3Y", "5Y"）
        retry: 失敗重試次數

    回傳：HTML 字串，或 None（失敗時）
    """
    log.info(f"  抓取時段 {period_code} 的數據...")

    # POST 表單參數（根據 MPFA 網站的實際請求格式）
    payload = {
        "lang":        "tch",       # 繁體中文
        "sortBy":      "fundName",  # 按基金名稱排序
        "sortOrder":   "asc",
        "period":      period_code,
        "fundType":    "",          # 空白 = 全部類別
        "trusteeId":   "",          # 空白 = 全部受託人
        "pageNo":      "1",
        "pageSize":    "1000",      # 取得全部數據
    }

    headers = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer":       PERF_PAGE,
        "Origin":        BASE_URL,
    }

    for attempt in range(retry):
        try:
            resp = session.post(
                PERF_API,
                data=payload,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"

            if len(resp.text) < 500:
                log.warning(f"  ⚠️  回應內容太短 ({len(resp.text)} bytes)，可能失敗")
                if attempt < retry - 1:
                    time.sleep(2 ** attempt)
                    continue

            log.info(f"  ✅ {period_code}: HTTP {resp.status_code}，{len(resp.text):,} bytes")
            return resp.text

        except requests.exceptions.Timeout:
            log.warning(f"  ⚠️  {period_code} 第 {attempt+1} 次逾時，重試...")
            time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            log.warning(f"  ⚠️  {period_code} 第 {attempt+1} 次失敗：{e}")
            time.sleep(2 ** attempt)

    log.error(f"  ❌ {period_code} 抓取失敗（{retry} 次重試後放棄）")
    return None


# ─── HTML 解析 ────────────────────────────────────────────────────────────────

def parse_fund_table(html: str, period_key: str) -> dict:
    """
    步驟 3：解析 MPFA 回應的 HTML 表格

    MPFA 的基金表格結構：
    <table class="fund-list-table">
      <thead>
        <tr>
          <th>基金名稱</th>
          <th>基金類型</th>
          <th>受託人</th>
          <th>回報率(%)</th>
          <th>資產淨值</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>宏利MPF香港股票基金</td>
          <td>股票基金</td>
          <td>宏利強積金計劃</td>
          <td>2.35</td>
          <td>18.56</td>
        </tr>
        ...
      </tbody>
    </table>

    參數：
        html: MPFA 回應的 HTML
        period_key: 對應的 JSON key（如 "oneWeek"）

    回傳：{基金名稱: {period_key: 回報率, "category": ..., "provider": ..., "nav": ...}}
    """
    soup = BeautifulSoup(html, "lxml")
    funds = {}

    # 嘗試多種表格選擇器（MPFA 網頁可能改版）
    table = (
        soup.find("table", class_=re.compile(r"fund", re.I))
        or soup.find("table", id=re.compile(r"fund", re.I))
        or soup.find("table")  # 退而求其次，取第一個表格
    )

    if not table:
        log.warning(f"  ⚠️  找不到基金表格（{period_key}）")
        return {}

    rows = table.find_all("tr")
    data_rows = [r for r in rows if r.find("td")]  # 過濾掉表頭

    log.info(f"  📊 {period_key}: 找到 {len(data_rows)} 行數據")

    for row in data_rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        # 提取文字（清除 HTML 標籤和多餘空白）
        def text(cell):
            return cell.get_text(strip=True).replace("\xa0", "").strip()

        name     = text(cells[0])
        category = text(cells[1]) if len(cells) > 1 else ""
        provider = text(cells[2]) if len(cells) > 2 else ""

        # 找到回報率欄（可能在第 3 或第 4 個 td）
        return_val = 0.0
        nav_val    = 0.0

        for i in range(3, min(len(cells), 7)):
            val_str = text(cells[i]).replace("%", "").replace(",", "")
            try:
                return_val = float(val_str)
                # 嘗試取 NAV（下一個欄位）
                if i + 1 < len(cells):
                    nav_str = text(cells[i + 1]).replace(",", "")
                    try:
                        nav_val = float(nav_str)
                    except ValueError:
                        pass
                break
            except ValueError:
                continue

        if not name:
            continue

        # 標準化類別名稱
        category_zh = CATEGORY_MAP.get(category, category) or "股票基金"

        # 用基金名稱作為唯一識別鍵
        if name not in funds:
            funds[name] = {
                "category": category_zh,
                "provider": provider,
                "nav":      nav_val,
            }

        funds[name][period_key] = return_val

    return funds


# ─── 數據合併 ─────────────────────────────────────────────────────────────────

def merge_period_data(all_period_data: dict) -> list:
    """
    步驟 4：合併各時段數據為完整的基金記錄列表

    all_period_data 格式：
    {
      "oneWeek":    {"宏利MPF香港股票基金": {"oneWeek": 2.35, "category": ..., ...}},
      "oneMonth":   {"宏利MPF香港股票基金": {"oneMonth": 5.10, ...}},
      ...
    }

    合併後格式：
    [
      {
        "id": "fund-001",
        "name": "宏利MPF香港股票基金",
        "returns": {"oneWeek": 2.35, "oneMonth": 5.10, ...},
        ...
      },
      ...
    ]
    """
    # 收集所有唯一基金名稱
    all_names = set()
    for period_funds in all_period_data.values():
        all_names.update(period_funds.keys())

    log.info(f"📊 共找到 {len(all_names)} 個唯一基金")

    funds = []
    for idx, name in enumerate(sorted(all_names), 1):
        # 從任何有數據的時段取得基本資訊
        base_info = {}
        for period_funds in all_period_data.values():
            if name in period_funds:
                base_info = period_funds[name]
                break

        category = base_info.get("category", "股票基金")
        provider = base_info.get("provider", "")
        nav      = base_info.get("nav", 10.0)

        # 組合回報數據
        returns = {}
        for period_key in PERIODS.values():
            val = 0.0
            for period_funds in all_period_data.values():
                if name in period_funds and period_key in period_funds[name]:
                    val = period_funds[name][period_key]
                    break
            returns[period_key] = round(val, 4)

        # 生成穩定的基金 ID（用名稱的 hash 前 6 位）
        fund_id = f"fund-{hashlib.md5(name.encode()).hexdigest()[:6]}"

        funds.append({
            "id":        fund_id,
            "name":      name,
            "provider":  provider,
            "category":  category,
            "riskLevel": RISK_BY_CATEGORY.get(category, 3),
            "nav":       round(nav, 4) if nav else 10.0,
            "currency":  "HKD",
            "returns":   returns,
        })

    # 按一年回報降序排列
    funds.sort(key=lambda f: f["returns"].get("oneYear", 0), reverse=True)
    return funds


# ─── 主程式 ───────────────────────────────────────────────────────────────────

def load_existing_data() -> Optional[dict]:
    """讀取現有的 funds.json（抓取失敗時使用）"""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save_data(funds: list, source: str, note: str) -> None:
    """將基金數據寫入 data/funds.json"""
    hkt = timezone(timedelta(hours=8))
    now_hkt = datetime.now(hkt)

    output = {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "lastUpdatedHKT": now_hkt.strftime("%Y-%m-%d %H:%M HKT"),
        "dataSource": source,
        "note": note,
        "totalFunds": len(funds),
        "funds": funds,
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    log.info(f"✅ 數據已寫入 {DATA_FILE}")
    log.info(f"   共 {len(funds)} 個基金，來源：{source}")
    log.info(f"   更新時間：{now_hkt.strftime('%Y-%m-%d %H:%M HKT')}")


def main():
    log.info("=" * 60)
    log.info("🚀 MPF 基金數據爬蟲啟動")
    log.info("=" * 60)

    session = create_session()

    # ── 步驟 1：建立 Session ──────────────────────────────────────────────────
    if not get_session_cookie(session):
        log.warning("⚠️  無法連接 MPFA，使用現有快取數據")
        existing = load_existing_data()
        if existing:
            log.info(f"📋 保留現有數據（{existing.get('lastUpdatedHKT', '未知時間')}）")
            sys.exit(0)
        else:
            log.error("❌ 無快取數據，爬取失敗")
            sys.exit(1)

    # ── 步驟 2：逐一抓取各時段數據 ──────────────────────────────────────────
    log.info("\n步驟 2：抓取各時段回報數據...")
    all_period_data = {}
    failed_periods = []

    for period_code, period_key in PERIODS.items():
        html = fetch_period_data(session, period_code)

        if html:
            period_funds = parse_fund_table(html, period_key)
            if period_funds:
                all_period_data[period_key] = period_funds
                log.info(f"  ✅ {period_code}: 解析到 {len(period_funds)} 個基金")
            else:
                log.warning(f"  ⚠️  {period_code}: 解析失敗（0 個基金）")
                failed_periods.append(period_code)
        else:
            failed_periods.append(period_code)

        # 避免請求太頻繁（降低被封鎖的機率）
        time.sleep(1.5)

    # ── 步驟 3：評估結果 ──────────────────────────────────────────────────────
    log.info(f"\n步驟 3：評估抓取結果...")
    log.info(f"  成功時段：{len(all_period_data)}/{len(PERIODS)}")

    if not all_period_data:
        log.warning("⚠️  所有時段均抓取失敗，保留現有快取數據")
        existing = load_existing_data()
        if existing:
            log.info(f"📋 保留現有數據（{existing.get('lastUpdatedHKT', '未知')}）")
            sys.exit(0)
        else:
            log.error("❌ 無快取且爬取失敗")
            sys.exit(1)

    # ── 步驟 4：合併數據 ──────────────────────────────────────────────────────
    log.info("\n步驟 4：合併各時段數據...")
    funds = merge_period_data(all_period_data)

    if not funds:
        log.error("❌ 合併後基金列表為空")
        sys.exit(1)

    # ── 步驟 5：儲存數據 ──────────────────────────────────────────────────────
    log.info(f"\n步驟 5：儲存數據到 {DATA_FILE}...")

    if failed_periods:
        note = (
            f"數據來源：積金局基金表現平台 mfp.mpfa.org.hk。"
            f"部分時段數據缺失：{', '.join(failed_periods)}。"
        )
        source = "mpfa_partial"
    else:
        note = "數據來源：積金局基金表現平台 mfp.mpfa.org.hk"
        source = "mpfa"

    save_data(funds, source, note)

    log.info("\n" + "=" * 60)
    log.info("🎉 爬蟲完成！")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
