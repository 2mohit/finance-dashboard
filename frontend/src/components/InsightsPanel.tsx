import type { MonthInsight } from "../types";

interface Props {
  insight: (MonthInsight & { month?: string }) | null;
}

export default function InsightsPanel({ insight }: Props) {
  if (!insight || !insight.summary) {
    return (
      <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">AI Insights</h2>
        <p className="text-slate-500 text-sm">No insights yet. Sync your emails to generate insights.</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-300">AI Insights</h2>
        {insight.month && (
          <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">
            {insight.month}
          </span>
        )}
      </div>

      {insight.alert && (
        <div className="rounded-lg bg-amber-950 border border-amber-800 px-4 py-3 text-sm text-amber-300">
          ⚠ {insight.alert}
        </div>
      )}

      <p className="text-sm text-slate-300 leading-relaxed">{insight.summary}</p>

      {insight.top_categories?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Top Spend</p>
          <div className="space-y-1.5">
            {insight.top_categories.map((item, i) => (
              <div key={i} className="flex justify-between text-sm">
                <span className="text-slate-300">{item.category}</span>
                <span className="text-slate-400 font-mono">₹{Number(item.amount).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {insight.saving_tips?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Tips</p>
          <ul className="space-y-1">
            {insight.saving_tips.map((tip, i) => (
              <li key={i} className="text-sm text-slate-400 flex gap-2">
                <span className="text-brand-500 shrink-0">→</span>
                <span>{tip}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
