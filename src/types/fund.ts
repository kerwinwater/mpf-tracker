/**
 * MPF 基金數據類型定義
 */

/** 基金回報數據（百分比） */
export interface FundReturns {
  oneYear:     number;   // 1 年回報
  sixMonths:   number;   // 6 個月回報
  threeMonths: number;   // 3 個月回報
  oneMonth:    number;   // 1 個月回報
  ytd:         number;   // 本年迄今回報
}

/** 單個 MPF 基金 */
export interface Fund {
  id:           string;
  name:         string;        // 基金名稱（繁體中文）
  provider:     string;        // 受託人
  category:     string;        // 基金類別
  price:        number;        // 單位價格（NAV）
  expenseRatio: number;        // 開支比率（%）
  returns:      FundReturns;
}

/** 數據檔案結構 */
export interface FundsData {
  lastUpdated:    string;      // ISO 8601 格式時間戳
  lastUpdatedHKT: string;
  dataSource:     string;      // "aastocks"
  note:           string;
  totalFunds:     number;
  funds:          Fund[];
}

/** 排序時段選項 */
export type SortPeriod =
  | "ytd"
  | "oneYear"
  | "sixMonths"
  | "threeMonths"
  | "oneMonth";

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
  ytd:         "本年迄今",
  oneYear:     "1年",
  sixMonths:   "6個月",
  threeMonths: "3個月",
  oneMonth:    "1個月",
};
