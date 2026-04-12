/**
 * 回報率分級工具
 * 依據 MPF 賽馬改版規格 §2.2 四段分色系統
 */

export type Tier = "leading" | "middle" | "mild" | "down";

/** 依回報率取分級 */
export function getTier(rate: number): Tier {
  if (rate > 50) return "leading";
  if (rate >= 20) return "middle";
  if (rate >= 0)  return "mild";
  return "down";
}

/** 進度條背景（gradient 或純色） */
export const TIER_BAR: Record<Tier, string> = {
  leading: "linear-gradient(90deg, #059669 0%, #22c55e 60%, #86efac 100%)",
  middle:  "linear-gradient(90deg, #0d9488 0%, #14b8a6 100%)",
  mild:    "#3b82f6",
  down:    "#ef4444",
};

/** 數字文字顏色 */
export const TIER_TEXT: Record<Tier, string> = {
  leading: "#22c55e",
  middle:  "#2dd4bf",
  mild:    "#60a5fa",
  down:    "#ef4444",
};
