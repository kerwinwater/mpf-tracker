/**
 * MPF 基金數據類型定義
 * 此檔案定義所有基金相關的 TypeScript 介面
 */

/** 基金回報數據（百分比） */
export interface FundReturns {
  year2025: number;      // 2025 年度回報（YTD）
  year2024: number;      // 2024 年度回報
  year2023: number;      // 2023 年度回報
  threeYears: number;    // 3 年累積回報（2023-2025 複利）
  fiveYears: number;     // 5 年累積回報
}

/** 單個 MPF 基金 */
export interface Fund {
  id: string;
  name: string;          // 基金名稱（繁體中文）
  provider: string;      // 受託人（例：宏利強積金）
  scheme: string;        // 計劃名稱
  category: string;      // 基金類別
  riskLevel: number;     // 風險等級 1-7
  nav: number;           // 最新資產淨值
  currency: string;      // 貨幣（HKD）
  fundSize?: number;     // 基金規模（億港元，選用）
  returns: FundReturns;
}

/** 數據檔案結構 */
export interface FundsData {
  lastUpdated: string;   // ISO 8601 格式時間戳
  lastUpdatedHKT?: string;
  dataSource: string;    // 數據來源（"mpfa" 或 "fallback"）
  note: string;          // 數據說明
  totalFunds: number;    // 基金總數
  funds: Fund[];
}

/** 排序時段選項 */
export type SortPeriod =
  | "year2025"
  | "year2024"
  | "year2023"
  | "threeYears"
  | "fiveYears";

/** 基金類別 */
export const FUND_CATEGORIES = [
  "全部類別",
  "股票基金",
  "混合資產基金",
  "債券基金",
  "保本基金",
  "貨幣市場基金",
  "保證基金",
  "強積金保守基金",
] as const;

/** 時段標籤對照 */
export const PERIOD_LABELS: Record<SortPeriod, string> = {
  year2025:   "2025",
  year2024:   "2024",
  year2023:   "2023",
  threeYears: "3年",
  fiveYears:  "5年",
};

/** 風險等級標籤 */
export const RISK_LABELS: Record<number, string> = {
  1: "甚低風險",
  2: "低風險",
  3: "中風險",
  4: "中至高風險",
  5: "高風險",
  6: "高風險",
  7: "甚高風險",
};
