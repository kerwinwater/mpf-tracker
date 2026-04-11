import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MPF 強積金賽馬排名 | 基金回報比較",
  description:
    "一站式香港強積金基金表現比較平台。查看每週、每月、每年回報排名，找出最佳表現的 MPF 基金。數據來源：積金局 MPFA。",
  keywords: "MPF, 強積金, 基金比較, 回報排名, 香港, MPFA, 積金局",
  openGraph: {
    title: "MPF 強積金賽馬排名",
    description: "香港強積金基金回報排名 — 每日自動更新",
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
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="theme-color" content="#0f1117" />
      </head>
      <body className="min-h-screen" style={{ backgroundColor: "#0f1117" }}>
        {children}
      </body>
    </html>
  );
}
