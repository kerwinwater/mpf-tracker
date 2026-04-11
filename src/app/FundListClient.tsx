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
  const [activePeriod, setActivePeriod] = useState<SortPeriod>("oneYear");
  const [activeCategory, setActiveCategory] = useState<Category>("全部類別");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortAsc, setSortAsc] = useState(false);

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { "全部類別": funds.length };
    for (const fund of funds) {
      counts[fund.category] = (counts[fund.category] ?? 0) + 1;
    }
    return counts;
  }, [funds]);

  const filteredAndSorted = useMemo(() => {
    let result = [...funds];

    if (activeCategory !== "全部類別") {
      result = result.filter((f) => f.category === activeCategory);
    }

    const query = searchQuery.trim().toLowerCase();
    if (query) {
      result = result.filter(
        (f) =>
          f.name.toLowerCase().includes(query) ||
          f.provider.toLowerCase().includes(query) ||
          f.category.toLowerCase().includes(query)
      );
    }

    result.sort((a, b) => {
      const diff = a.returns[activePeriod] - b.returns[activePeriod];
      return sortAsc ? diff : -diff;
    });

    return result;
  }, [funds, activePeriod, activeCategory, searchQuery, sortAsc]);

  // Max absolute return in current view — used to scale racing bars
  const maxAbsReturn = useMemo(() => {
    if (filteredAndSorted.length === 0) return 1;
    return (
      Math.max(...filteredAndSorted.map((f) => Math.abs(f.returns[activePeriod]))) || 1
    );
  }, [filteredAndSorted, activePeriod]);

  // Stats use the same list (already sorted descending by default)
  const statsData = useMemo(() => {
    if (sortAsc) {
      return [...filteredAndSorted].sort(
        (a, b) => b.returns[activePeriod] - a.returns[activePeriod]
      );
    }
    return filteredAndSorted;
  }, [filteredAndSorted, activePeriod, sortAsc]);

  return (
    <div className="space-y-4">
      {/* ─── 搜索欄 ──────────────────────────────────────────── */}
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

      {/* ─── 時段選擇標籤 ─────────────────────────────────── */}
      <PeriodTabs activePeriod={activePeriod} onChange={setActivePeriod} />

      {/* ─── 類別篩選 ──────────────────────────────────────── */}
      <CategoryFilter
        activeCategory={activeCategory}
        onChange={setActiveCategory}
        counts={categoryCounts}
      />

      {/* ─── 統計摘要 ──────────────────────────────────────── */}
      {statsData.length > 0 && (
        <StatsBar funds={statsData} period={activePeriod} />
      )}

      {/* ─── 排行榜標題 ────────────────────────────────────── */}
      <div className="flex items-center justify-between pt-1">
        <h2 className="font-bold text-white text-sm">
          {activeCategory === "全部類別" ? "全部基金" : activeCategory}
          <span className="ml-2 font-normal" style={{ color: "#666" }}>
            {filteredAndSorted.length} 隻
          </span>
        </h2>
        <button
          onClick={() => setSortAsc((prev) => !prev)}
          className="flex items-center gap-1 text-sm font-medium transition-colors"
          style={{ color: "#4ade80" }}
        >
          {sortAsc ? "↑ 升序" : "↓ 降序"}
        </button>
      </div>

      {/* ─── 賽馬排行榜 ────────────────────────────────────── */}
      {filteredAndSorted.length > 0 ? (
        <div className="space-y-2">
          {filteredAndSorted.map((fund, index) => (
            <div
              key={fund.id}
              className="animate-fade-in"
              style={{ animationDelay: `${Math.min(index * 25, 400)}ms` }}
            >
              <FundCard
                fund={fund}
                rank={index + 1}
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
  );
}
