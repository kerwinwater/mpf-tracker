/**
 * CategoryFilter 組件
 *
 * 基金類別篩選欄，水平滾動的標籤列表。
 * 設計類似 App Store 的類別選擇橫向滾動條。
 *
 * 點擊類別可篩選顯示特定類型的基金。
 */

"use client";

import { FUND_CATEGORIES } from "@/types/fund";

type Category = typeof FUND_CATEGORIES[number];

interface CategoryFilterProps {
  activeCategory: Category;
  onChange: (category: Category) => void;
  counts: Record<string, number>; // 每個類別的基金數量
}

// 類別圖示
const ICONS: Record<string, string> = {
  "全部類別": "🏠",
  "股票基金": "📈",
  "混合資產基金": "⚖️",
  "債券基金": "🏦",
  "保本基金": "🛡️",
  "貨幣市場基金": "💵",
  "保證基金": "✅",
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
              className={`
                flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium
                transition-all duration-200 whitespace-nowrap border
                ${isActive
                  ? "bg-blue-600 text-white border-blue-600 shadow-sm"
                  : "bg-white text-gray-600 border-gray-200 hover:border-blue-300 hover:text-blue-600"
                }
              `}
            >
              <span>{ICONS[category]}</span>
              <span>{category}</span>
              {/* 顯示該類別的基金數量 */}
              {count > 0 && (
                <span
                  className={`
                    text-xs px-1.5 py-0.5 rounded-full min-w-[20px] text-center
                    ${isActive ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-500"}
                  `}
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
