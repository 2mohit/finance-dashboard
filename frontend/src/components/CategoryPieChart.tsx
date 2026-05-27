import { useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import type { CategoryTotals } from "../types";
import { CATEGORY_COLORS } from "../types";

interface Props {
  monthData: CategoryTotals;
  allData: CategoryTotals;
  monthLabel?: string;
}

const RADIAN = Math.PI / 180;

// Percentage label rendered inside each slice — skips tiny slices to avoid overlap
function PctLabel({
  cx, cy, midAngle, innerRadius, outerRadius, percent,
}: {
  cx: number; cy: number; midAngle: number;
  innerRadius: number; outerRadius: number; percent: number;
}) {
  if (percent < 0.05) return null; // skip slices < 5%
  const r = innerRadius + (outerRadius - innerRadius) * 0.55;
  const x = cx + r * Math.cos(-midAngle * RADIAN);
  const y = cy + r * Math.sin(-midAngle * RADIAN);
  return (
    <text
      x={x} y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      fontSize={11}
      fontWeight={700}
      style={{ pointerEvents: "none", textShadow: "0 1px 2px rgba(0,0,0,0.8)" }}
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
}

export default function CategoryPieChart({ monthData, allData, monthLabel }: Props) {
  const [view, setView] = useState<"month" | "all">("month");

  const raw = view === "month" ? monthData : allData;

  const entries = Object.entries(raw)
    .filter(([cat]) => cat !== "Income")
    .filter(([, v]) => v > 0)           // hide net-negative categories
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  const total = entries.reduce((s, [, v]) => s + v, 0);

  const chartData = entries.map(([name, value]) => ({
    name,
    value: Math.round(value),
    pct: total > 0 ? ((value / total) * 100).toFixed(1) : "0",
  }));

  return (
    <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-slate-300">Category Breakdown</h2>
        <div className="flex gap-1">
          <button
            onClick={() => setView("month")}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
              view === "month"
                ? "bg-brand-600 text-white"
                : "bg-slate-800 text-slate-400 hover:bg-slate-700"
            }`}
          >
            {monthLabel ?? "Month"}
          </button>
          <button
            onClick={() => setView("all")}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
              view === "all"
                ? "bg-brand-600 text-white"
                : "bg-slate-800 text-slate-400 hover:bg-slate-700"
            }`}
          >
            All Time
          </button>
        </div>
      </div>

      {chartData.length === 0 ? (
        <div className="flex items-center justify-center h-64 text-slate-500 text-sm">
          No spending data for this period
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="48%"
              innerRadius={68}
              outerRadius={108}
              paddingAngle={2}
              dataKey="value"
              labelLine={false}
              label={PctLabel}
              isAnimationActive={true}
            >
              {chartData.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={CATEGORY_COLORS[entry.name] ?? "#94a3b8"}
                  stroke="transparent"
                />
              ))}
            </Pie>

            <Tooltip
              formatter={(value: number, name: string, item: { payload: { pct: string } }) => [
                `₹${value.toLocaleString("en-IN")}  (${item.payload.pct}%)`,
                name,
              ]}
              contentStyle={{
                background: "#0f172a",
                border: "1px solid #334155",
                borderRadius: 10,
                fontSize: 12,
                padding: "8px 12px",
              }}
              itemStyle={{ color: "#e2e8f0" }}
              labelStyle={{ color: "#94a3b8", marginBottom: 4 }}
            />

            <Legend
              wrapperStyle={{ fontSize: 11, color: "#94a3b8", paddingTop: 8 }}
              formatter={(value) => (
                <span style={{ color: "#94a3b8" }}>{value}</span>
              )}
            />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
