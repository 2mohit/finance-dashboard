import type { Transaction } from "../types";
import { CATEGORY_COLORS } from "../types";

interface Props {
  transactions: Transaction[];
}

export default function TransactionTable({ transactions }: Props) {
  const sorted = [...transactions].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 50);

  return (
    <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
      <h2 className="text-sm font-semibold text-slate-300 mb-4">Recent Transactions</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800">
              <th className="pb-2 text-left font-medium">Date</th>
              <th className="pb-2 text-left font-medium">Description</th>
              <th className="pb-2 text-left font-medium">Category</th>
              <th className="pb-2 text-right font-medium">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {sorted.map((t, i) => (
              <tr key={i} className="hover:bg-slate-800/50 transition-colors">
                <td className="py-2.5 pr-4 text-slate-500 font-mono text-xs whitespace-nowrap">
                  {t.date}
                </td>
                <td className="py-2.5 pr-4 text-slate-300 max-w-xs truncate">{t.description}</td>
                <td className="py-2.5 pr-4">
                  <span
                    className="px-2 py-0.5 rounded-full text-xs font-medium"
                    style={{
                      backgroundColor: (CATEGORY_COLORS[t.category] ?? "#94a3b8") + "22",
                      color: CATEGORY_COLORS[t.category] ?? "#94a3b8",
                    }}
                  >
                    {t.category}
                  </span>
                </td>
                <td className="py-2.5 text-right font-mono font-medium text-slate-200">
                  ₹{(t.amount ?? t.credit ?? 0).toLocaleString()}
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={4} className="py-8 text-center text-slate-500">
                  No transactions yet. Sync your emails to get started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
