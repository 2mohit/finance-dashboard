import { useState, useEffect } from "react";
import { api } from "../api";
import type { MonitorStats, ApiCall } from "../types";

function fmt(n: number) {
  return n.toLocaleString();
}

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function modelBadge(model: string) {
  if (model.includes("haiku"))
    return { label: "Haiku", color: "text-sky-400", bg: "bg-sky-400/10" };
  if (model.includes("sonnet"))
    return { label: "Sonnet", color: "text-violet-400", bg: "bg-violet-400/10" };
  return { label: model, color: "text-slate-400", bg: "bg-slate-700" };
}

export default function MonitorTab() {
  const [stats, setStats] = useState<MonitorStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api
      .monitor()
      .then(setStats)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return (
      <div className="flex items-center justify-center h-64 text-slate-500">Loading…</div>
    );

  if (error || !stats)
    return (
      <div className="text-red-400 p-6">Failed to load monitor stats. Is the backend running?</div>
    );

  const { cache, api_usage } = stats;
  const calls: ApiCall[] = api_usage.calls ?? [];
  const totals = api_usage.totals;

  // Group cost by model
  const byModel: Record<string, { calls: number; cost: number; input: number; output: number }> = {};
  for (const c of calls) {
    if (!byModel[c.model])
      byModel[c.model] = { calls: 0, cost: 0, input: 0, output: 0 };
    byModel[c.model].calls++;
    byModel[c.model].cost += c.cost_usd;
    byModel[c.model].input += c.input_tokens;
    byModel[c.model].output += c.output_tokens;
  }

  return (
    <div className="space-y-6">
      {/* ── Cost summary ──────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Total Cost</p>
          <p className="mt-1 text-2xl font-bold text-amber-400">
            ${totals.cost_usd.toFixed(4)}
          </p>
          <p className="mt-1 text-xs text-slate-500">{fmt(totals.calls)} API calls</p>
        </div>
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Input Tokens</p>
          <p className="mt-1 text-2xl font-bold text-sky-400">{fmt(totals.input_tokens)}</p>
          <p className="mt-1 text-xs text-slate-500">prompt tokens sent</p>
        </div>
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Output Tokens</p>
          <p className="mt-1 text-2xl font-bold text-violet-400">{fmt(totals.output_tokens)}</p>
          <p className="mt-1 text-xs text-slate-500">tokens generated</p>
        </div>
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Cache Savings</p>
          <p className="mt-1 text-2xl font-bold text-green-400">
            {cache.last_emails_skipped_from_cache ?? 0}
          </p>
          <p className="mt-1 text-xs text-slate-500">emails skipped last sync</p>
        </div>
      </div>

      {/* ── Per-model breakdown ───────────────────────────────────── */}
      {Object.entries(byModel).length > 0 && (
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Cost by Model</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {Object.entries(byModel).map(([model, m]) => {
              const badge = modelBadge(model);
              return (
                <div key={model} className="rounded-xl bg-slate-800/60 border border-slate-700 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded ${badge.bg} ${badge.color}`}>
                      {badge.label}
                    </span>
                    <span className="text-xs text-slate-500 truncate">{model}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <p className="text-slate-500 text-xs">Cost</p>
                      <p className="font-mono font-medium text-amber-400">${m.cost.toFixed(4)}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-xs">Calls</p>
                      <p className="font-mono font-medium text-slate-200">{m.calls}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-xs">Input tokens</p>
                      <p className="font-mono text-sky-400">{fmt(m.input)}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-xs">Output tokens</p>
                      <p className="font-mono text-violet-400">{fmt(m.output)}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Sync cache state ─────────────────────────────────────── */}
      <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">Sync Cache State</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 text-sm">
          {[
            ["Last Sync", cache.last_sync ? fmtDate(cache.last_sync) : "Never"],
            ["Emails Processed", fmt(cache.total_emails_processed)],
            ["Parse Cache Entries", fmt(cache.parse_cache_entries)],
            ["Last Fetched", fmt(cache.last_emails_fetched ?? 0)],
            ["Last Skipped", fmt(cache.last_emails_skipped_from_cache ?? 0)],
            ["Total Transactions", fmt(cache.total_transactions ?? 0)],
          ].map(([label, value]) => (
            <div key={label} className="bg-slate-800/50 rounded-xl p-3">
              <p className="text-xs text-slate-500 mb-1">{label}</p>
              <p className="font-medium text-slate-200 text-sm leading-tight">{value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Full call log ─────────────────────────────────────────── */}
      <div className="rounded-2xl bg-slate-900 border border-slate-800">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <h2 className="text-sm font-semibold text-slate-300">API Call Log</h2>
          <span className="text-xs text-slate-500">{calls.length} calls recorded</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800">
                <th className="px-5 py-2 text-left font-medium">Time</th>
                <th className="px-5 py-2 text-left font-medium">Model</th>
                <th className="px-5 py-2 text-left font-medium">Purpose</th>
                <th className="px-5 py-2 text-right font-medium">In</th>
                <th className="px-5 py-2 text-right font-medium">Out</th>
                <th className="px-5 py-2 text-right font-medium">Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {[...calls].reverse().map((c, i) => {
                const badge = modelBadge(c.model);
                return (
                  <tr key={i} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-5 py-2.5 text-slate-500 font-mono text-xs whitespace-nowrap">
                      {fmtDate(c.ts)}
                    </td>
                    <td className="px-5 py-2.5">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${badge.bg} ${badge.color}`}>
                        {badge.label}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 text-slate-400 text-xs">{c.purpose}</td>
                    <td className="px-5 py-2.5 text-right font-mono text-xs text-sky-400">
                      {fmt(c.input_tokens)}
                    </td>
                    <td className="px-5 py-2.5 text-right font-mono text-xs text-violet-400">
                      {fmt(c.output_tokens)}
                    </td>
                    <td className="px-5 py-2.5 text-right font-mono text-xs text-amber-400">
                      ${c.cost_usd.toFixed(5)}
                    </td>
                  </tr>
                );
              })}
              {calls.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center text-slate-500">
                    No API calls recorded yet. Run a sync to populate.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
