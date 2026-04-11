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
  const topFund = funds[0];

  const periodLabel = PERIOD_LABELS[period];

  const cardStyle = {
    backgroundColor: "#1a1d27",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: "0.75rem",
    padding: "0.75rem",
    textAlign: "center" as const,
  };

  return (
    <div className="grid grid-cols-3 gap-3">
      {/* 最高回報 */}
      <div style={cardStyle}>
        <div className="text-xs mb-1" style={{ color: "#888" }}>
          {periodLabel}最高
        </div>
        <div className="text-base font-bold tabular-nums" style={{ color: "#4ade80" }}>
          +{topFund.returns[period].toFixed(2)}%
        </div>
        <div className="text-xs truncate mt-0.5" style={{ color: "#666" }}>
          {topFund.name.length > 8 ? topFund.name.slice(0, 8) + "…" : topFund.name}
        </div>
      </div>

      {/* 升跌比例 */}
      <div style={cardStyle}>
        <div className="text-xs mb-1" style={{ color: "#888" }}>
          升跌比
        </div>
        <div className="flex items-center justify-center gap-1.5">
          <span className="text-sm font-bold tabular-nums" style={{ color: "#4ade80" }}>
            {rising}↑
          </span>
          <span style={{ color: "#444" }}>/</span>
          <span className="text-sm font-bold tabular-nums" style={{ color: "#f87171" }}>
            {falling}↓
          </span>
        </div>
        <div className="text-xs mt-0.5" style={{ color: "#666" }}>
          共 {funds.length} 隻
        </div>
      </div>

      {/* 平均回報 */}
      <div style={cardStyle}>
        <div className="text-xs mb-1" style={{ color: "#888" }}>
          {periodLabel}平均
        </div>
        <div
          className="text-base font-bold tabular-nums"
          style={{ color: avgReturn >= 0 ? "#4ade80" : "#f87171" }}
        >
          {avgReturn >= 0 ? "+" : ""}
          {avgReturn.toFixed(2)}%
        </div>
        <div className="text-xs mt-0.5" style={{ color: "#666" }}>
          全市場均值
        </div>
      </div>
    </div>
  );
}
