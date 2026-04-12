'use client';

import { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { Fund, Period } from '@/types/fund';
import { getTier } from '@/lib/fund-tier';
import RankBar from './RankBar';

interface FundListProps {
  funds: Fund[];
  period: Period;
  maxReturn: number;
}

export default function FundList({ funds, period, maxReturn }: FundListProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: funds.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 90,
    overscan: 5,
  });

  if (funds.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '64px 0' }}>
        <div style={{ fontSize: 36, marginBottom: 12 }}>🔍</div>
        <p style={{ color: '#e6edf3', fontWeight: 600, margin: 0 }}>找不到相關基金</p>
        <p style={{ color: '#7d8a97', fontSize: 13, marginTop: 4 }}>試試其他類別</p>
      </div>
    );
  }

  return (
    <div
      ref={parentRef}
      style={{ height: 600, overflowY: 'auto', overflowX: 'hidden' }}
    >
      <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
        {virtualizer.getVirtualItems().map((virtualItem) => {
          const fund = funds[virtualItem.index];
          return (
            <div
              key={virtualItem.key}
              data-index={virtualItem.index}
              ref={virtualizer.measureElement}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualItem.start}px)`,
                paddingBottom: 8,
              }}
            >
              <RankBar
                rank={virtualItem.index + 1}
                name={fund.name}
                provider={fund.provider}
                returnPct={fund.returns[period]}
                maxReturn={maxReturn}
                tier={getTier(fund.returns[period])}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
