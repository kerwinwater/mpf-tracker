/**
 * PeriodTabs 組件
 *
 * 時段選擇標籤欄，讓用戶在不同回報時段之間切換。
 * 設計類似 iOS 分段控制器（Segmented Control）。
 *
 * 時段選項：1週 | 1個月 | 3個月 | 6個月 | 1年 | 3年 | 5年
 */

"use client";

import { SortPeriod, PERIOD_LABELS } from "@/types/fund";

interface PeriodTabsProps {
  activePeriod: SortPeriod;
  onChange: (period: SortPeriod) => void;
}

const PERIODS: SortPeriod[] = [
  "oneWeek",
  "oneMonth",
  "threeMonths",
  "sixMonths",
  "oneYear",
  "threeYears",
  "fiveYears",
];

export default function PeriodTabs({ activePeriod, onChange }: PeriodTabsProps) {
  return (
    // 橫向可滾動，方便手機使用
    <div className="overflow-x-auto scrollbar-hide -mx-4 px-4">
      <div className="flex gap-1.5 bg-gray-100/80 rounded-xl p-1.5 w-max min-w-full">
        {PERIODS.map((period) => (
          <button
            key={period}
            onClick={() => onChange(period)}
            className={`
              px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 whitespace-nowrap
              ${activePeriod === period
                ? "bg-white text-blue-600 shadow-sm font-semibold"
                : "text-gray-500 hover:text-gray-700 active:bg-white/50"
              }
            `}
          >
            {PERIOD_LABELS[period]}
          </button>
        ))}
      </div>
    </div>
  );
}
