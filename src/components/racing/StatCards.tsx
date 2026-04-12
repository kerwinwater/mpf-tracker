interface Stats {
  max: number;
  up: number;
  down: number;
  avg: number;
  leader: string;
  total: number;
}

interface StatCardsProps {
  stats: Stats;
}

function Card({
  icon,
  label,
  value,
  sub,
}: {
  icon: string;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div
      style={{
        backgroundColor: '#0f1720',
        border: '1px solid rgba(148,163,184,0.08)',
        borderRadius: 12,
        padding: '12px 14px',
      }}
    >
      <div style={{ fontSize: 18 }}>{icon}</div>
      <div style={{ color: '#7d8a97', fontSize: 11, marginTop: 6 }}>{label}</div>
      <div
        style={{
          color: '#e6edf3',
          fontSize: 16,
          fontWeight: 700,
          marginTop: 2,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {value}
      </div>
      {sub && (
        <div
          style={{
            color: '#7d8a97',
            fontSize: 11,
            marginTop: 2,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {sub}
        </div>
      )}
    </div>
  );
}

export default function StatCards({ stats }: StatCardsProps) {
  const maxSign = stats.max >= 0 ? '+' : '';
  const avgSign = stats.avg >= 0 ? '+' : '';

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 10,
        marginBottom: 16,
      }}
    >
      <Card
        icon="🏆"
        label="頭馬回報"
        value={`${maxSign}${stats.max.toFixed(2)}%`}
        sub={stats.leader}
      />
      <Card
        icon="📊"
        label="升跌比"
        value={`${stats.up} / ${stats.down}`}
        sub={`共 ${stats.total} 隻`}
      />
      <Card
        icon="⚖️"
        label="全場平均"
        value={`${avgSign}${stats.avg.toFixed(2)}%`}
      />
    </div>
  );
}
