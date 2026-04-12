import { readFileSync } from 'fs';
import { join } from 'path';
import type { Metadata } from 'next';
import FundListClient from './FundListClient';
import type { FundsData } from '@/types/fund';

export const metadata: Metadata = {
  title: 'MPF 強積金賽馬排名 | 基金回報比較',
  description:
    '一站式香港強積金基金表現比較平台。查看每週、每月、每年回報排名，找出最佳表現的 MPF 基金。數據來源：積金局 MPFA。',
  keywords: 'MPF, 強積金, 基金比較, 回報排名, 香港, MPFA, 積金局',
  openGraph: {
    title: 'MPF 強積金賽馬排名',
    description: '香港強積金基金回報排名 — 每日自動更新',
    locale: 'zh_HK',
    type: 'website',
  },
  icons: { icon: '/favicon.svg' },
};

export default function HomePage() {
  const raw = readFileSync(join(process.cwd(), 'data', 'funds.json'), 'utf-8');
  const data: FundsData = JSON.parse(raw);

  return (
    <div style={{ backgroundColor: '#0a0f14' }}>
      <FundListClient funds={data.funds} lastUpdated={data.lastUpdated} />
    </div>
  );
}
