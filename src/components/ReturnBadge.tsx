/**
 * ReturnBadge 組件
 *
 * 顯示基金回報百分比的徽章。
 * - 正數：綠色（上升）
 * - 負數：紅色（下跌）
 * - 零：灰色
 *
 * 這與 App Store 評分的視覺設計一致。
 */

interface ReturnBadgeProps {
  value: number;      // 回報百分比
  size?: "sm" | "md" | "lg";
  showSign?: boolean; // 是否顯示 +/- 號
}

export default function ReturnBadge({
  value,
  size = "md",
  showSign = true,
}: ReturnBadgeProps) {
  const isPositive = value > 0;
  const isNegative = value < 0;

  // 根據大小設定文字樣式
  const sizeClasses = {
    sm: "text-xs font-medium",
    md: "text-sm font-semibold",
    lg: "text-base font-bold",
  };

  // 根據正負設定顏色
  const colorClass = isPositive
    ? "text-emerald-600"
    : isNegative
    ? "text-red-500"
    : "text-gray-400";

  // 格式化數字顯示（最多 2 位小數）
  const formatted = Math.abs(value).toFixed(2);
  const sign = isPositive && showSign ? "+" : isNegative ? "−" : "";

  return (
    <span className={`${sizeClasses[size]} ${colorClass} tabular-nums`}>
      {sign}{formatted}%
    </span>
  );
}
