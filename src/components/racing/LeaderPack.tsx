import type { Fund, Period } from '@/types/fund';
import { getTier } from '@/lib/fund-tier';
import RankBar from './RankBar';

interface LeaderPackProps {
  funds: Fund[];
  period: Period;
  maxReturn: number;
}

export default function LeaderPack({ funds, period, maxReturn }: LeaderPackProps) {
  const year = new Date().getFullYear();

  return (
    <section
      style={{
        backgroundColor: '#0f1720',
        borderRadius: 16,
        padding: 20,
        marginBottom: 16,
        border: '1px solid rgba(148,163,184,0.08)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 14,
        }}
      >
        <h2 style={{ color: '#e6edf3', fontSize: 14, fontWeight: 700, margin: 0 }}>
          今季領先集團
        </h2>
        <span style={{ color: '#7d8a97', fontSize: 12 }}>🏁 {year} 年終衝線</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {funds.map((fund, i) => (
          <RankBar
            key={fund.id}
            rank={i + 1}
            name={fund.name}
            provider={fund.provider}
            returnPct={fund.returns[period]}
            maxReturn={maxReturn}
            tier={getTier(fund.returns[period])}
          />
        ))}
      </div>
    </section>
  );
}
