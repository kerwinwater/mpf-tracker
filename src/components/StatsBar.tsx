/**
 * StatsBar 組件
 *
 * 頁面頂部的統計摘要欄，顯示本時段的整體市場概覽：
 * - 最高回報基金
 * - 上升基金數量
 * - 平均回報
 *
 * 類似股票市場行情摘要的設計。
 */

import { Fund, SortPeriod, PERIOD_LABELS } from "@/types/fund";

interface StatsBarProps {
  funds: Fund[];
  period: SortPeriod;
}

export default function StatsBar({ funds, period }: StatsBarProps) {
  if (funds.length === 0) return null;

  const returns = funds.map((f) => f.returns[period]);
  const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
  const rising = returns.filter((r) => r > 0).length;
  const falling = returns.filter((r) => r < 0).length;
  const topFund = funds[0]; // 已排序，第一個就是最高

  const periodLabel = PERIOD_LABELS[period];

  return (
    <div className="grid grid-cols-3 gap-3">
      {/* 最高回報 */}
      <div className="card p-3 text-center">
        <div className="text-xs text-gray-400 mb-1">{periodLabel}最高</div>
        <div className="text-lg font-bold text-emerald-600">
          +{topFund.returns[period].toFixed(2)}%
        </div>
        <div className="text-xs text-gray-500 truncate mt-0.5">
          {topFund.name.slice(0, 6)}...
        </div>
      </div>

      {/* 上升/下跌比例 */}
      <div className="card p-3 text-center">
        <div className="text-xs text-gray-400 mb-1">升跌比</div>
        <div className="flex items-center justify-center gap-1">
          <span className="text-sm font-bold text-emerald-600">{rising}↑</span>
          <span className="text-gray-300">/</span>
          <span className="text-sm font-bold text-red-500">{falling}↓</span>
        </div>
        <div className="text-xs text-gray-400 mt-0.5">
          共 {funds.length} 隻
        </div>
      </div>

      {/* 平均回報 */}
      <div className="card p-3 text-center">
        <div className="text-xs text-gray-400 mb-1">{periodLabel}平均</div>
        <div
          className={`text-lg font-bold ${
            avgReturn >= 0 ? "text-emerald-600" : "text-red-500"
          }`}
        >
          {avgReturn >= 0 ? "+" : ""}{avgReturn.toFixed(2)}%
        </div>
        <div className="text-xs text-gray-400 mt-0.5">全市場均值</div>
      </div>
    </div>
  );
}
