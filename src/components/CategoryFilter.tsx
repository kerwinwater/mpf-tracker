"use client";

import { FUND_CATEGORIES } from "@/types/fund";

type Category = typeof FUND_CATEGORIES[number];

interface CategoryFilterProps {
  activeCategory: Category;
  onChange: (category: Category) => void;
  counts: Record<string, number>;
}

const ICONS: Record<string, string> = {
  "全部類別":    "🏠",
  "股票基金":    "📈",
  "混合資產基金": "⚖️",
  "債券基金":    "🏦",
  "保本基金":    "🛡️",
  "貨幣市場基金": "💵",
  "保證基金":    "✅",
  "強積金保守基金": "🔒",
};

export default function CategoryFilter({
  activeCategory,
  onChange,
  counts,
}: CategoryFilterProps) {
  return (
    <div className="overflow-x-auto scrollbar-hide -mx-4 px-4">
      <div className="flex gap-2 pb-1 w-max">
        {FUND_CATEGORIES.map((category) => {
          const isActive = activeCategory === category;
          const count = counts[category] ?? 0;

          return (
            <button
              key={category}
              onClick={() => onChange(category)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200 whitespace-nowrap"
              style={{
                backgroundColor: isActive ? "#4ade80" : "rgba(255,255,255,0.07)",
                color: isActive ? "#0f1117" : "#888",
                border: isActive ? "1px solid #4ade80" : "1px solid rgba(255,255,255,0.1)",
              }}
            >
              <span>{ICONS[category] ?? "📊"}</span>
              <span>{category}</span>
              {count > 0 && (
                <span
                  className="text-xs px-1.5 py-0.5 rounded-full min-w-[20px] text-center tabular-nums"
                  style={{
                    backgroundColor: isActive
                      ? "rgba(0,0,0,0.15)"
                      : "rgba(255,255,255,0.08)",
                    color: isActive ? "#0f1117" : "#666",
                  }}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
