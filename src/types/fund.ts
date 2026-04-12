/**
 * MPF 基金數據類型定義
 */

/** 基金回報數據（百分比） */
export type FundReturns = {
  oneWeek:     number;   // 1 週回報
  oneMonth:    number;   // 1 個月回報
  threeMonths: number;   // 3 個月回報
  sixMonths:   number;   // 6 個月回報
  oneYear:     number;   // 1 年回報
  threeYears:  number;   // 3 年回報
  fiveYears:   number;   // 5 年回報
};

export type Period = keyof FundReturns;

/** 單個 MPF 基金 */
export type Fund = {
  id:         string;
  name:       string;        // 基金名稱（繁體中文）
  provider:   string;        // 受託人
  category:   string;        // 基金類別
  riskLevel:  number;        // 風險等級 1-5
  nav:        number;        // 單位資產淨值
  currency:   string;        // "HKD"
  fundSize:   number;        // 基金規模
  launchYear: number;        // 成立年份
  returns:    FundReturns;
};

/** 數據檔案結構 */
export interface FundsData {
  lastUpdated:    string;      // ISO 8601 格式時間戳
  lastUpdatedHKT: string;
  dataSource:     string;
  note:           string;
  totalFunds:     number;
  funds:          Fund[];
}

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
export const PERIOD_LABELS: Record<Period, string> = {
  oneWeek:     "1週",
  oneMonth:    "1個月",
  threeMonths: "3個月",
  sixMonths:   "6個月",
  oneYear:     "1年",
  threeYears:  "3年",
  fiveYears:   "5年",
};
