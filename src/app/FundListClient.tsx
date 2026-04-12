'use client';

import { useState, useMemo } from 'react';
import type { Fund, Period } from '@/types/fund';
import HeroHeader from '@/components/racing/HeroHeader';
import PeriodSelector from '@/components/racing/PeriodSelector';
import LeaderPack from '@/components/racing/LeaderPack';
import StatCards from '@/components/racing/StatCards';
import CategoryTabs from '@/components/racing/CategoryTabs';
import ReturnLegend from '@/components/racing/ReturnLegend';
import FundList from '@/components/racing/FundList';

interface FundListClientProps {
  funds: Fund[];
  lastUpdated: string;
}

export default function FundListClient({ funds, lastUpdated }: FundListClientProps) {
  const [period, setPeriod] = useState<Period>('oneYear');
  const [category, setCategory] = useState<string>('all');

  const sorted = useMemo(
    () => [...funds].sort((a, b) => b.returns[period] - a.returns[period]),
    [funds, period]
  );

  const top5 = sorted.slice(0, 5);
  const maxReturn = sorted[0]?.returns[period] ?? 1;

  const filtered = useMemo(
    () => (category === 'all' ? sorted : sorted.filter((f) => f.category === category)),
    [sorted, category]
  );

  const stats = useMemo(() => {
    const values = sorted.map((f) => f.returns[period]);
    const max = values[0] ?? 0;
    const up = values.filter((v) => v > 0).length;
    const down = values.filter((v) => v < 0).length;
    const avg = values.reduce((s, v) => s + v, 0) / (values.length || 1);
    return { max, up, down, avg, leader: sorted[0]?.name ?? '-', total: sorted.length };
  }, [sorted, period]);

  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    for (const f of funds) {
      counts.set(f.category, (counts.get(f.category) ?? 0) + 1);
    }
    return [
      { id: 'all', label: '全部', count: funds.length },
      ...Array.from(counts).map(([id, count]) => ({ id, label: id, count })),
    ];
  }, [funds]);

  return (
    <>
      <main
        style={{
          minHeight: '100vh',
          backgroundColor: '#0a0f14',
          color: '#e6edf3',
        }}
      >
        <div
          style={{
            maxWidth: 800,
            margin: '0 auto',
            padding: '32px 16px',
          }}
        >
          <HeroHeader lastUpdated={lastUpdated} />
          <PeriodSelector value={period} onChange={setPeriod} />
          <LeaderPack funds={top5} period={period} maxReturn={maxReturn} />
          <StatCards stats={stats} />
          <CategoryTabs categories={categories} activeId={category} onChange={setCategory} />
          <ReturnLegend />
          <FundList funds={filtered} period={period} maxReturn={maxReturn} />
        </div>
      </main>

      {/* ─── 頁尾 ──────────────────────────────────────────────────────────── */}
      <footer
        style={{
          backgroundColor: '#0a0f14',
          padding: '0 16px 40px',
        }}
      >
        <div
          style={{
            maxWidth: 800,
            margin: '0 auto',
          }}
        >
          <div
            style={{
              borderRadius: 12,
              padding: 16,
              border: '1px solid rgba(251,191,36,0.15)',
              backgroundColor: '#1a1d27',
            }}
          >
            <p
              style={{
                fontSize: 12,
                lineHeight: 1.7,
                color: '#9a8a60',
                margin: 0,
              }}
            >
              <span style={{ color: '#fbbf24', fontWeight: 500 }}>⚠️ 免責聲明：</span>
              以上資料轉載至積金局，資料更新時間以積金局公布為準。基金價格為最新資料，僅作參考之用。
              <br />
              本網站僅供參考，不構成任何投資建議。強積金投資涉及風險，基金過往表現並不代表將來表現。
              如需查閱官方數據，請訪問{' '}
              <a
                href="https://mfp.mpfa.org.hk"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: '#fbbf24', textDecoration: 'underline', textUnderlineOffset: 2 }}
              >
                積金局官方網站
              </a>
              。
            </p>
          </div>
          <p
            style={{
              textAlign: 'center',
              fontSize: 12,
              marginTop: 16,
              color: '#555',
            }}
          >
            數據來源：香港強積金管理局 (MPFA) · 每日自動更新
            <br />
            共 {funds.length} 個基金
          </p>
        </div>
      </footer>
    </>
  );
}
