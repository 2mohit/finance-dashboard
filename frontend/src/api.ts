import type { Transaction, MonthlySummary, CategoryTotals, MonthInsight, SyncStatus } from "./types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  health: () => get<{ status: string; transaction_count: number }>("/health"),

  transactions: (month?: string, category?: string) => {
    const params = new URLSearchParams();
    if (month) params.set("month", month);
    if (category) params.set("category", category);
    const qs = params.toString();
    return get<Transaction[]>(`/transactions${qs ? "?" + qs : ""}`);
  },

  summary: () => get<MonthlySummary>("/transactions/summary"),

  categories: () => get<CategoryTotals>("/transactions/categories"),

  insights: (month?: string) =>
    month
      ? get<MonthInsight>(`/insights?month=${month}`)
      : get<Record<string, MonthInsight>>("/insights"),

  latestInsight: () => get<MonthInsight & { month: string }>("/insights/latest"),

  triggerSync: (type = "all") =>
    fetch(`${BASE}/sync?type=${type}`, { method: "POST" }).then((r) => r.json()),

  syncStatus: () => get<SyncStatus>("/sync/status"),
};
