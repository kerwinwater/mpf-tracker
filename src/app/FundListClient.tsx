"use client";

/**
 * FundListClient — 客戶端主組件
 *
 * 責任：
 * 1. 在瀏覽器啟動後 fetch /data/funds.json（由爬蟲生成）
 * 2. 顯示載入骨架屏（Skeleton）
 * 3. 管理所有互動狀態：時段、類別、搜索、排序
 * 4. 渲染頂部導航欄（含動態更新時間）、排行榜、頁尾
 */

import { useState, useEffect, useMemo } from "react";
import { Fund, FundsData, SortPeriod, FUND_CATEGORIES } from "@/types/fund";
import PeriodTabs from "@/components/PeriodTabs";
import CategoryFilter from "@/components/CategoryFilter";
import FundCard from "@/components/FundCard";
import StatsBar from "@/components/StatsBar";

type Category = (typeof FUND_CATEGORIES)[number];

// ─── 骨架屏組件 ────────────────────────────────────────────────────────────────
function Skeleton({ className = "", style = {} }: { className?: string; style?: React.CSSProperties }) {
  return (
    <div
      className={`animate-pulse rounded-lg ${className}`}
      style={{ backgroundColor: "rgba(255,255,255,0.06)", ...style }}
    />
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4 pt-2">
      {/* 搜索欄 */}
      <Skeleton style={{ height: 48 }} />
      {/* 時段標籤 */}
      <Skeleton style={{ height: 44 }} />
      {/* 類別篩選 */}
      <Skeleton style={{ height: 40 }} />
      {/* 統計欄 */}
      <div className="grid grid-cols-3 gap-3">
        <Skeleton style={{ height: 72 }} />
        <Skeleton style={{ height: 72 }} />
        <Skeleton style={{ height: 72 }} />
      </div>
      {/* 基金列表 */}
      {Array.from({ length: 10 }).map((_, i) => (
        <Skeleton key={i} style={{ height: 88, animationDelay: `${i * 60}ms` }} />
      ))}
    </div>
  );
}

// ─── 格式化更新時間 ─────────────────────────────────────────────────────────────
function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-HK", {
      timeZone:  "Asia/Hong_Kong",
      month:     "2-digit",
      day:       "2-digit",
      hour:      "2-digit",
      minute:    "2-digit",
    });
  } catch {
    return iso;
  }
}

// ─── 主組件 ────────────────────────────────────────────────────────────────────
export default function FundListClient() {
  // ── 數據狀態 ───────────────────────────────────────────────────────────────
  const [fundsData, setFundsData] = useState<FundsData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [fetchError, setFetchError] = useState(false);

  // ── 互動狀態 ───────────────────────────────────────────────────────────────
  const [activePeriod, setActivePeriod]   = useState<SortPeriod>("oneYear");
  const [activeCategory, setActiveCategory] = useState<Category>("全部類別");
  const [searchQuery, setSearchQuery]     = useState("");
  const [sortAsc, setSortAsc]             = useState(false);

  // ── 取得數據 ───────────────────────────────────────────────────────────────
  useEffect(() => {
    fetch("/data/funds.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<FundsData>;
      })
      .then((data) => {
        setFundsData(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("無法載入基金數據：", err);
        setFetchError(true);
        setLoading(false);
      });
  }, []);

  const funds      = fundsData?.funds ?? [];
  const isLive     = fundsData?.dataSource === "mpfa" || fundsData?.dataSource === "mpfa_partial";
  const updateTime = fundsData?.lastUpdated ? formatTime(fundsData.lastUpdated) : "";

  // ── 計算各類別基金數量 ────────────────────────────────────────────────────
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { "全部類別": funds.length };
    for (const f of funds) {
      counts[f.category] = (counts[f.category] ?? 0) + 1;
    }
    return counts;
  }, [funds]);

  // ── 篩選 + 排序 ───────────────────────────────────────────────────────────
  const filteredAndSorted = useMemo(() => {
    let result = [...funds];

    if (activeCategory !== "全部類別") {
      result = result.filter((f) => f.category === activeCategory);
    }

    const q = searchQuery.trim().toLowerCase();
    if (q) {
      result = result.filter(
        (f) =>
          f.name.toLowerCase().includes(q) ||
          f.provider.toLowerCase().includes(q) ||
          f.category.toLowerCase().includes(q)
      );
    }

    result.sort((a, b) => {
      const diff = a.returns[activePeriod] - b.returns[activePeriod];
      return sortAsc ? diff : -diff;
    });

    return result;
  }, [funds, activePeriod, activeCategory, searchQuery, sortAsc]);

  // 統計用（始終降序）
  const statsData = useMemo(() => {
    if (sortAsc) {
      return [...filteredAndSorted].sort(
        (a, b) => b.returns[activePeriod] - a.returns[activePeriod]
      );
    }
    return filteredAndSorted;
  }, [filteredAndSorted, activePeriod, sortAsc]);

  // 賽馬橫條最大值
  const maxAbsReturn = useMemo(() => {
    if (!filteredAndSorted.length) return 1;
    return (
      Math.max(...filteredAndSorted.map((f) => Math.abs(f.returns[activePeriod]))) || 1
    );
  }, [filteredAndSorted, activePeriod]);

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <>
      {/* ─── 頂部導航欄 ────────────────────────────────────────────────── */}
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

            {/* 數據狀態 + 更新時間 */}
            <div className="text-right">
              {fundsData ? (
                <>
                  <div className="flex items-center justify-end gap-1.5">
                    <span
                      className={`w-2 h-2 rounded-full ${isLive ? "animate-pulse" : ""}`}
                      style={{ backgroundColor: isLive ? "#4ade80" : "#fbbf24" }}
                    />
                    <span className="text-xs" style={{ color: "#888" }}>
                      {isLive ? "MPFA數據" : "示範數據"}
                    </span>
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: "#666" }}>
                    更新：{updateTime}
                  </div>
                </>
              ) : (
                <Skeleton style={{ width: 80, height: 28 }} />
              )}
            </div>
          </div>
        </div>
      </header>

      {/* ─── 主體 ──────────────────────────────────────────────────────── */}
      <main className="max-w-3xl mx-auto px-4 py-5">
        {/* 載入中 */}
        {loading && <LoadingSkeleton />}

        {/* 取得失敗 */}
        {fetchError && (
          <div className="text-center py-20">
            <div className="text-4xl mb-3">⚠️</div>
            <p className="font-medium text-white">無法載入基金數據</p>
            <p className="text-sm mt-1" style={{ color: "#888" }}>
              請重新整理頁面，或稍後再試
            </p>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 rounded-lg text-sm font-medium text-gray-900"
              style={{ backgroundColor: "#4ade80" }}
            >
              重新整理
            </button>
          </div>
        )}

        {/* 數據已載入 */}
        {fundsData && !fetchError && (
          <div className="space-y-4">
            {/* 搜索欄 */}
            <div className="relative">
              <div className="absolute inset-y-0 left-3.5 flex items-center pointer-events-none">
                <svg
                  className="w-4 h-4"
                  style={{ color: "#555" }}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
              </div>
              <input
                type="search"
                placeholder="搜索基金名稱、受託人..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="search-input pl-10"
              />
            </div>

            {/* 時段選擇 */}
            <PeriodTabs activePeriod={activePeriod} onChange={setActivePeriod} />

            {/* 類別篩選 */}
            <CategoryFilter
              activeCategory={activeCategory}
              onChange={setActiveCategory}
              counts={categoryCounts}
            />

            {/* 統計摘要 */}
            {statsData.length > 0 && (
              <StatsBar funds={statsData} period={activePeriod} />
            )}

            {/* 排行榜標題 */}
            <div className="flex items-center justify-between pt-1">
              <h2 className="font-bold text-white text-sm">
                {activeCategory === "全部類別" ? "全部基金" : activeCategory}
                <span
                  className="ml-2 font-semibold text-xs px-1.5 py-0.5 rounded-full tabular-nums"
                  style={{ backgroundColor: "rgba(74,222,128,0.15)", color: "#4ade80" }}
                >
                  {filteredAndSorted.length} 隻
                </span>
              </h2>
              <button
                onClick={() => setSortAsc((v) => !v)}
                className="text-sm font-medium transition-colors"
                style={{ color: "#4ade80" }}
              >
                {sortAsc ? "↑ 升序" : "↓ 降序"}
              </button>
            </div>

            {/* 賽馬排行榜 */}
            {filteredAndSorted.length > 0 ? (
              <div className="space-y-2">
                {filteredAndSorted.map((fund, idx) => (
                  <div
                    key={`${fund.id}-${activeCategory}`}
                    className="animate-fade-in"
                    style={{ animationDelay: `${Math.min(idx * 20, 300)}ms` }}
                  >
                    <FundCard
                      fund={fund}
                      rank={idx + 1}
                      activePeriod={activePeriod}
                      maxAbsReturn={maxAbsReturn}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-16">
                <div className="text-4xl mb-3">🔍</div>
                <p className="font-medium text-white">找不到相關基金</p>
                <p className="text-sm mt-1" style={{ color: "#888" }}>
                  試試其他關鍵字
                </p>
              </div>
            )}
          </div>
        )}
      </main>

      {/* ─── 頁尾 ──────────────────────────────────────────────────────── */}
      {fundsData && (
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
              {fundsData.note}
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
            共 {fundsData.totalFunds} 個基金
          </p>
        </footer>
      )}
    </>
  );
}
