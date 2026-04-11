import { readFileSync } from "fs";
import { join } from "path";
import { FundsData } from "@/types/fund";
import FundListClient from "./FundListClient";

function getFundsData(): FundsData {
  const filePath = join(process.cwd(), "data", "funds.json");
  const raw = readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as FundsData;
}

function formatUpdateTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString("zh-HK", {
    timeZone: "Asia/Hong_Kong",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function HomePage() {
  const data = getFundsData();
  const updateTime = formatUpdateTime(data.lastUpdated);
  const isLiveData = data.dataSource === "mpfa";

  return (
    <div className="min-h-screen" style={{ backgroundColor: "#0f1117" }}>
      {/* ─── 頂部導航欄 ─────────────────────────────────────── */}
      <header
        className="sticky top-0 z-50 border-b"
        style={{
          backgroundColor: "#1a1d27",
          borderColor: "rgba(255,255,255,0.06)",
        }}
      >
        <div className="max-w-3xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-base font-bold text-white leading-snug">
                🏇 MPF 強積金賽馬排名
              </h1>
              <p className="text-xs mt-0.5" style={{ color: "#888" }}>
                香港強積金基金回報比較
              </p>
            </div>
            <div className="text-right">
              <div className="flex items-center justify-end gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full ${isLiveData ? "animate-pulse" : ""}`}
                  style={{
                    backgroundColor: isLiveData ? "#4ade80" : "#fbbf24",
                  }}
                />
                <span className="text-xs" style={{ color: "#888" }}>
                  {isLiveData ? "即時數據" : "示範數據"}
                </span>
              </div>
              <div className="text-xs mt-0.5" style={{ color: "#666" }}>
                更新：{updateTime}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* ─── 主體 ────────────────────────────────────────────── */}
      <main className="max-w-3xl mx-auto px-4 py-5">
        <FundListClient funds={data.funds} />
      </main>

      {/* ─── 頁尾 ────────────────────────────────────────────── */}
      <footer className="max-w-3xl mx-auto px-4 pb-10 mt-6">
        <div
          className="rounded-xl p-4 border"
          style={{
            backgroundColor: "#1a1d27",
            borderColor: "rgba(251,191,36,0.15)",
          }}
        >
          <p className="text-xs leading-relaxed" style={{ color: "#9a8a60" }}>
            <span className="text-yellow-400 font-medium">⚠️ 免責聲明：</span>
            {data.note}
            <br />
            本網站僅供參考，不構成任何投資建議。強積金投資涉及風險，基金過往表現並不代表將來表現。
            如需查閱官方數據，請訪問{" "}
            <a
              href="https://mfp.mpfa.org.hk"
              target="_blank"
              rel="noopener noreferrer"
              className="text-yellow-400 underline underline-offset-2"
            >
              積金局官方網站
            </a>
            。
          </p>
        </div>

        <p className="text-center text-xs mt-4" style={{ color: "#555" }}>
          數據來源：香港強積金管理局 (MPFA) · 每日自動更新
          <br />
          共 {data.totalFunds} 個基金
        </p>
      </footer>
    </div>
  );
}
