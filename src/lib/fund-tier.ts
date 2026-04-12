export type Tier = 'lead' | 'mid' | 'mild' | 'down';

export function getTier(pct: number): Tier {
  if (pct < 0) return 'down';
  if (pct < 20) return 'mild';
  if (pct < 50) return 'mid';
  return 'lead';
}

export const TIER_TEXT_COLOR: Record<Tier, string> = {
  lead: '#4ade80',
  mid:  '#22d3ee',
  mild: '#60a5fa',
  down: '#f87171',
};

export const TIER_BAR_GRADIENT: Record<Tier, string> = {
  lead: 'linear-gradient(90deg,#14532d 0%,#22c55e 60%,#86efac 100%)',
  mid:  'linear-gradient(90deg,#0e7490 0%,#22d3ee 60%,#a5f3fc 100%)',
  mild: 'linear-gradient(90deg,#1e3a8a 0%,#3b82f6 100%)',
  down: 'linear-gradient(90deg,#7f1d1d 0%,#ef4444 100%)',
};
