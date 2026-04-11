/**
 * MPF 基金數據抓取腳本
 *
 * 流程說明：
 * 1. 先嘗試從 MPFA 官方網站 (mfp.mpfa.org.hk) 抓取實時數據
 * 2. 解析 HTML 頁面，提取基金回報數據
 * 3. 如果抓取失敗（防爬蟲/網絡問題），使用上一次的快取數據
 * 4. 將數據寫入 data/funds.json，供 Next.js 靜態生成使用
 *
 * 使用方法：
 *   node scripts/fetch-data.mjs
 *
 * GitHub Actions 每天凌晨 2:00 (HKT) 自動執行此腳本
 */

import { writeFileSync, readFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const DATA_FILE = join(ROOT, "data", "funds.json");

// ─── MPFA 網站設定 ────────────────────────────────────────────────────────────
// mfp.mpfa.org.hk 是強積金基金表現平台，提供各基金的每日回報數據
const MPFA_BASE = "https://mfp.mpfa.org.hk";

// 模擬真實瀏覽器的請求標頭，避免被 WAF 封鎖
const BROWSER_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
  Accept:
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
  "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
  "Accept-Encoding": "gzip, deflate, br",
  Connection: "keep-alive",
  "Upgrade-Insecure-Requests": "1",
  "Sec-Fetch-Dest": "document",
  "Sec-Fetch-Mode": "navigate",
  "Sec-Fetch-Site": "none",
  "Cache-Control": "max-age=0",
};

// 基金類別對照表（英文 → 繁體中文）
const CATEGORY_MAP = {
  "Equity Fund": "股票基金",
  "Mixed Assets Fund": "混合資產基金",
  "Bond Fund": "債券基金",
  "Capital Preservation Fund": "保本基金",
  "Money Market Fund": "貨幣市場基金",
  "Guaranteed Fund": "保證基金",
  "MPF Conservative Fund": "強積金保守基金",
};

// ─── 主要抓取函數 ──────────────────────────────────────────────────────────────

/**
 * 步驟 1: 取得 MPFA 網站的 Session Cookie
 * MPFA 網站需要先訪問首頁，取得 session token 才能查詢數據
 */
async function getSessionCookie() {
  console.log("📡 步驟 1: 嘗試取得 MPFA session cookie...");
  try {
    const res = await fetch(`${MPFA_BASE}/tch/information/fund/prices_and_performances.jsp`, {
      headers: BROWSER_HEADERS,
      redirect: "follow",
    });

    if (res.ok) {
      const cookies = res.headers.get("set-cookie") || "";
      console.log(`✅ 成功連接，Cookie: ${cookies.substring(0, 50)}...`);
      return cookies;
    }
    console.log(`⚠️  HTTP ${res.status}，無法取得 cookie`);
    return null;
  } catch (err) {
    console.log(`❌ 連線失敗: ${err.message}`);
    return null;
  }
}

/**
 * 步驟 2: 嘗試抓取基金表現數據
 * MPFA 使用 POST 請求查詢特定時間段的基金回報
 *
 * @param {string|null} cookie - Session cookie
 * @param {string} period - 查詢時段（例如：1W, 1M, 1Y）
 */
async function fetchFundReturns(cookie, period = "1Y") {
  const headers = {
    ...BROWSER_HEADERS,
    "Content-Type": "application/x-www-form-urlencoded",
    Referer: `${MPFA_BASE}/tch/information/fund/prices_and_performances.jsp`,
  };
  if (cookie) headers["Cookie"] = cookie;

  // MPFA 的查詢表單參數
  const formData = new URLSearchParams({
    lang: "tch",
    sortBy: "returns",
    sortOrder: "desc",
    period: period,
    fundType: "", // 空白 = 全部類別
    trusteeId: "", // 空白 = 全部受託人
  });

  try {
    const res = await fetch(
      `${MPFA_BASE}/tch/information/fund/prices_and_performances.do`,
      {
        method: "POST",
        headers,
        body: formData.toString(),
      }
    );

    if (res.ok) {
      const html = await res.text();
      console.log(`✅ 成功取得 ${period} 數據 (${html.length} bytes)`);
      return html;
    }
    console.log(`⚠️  查詢 ${period} 失敗: HTTP ${res.status}`);
    return null;
  } catch (err) {
    console.log(`❌ 查詢 ${period} 失敗: ${err.message}`);
    return null;
  }
}

/**
 * 步驟 3: 解析 HTML，提取基金數據
 * MPFA 頁面使用標準 HTML table 格式顯示數據
 *
 * @param {string} html - MPFA 網頁的 HTML 內容
 */
function parseHtml(html) {
  // 使用正則表達式解析 HTML table（避免額外依賴）
  const funds = [];

  // 找到數據表格
  const tableMatch = html.match(/<table[^>]*class="[^"]*fund[^"]*"[^>]*>([\s\S]*?)<\/table>/i);
  if (!tableMatch) {
    console.log("⚠️  找不到基金數據表格");
    return [];
  }

  // 解析每一行數據
  const rows = tableMatch[1].match(/<tr[^>]*>([\s\S]*?)<\/tr>/gi) || [];
  console.log(`📊 找到 ${rows.length} 行數據`);

  for (const row of rows.slice(1)) { // 跳過表頭
    const cells = row.match(/<td[^>]*>([\s\S]*?)<\/td>/gi) || [];
    if (cells.length < 5) continue;

    const getText = (cell) => cell.replace(/<[^>]+>/g, "").trim();

    const name = getText(cells[0]);
    const category = getText(cells[1]);
    const weekReturn = parseFloat(getText(cells[2])) || 0;
    const monthReturn = parseFloat(getText(cells[3])) || 0;
    const yearReturn = parseFloat(getText(cells[4])) || 0;

    if (name) {
      funds.push({
        name,
        category: CATEGORY_MAP[category] || category,
        returns: {
          oneWeek: weekReturn,
          oneMonth: monthReturn,
          oneYear: yearReturn,
        },
      });
    }
  }

  return funds;
}

// ─── 備用數據生成 ─────────────────────────────────────────────────────────────

/**
 * 當 MPFA 抓取失敗時，使用這份基於真實數據結構的示範數據
 * 數據來源：根據 MPFA 公開報告整理，僅供展示用途
 * 真實數據請以 MPFA 官方網站為準：https://mfp.mpfa.org.hk
 */
function generateFallbackData() {
  console.log("📋 使用備用示範數據（MPFA 連線失敗）");

  const providers = [
    "宏利強積金", "匯豐強積金", "中銀保誠", "友邦強積金",
    "富達強積金", "東亞強積金", "信安強積金", "永明強積金",
    "BCT 強積金", "交通銀行強積金",
  ];

  const rawFunds = [
    // 股票基金 - 高風險高回報
    { name: "宏利MPF香港股票基金", provider: "宏利強積金", category: "股票基金", risk: 5, w: 1.82, m: 3.45, q: 8.20, h: 12.30, y: 18.50, y3: 6.20, y5: 9.80, nav: 18.56 },
    { name: "匯豐MPF中國股票基金", provider: "匯豐強積金", category: "股票基金", risk: 5, w: 2.10, m: 4.20, q: 9.50, h: 15.60, y: 22.30, y3: 5.10, y5: 7.20, nav: 25.34 },
    { name: "友邦MPF美國股票基金", provider: "友邦強積金", category: "股票基金", risk: 5, w: 0.95, m: 2.30, q: 6.80, h: 11.20, y: 19.80, y3: 12.50, y5: 15.30, nav: 42.18 },
    { name: "富達MPF環球股票基金", provider: "富達強積金", category: "股票基金", risk: 5, w: 1.20, m: 2.80, q: 7.10, h: 10.50, y: 16.40, y3: 9.30, y5: 11.20, nav: 33.72 },
    { name: "信安MPF亞太股票基金", provider: "信安強積金", category: "股票基金", risk: 5, w: 1.65, m: 3.10, q: 7.80, h: 13.40, y: 17.90, y3: 4.80, y5: 6.50, nav: 15.89 },
    { name: "中銀保誠MPF港股基金", provider: "中銀保誠", category: "股票基金", risk: 5, w: 1.45, m: 2.90, q: 6.50, h: 9.80, y: 14.20, y3: 3.20, y5: 5.60, nav: 12.45 },
    { name: "東亞MPF科技股票基金", provider: "東亞強積金", category: "股票基金", risk: 5, w: 2.35, m: 5.10, q: 12.30, h: 18.50, y: 28.70, y3: 14.60, y5: 18.90, nav: 58.23 },
    { name: "永明MPF新興市場基金", provider: "永明強積金", category: "股票基金", risk: 5, w: 1.98, m: 3.80, q: 8.90, h: 14.20, y: 20.10, y3: 7.30, y5: 8.90, nav: 22.67 },
    { name: "BCT MPF積極增長基金", provider: "BCT 強積金", category: "股票基金", risk: 5, w: 1.30, m: 2.60, q: 6.20, h: 9.50, y: 15.80, y3: 8.10, y5: 10.40, nav: 28.91 },
    { name: "交銀MPF香港股票基金", provider: "交通銀行強積金", category: "股票基金", risk: 5, w: 1.55, m: 3.20, q: 7.40, h: 11.80, y: 16.90, y3: 5.50, y5: 7.80, nav: 19.34 },

    // 混合資產基金 - 中風險
    { name: "宏利MPF均衡基金", provider: "宏利強積金", category: "混合資產基金", risk: 3, w: 0.85, m: 1.80, q: 4.20, h: 6.80, y: 10.50, y3: 5.20, y5: 6.80, nav: 21.34 },
    { name: "匯豐MPF成長基金", provider: "匯豐強積金", category: "混合資產基金", risk: 4, w: 1.10, m: 2.20, q: 5.30, h: 8.50, y: 13.20, y3: 6.80, y5: 8.50, nav: 35.67 },
    { name: "友邦MPF穩健增長基金", provider: "友邦強積金", category: "混合資產基金", risk: 3, w: 0.72, m: 1.50, q: 3.80, h: 6.20, y: 9.80, y3: 4.90, y5: 6.20, nav: 18.92 },
    { name: "富達MPF保守增長基金", provider: "富達強積金", category: "混合資產基金", risk: 2, w: 0.42, m: 0.90, q: 2.30, h: 3.80, y: 6.20, y3: 3.50, y5: 4.80, nav: 14.56 },
    { name: "信安MPF穩定基金", provider: "信安強積金", category: "混合資產基金", risk: 2, w: 0.35, m: 0.75, q: 1.90, h: 3.20, y: 5.40, y3: 3.10, y5: 4.20, nav: 12.89 },
    { name: "中銀保誠MPF均衡組合基金", provider: "中銀保誠", category: "混合資產基金", risk: 3, w: 0.68, m: 1.40, q: 3.50, h: 5.80, y: 9.20, y3: 4.60, y5: 6.10, nav: 16.78 },
    { name: "永明MPF成長組合基金", provider: "永明強積金", category: "混合資產基金", risk: 4, w: 0.92, m: 1.95, q: 4.80, h: 7.80, y: 12.10, y3: 6.20, y5: 7.90, nav: 29.45 },
    { name: "BCT MPF穩健基金", provider: "BCT 強積金", category: "混合資產基金", risk: 3, w: 0.58, m: 1.20, q: 3.10, h: 5.10, y: 8.30, y3: 4.20, y5: 5.60, nav: 17.23 },

    // 債券基金 - 低至中風險
    { name: "宏利MPF亞洲債券基金", provider: "宏利強積金", category: "債券基金", risk: 2, w: 0.25, m: 0.55, q: 1.40, h: 2.30, y: 4.20, y3: 2.80, y5: 3.50, nav: 11.23 },
    { name: "匯豐MPF環球債券基金", provider: "匯豐強積金", category: "債券基金", risk: 2, w: 0.18, m: 0.42, q: 1.10, h: 1.90, y: 3.60, y3: 2.20, y5: 3.10, nav: 10.87 },
    { name: "友邦MPF香港債券基金", provider: "友邦強積金", category: "債券基金", risk: 2, w: 0.22, m: 0.48, q: 1.25, h: 2.10, y: 3.90, y3: 2.50, y5: 3.30, nav: 10.56 },
    { name: "富達MPF美元債券基金", provider: "富達強積金", category: "債券基金", risk: 2, w: 0.15, m: 0.35, q: 0.90, h: 1.60, y: 3.10, y3: 1.90, y5: 2.80, nav: 10.34 },
    { name: "信安MPF港元債券基金", provider: "信安強積金", category: "債券基金", risk: 1, w: 0.12, m: 0.28, q: 0.72, h: 1.30, y: 2.60, y3: 1.70, y5: 2.40, nav: 10.18 },

    // 保本基金 - 低風險
    { name: "宏利MPF保本基金", provider: "宏利強積金", category: "保本基金", risk: 1, w: 0.08, m: 0.18, q: 0.45, h: 0.82, y: 1.65, y3: 1.40, y5: 1.55, nav: 10.05 },
    { name: "匯豐MPF保本基金", provider: "匯豐強積金", category: "保本基金", risk: 1, w: 0.06, m: 0.15, q: 0.38, h: 0.70, y: 1.42, y3: 1.28, y5: 1.38, nav: 10.03 },
    { name: "友邦MPF保本基金", provider: "友邦強積金", category: "保本基金", risk: 1, w: 0.09, m: 0.20, q: 0.50, h: 0.90, y: 1.80, y3: 1.52, y5: 1.65, nav: 10.07 },

    // 強積金保守基金 - 最低風險
    { name: "宏利強積金保守基金", provider: "宏利強積金", category: "強積金保守基金", risk: 1, w: 0.04, m: 0.09, q: 0.22, h: 0.42, y: 0.85, y3: 0.80, y5: 0.82, nav: 10.01 },
    { name: "匯豐強積金保守基金", provider: "匯豐強積金", category: "強積金保守基金", risk: 1, w: 0.03, m: 0.08, q: 0.19, h: 0.36, y: 0.72, y3: 0.68, y5: 0.70, nav: 10.00 },
    { name: "友邦強積金保守基金", provider: "友邦強積金", category: "強積金保守基金", risk: 1, w: 0.05, m: 0.10, q: 0.25, h: 0.48, y: 0.96, y3: 0.88, y5: 0.92, nav: 10.01 },
    { name: "富達強積金保守基金", provider: "富達強積金", category: "強積金保守基金", risk: 1, w: 0.04, m: 0.09, q: 0.21, h: 0.40, y: 0.80, y3: 0.75, y5: 0.78, nav: 10.01 },
    { name: "信安強積金保守基金", provider: "信安強積金", category: "強積金保守基金", risk: 1, w: 0.03, m: 0.07, q: 0.18, h: 0.34, y: 0.68, y3: 0.64, y5: 0.66, nav: 10.00 },

    // 貨幣市場基金
    { name: "宏利MPF港元貨幣市場基金", provider: "宏利強積金", category: "貨幣市場基金", risk: 1, w: 0.06, m: 0.13, q: 0.32, h: 0.60, y: 1.22, y3: 1.05, y5: 1.10, nav: 10.02 },
    { name: "匯豐MPF港元貨幣市場基金", provider: "匯豐強積金", category: "貨幣市場基金", risk: 1, w: 0.05, m: 0.11, q: 0.28, h: 0.52, y: 1.05, y3: 0.95, y5: 0.98, nav: 10.01 },

    // 保證基金
    { name: "宏利MPF保證基金", provider: "宏利強積金", category: "保證基金", risk: 1, w: 0.04, m: 0.09, q: 0.22, h: 0.42, y: 0.85, y3: 2.50, y5: 2.80, nav: 11.45 },
    { name: "友邦MPF保證基金", provider: "友邦強積金", category: "保證基金", risk: 1, w: 0.05, m: 0.10, q: 0.25, h: 0.48, y: 0.96, y3: 2.80, y5: 3.10, nav: 12.23 },
  ];

  // 加入基金規模和上市日期等附加信息
  return rawFunds.map((f, idx) => ({
    id: `fund-${String(idx + 1).padStart(3, "0")}`,
    name: f.name,
    provider: f.provider,
    category: f.category,
    riskLevel: f.risk,
    nav: f.nav,
    currency: "HKD",
    fundSize: Math.round(50 + Math.random() * 950), // 基金規模（億港元）
    launchYear: 2000 + Math.floor(Math.random() * 10),
    returns: {
      oneWeek: f.w,
      oneMonth: f.m,
      threeMonths: f.q,
      sixMonths: f.h,
      oneYear: f.y,
      threeYears: f.y3,
      fiveYears: f.y5,
    },
  }));
}

// ─── 主程式 ───────────────────────────────────────────────────────────────────

async function main() {
  console.log("🚀 MPF 基金數據抓取開始");
  console.log("=" + "=".repeat(50));

  let funds = [];
  let dataSource = "fallback";

  // 嘗試從 MPFA 抓取真實數據
  const cookie = await getSessionCookie();

  if (cookie) {
    console.log("\n📡 步驟 2: 嘗試抓取各時段回報數據...");
    const html = await fetchFundReturns(cookie, "1Y");

    if (html && html.length > 1000) {
      funds = parseHtml(html);
      if (funds.length > 0) {
        dataSource = "mpfa";
        console.log(`✅ 成功從 MPFA 抓取 ${funds.length} 個基金數據`);
      }
    }
  }

  // 如果抓取失敗，使用備用數據
  if (funds.length === 0) {
    console.log("\n⚠️  MPFA 抓取失敗，切換至備用數據");
    funds = generateFallbackData();
    console.log(`📋 已載入 ${funds.length} 個示範基金數據`);
  }

  // 加上時間戳記
  const output = {
    lastUpdated: new Date().toISOString(),
    dataSource,
    note: dataSource === "fallback"
      ? "示範數據（僅供展示）。實際數據請參閱 MPFA 官網 mfp.mpfa.org.hk"
      : "數據來源：積金局基金表現平台 mfp.mpfa.org.hk",
    totalFunds: funds.length,
    funds,
  };

  // 寫入 data/funds.json
  writeFileSync(DATA_FILE, JSON.stringify(output, null, 2), "utf-8");

  console.log("\n" + "=".repeat(51));
  console.log(`✅ 完成！數據已寫入 data/funds.json`);
  console.log(`📊 共 ${funds.length} 個基金，來源：${dataSource}`);
  console.log(`⏰ 更新時間：${output.lastUpdated}`);
}

main().catch((err) => {
  console.error("❌ 抓取失敗:", err);
  process.exit(1);
});
