/**
 * 主頁面 (app/page.tsx)
 *
 * MPF 強積金基金回報排名頁面。
 *
 * 架構說明：
 * - 使用 Next.js 靜態生成 (Static Generation)
 * - 在構建時讀取 data/funds.json（由爬蟲腳本定期更新）
 * - 客戶端負責篩選、排序、搜索等互動功能
 *
 * 頁面結構：
 * 1. 頂部導航欄（網站名稱 + 數據更新時間）
 * 2. 搜索欄
 * 3. 時段選擇標籤（1週/1月/3月/半年/1年/3年/5年）
 * 4. 類別篩選橫向滾動條
 * 5. 市場統計摘要
 * 6. 基金卡片排行榜
 * 7. 頁尾說明
 */

import { readFileSync } from "fs";
import { join } from "path";
import { FundsData } from "@/types/fund";
import FundListClient from "./FundListClient";

/**
 * 靜態讀取基金數據
 * 這個函數只在構建時（build time）執行，不影響客戶端性能。
 */
function getFundsData(): FundsData {
  const filePath = join(process.cwd(), "data", "funds.json");
  const raw = readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as FundsData;
}

/**
 * 格式化最後更新時間（Hong Kong Time）
 */
function formatUpdateTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString("zh-HK", {
    timeZone: "Asia/Hong_Kong",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ─── 主頁面組件（服務器端） ────────────────────────────────────────────────────
export default function HomePage() {
  const data = getFundsData();
  const updateTime = formatUpdateTime(data.lastUpdated);
  const isLiveData = data.dataSource === "mpfa";

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ─── 頂部導航欄 ─────────────────────────────────────────── */}
      <header className="bg-white/80 backdrop-blur-lg sticky top-0 z-50 border-b border-gray-100">
        <div className="max-w-3xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-bold text-gray-900">
                💰 MPF 強積金排名
              </h1>
              <p className="text-xs text-gray-400">香港強積金基金回報比較</p>
            </div>
            <div className="text-right">
              {/* 數據來源指示燈 */}
              <div className="flex items-center justify-end gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full ${
                    isLiveData ? "bg-green-400 animate-pulse" : "bg-amber-400"
                  }`}
                />
                <span className="text-xs text-gray-500">
                  {isLiveData ? "即時數據" : "示範數據"}
                </span>
              </div>
              <div className="text-xs text-gray-400 mt-0.5">
                更新：{updateTime}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* ─── 頁面主體：傳給客戶端組件處理互動 ─────────────────── */}
      <main className="max-w-3xl mx-auto px-4 py-5">
        <FundListClient funds={data.funds} />
      </main>

      {/* ─── 頁尾 ───────────────────────────────────────────────── */}
      <footer className="max-w-3xl mx-auto px-4 pb-8 mt-6">
        <div className="bg-amber-50 border border-amber-100 rounded-2xl p-4">
          <p className="text-xs text-amber-700 leading-relaxed">
            <strong>⚠️ 免責聲明：</strong>
            {data.note}
            <br />
            本網站僅供參考，不構成任何投資建議。強積金投資涉及風險，基金過往表現並不代表將來表現。
            如需查閱官方數據，請訪問{" "}
            <a
              href="https://mfp.mpfa.org.hk"
              target="_blank"
              rel="noopener noreferrer"
              className="text-amber-600 underline"
            >
              積金局官方網站
            </a>
            。
          </p>
        </div>

        <p className="text-center text-xs text-gray-400 mt-4">
          數據來源：香港強積金管理局 (MPFA) · 每日自動更新
          <br />
          共 {data.totalFunds} 個基金
        </p>
      </footer>
    </div>
  );
}
