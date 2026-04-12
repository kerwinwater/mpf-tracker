# MPF 強積金賽馬排名 — 首頁改版規格

> 目標：強化「賽馬」主題識別度，提升資訊密度與視覺層次，讓頁面從「一般金融排行榜」升級為具品牌記憶點的產品。
> 網址：https://www.mpfrace.com/
> 範圍：首頁（排名列表檢視）

---

## 1. 設計原則

1. **保留現有深色主題**。不改變整體色系骨架（深色底 + 綠色強調色），僅在細節加入層次。
2. **賽馬語言滲透**。UI 文案、Icon、微互動都帶有賽馬語彙（頭馬、衝線、跑道、場均），但克制使用，避免變成卡通風。
3. **顏色即資訊**。所有進度條、數字顏色必須對應回報率區間，不做單一色塊。
4. **不破壞資料密度**。改版不應讓可見基金數量減少。

---

## 2. 配色系統

### 2.1 背景層
| 用途 | 顏色 |
|------|------|
| 頁面主背景 | `#0a0e14` |
| Hero 卡片背景 | `linear-gradient(180deg, #0f1720 0%, #0a0e14 100%)` |
| 一般卡片背景 | `#111827` |
| 卡片邊框 | `0.5px solid #1f2937` |

### 2.2 回報率分級色（關鍵）
進度條與數字顏色依回報率區間決定：

| 回報率區間 | 語意 | 進度條顏色 | 數字顏色 |
|------------|------|------------|----------|
| > 50% | 領先 | `linear-gradient(90deg, #059669 0%, #22c55e 60%, #86efac 100%)` | `#22c55e` |
| 20% ~ 50% | 中段 | `linear-gradient(90deg, #0d9488 0%, #14b8a6 100%)` | `#2dd4bf` |
| 0% ~ 20% | 溫和 | `#3b82f6` | `#60a5fa` |
| < 0% | 下跌 | `#ef4444` | `#ef4444` |

### 2.3 獎牌漸層（前三名）
使用徑向漸層創造金屬反光感：

| 名次 | 漸層 | 文字顏色 |
|------|------|----------|
| 1 金 | `radial-gradient(circle at 30% 30%, #fde68a, #d97706)` | `#422006` |
| 2 銀 | `radial-gradient(circle at 30% 30%, #f3f4f6, #9ca3af)` | `#1f2937` |
| 3 銅 | `radial-gradient(circle at 30% 30%, #fdba74, #c2410c)` | `#431407` |
| 4+ | `#1f2937` 實色 | `#9ca3af` |

⚠️ 現行第 2 名灰色過暗，必須更換為上述銀色漸層。

### 2.4 文字
| 用途 | 顏色 |
|------|------|
| 主要文字 | `#fff` |
| 次要文字 | `#d1d5db` |
| 輔助說明 | `#9ca3af` |
| 弱化 / 圖例 | `#6b7280` |

---

## 3. 結構與佈局

頁面由上到下分為五區：

1. **Header**：Logo 標題 + 資料來源狀態
2. **Hero 跑道區**（新增）：前 4 名以跑道樣式呈現，帶衝線視覺
3. **統計卡片區**：改以賽馬語言命名的三欄指標
4. **篩選區**：年份 + 類別 tag（維持現況，微調樣式）
5. **完整排名列表**：現行列表樣式 + 套用新進度條分級配色

---

## 4. 元件規格

### 4.1 Header
```
🏇 MPF 強積金賽馬排名        ● MPFA 數據
2025 年度 · 香港基金回報比較   更新 12/04 03:43
```
- 右上「MPFA 數據」前方的綠色圓點（`#22c55e`, 6×6 px, border-radius: 50%）代表資料同步狀態。

### 4.2 Hero 跑道區（新增）

顯示前 4 名基金，每一條為一條「跑道」：

**跑道容器**：
- 背景：漸層 `#0f1720 → #0a0e14`
- 邊框：`0.5px solid #1f2937`
- 圓角：12px
- 內距：18px 18px 14px
- **疊加紋理**：使用 `repeating-linear-gradient(90deg, transparent 0 38px, rgba(255,255,255,0.02) 38px 40px)` 作為 ::before 層，模擬跑道分隔線。

**標題列**：
- 左：「今季領先集團」(`13px #9ca3af`)
- 右：「🏁 2025 年終衝線」(`11px #6b7280`)

**每條跑道**（grid: 24px 1fr 70px, gap: 10px）：
- **左**：24×24 圓形名次徽章（獎牌漸層）
- **中**：14px 高的進度條，進度條內部左側顯示基金名稱（10px, 顏色依分級取暗色）
  - 進度寬度 = 回報率 / 該組最大回報率 × 100%（讓前 4 名的相對差距可視化）
- **右**：回報率百分比（12px, 500 weight, 顏色依分級）

**跑道條間距**：margin-bottom: 10px

### 4.3 統計卡片區

三欄等寬，gap: 10px。卡片樣式：
- 背景：`#111827`
- 邊框：`0.5px solid #1f2937`
- 圓角：10px
- 內距：12px

**卡片內容重新命名**：

| 原文案 | 新文案 | 主要數字 | 輔助說明 |
|--------|--------|----------|----------|
| 2025最高 | 🥇 頭馬回報 | 回報率（綠） | 頭馬基金名 |
| 升跌比 | 📊 升跌比 | `434 / 0`（綠 / 紅） | 全場 N 隻 |
| 2025平均 | ⚖️ 全場平均 | 均值（綠） | 場均回報 |

- 標題：11px, `#9ca3af`
- 主數字：18px, weight 500
- 輔助：10px, `#6b7280`

### 4.4 類別篩選 tag

- 選中狀態：背景 `#22c55e`，文字 `#042f2e`，weight 500
- 未選狀態：背景 `#111827`，邊框 `0.5px solid #1f2937`，文字 `#d1d5db`
- 內距：5px 12px
- 圓角：14px（膠囊形）
- 字級：12px
- 數量 badge 直接並排在名稱右側，不另加框

### 4.5 完整排名列表

保留現行卡片結構，但：
1. 進度條顏色改為第 2.2 節的分級配色
2. 回報率數字顏色依分級套用
3. 排名徽章 4 名之後改為 `#1f2937` 底 + `#9ca3af` 字，與前三名區隔

### 4.6 圖例（頁面底部新增）

排名列表下方加一條水平圖例說明顏色：

```
[綠漸層色條] 領先 >50%   [青漸層色條] 中段 20-50%   [藍] 溫和 0-20%   [紅] 下跌 <0%
```

- 色條：18×6 px，border-radius: 3px
- 字級：11px, `#6b7280`
- 間距：gap 14px
- 上邊框：`0.5px solid #1f2937`
- 頁面內距：8px 4px

---

## 5. 互動行為

| 元件 | 互動 |
|------|------|
| Hero 跑道條 | Hover 時底色微亮 `#1a2332`，cursor: pointer，點擊展開該基金詳情 |
| 類別 tag | 點擊切換篩選，切換時排名列表以 `opacity: 0 → 1` 200ms 淡入 |
| 排名列表項 | Hover 時邊框改為 `#374151`，點擊展開 |
| 進度條 | 首次載入時由 0 動畫增長至目標寬度，duration 600ms, ease-out |

---

## 6. 響應式

| 斷點 | 調整 |
|------|------|
| ≥1024px | 如現行設計 |
| 768 ~ 1023px | Hero 跑道區保留 4 條，統計卡片維持 3 欄 |
| < 768px | 統計卡片 3 欄改為 2+1 或水平捲動；Hero 跑道文字縮為 9px |
| < 480px | 類別 tag 改為水平捲動（overflow-x: auto），不換行 |

---

## 7. 不變更的項目

- 整體資訊架構（搜尋、年份分頁、類別、排行榜順序）
- 資料來源與更新邏輯
- 右下角浮動工具列（語言 / 主題 / 表情 / 設定）位置
- 免責聲明文字

---

## 8. 驗收清單

- [ ] 前 3 名徽章使用徑向漸層，金屬感明顯
- [ ] 第 2 名銀牌不再偏暗，與金銅名次視覺權重相當
- [ ] 所有進度條顏色依回報率四段分級
- [ ] 所有回報率數字顏色對應其進度條顏色
- [ ] Hero 跑道區背景帶有淡紋路（跑道感）
- [ ] 右側有 🏁 衝線標示
- [ ] 統計卡片三個標題使用 🥇 / 📊 / ⚖️ 並更名為「頭馬回報 / 升跌比 / 全場平均」
- [ ] 頁面底部有顏色分級圖例
- [ ] 進度條在首次載入時有動畫
- [ ] 手機版類別 tag 可水平捲動
- [ ] 深色主題下所有文字對比度符合 WCAG AA

---

## 9. 參考實作（HTML 片段）

```html
<div class="race-lane">
  <div class="medal medal-gold">1</div>
  <div class="track">
    <div class="bar bar-leading" style="width: 92%">
      <span class="fund-name">海通韓國基金 - A</span>
    </div>
  </div>
  <div class="return return-leading">+84.85%</div>
</div>
```

```css
.race-lane {
  display: grid;
  grid-template-columns: 24px 1fr 70px;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}
.medal-gold {
  width: 24px; height: 24px; border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, #fde68a, #d97706);
  color: #422006; font-weight: 500; font-size: 12px;
  display: flex; align-items: center; justify-content: center;
}
.track {
  position: relative; height: 14px;
  background: #111827; border-radius: 7px; overflow: hidden;
}
.bar-leading {
  position: absolute; left: 0; top: 0; height: 100%;
  background: linear-gradient(90deg, #059669 0%, #22c55e 60%, #86efac 100%);
  border-radius: 7px;
  transition: width 600ms ease-out;
}
.fund-name {
  position: absolute; left: 8px; top: 0; line-height: 14px;
  font-size: 10px; color: #022c22; font-weight: 500;
}
.return-leading { color: #22c55e; font-weight: 500; font-size: 12px; text-align: right; }
```

---

## 10. 建議實作順序

- [x] 1. 建立回報率分級工具函式 `getTier(rate) → 'leading' | 'middle' | 'mild' | 'down'`
- [x] 2. 替換全域的進度條與數字顏色邏輯（第 2.2 節）
- [x] 3. 更新獎牌徽章樣式（第 2.3 節）
- [x] 4. 改造統計卡片文案與 icon（第 4.3 節）
- [ ] 5. 新增 Hero 跑道區元件（第 4.2 節）
- [ ] 6. 新增底部圖例（第 4.6 節）
- [ ] 7. 加入進度條載入動畫（第 5 節）
- [ ] 8. 響應式驗證（第 6 節）

---

## v2 — Racing Theme（賽馬主題 UI）

### 主題概念

以「賽馬場」視覺語言重構整個頁面，深色模式為核心，霓虹漸層色為強調，讓基金回報排名如同賽馬直播般即時、緊張。

### Design Tokens

| Token | 值 |
|-------|----|
| 頁面主背景 | `#0a0f14` |
| 卡片背景 | `#0f1720` |
| 深卡片背景 | `#1a2430` |
| 邊框 | `rgba(148,163,184,0.08)` |
| 主文字 | `#e6edf3` |
| 次要文字 | `#b4c0cc` |
| 輔助文字 | `#7d8a97` |
| Tier Lead | `#4ade80`（進度條漸層 `#14532d→#22c55e→#86efac`） |
| Tier Mid | `#22d3ee`（進度條漸層 `#0e7490→#22d3ee→#a5f3fc`） |
| Tier Mild | `#60a5fa`（進度條漸層 `#1e3a8a→#3b82f6`） |
| Tier Down | `#f87171`（進度條漸層 `#7f1d1d→#ef4444`） |
| 金牌 | `radial-gradient(circle at 30% 30%, #fde047, #ca8a04)` + glow |
| 銀牌 | `linear-gradient(135deg, #e5e7eb, #9ca3af)` |
| 銅牌 | `linear-gradient(135deg, #fdba74, #c2410c)` |
| 圓角（卡片） | `12px` |
| 圓角（區塊） | `16px` |
| 圓角（chip） | `20px` |
| 數字排版 | `font-variant-numeric: tabular-nums` |

### Component 樹（`src/components/racing/`）

| 檔案 | 職責 |
|------|------|
| `RankBadge.tsx` | 圓形排名徽章，1–3 名獎牌色，其餘深灰 |
| `ReturnBadge.tsx` | 回報百分比文字，顏色依 Tier |
| `HeroHeader.tsx` | 漸層標題、副標、MPFA 狀態點、更新時間 |
| `RankBar.tsx` | 單行進度條：排名 + 名稱 + 受託人 + 進度條 + 回報 |
| `LeaderPack.tsx` | Top 5 卡片區塊，標題「今季領先集團」 |
| `StatCards.tsx` | 3 格統計卡：頭馬回報、升跌比、全場平均 |
| `CategoryTabs.tsx` | 類別 chip 篩選，選中 chip 有霓虹 glow |
| `ReturnLegend.tsx` | 四段 Tier 色塊圖例 |
| `PeriodSelector.tsx` | 7 個時段 chip（1週/1月/3月/6月/1年/3年/5年） |
| `FundList.tsx` | `@tanstack/react-virtual` 虛擬化列表，高度 600px |

### 互動規格

- **Period 切換**：`useState<Period>`，client-side sort，無網絡請求
- **Category filter**：`useState<string>`，client-side filter
- **FundList**：`useVirtualizer`，`estimateSize: 90px`，`overscan: 5`
- **數據源**：server component (`page.tsx`) 讀取 `data/funds.json`，以 props 傳入 client component
- **進度條寬度**：`max(returnPct / maxReturn * 100, 2)`（下限 2% 避免零長度）
