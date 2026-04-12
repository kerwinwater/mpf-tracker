"use client";

import { SortPeriod, PERIOD_LABELS } from "@/types/fund";

interface PeriodTabsProps {
  activePeriod: SortPeriod;
  onChange: (period: SortPeriod) => void;
}

const PERIODS: SortPeriod[] = [
  "ytd",
  "oneYear",
  "sixMonths",
  "threeMonths",
  "oneMonth",
];

export default function PeriodTabs({ activePeriod, onChange }: PeriodTabsProps) {
  return (
    <div className="overflow-x-auto scrollbar-hide -mx-4 px-4">
      <div
        className="flex gap-1 rounded-xl p-1 w-max min-w-full"
        style={{ backgroundColor: "rgba(255,255,255,0.05)" }}
      >
        {PERIODS.map((period) => {
          const isActive = activePeriod === period;
          return (
            <button
              key={period}
              onClick={() => onChange(period)}
              className="px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 whitespace-nowrap"
              style={{
                backgroundColor: isActive ? "#ffffff" : "transparent",
                color: isActive ? "#111" : "#888",
                fontWeight: isActive ? 600 : 400,
              }}
            >
              {PERIOD_LABELS[period]}
            </button>
          );
        })}
      </div>
    </div>
  );
}
