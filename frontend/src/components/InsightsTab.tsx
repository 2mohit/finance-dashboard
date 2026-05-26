import { useState, useEffect } from "react";
import { api } from "../api";
import type { MonthlySummary, CategoryTotals, MonthInsight } from "../types";
import StatCard from "./StatCard";
import MonthlyBarChart from "./MonthlyBarChart";
import CategoryPieChart from "./CategoryPieChart";
import InsightsPanel from "./InsightsPanel";

interface Props {
  summary: MonthlySummary;
  allCategories: CategoryTotals;
}

export default function InsightsTab({ summary, allCategories }: Props) {
  const months = Object.keys(summary).sort().reverse();
  const [selectedMonth, setSelectedMonth] = useState<string>(months[0] ?? "");
  const [insight, setInsight] = useState<(MonthInsight & { month?: string }) | null>(null);
  const [loadingInsight, setLoadingInsight] = useState(false);

  // Month-specific totals
  const monthData = selectedMonth ? summary[selectedMonth] ?? {} : {};
  const monthSpend = Object.entries(monthData)
    .filter(([cat]) => cat !== "Income")
    .reduce((s, [, v]) => s + v, 0);
  const monthIncome = monthData["Income"] ?? 0;
  const monthTxnCount = monthData ? Object.values(monthData).reduce((s, v) => s + Math.abs(v), 0) : 0; // not txn count

  // All-time stats for stat cards at top
  const totalSpend = Object.entries(allCategories)
    .filter(([cat]) => cat !== "Income")
    .reduce((s, [, v]) => s + v, 0);
  const totalIncome = allCategories["Income"] ?? 0;

  useEffect(() => {
    if (!selectedMonth) return;
    setLoadingInsight(true);
    api.insights(selectedMonth)
      .then((ins) => {
        if (ins && (ins as MonthInsight).summary) {
          setInsight({ ...(ins as MonthInsight), month: selectedMonth });
        } else {
          setInsight(null);
        }
      })
      .catch(() => setInsight(null))
      .finally(() => setLoadingInsight(false));
  }, [selectedMonth]);

  // Build month-specific category totals for pie chart
  const monthCategoryTotals: CategoryTotals = monthData;

  return (
    <div className="space-y-6">
      {/* Top stat cards + month selector */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 flex-1">
          <StatCard
            label="All-Time Spend"
            value={`₹${Math.round(totalSpend).toLocaleString()}`}
            sub="across all months"
            accent="text-red-400"
          />
          <StatCard
            label="All-Time Income"
            value={`₹${Math.round(totalIncome).toLocaleString()}`}
            sub="across all months"
            accent="text-green-400"
          />
          <StatCard
            label={`${selectedMonth} Spend`}
            value={`₹${Math.round(monthSpend).toLocaleString()}`}
            sub="selected month"
            accent="text-orange-400"
          />
          <StatCard
            label={`${selectedMonth} Income`}
            value={`₹${Math.round(monthIncome).toLocaleString()}`}
            sub="selected month"
            accent="text-emerald-400"
          />
        </div>

        {/* Month selector */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-slate-500">Month</span>
          <div className="flex gap-1 flex-wrap">
            {months.map((m) => (
              <button
                key={m}
                onClick={() => setSelectedMonth(m)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                  selectedMonth === m
                    ? "bg-brand-600 text-white"
                    : "bg-slate-800 text-slate-400 hover:bg-slate-700"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <MonthlyBarChart data={summary} />
        <CategoryPieChart data={monthCategoryTotals} />
      </div>

      {/* AI Insights panel — full width */}
      <div>
        {loadingInsight ? (
          <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6 text-slate-500 text-sm">
            Loading insights for {selectedMonth}…
          </div>
        ) : (
          <InsightsPanel insight={insight} />
        )}
      </div>
    </div>
  );
}
