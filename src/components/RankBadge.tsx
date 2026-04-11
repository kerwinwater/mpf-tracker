/**
 * RankBadge 組件
 *
 * 顯示基金排名的徽章，類似 App Store 的排行榜號碼。
 * - 第 1 名：金色
 * - 第 2 名：銀色
 * - 第 3 名：銅色
 * - 其他：灰色
 */

interface RankBadgeProps {
  rank: number;
}

export default function RankBadge({ rank }: RankBadgeProps) {
  let bgColor = "bg-gray-100 text-gray-500";
  let size = "w-7 h-7 text-sm";

  if (rank === 1) {
    bgColor = "bg-yellow-400 text-white";
    size = "w-8 h-8 text-base";
  } else if (rank === 2) {
    bgColor = "bg-gray-400 text-white";
    size = "w-7 h-7 text-sm";
  } else if (rank === 3) {
    bgColor = "bg-amber-600 text-white";
    size = "w-7 h-7 text-sm";
  }

  return (
    <div
      className={`${bgColor} ${size} rounded-full flex items-center justify-center font-bold flex-shrink-0`}
    >
      {rank}
    </div>
  );
}
