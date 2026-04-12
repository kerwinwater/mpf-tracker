interface RankBadgeProps {
  rank: number;
}

export default function RankBadge({ rank }: RankBadgeProps) {
  const style: React.CSSProperties = (() => {
    if (rank === 1) return {
      background: 'radial-gradient(circle at 30% 30%, #fde047, #ca8a04)',
      boxShadow: '0 0 12px rgba(253,224,71,0.4)',
      color: '#1a0e00',
    };
    if (rank === 2) return {
      background: 'linear-gradient(135deg, #e5e7eb, #9ca3af)',
      color: '#1f2937',
    };
    if (rank === 3) return {
      background: 'linear-gradient(135deg, #fdba74, #c2410c)',
      color: '#fff',
    };
    return {
      background: '#2a3441',
      color: '#b4c0cc',
    };
  })();

  return (
    <div
      style={{
        ...style,
        width: 28,
        height: 28,
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 13,
        fontWeight: 700,
        flexShrink: 0,
      }}
    >
      {rank}
    </div>
  );
}
