import { getTier, TIER_TEXT_COLOR } from '@/lib/fund-tier';

interface ReturnBadgeProps {
  value: number;
  size?: 'sm' | 'md' | 'lg';
}

const FONT_SIZE = { sm: 12, md: 14, lg: 16 } as const;
const FONT_WEIGHT = { sm: 500, md: 600, lg: 700 } as const;

export default function ReturnBadge({ value, size = 'md' }: ReturnBadgeProps) {
  const color = TIER_TEXT_COLOR[getTier(value)];
  const sign = value > 0 ? '+' : '';

  return (
    <span
      style={{
        color,
        fontSize: FONT_SIZE[size],
        fontWeight: FONT_WEIGHT[size],
        fontVariantNumeric: 'tabular-nums',
      }}
    >
      {sign}{value.toFixed(2)}%
    </span>
  );
}
