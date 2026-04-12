import type { Tier } from '@/lib/fund-tier';
import { TIER_BAR_GRADIENT, TIER_TEXT_COLOR } from '@/lib/fund-tier';

const ENTRIES: { tier: Tier; label: string; range: string }[] = [
  { tier: 'lead', label: '領先', range: '≥ 50%' },
  { tier: 'mid',  label: '中段', range: '20–50%' },
  { tier: 'mild', label: '溫和', range: '0–20%' },
  { tier: 'down', label: '下跌', range: '< 0%' },
];

export default function ReturnLegend() {
  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        flexWrap: 'wrap',
        marginBottom: 12,
      }}
    >
      {ENTRIES.map(({ tier, label, range }) => (
        <div key={tier} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div
            style={{
              width: 32,
              height: 6,
              borderRadius: 3,
              background: TIER_BAR_GRADIENT[tier],
              flexShrink: 0,
            }}
          />
          <span style={{ color: TIER_TEXT_COLOR[tier], fontSize: 12, fontWeight: 600 }}>
            {label}
          </span>
          <span style={{ color: '#7d8a97', fontSize: 11 }}>{range}</span>
        </div>
      ))}
    </div>
  );
}
