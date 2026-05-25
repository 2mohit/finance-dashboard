import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import type { CategoryTotals } from "../types";
import { CATEGORY_COLORS } from "../types";

interface Props {
  data: CategoryTotals;
}

export default function CategoryPieChart({ data }: Props) {
  const entries = Object.entries(data)
    .filter(([cat]) => cat !== "Income")
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);

  const chartData = entries.map(([name, value]) => ({ name, value: Math.round(value) }));

  return (
    <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
      <h2 className="text-sm font-semibold text-slate-300 mb-4">All-Time Category Breakdown</h2>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={70}
            outerRadius={110}
            paddingAngle={2}
            dataKey="value"
          >
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={CATEGORY_COLORS[entry.name] ?? "#94a3b8"} />
            ))}
          </Pie>
          <Tooltip
            formatter={(v: number) => `₹${v.toLocaleString()}`}
            contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
          />
          <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
