import type { Period } from '@/types/fund';
import { PERIOD_LABELS } from '@/types/fund';

interface PeriodSelectorProps {
  value: Period;
  onChange: (p: Period) => void;
}

const PERIODS: Period[] = [
  'oneWeek',
  'oneMonth',
  'threeMonths',
  'sixMonths',
  'oneYear',
  'threeYears',
  'fiveYears',
];

export default function PeriodSelector({ value, onChange }: PeriodSelectorProps) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 6,
        overflowX: 'auto',
        paddingBottom: 4,
        marginBottom: 16,
      }}
    >
      {PERIODS.map((p) => {
        const isActive = p === value;
        return (
          <button
            key={p}
            onClick={() => onChange(p)}
            style={{
              padding: '6px 14px',
              borderRadius: 20,
              fontSize: 12,
              fontWeight: 600,
              border: 'none',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              flexShrink: 0,
              background: isActive
                ? 'linear-gradient(90deg, #22c55e, #4ade80)'
                : 'rgba(255,255,255,0.06)',
              color: isActive ? '#052e16' : '#b4c0cc',
              boxShadow: isActive ? '0 0 8px rgba(74,222,128,0.35)' : 'none',
              transition: 'all 0.2s',
            }}
          >
            {PERIOD_LABELS[p]}
          </button>
        );
      })}
    </div>
  );
}
