/**
 * 主頁面（伺服器組件）
 *
 * 只負責提供最外層的深色背景容器。
 * 所有數據讀取和互動邏輯均在 FundListClient（客戶端組件）。
 *
 * 架構說明：
 * - FundListClient 在瀏覽器啟動後 fetch /data/funds.json
 * - 每次 GitHub Actions 更新數據後，Vercel 重新部署時會更新此 JSON
 * - 使用者瀏覽時取得最新已部署的數據
 */

import type { Metadata } from "next";
import FundListClient from "./FundListClient";

export const metadata: Metadata = {
  title: "MPF 強積金賽馬排名 | 基金回報比較",
  description:
    "一站式香港強積金基金表現比較平台。查看每週、每月、每年回報排名，找出最佳表現的 MPF 基金。數據來源：積金局 MPFA。",
  keywords: "MPF, 強積金, 基金比較, 回報排名, 香港, MPFA, 積金局",
  openGraph: {
    title: "MPF 強積金賽馬排名",
    description: "香港強積金基金回報排名 — 每日自動更新",
    locale: "zh_HK",
    type: "website",
  },
  icons: { icon: "/favicon.svg" },
};

export default function HomePage() {
  return (
    <div className="min-h-screen" style={{ backgroundColor: "#0f1117" }}>
      <FundListClient />
    </div>
  );
}
