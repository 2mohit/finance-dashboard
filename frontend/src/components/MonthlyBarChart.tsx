import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { MonthlySummary } from "../types";
import { CATEGORY_COLORS } from "../types";

interface Props {
  data: MonthlySummary;
}

const TOP_CATEGORIES = [
  "DailyFood",
  "Dining",
  "Groceries",
  "Shopping",
  "BabyShopping",
  "DailyTravel",
  "Bills & Utilities",
  "Entertainment",
];

export default function MonthlyBarChart({ data }: Props) {
  const months = Object.keys(data).sort();

  const chartData = months.map((month) => ({
    month: month.slice(5), // "2024-11" → "11"
    ...TOP_CATEGORIES.reduce(
      (acc, cat) => ({
        ...acc,
        // Floor at 0: refunds reduce the net but a negative bar is misleading
        // on a spending chart. Net-negative categories (big refund month) show as 0.
        [cat]: Math.max(0, Math.round(data[month]?.[cat] ?? 0)),
      }),
      {}
    ),
  }));

  return (
    <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
      <h2 className="text-sm font-semibold text-slate-300 mb-4">Monthly Spend by Category</h2>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <XAxis dataKey="month" tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} width={48} />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
            labelStyle={{ color: "#94a3b8" }}
          />
          <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
          {TOP_CATEGORIES.map((cat) => (
            <Bar key={cat} dataKey={cat} stackId="a" fill={CATEGORY_COLORS[cat]} radius={[0, 0, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
