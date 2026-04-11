/**
 * FundListClient 組件（客戶端互動層）
 *
 * 這個組件負責所有客戶端互動：
 * - 時段切換（useState）
 * - 搜索篩選（useMemo）
 * - 類別篩選（useMemo）
 * - 排序邏輯（useMemo）
 *
 * 為什麼分離成獨立檔案？
 * 因為 Next.js App Router 中，只有標記 "use client" 的組件才能使用
 * useState/useEffect 等 React hooks。服務器組件不能使用 hooks。
 */

"use client";

import { useState, useMemo } from "react";
import { Fund, SortPeriod, FUND_CATEGORIES } from "@/types/fund";
import PeriodTabs from "@/components/PeriodTabs";
import CategoryFilter from "@/components/CategoryFilter";
import FundCard from "@/components/FundCard";
import StatsBar from "@/components/StatsBar";

type Category = typeof FUND_CATEGORIES[number];

interface FundListClientProps {
  funds: Fund[];
}

export default function FundListClient({ funds }: FundListClientProps) {
  // ─── 狀態管理 ────────────────────────────────────────────────────────────
  // 當前選中的時段（預設：1年）
  const [activePeriod, setActivePeriod] = useState<SortPeriod>("oneYear");
  // 當前類別篩選
  const [activeCategory, setActiveCategory] = useState<Category>("全部類別");
  // 搜索關鍵字
  const [searchQuery, setSearchQuery] = useState("");
  // 排序方向（預設：降序 = 最高回報在最前）
  const [sortAsc, setSortAsc] = useState(false);

  // ─── 計算各類別的基金數量（供 CategoryFilter 顯示） ─────────────────────
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { "全部類別": funds.length };
    for (const fund of funds) {
      counts[fund.category] = (counts[fund.category] ?? 0) + 1;
    }
    return counts;
  }, [funds]);

  // ─── 篩選 + 排序邏輯 ─────────────────────────────────────────────────────
  const filteredAndSorted = useMemo(() => {
    let result = [...funds];

    // 1. 類別篩選
    if (activeCategory !== "全部類別") {
      result = result.filter((f) => f.category === activeCategory);
    }

    // 2. 關鍵字搜索（搜索基金名稱或受託人）
    const query = searchQuery.trim().toLowerCase();
    if (query) {
      result = result.filter(
        (f) =>
          f.name.toLowerCase().includes(query) ||
          f.provider.toLowerCase().includes(query) ||
          f.category.toLowerCase().includes(query)
      );
    }

    // 3. 按回報排序
    result.sort((a, b) => {
      const diff = a.returns[activePeriod] - b.returns[activePeriod];
      return sortAsc ? diff : -diff;
    });

    return result;
  }, [funds, activePeriod, activeCategory, searchQuery, sortAsc]);

  // 當前選中類別和時段的統計數據（供 StatsBar 用）
  const statsData = useMemo(() => {
    return [...filteredAndSorted].sort(
      (a, b) => b.returns[activePeriod] - a.returns[activePeriod]
    );
  }, [filteredAndSorted, activePeriod]);

  return (
    <div className="space-y-5">
      {/* ─── 搜索欄 ──────────────────────────────────────────────── */}
      <div className="relative">
        <div className="absolute inset-y-0 left-3.5 flex items-center pointer-events-none">
          <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
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

      {/* ─── 時段選擇標籤 ──────────────────────────────────────── */}
      <PeriodTabs activePeriod={activePeriod} onChange={setActivePeriod} />

      {/* ─── 類別篩選 ─────────────────────────────────────────── */}
      <CategoryFilter
        activeCategory={activeCategory}
        onChange={setActiveCategory}
        counts={categoryCounts}
      />

      {/* ─── 市場統計摘要 ─────────────────────────────────────── */}
      {statsData.length > 0 && (
        <StatsBar funds={statsData} period={activePeriod} />
      )}

      {/* ─── 排行榜標題欄 ─────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <h2 className="font-bold text-gray-800">
          {activeCategory === "全部類別" ? "全部基金" : activeCategory}
          <span className="ml-2 text-sm font-normal text-gray-400">
            {filteredAndSorted.length} 個
          </span>
        </h2>
        {/* 切換排序方向按鈕 */}
        <button
          onClick={() => setSortAsc((prev) => !prev)}
          className="flex items-center gap-1 text-sm text-blue-600 font-medium"
        >
          <span>{sortAsc ? "⬆️ 升序" : "⬇️ 降序"}</span>
        </button>
      </div>

      {/* ─── 基金卡片列表 ─────────────────────────────────────── */}
      {filteredAndSorted.length > 0 ? (
        <div className="space-y-2.5">
          {filteredAndSorted.map((fund, index) => (
            <div
              key={fund.id}
              className="animate-fade-in"
              style={{ animationDelay: `${Math.min(index * 30, 300)}ms` }}
            >
              <FundCard
                fund={fund}
                rank={index + 1}
                activePeriod={activePeriod}
              />
            </div>
          ))}
        </div>
      ) : (
        /* 搜索無結果 */
        <div className="text-center py-16 text-gray-400">
          <div className="text-4xl mb-3">🔍</div>
          <p className="font-medium">找不到相關基金</p>
          <p className="text-sm mt-1">試試其他關鍵字</p>
        </div>
      )}
    </div>
  );
}
