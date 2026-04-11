/**
 * FundCard 組件
 *
 * 以 App Store 卡片風格顯示單個 MPF 基金的資訊。
 * 包含：排名、基金名稱、類別、回報數據、風險等級。
 *
 * 設計參考 App Store 的排行榜卡片：
 * - 左側排名號碼
 * - 中間基金名稱和類別
 * - 右側主要回報數字（大字）
 * - 底部多時段迷你回報列
 */

"use client";

import { Fund, RISK_LABELS, RISK_COLORS, SortPeriod, PERIOD_LABELS } from "@/types/fund";
import RankBadge from "./RankBadge";
import ReturnBadge from "./ReturnBadge";

interface FundCardProps {
  fund: Fund;
  rank: number;
  activePeriod: SortPeriod;
}

// 類別圖示對照表
const CATEGORY_ICONS: Record<string, string> = {
  "股票基金": "📈",
  "混合資產基金": "⚖️",
  "債券基金": "🏦",
  "保本基金": "🛡️",
  "貨幣市場基金": "💵",
  "保證基金": "✅",
  "強積金保守基金": "🔒",
};

// 受託人縮寫對照表
const PROVIDER_SHORT: Record<string, string> = {
  "宏利強積金": "宏利",
  "匯豐強積金": "匯豐",
  "中銀保誠": "中銀",
  "友邦強積金": "友邦",
  "富達強積金": "富達",
  "東亞強積金": "東亞",
  "信安強積金": "信安",
  "永明強積金": "永明",
  "BCT 強積金": "BCT",
  "交通銀行強積金": "交銀",
};

export default function FundCard({ fund, rank, activePeriod }: FundCardProps) {
  // 取得當前排序時段的回報值
  const mainReturn = fund.returns[activePeriod];

  // 其他時段（底部迷你顯示）
  const otherPeriods: SortPeriod[] = ["oneWeek", "oneMonth", "threeMonths", "oneYear"];
  const displayPeriods = otherPeriods.filter((p) => p !== activePeriod);

  const categoryIcon = CATEGORY_ICONS[fund.category] || "📊";
  const providerShort = PROVIDER_SHORT[fund.provider] || fund.provider.slice(0, 2);

  return (
    <div className="card p-4 group cursor-pointer">
      {/* 主要內容行 */}
      <div className="flex items-center gap-3">
        {/* 左側：排名徽章 */}
        <RankBadge rank={rank} />

        {/* 中間：基金圖示 + 名稱 */}
        <div
          className="w-11 h-11 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
          style={{
            background: `hsl(${(rank * 47) % 360}, 65%, 90%)`,
          }}
        >
          {categoryIcon}
        </div>

        <div className="flex-1 min-w-0">
          {/* 基金名稱（截短防溢出） */}
          <h3 className="font-semibold text-gray-900 text-sm leading-snug truncate">
            {fund.name}
          </h3>
          {/* 類別 + 受託人 */}
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="text-xs text-gray-400">{fund.category}</span>
            <span className="text-gray-200">·</span>
            <span className="text-xs text-gray-400">{providerShort}</span>
          </div>
        </div>

        {/* 右側：主回報（大字） */}
        <div className="text-right flex-shrink-0">
          <div className="text-xl font-bold leading-none">
            <ReturnBadge value={mainReturn} size="lg" />
          </div>
          <div className="text-xs text-gray-400 mt-1">
            {PERIOD_LABELS[activePeriod]}
          </div>
        </div>
      </div>

      {/* 分隔線 + 底部數據欄 */}
      <div className="mt-3 pt-3 border-t border-gray-50 flex items-center justify-between">
        {/* 風險等級 */}
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-medium ${RISK_COLORS[fund.riskLevel]}`}
        >
          {RISK_LABELS[fund.riskLevel]}
        </span>

        {/* 其他時段迷你回報 */}
        <div className="flex items-center gap-3">
          {displayPeriods.slice(0, 3).map((period) => (
            <div key={period} className="text-center">
              <div className="text-xs text-gray-400 leading-none mb-0.5">
                {PERIOD_LABELS[period]}
              </div>
              <ReturnBadge value={fund.returns[period]} size="sm" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
