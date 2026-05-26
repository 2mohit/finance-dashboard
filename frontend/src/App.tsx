import { useState, useEffect, useCallback } from "react";
import { api } from "./api";
import type { MonthlySummary, CategoryTotals, Transaction } from "./types";
import SyncButton from "./components/SyncButton";
import DataTab from "./components/DataTab";
import InsightsTab from "./components/InsightsTab";
import MonitorTab from "./components/MonitorTab";

type Tab = "data" | "insights" | "monitor";

const TABS: { id: Tab; label: string }[] = [
  { id: "data",     label: "Data" },
  { id: "insights", label: "Insights" },
  { id: "monitor",  label: "Monitor" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("data");
  const [summary, setSummary] = useState<MonthlySummary>({});
  const [categories, setCategories] = useState<CategoryTotals>({});
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [s, c, t] = await Promise.all([
        api.summary(),
        api.categories(),
        api.transactions(),
      ]);
      setSummary(s);
      setCategories(c);
      setTransactions(t);
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

  const totalTxns = transactions.length;
  const months = Object.keys(summary).length;

  return (
    <div className="min-h-screen bg-slate-950">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <header className="border-b border-slate-800 px-6 py-4 sticky top-0 z-20 bg-slate-950">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div>
              <h1 className="text-lg font-bold text-white">Finance Dashboard</h1>
              <p className="text-xs text-slate-500 mt-0.5">
                {backendOk === false
                  ? "⚠ Backend offline — start the FastAPI server"
                  : `${totalTxns} transactions · ${months} months`}
              </p>
            </div>

            {/* Tab bar */}
            <nav className="flex items-center gap-1 ml-4">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    tab === t.id
                      ? "bg-brand-600 text-white"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </nav>
          </div>

          <SyncButton onSyncComplete={loadData} />
        </div>
      </header>

      {/* ── Main content ───────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        {loading ? (
          <div className="flex items-center justify-center h-64 text-slate-500">
            Loading…
          </div>
        ) : (
          <>
            {tab === "data" && (
              <DataTab transactions={transactions} />
            )}
            {tab === "insights" && (
              <InsightsTab summary={summary} allCategories={categories} />
            )}
            {tab === "monitor" && (
              <MonitorTab />
            )}
          </>
        )}
      </main>
    </div>
  );
}
