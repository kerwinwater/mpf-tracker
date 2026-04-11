# 💰 MPF 強積金基金比較平台

一站式香港強積金基金回報排名網站，每日自動從 MPFA 抓取最新數據。

## 功能特點

- 📊 **回報排名** — 顯示每週、每月、3個月、6個月、1年、3年、5年回報
- 🎨 **App Store 風格** — 卡片式設計，簡潔直觀
- 🔍 **即時搜索** — 按基金名稱、受託人搜索
- 🏷️ **類別篩選** — 股票基金、混合資產、債券、保本等
- 📱 **手機友好** — 響應式設計，完美支持手機瀏覽
- 🤖 **每日自動更新** — GitHub Actions 自動抓取 MPFA 數據

## 技術架構

```
mpf-tracker/
├── .github/workflows/
│   └── update-data.yml      # 每日自動更新數據
├── data/
│   └── funds.json           # 基金數據（自動生成）
├── scripts/
│   └── fetch-data.mjs       # MPFA 數據抓取腳本
├── src/
│   ├── app/
│   │   ├── layout.tsx        # 根佈局
│   │   ├── page.tsx          # 主頁（服務器端讀取數據）
│   │   └── FundListClient.tsx # 客戶端互動層
│   ├── components/
│   │   ├── FundCard.tsx      # 基金卡片
│   │   ├── PeriodTabs.tsx    # 時段選擇標籤
│   │   ├── CategoryFilter.tsx # 類別篩選
│   │   └── StatsBar.tsx      # 市場統計摘要
│   └── types/
│       └── fund.ts           # TypeScript 類型定義
└── vercel.json               # Vercel 部署配置
```

## 本地開發

```bash
# 安裝依賴
npm install

# 更新基金數據
npm run fetch-data

# 啟動開發服務器
npm run dev
```

## 部署到 Vercel

1. Fork 此倉庫到你的 GitHub 帳號
2. 在 [Vercel](https://vercel.com) 點擊 "New Project" 並導入倉庫
3. Framework: Next.js（自動偵測）
4. Build Command: `npm run build`（預設）
5. Output Directory: `out`
6. 點擊 Deploy！

## GitHub Actions 自動更新

GitHub Actions 已配置每個工作日 09:00 HKT 自動更新數據。
如需手動觸發，前往 GitHub → Actions → 每日更新 MPF 基金數據 → Run workflow。

**設定 Vercel Deploy Hook（可選）**

在 GitHub 倉庫 Settings → Secrets → Actions 中加入：
`VERCEL_DEPLOY_HOOK` = 你的 Vercel Deploy Hook URL

每次數據更新後會自動觸發 Vercel 重新部署。

## 數據來源

- **官方來源**: 香港強積金管理局 (MPFA) — [mfp.mpfa.org.hk](https://mfp.mpfa.org.hk)
- **更新頻率**: 每個工作日
- **免責聲明**: 本網站數據僅供參考，不構成任何投資建議

## License

MIT