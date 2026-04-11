/**
 * MPF 基金數據類型定義
 * 此檔案定義所有基金相關的 TypeScript 介面
 */

/** 基金回報數據（百分比） */
export interface FundReturns {
  oneWeek: number;       // 1 週回報
  oneMonth: number;      // 1 個月回報
  threeMonths: number;   // 3 個月回報
  sixMonths: number;     // 6 個月回報
  oneYear: number;       // 1 年回報
  threeYears: number;    // 3 年累積回報
  fiveYears: number;     // 5 年累積回報
}

/** 單個 MPF 基金 */
export interface Fund {
  id: string;
  name: string;          // 基金名稱（繁體中文）
  provider: string;      // 受託人（例：宏利強積金）
  category: string;      // 基金類別
  riskLevel: number;     // 風險等級 1-5（1=最低，5=最高）
  nav: number;           // 最新資產淨值
  currency: string;      // 貨幣（HKD）
  fundSize?: number;     // 基金規模（億港元，選用）
  launchYear?: number;   // 成立年份（選用）
  returns: FundReturns;
}

/** 數據檔案結構 */
export interface FundsData {
  lastUpdated: string;   // ISO 8601 格式時間戳
  dataSource: string;    // 數據來源（"mpfa" 或 "fallback"）
  note: string;          // 數據說明
  totalFunds: number;    // 基金總數
  funds: Fund[];
}

/** 排序時段選項 */
export type SortPeriod =
  | "oneWeek"
  | "oneMonth"
  | "threeMonths"
  | "sixMonths"
  | "oneYear"
  | "threeYears"
  | "fiveYears";

/** 排序方向 */
export type SortOrder = "desc" | "asc";

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
  oneWeek: "1週",
  oneMonth: "1個月",
  threeMonths: "3個月",
  sixMonths: "6個月",
  oneYear: "1年",
  threeYears: "3年",
  fiveYears: "5年",
};

/** 風險等級標籤 */
export const RISK_LABELS: Record<number, string> = {
  1: "極低風險",
  2: "低風險",
  3: "中風險",
  4: "中高風險",
  5: "高風險",
};

/** 風險等級顏色 */
export const RISK_COLORS: Record<number, string> = {
  1: "text-emerald-600 bg-emerald-50",
  2: "text-blue-600 bg-blue-50",
  3: "text-amber-600 bg-amber-50",
  4: "text-orange-600 bg-orange-50",
  5: "text-red-600 bg-red-50",
};
