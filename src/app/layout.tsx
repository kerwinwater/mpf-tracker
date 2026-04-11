/**
 * 根佈局 (Root Layout)
 *
 * 這是 Next.js App Router 的最外層佈局組件。
 * 定義了整個網站的 HTML 結構、SEO metadata 和全域字體。
 */

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MPF 強積金基金比較 | 回報排名",
  description:
    "一站式香港強積金基金表現比較平台。查看每週、每月、每年回報排名，找出最佳表現的 MPF 基金。數據來源：積金局 MPFA。",
  keywords: "MPF, 強積金, 基金比較, 回報排名, 香港, MPFA, 積金局",
  openGraph: {
    title: "MPF 強積金基金比較",
    description: "香港強積金基金回報排名 - 每週自動更新",
    locale: "zh_HK",
    type: "website",
  },
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-HK">
      <head>
        {/* 設定視窗寬度，讓手機版顯示正常 */}
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {/* PWA 設定 */}
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
      </head>
      <body className="min-h-screen bg-gray-50">{children}</body>
    </html>
  );
}
