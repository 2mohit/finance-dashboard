export interface Transaction {
  date: string;
  description: string;
  amount: number | null;
  credit: number | null;
  category: string;
  source: string;
  raw?: string;
}

export interface MonthlySummary {
  [month: string]: {
    [category: string]: number;
  };
}

export interface CategoryTotals {
  [category: string]: number;
}

export interface MonthInsight {
  summary: string;
  top_categories: Array<{ category: string; amount: number }>;
  saving_tips: string[];
  alert: string | null;
  generated_at?: string;
}

export interface SyncStatus {
  running: boolean;
  last_result: {
    emails_fetched: number;
    transactions_parsed: number;
    new_transactions: number;
    total_transactions: number;
  } | null;
}

export const CATEGORY_COLORS: Record<string, string> = {
  "Food & Dining": "#f97316",
  Groceries: "#84cc16",
  Shopping: "#a855f7",
  Transport: "#3b82f6",
  Entertainment: "#ec4899",
  "Bills & Utilities": "#64748b",
  Health: "#10b981",
  Travel: "#f59e0b",
  Income: "#22c55e",
  Other: "#94a3b8",
};
