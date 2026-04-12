interface HeroHeaderProps {
  lastUpdated: string;
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-HK', {
      timeZone: 'Asia/Hong_Kong',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export default function HeroHeader({ lastUpdated }: HeroHeaderProps) {
  return (
    <header style={{ marginBottom: 28 }}>
      <h1
        style={{
          fontSize: 28,
          fontWeight: 800,
          background: 'linear-gradient(90deg, #4ade80, #22d3ee)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          lineHeight: 1.2,
          margin: 0,
        }}
      >
        🏇 MPF 強積金賽馬排名
      </h1>
      <p style={{ color: '#7d8a97', fontSize: 13, marginTop: 6, marginBottom: 0 }}>
        香港強積金基金回報比較
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10 }}>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            backgroundColor: '#4ade80',
            boxShadow: '0 0 6px rgba(74,222,128,0.8)',
            display: 'inline-block',
            flexShrink: 0,
          }}
        />
        <span style={{ color: '#7d8a97', fontSize: 12 }}>
          更新：{formatTime(lastUpdated)}
        </span>
      </div>
    </header>
  );
}
