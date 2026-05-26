import { useState, useEffect } from "react";
import { api } from "../api";
import type { PdfMeta, Transaction } from "../types";
import { CATEGORY_COLORS } from "../types";

interface Props {
  transactions: Transaction[];
}

function parsePdfLabel(filename: string) {
  // "SBI_2025-01_abc12345.pdf" → { bank: "SBI", month: "2025-01" }
  const parts = filename.replace(".pdf", "").split("_");
  return {
    bank: parts[0] ?? filename,
    month: parts[1] ?? "",
  };
}

export default function DataTab({ transactions }: Props) {
  const [pdfs, setPdfs] = useState<PdfMeta[]>([]);
  const [selected, setSelected] = useState<PdfMeta | null>(null);
  const [loadingPdfs, setLoadingPdfs] = useState(true);

  useEffect(() => {
    api.pdfs()
      .then((list) => {
        setPdfs(list);
        if (list.length > 0) setSelected(list[0]);
      })
      .catch(() => setPdfs([]))
      .finally(() => setLoadingPdfs(false));
  }, []);

  const filteredTxns = selected
    ? transactions
        .filter((t) => t.pdf_file === selected.filename)
        .sort((a, b) => b.date.localeCompare(a.date))
    : [];

  const pdfUrl = selected ? `/api/pdfs/${encodeURIComponent(selected.filename)}` : null;

  return (
    <div className="flex gap-4 h-[calc(100vh-12rem)]">
      {/* ── Left panel: PDF list + viewer ─────────────────────────── */}
      <div className="flex flex-col w-[45%] gap-3 min-w-0">
        {/* Statement selector */}
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
            Statement PDFs
          </p>
          {loadingPdfs ? (
            <p className="text-slate-500 text-sm">Loading…</p>
          ) : pdfs.length === 0 ? (
            <p className="text-slate-500 text-sm">
              No PDFs yet — run a sync to download statements.
            </p>
          ) : (
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
          )}
        </div>

        {/* PDF viewer */}
        <div className="flex-1 rounded-2xl bg-slate-900 border border-slate-800 overflow-hidden">
          {pdfUrl ? (
            <iframe
              key={pdfUrl}
              src={pdfUrl}
              className="w-full h-full"
              title="Statement PDF"
            />
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
                      {isCredit ? "−" : ""}₹{Math.abs(amt).toLocaleString()}
                    </td>
                  </tr>
                );
              })}
              {filteredTxns.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-5 py-12 text-center text-slate-500">
                    {selected
                      ? "No transactions found for this statement."
                      : "Select a statement PDF to see its transactions."}
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

function bankColor(bank: string): string {
  const colors: Record<string, string> = {
    SBI:   "#22c55e",
    ICICI: "#f97316",
    HSBC:  "#ef4444",
    HDFC:  "#3b82f6",
  };
  return colors[bank] ?? "#94a3b8";
}
