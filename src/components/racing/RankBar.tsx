import type { Tier } from '@/lib/fund-tier';
import { TIER_BAR_GRADIENT } from '@/lib/fund-tier';
import RankBadge from './RankBadge';
import ReturnBadge from './ReturnBadge';

interface RankBarProps {
  rank: number;
  name: string;
  provider: string;
  returnPct: number;
  maxReturn: number;
  tier: Tier;
}

const GLOW: Record<Tier, string> = {
  lead: 'rgba(74,222,128,0.25)',
  mid:  'rgba(34,211,238,0.25)',
  mild: 'rgba(96,165,250,0.2)',
  down: 'rgba(248,113,113,0.2)',
};

export default function RankBar({ rank, name, provider, returnPct, maxReturn, tier }: RankBarProps) {
  const widthPct = maxReturn > 0
    ? Math.max((returnPct / maxReturn) * 100, returnPct > 0 ? 2 : 0)
    : 0;

  return (
    <div
      style={{
        backgroundColor: '#0f1720',
        border: '1px solid rgba(148,163,184,0.08)',
        borderRadius: 12,
        padding: '10px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <RankBadge rank={rank} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              color: '#e6edf3',
              fontSize: 13,
              fontWeight: 600,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {name}
          </div>
          <div style={{ color: '#7d8a97', fontSize: 11, marginTop: 2 }}>{provider}</div>
        </div>
        <ReturnBadge value={returnPct} size="md" />
      </div>
      <div
        style={{
          height: 6,
          backgroundColor: 'rgba(255,255,255,0.06)',
          borderRadius: 3,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${widthPct}%`,
            background: TIER_BAR_GRADIENT[tier],
            borderRadius: 3,
            boxShadow: `0 0 8px ${GLOW[tier]}`,
            transition: 'width 0.4s ease',
          }}
        />
      </div>
    </div>
  );
}
