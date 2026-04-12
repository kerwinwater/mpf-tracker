import { Fund, SortPeriod } from "@/types/fund";
import { getTier, TIER_TEXT } from "@/lib/tier";

interface StatsBarProps {
  funds: Fund[];
  period: SortPeriod;
}

export default function StatsBar({ funds, period }: StatsBarProps) {
  if (funds.length === 0) return null;

  const returns = funds.map((f) => f.returns[period] ?? 0);
  const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
  const rising  = returns.filter((r) => r > 0).length;
  const falling = returns.filter((r) => r < 0).length;
  const topFund = funds[0];
  const topReturn = topFund.returns[period] ?? 0;

  // §2.3 卡片樣式
  const cardStyle = {
    backgroundColor: "#111827",
    border: "0.5px solid #1f2937",
    borderRadius: "10px",
    padding: "12px",
    textAlign: "center" as const,
  };

  return (
    <div className="grid grid-cols-3 gap-3">

      {/* 🥇 頭馬回報 */}
      <div style={cardStyle}>
        <div style={{ fontSize: 11, color: "#9ca3af", marginBottom: 6 }}>
          🥇 頭馬回報
        </div>
        <div
          style={{
            fontSize: 18,
            fontWeight: 500,
            fontVariantNumeric: "tabular-nums",
            color: TIER_TEXT[getTier(topReturn)],
            lineHeight: 1.1,
          }}
        >
          {topReturn >= 0 ? "+" : ""}
          {topReturn.toFixed(2)}%
        </div>
        <div
          className="truncate mt-1"
          style={{ fontSize: 10, color: "#6b7280" }}
          title={topFund.name}
        >
          {topFund.name.length > 10 ? topFund.name.slice(0, 10) + "…" : topFund.name}
        </div>
      </div>

      {/* 📊 升跌比 */}
      <div style={cardStyle}>
        <div style={{ fontSize: 11, color: "#9ca3af", marginBottom: 6 }}>
          📊 升跌比
        </div>
        <div className="flex items-center justify-center gap-1.5" style={{ lineHeight: 1.1 }}>
          <span
            style={{ fontSize: 18, fontWeight: 500, fontVariantNumeric: "tabular-nums", color: "#22c55e" }}
          >
            {rising}↑
          </span>
          <span style={{ color: "#374151", fontSize: 14 }}>/</span>
          <span
            style={{ fontSize: 18, fontWeight: 500, fontVariantNumeric: "tabular-nums", color: "#ef4444" }}
          >
            {falling}↓
          </span>
        </div>
        <div style={{ fontSize: 10, color: "#6b7280", marginTop: 4 }}>
          全場 {funds.length} 隻
        </div>
      </div>

      {/* ⚖️ 全場平均 */}
      <div style={cardStyle}>
        <div style={{ fontSize: 11, color: "#9ca3af", marginBottom: 6 }}>
          ⚖️ 全場平均
        </div>
        <div
          style={{
            fontSize: 18,
            fontWeight: 500,
            fontVariantNumeric: "tabular-nums",
            color: TIER_TEXT[getTier(avgReturn)],
            lineHeight: 1.1,
          }}
        >
          {avgReturn >= 0 ? "+" : ""}
          {avgReturn.toFixed(2)}%
        </div>
        <div style={{ fontSize: 10, color: "#6b7280", marginTop: 4 }}>
          場均回報
        </div>
      </div>

    </div>
  );
}
