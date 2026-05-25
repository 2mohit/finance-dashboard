import { useState, useEffect, useCallback } from "react";
import { api } from "./api";
import type { MonthlySummary, CategoryTotals, Transaction, MonthInsight } from "./types";
import StatCard from "./components/StatCard";
import MonthlyBarChart from "./components/MonthlyBarChart";
import CategoryPieChart from "./components/CategoryPieChart";
import InsightsPanel from "./components/InsightsPanel";
import TransactionTable from "./components/TransactionTable";
import SyncButton from "./components/SyncButton";

export default function App() {
  const [summary, setSummary] = useState<MonthlySummary>({});
  const [categories, setCategories] = useState<CategoryTotals>({});
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [insight, setInsight] = useState<(MonthInsight & { month?: string }) | null>(null);
  const [loading, setLoading] = useState(true);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [s, c, t, i] = await Promise.all([
        api.summary(),
        api.categories(),
        api.transactions(),
        api.latestInsight().catch(() => null),
      ]);
      setSummary(s);
      setCategories(c);
      setTransactions(t);
      setInsight(i);
      setBackendOk(true);
    } catch {
      setBackendOk(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Derived stats
  const totalSpend = Object.values(categories)
    .filter((_, i) => Object.keys(categories)[i] !== "Income")
    .reduce((a, b) => a + b, 0);
  const totalIncome = categories["Income"] ?? 0;
  const totalTxns = transactions.length;
  const months = Object.keys(summary).length;

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Header */}
      <header className="border-b border-slate-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-white">Finance Dashboard</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              {backendOk === false
                ? "⚠ Backend offline — start the FastAPI server"
                : `${totalTxns} transactions · ${months} months`}
            </p>
          </div>
          <SyncButton onSyncComplete={loadData} />
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {loading ? (
          <div className="flex items-center justify-center h-64 text-slate-500">Loading…</div>
        ) : (
          <>
            {/* Stat cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                label="Total Spend"
                value={`₹${Math.round(totalSpend).toLocaleString()}`}
                sub="all time"
                accent="text-red-400"
              />
              <StatCard
                label="Total Income"
                value={`₹${Math.round(totalIncome).toLocaleString()}`}
                sub="all time"
                accent="text-green-400"
              />
              <StatCard
                label="Net Savings"
                value={`₹${Math.round(totalIncome - totalSpend).toLocaleString()}`}
                sub="income − spend"
                accent={totalIncome - totalSpend >= 0 ? "text-green-400" : "text-red-400"}
              />
              <StatCard
                label="Transactions"
                value={totalTxns.toString()}
                sub={`across ${months} months`}
              />
            </div>

            {/* Charts row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <MonthlyBarChart data={summary} />
              <CategoryPieChart data={categories} />
            </div>

            {/* Insights + table */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-1">
                <InsightsPanel insight={insight} />
              </div>
              <div className="lg:col-span-2">
                <TransactionTable transactions={transactions} />
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
