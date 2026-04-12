# MPF 強積金賽馬排名 — 項目指引

## 1. 項目簡介

**網站**：[mpfrace.com](https://www.mpfrace.com/)

香港強積金（MPF）基金回報比較平台，以賽馬排名的形式呈現全市場基金的短期與長期回報，協助用戶快速比較不同受託人和基金類別的表現。

---

## 2. 技術架構

| 層次 | 技術 |
|------|------|
| 前端框架 | Next.js 14（App Router） |
| 樣式 | Tailwind CSS + 自定義 CSS |
| 部署平台 | Vercel（main branch 自動部署） |
| 數據更新 | GitHub Actions（每日 18:00 HKT 自動執行） |
| 語言 | TypeScript（前端）+ Python 3.11（爬蟲） |

---

## 3. 數據來源

### 主要：aastocks.com
- URL：`http://www.aastocks.com/tc/mpf/search.aspx?tab=1&s=3&o=1&sp=&t=1&r=1`
- 數據轉載自積金局，包含：名稱、類別、單位價格、1年/6月/3月/1月/本年迄今回報、開支比率
- 爬蟲：`scripts/fetch_aastocks.py`

### 備用：MPFA 積金局
- URL：`https://mfp.mpfa.org.hk/tch/mpp_list.jsp`
- 包含：2025/2024/2023 年度回報、3年/5年累計回報
- 爬蟲：`scripts/fetch_mpfa.py`（備用，現已不在主流程）

---

## 4. 重要文件位置

```
mpf-tracker/
├── src/
│   ├── app/
│   │   └── FundListClient.tsx       # 前端主文件（篩選、排序、列表）
│   ├── components/
│   │   ├── FundCard.tsx             # 基金卡片（進度條、回報顯示）
│   │   ├── StatsBar.tsx             # 統計卡片（頭馬/升跌比/平均）
│   │   ├── PeriodTabs.tsx           # 時段切換標籤
│   │   └── CategoryFilter.tsx       # 類別篩選
│   ├── lib/
│   │   └── tier.ts                  # 回報率分級工具（getTier）
│   └── types/
│       └── fund.ts                  # TypeScript 類型定義
├── public/
│   └── data/
│       └── funds.json               # 爬蟲生成的基金數據（自動更新）
├── scripts/
│   ├── fetch_aastocks.py            # 主爬蟲（aastocks.com）
│   └── fetch_mpfa.py                # 備用爬蟲（MPFA）
├── .github/
│   └── workflows/
│       └── update-data.yml          # GitHub Actions 自動更新排程
└── docs/
    ├── CLAUDE.md                    # 本文件
    ├── redesign-spec.md             # 改版規格
    └── images/                      # UI 截圖與參考圖
```

---

## 5. 設計原則

1. **深色賽馬主題**
   - 頁面主背景：`#0a0e14`
   - 卡片背景：`#111827`
   - 邊框：`0.5px solid #1f2937`

2. **顏色即資訊**（回報率四段分色）
   - 領先 >50%：綠漸層 `#059669 → #22c55e → #86efac`
   - 中段 20-50%：青漸層 `#0d9488 → #14b8a6`
   - 溫和 0-20%：藍 `#3b82f6`
   - 下跌 <0%：紅 `#ef4444`
   - 實作工具：`src/lib/tier.ts` 的 `getTier(rate)`

3. **保留現有介面結構**
   - 不減少可見基金數量
   - 維持搜尋、篩選、排序功能
   - Header 固定置頂

4. **改版規格**
   - 詳見 `docs/redesign-spec.md`

---

## 6. 開發注意事項

### Git 規範
- ⚠️ **每次 push 前確認在 `main` branch**（`git branch --show-current`）
- 遠端 URL 使用本地代理，push 需臨時切換為 PAT URL

### 免責聲明
- ⚠️ **不要修改免責聲明文字**
- 位置：`src/app/FundListClient.tsx` 頁尾 `<footer>` 區塊
- 現行文字：「以上資料轉載至積金局，資料更新時間以積金局公布為準。基金價格為最新資料，僅作參考之用。」

### funds.json 格式
```json
{
  "lastUpdated": "ISO 8601",
  "lastUpdatedHKT": "YYYY-MM-DD HH:MM HKT",
  "totalFunds": 434,
  "dataSource": "aastocks",
  "funds": [{
    "id": "aa_0001",
    "name": "基金名稱",
    "provider": "受託人",
    "category": "股票基金",
    "price": 12.3456,
    "expenseRatio": 1.23,
    "returns": {
      "oneYear": 12.34,
      "sixMonths": 5.67,
      "threeMonths": 2.34,
      "oneMonth": 0.56,
      "ytd": 3.45
    }
  }]
}
```

### GitHub Actions
- 排程：`0 10 * * 1-5`（UTC）= 18:00 HKT 週一至週五
- 觸發：亦可手動於 GitHub Actions 頁面 Run workflow
- 超時：20 分鐘
