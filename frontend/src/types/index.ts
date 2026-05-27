export interface Transaction {
  date: string;
  description: string;
  amount: number | null;
  credit: number | null;
  category: string;
  source: string;
  raw?: string;
  pdf_file?: string;
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

export interface PdfMeta {
  filename: string;
  size_kb: number;
  transaction_count: number;
  unlocked: boolean;
}

export type AuditAction = "none" | "download" | "redownload_pdf" | "unlock";

export interface AuditEmail {
  id: string;
  bank: string;
  subject: string;
  date: string;
  in_cache: boolean;
  pdf_saved: boolean;
  pdf_unlocked: boolean;
  pdf_files: string[];
  action: AuditAction;
}

export interface AuditResult {
  emails: AuditEmail[];
  summary: {
    gmail_total: number;
    cached: number;
    pdf_saved: number;
    pdf_unlocked: number;
    needs_download: number;
    needs_redownload_pdf: number;
    needs_unlock: number;
    all_good: boolean;
  };
}

export interface ApiCall {
  ts: string;
  model: string;
  purpose: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface MonitorStats {
  cache: {
    last_sync: string | null;
    total_emails_processed: number;
    parse_cache_entries: number;
    last_emails_fetched?: number;
    last_emails_skipped_from_cache?: number;
    last_new_classified?: number;
    total_transactions?: number;
  };
  api_usage: {
    calls: ApiCall[];
    totals: {
      calls: number;
      input_tokens: number;
      output_tokens: number;
      cost_usd: number;
    };
  };
}

export const CATEGORY_COLORS: Record<string, string> = {
  DailyFood:         "#f97316",
  Dining:            "#fb923c",
  Groceries:         "#84cc16",
  Shopping:          "#a855f7",
  BabyShopping:      "#ec4899",
  Entertainment:     "#06b6d4",
  DailyTravel:       "#3b82f6",
  VacationTravel:    "#0ea5e9",
  BusinessTravel:    "#6366f1",
  Health:            "#10b981",
  "Bills & Utilities": "#64748b",
  Income:            "#22c55e",
  Other:             "#94a3b8",
};

export const ALL_CATEGORIES = Object.keys(CATEGORY_COLORS);
