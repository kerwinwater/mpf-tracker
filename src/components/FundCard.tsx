"use client";

import { useEffect, useState } from "react";
import { Fund, SortPeriod, PERIOD_LABELS } from "@/types/fund";

interface FundCardProps {
  fund: Fund;
  rank: number;
  activePeriod: SortPeriod;
  maxAbsReturn: number;
}

const MEDALS = ["🥇", "🥈", "🥉"];

// Always show these 3 periods in the mini-stats row
const MINI_PERIODS: SortPeriod[] = ["year2025", "year2024", "fiveYears"];

function getRankStyle(rank: number): { bg: string; color: string } {
  if (rank === 1) return { bg: "#fbbf24", color: "#000" };
  if (rank === 2) return { bg: "#9ca3af", color: "#000" };
  if (rank === 3) return { bg: "#b45309", color: "#fff" };
  return { bg: "rgba(255,255,255,0.08)", color: "#888" };
}

export default function FundCard({
  fund,
  rank,
  activePeriod,
  maxAbsReturn,
}: FundCardProps) {
  const mainReturn = fund.returns[activePeriod] ?? 0;
  const isPositive = mainReturn >= 0;

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

  const returnColor = isPositive ? "#4ade80" : "#f87171";
  const barGradient = isPositive
    ? "linear-gradient(90deg, rgba(74,222,128,0.5), #4ade80)"
    : "linear-gradient(90deg, rgba(248,113,113,0.5), #f87171)";

  return (
    <div className="racing-card">
      {/* ─── Row 1: rank · name · return ─── */}
      <div className="flex items-center gap-3">
        {/* Rank circle */}
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
          style={{ backgroundColor: rankStyle.bg, color: rankStyle.color }}
        >
          {rank}
        </div>

        {/* Name + provider */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 leading-snug">
            {medal && (
              <span className="text-base leading-none flex-shrink-0">{medal}</span>
            )}
            <h3 className="text-sm font-semibold text-white truncate">
              {fund.name}
            </h3>
          </div>
          <p className="text-xs truncate mt-0.5" style={{ color: "#888" }}>
            {fund.provider}
          </p>
        </div>

        {/* Main return (big) */}
        <div className="flex-shrink-0 text-right">
          <div
            className="text-xl font-bold tabular-nums leading-none"
            style={{ color: returnColor }}
          >
            {isPositive ? "+" : ""}
            {mainReturn.toFixed(2)}%
          </div>
          <div className="text-[11px] mt-1" style={{ color: "#666" }}>
            {PERIOD_LABELS[activePeriod]}
          </div>
        </div>
      </div>

      {/* ─── Row 2: racing bar ─── */}
      <div
        className="mt-3 h-2 rounded-full overflow-hidden"
        style={{ backgroundColor: "rgba(255,255,255,0.05)" }}
      >
        <div
          className="h-full rounded-full"
          style={{
            width: `${barPct}%`,
            background: barGradient,
            transition: revealed ? "width 0.8s cubic-bezier(0.25,1,0.5,1)" : "none",
          }}
        />
      </div>

      {/* ─── Row 3: mini stats (1週 / 1月 / 1年) ─── */}
      <div className="mt-2 flex items-center gap-4 flex-wrap">
        {MINI_PERIODS.map((p) => {
          const val = fund.returns[p];
          const pos = val >= 0;
          const isActive = p === activePeriod;
          return (
            <div key={p} className="flex items-center gap-1">
              <span
                className="text-[11px]"
                style={{ color: isActive ? "#aaa" : "#555" }}
              >
                {PERIOD_LABELS[p]}
              </span>
              <span
                className="text-[11px] font-medium tabular-nums"
                style={{
                  color: pos ? "#4ade80" : "#f87171",
                  opacity: isActive ? 1 : 0.85,
                }}
              >
                {pos ? "+" : ""}
                {val.toFixed(1)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
