"use client";

import { useEffect, useState } from "react";
import { Fund, SortPeriod, PERIOD_LABELS } from "@/types/fund";
import { getTier, TIER_BAR, TIER_TEXT } from "@/lib/tier";

interface FundCardProps {
  fund: Fund;
  rank: number;
  activePeriod: SortPeriod;
  maxAbsReturn: number;
}

const MEDALS = ["🥇", "🥈", "🥉"];

// Always show these 3 periods in the mini-stats row
const MINI_PERIODS: SortPeriod[] = ["oneMonth", "sixMonths", "oneYear"];

/** §2.3 獎牌漸層（前三名金屬感） */
function getRankStyle(rank: number): { background: string; color: string } {
  if (rank === 1) return {
    background: "radial-gradient(circle at 30% 30%, #fde68a, #d97706)",
    color: "#422006",
  };
  if (rank === 2) return {
    background: "radial-gradient(circle at 30% 30%, #f3f4f6, #9ca3af)",
    color: "#1f2937",
  };
  if (rank === 3) return {
    background: "radial-gradient(circle at 30% 30%, #fdba74, #c2410c)",
    color: "#431407",
  };
  return { background: "#1f2937", color: "#9ca3af" };
}

export default function FundCard({
  fund,
  rank,
  activePeriod,
  maxAbsReturn,
}: FundCardProps) {
  const mainReturn = fund.returns[activePeriod] ?? 0;
  const isPositive = mainReturn >= 0;
  const tier = getTier(mainReturn);

  const barPct =
    maxAbsReturn > 0
      ? Math.min((Math.abs(mainReturn) / maxAbsReturn) * 100, 100)
      : 0;

  // Re-animate bar whenever period or rank changes
  const [revealed, setRevealed] = useState(false);
  useEffect(() => {
    setRevealed(false);
    let rafId: number;
    let timerId: ReturnType<typeof setTimeout>;
    rafId = requestAnimationFrame(() => {
      timerId = setTimeout(() => setRevealed(true), rank * 30);
    });
    return () => {
      cancelAnimationFrame(rafId);
      clearTimeout(timerId);
    };
  }, [rank, activePeriod]);

  const rankStyle = getRankStyle(rank);
  const medal = rank <= 3 ? MEDALS[rank - 1] : null;

  // §2.2 分級配色
  const returnColor = TIER_TEXT[tier];
  const barBackground = TIER_BAR[tier];

  return (
    <div className="racing-card">
      {/* ─── Row 1: rank · name · return ─── */}
      <div className="flex items-center gap-3">
        {/* Rank circle — §2.3 漸層徽章 */}
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
          style={{ background: rankStyle.background, color: rankStyle.color }}
        >
          {rank}
        </div>

        {/* Name + provider + price */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 leading-snug">
            {medal && (
              <span className="text-base leading-none flex-shrink-0">{medal}</span>
            )}
            <h3 className="text-sm font-semibold text-white truncate">
              {fund.name}
            </h3>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            {fund.provider && (
              <p className="text-xs truncate" style={{ color: "#9ca3af" }}>
                {fund.provider}
              </p>
            )}
            {fund.price > 0 && (
              <span
                className="text-[11px] tabular-nums flex-shrink-0"
                style={{ color: "#6b7280" }}
              >
                ${fund.price.toFixed(4)}
              </span>
            )}
          </div>
        </div>

        {/* Main return — §2.2 分級顏色 */}
        <div className="flex-shrink-0 text-right">
          <div
            className="text-xl font-bold tabular-nums leading-none"
            style={{ color: returnColor }}
          >
            {isPositive ? "+" : ""}
            {mainReturn.toFixed(2)}%
          </div>
          <div className="text-[11px] mt-1" style={{ color: "#6b7280" }}>
            {PERIOD_LABELS[activePeriod]}
          </div>
        </div>
      </div>

      {/* ─── Row 2: racing bar — §2.2 分級漸層 ─── */}
      <div
        className="mt-3 h-2 rounded-full overflow-hidden"
        style={{ backgroundColor: "#111827" }}
      >
        <div
          className="h-full rounded-full"
          style={{
            width: `${barPct}%`,
            background: barBackground,
            transition: revealed ? "width 0.6s ease-out" : "none",
          }}
        />
      </div>

      {/* ─── Row 3: mini stats (1M / 6M / 1Y) ─── */}
      <div className="mt-2 flex items-center gap-4 flex-wrap">
        {MINI_PERIODS.map((p) => {
          const val = fund.returns[p] ?? 0;
          const miniTier = getTier(val);
          const isActive = p === activePeriod;
          return (
            <div key={p} className="flex items-center gap-1">
              <span
                className="text-[11px]"
                style={{ color: isActive ? "#d1d5db" : "#6b7280" }}
              >
                {PERIOD_LABELS[p]}
              </span>
              <span
                className="text-[11px] font-medium tabular-nums"
                style={{
                  color: TIER_TEXT[miniTier],
                  opacity: isActive ? 1 : 0.75,
                }}
              >
                {val >= 0 ? "+" : ""}
                {val.toFixed(1)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
