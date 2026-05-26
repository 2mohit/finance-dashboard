import { useState, useEffect, useCallback } from "react";
import { api } from "../api";
import type { PdfMeta, Transaction } from "../types";
import { CATEGORY_COLORS } from "../types";

interface Props {
  transactions: Transaction[];
  onSyncComplete: () => void;
}

function parsePdfLabel(filename: string) {
  // "SBI_2025-01_abc12345.pdf" → { bank: "SBI", month: "2025-01" }
  const parts = filename.replace(".pdf", "").split("_");
  return {
    bank: parts[0] ?? filename,
    month: parts[1] ?? "",
  };
}

function bankColor(bank: string): string {
  const colors: Record<string, string> = {
    SBI:   "#22c55e",
    ICICI: "#f97316",
    HSBC:  "#ef4444",
    HDFC:  "#3b82f6",
  };
  return colors[bank] ?? "#94a3b8";
}

export default function DataTab({ transactions, onSyncComplete }: Props) {
  const [pdfs, setPdfs] = useState<PdfMeta[]>([]);
  const [selected, setSelected] = useState<PdfMeta | null>(null);
  const [loadingPdfs, setLoadingPdfs] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadPdfs = useCallback(() => {
    setLoadingPdfs(true);
    api.pdfs()
      .then((list) => {
        setPdfs(list);
        if (list.length > 0 && !selected) setSelected(list[0]);
      })
      .catch(() => setPdfs([]))
      .finally(() => setLoadingPdfs(false));
  }, [selected]);

  useEffect(() => {
    loadPdfs();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Reset cache → sync → reload (backfills pdf_file on existing transactions)
  const handleRefreshPdfs = async () => {
    setRefreshing(true);
    try {
      await api.resetCache();
      await api.triggerSync("all");
      // Poll until sync finishes
      await new Promise<void>((resolve) => {
        const iv = setInterval(async () => {
          const s = await api.syncStatus();
          if (!s.running) {
            clearInterval(iv);
            resolve();
          }
        }, 2500);
      });
      onSyncComplete(); // refresh transactions in parent
      loadPdfs();
    } finally {
      setRefreshing(false);
    }
  };

  // Primary filter: exact pdf_file match
  let filteredTxns = selected
    ? transactions
        .filter((t) => t.pdf_file === selected.filename)
        .sort((a, b) => b.date.localeCompare(a.date))
    : [];

  // Fallback filter: when pdf_file not yet backfilled, match by bank source + month
  let fallbackActive = false;
  if (filteredTxns.length === 0 && selected) {
    const { bank, month } = parsePdfLabel(selected.filename);
    const fallback = transactions
      .filter((t) => {
        const srcMatch = (t.source ?? "").toUpperCase().includes(bank.toUpperCase());
        const monthMatch = (t.date ?? "").startsWith(month);
        return srcMatch && monthMatch;
      })
      .sort((a, b) => b.date.localeCompare(a.date));
    if (fallback.length > 0) {
      filteredTxns = fallback;
      fallbackActive = true;
    }
  }

  const pdfUrl = selected ? `/api/pdfs/${encodeURIComponent(selected.filename)}` : null;

  return (
    <div className="flex gap-4 h-[calc(100vh-12rem)]">
      {/* ── Left panel: PDF list + viewer ─────────────────────────── */}
      <div className="flex flex-col w-[45%] gap-3 min-w-0">
        {/* Statement selector */}
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Statement PDFs
            </p>
            <button
              onClick={handleRefreshPdfs}
              disabled={refreshing}
              title="Reset cache and re-sync to download all PDFs from Gmail"
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 disabled:opacity-50 transition-colors"
            >
              {refreshing ? (
                <>
                  <span className="inline-block w-3 h-3 border-2 border-slate-500 border-t-slate-200 rounded-full animate-spin" />
                  Syncing…
                </>
              ) : (
                <>↻ Refresh PDFs</>
              )}
            </button>
          </div>

          {loadingPdfs ? (
            <p className="text-slate-500 text-sm">Loading…</p>
          ) : pdfs.length === 0 ? (
            <div className="space-y-2">
              <p className="text-slate-500 text-sm">
                No statement PDFs downloaded yet.
              </p>
              <p className="text-slate-600 text-xs leading-relaxed">
                Click{" "}
                <button
                  onClick={handleRefreshPdfs}
                  disabled={refreshing}
                  className="text-brand-400 hover:underline disabled:opacity-50"
                >
                  ↻ Refresh PDFs
                </button>{" "}
                to re-download all statements from Gmail and save them locally.
                Existing transactions will be linked automatically.
              </p>
            </div>
          ) : (
            <>
              <div className="space-y-1.5">
                {pdfs.map((pdf) => {
                  const { bank, month } = parsePdfLabel(pdf.filename);
                  const isActive = selected?.filename === pdf.filename;
                  return (
                    <button
                      key={pdf.filename}
                      onClick={() => setSelected(pdf)}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors text-left ${
                        isActive
                          ? "bg-brand-600/20 border border-brand-600/40 text-brand-400"
                          : "bg-slate-800/50 border border-transparent text-slate-300 hover:bg-slate-800"
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <span
                          className="text-xs font-bold px-1.5 py-0.5 rounded"
                          style={{ background: bankColor(bank) + "33", color: bankColor(bank) }}
                        >
                          {bank}
                        </span>
                        <span>{month}</span>
                      </span>
                      <span className="text-xs text-slate-500">
                        {pdf.transaction_count} txns · {pdf.size_kb} KB
                      </span>
                    </button>
                  );
                })}
              </div>
              {pdfs.length < 3 && (
                <p className="mt-3 text-xs text-slate-600 leading-relaxed">
                  Only {pdfs.length} statement{pdfs.length === 1 ? "" : "s"} downloaded.
                  Click ↻ Refresh PDFs to fetch all statements from Gmail.
                </p>
              )}
            </>
          )}
        </div>

        {/* PDF viewer */}
        <div className="flex-1 rounded-2xl bg-slate-900 border border-slate-800 overflow-hidden flex flex-col min-h-0">
          {pdfUrl ? (
            <>
              {/* Toolbar */}
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-800 flex-shrink-0">
                <p className="text-xs text-slate-500 leading-snug">
                  Bank PDFs are password-protected.
                  <br />
                  Password: last 4 digits of your registered mobile number.
                </p>
                <a
                  href={pdfUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors whitespace-nowrap ml-3"
                >
                  Open PDF ↗
                </a>
              </div>
              <iframe
                key={pdfUrl}
                src={pdfUrl}
                className="w-full flex-1"
                title="Statement PDF"
              />
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-slate-500 text-sm">
              Select a statement to preview
            </div>
          )}
        </div>
      </div>

      {/* ── Right panel: transactions ──────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 rounded-2xl bg-slate-900 border border-slate-800">
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-slate-800">
          <div>
            <h2 className="text-sm font-semibold text-slate-300">
              {selected ? (
                <>
                  {parsePdfLabel(selected.filename).bank}{" "}
                  <span className="text-slate-500">{parsePdfLabel(selected.filename).month}</span>
                </>
              ) : (
                "Transactions"
              )}
            </h2>
            {fallbackActive && (
              <p className="text-xs text-amber-500/80 mt-0.5">
                Showing by bank + month · click ↻ Refresh PDFs to link directly
              </p>
            )}
          </div>
          <span className="text-xs text-slate-500">{filteredTxns.length} transactions</span>
        </div>

        <div className="flex-1 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-slate-900 z-10">
              <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-800">
                <th className="px-5 py-2 text-left font-medium">Date</th>
                <th className="px-5 py-2 text-left font-medium">Description</th>
                <th className="px-5 py-2 text-left font-medium">Category</th>
                <th className="px-5 py-2 text-right font-medium">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filteredTxns.map((t, i) => {
                const amt = t.amount ?? t.credit ?? 0;
                const isCredit = amt < 0;
                return (
                  <tr key={i} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-5 py-2.5 text-slate-500 font-mono text-xs whitespace-nowrap">
                      {t.date}
                    </td>
                    <td className="px-5 py-2.5 text-slate-300 max-w-[240px] truncate" title={t.description}>
                      {t.description}
                    </td>
                    <td className="px-5 py-2.5">
                      <span
                        className="px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap"
                        style={{
                          backgroundColor: (CATEGORY_COLORS[t.category] ?? "#94a3b8") + "22",
                          color: CATEGORY_COLORS[t.category] ?? "#94a3b8",
                        }}
                      >
                        {t.category}
                      </span>
                    </td>
                    <td
                      className={`px-5 py-2.5 text-right font-mono font-medium ${
                        isCredit ? "text-green-400" : "text-slate-200"
                      }`}
                    >
                      {isCredit ? "−" : ""}₹{Math.abs(amt).toLocaleString("en-IN")}
                    </td>
                  </tr>
                );
              })}
              {filteredTxns.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-5 py-12 text-center">
                    {selected ? (
                      <div className="space-y-2">
                        <p className="text-slate-500">No transactions matched for this statement.</p>
                        <p className="text-slate-600 text-xs">
                          Click{" "}
                          <button
                            onClick={handleRefreshPdfs}
                            disabled={refreshing}
                            className="text-brand-400 hover:underline disabled:opacity-50"
                          >
                            ↻ Refresh PDFs
                          </button>{" "}
                          to re-sync statements from Gmail and link transactions to their source PDF.
                        </p>
                      </div>
                    ) : (
                      <p className="text-slate-500">Select a statement PDF to see its transactions.</p>
                    )}
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
