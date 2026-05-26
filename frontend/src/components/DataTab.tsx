import { useState, useEffect, useCallback } from "react";
import { api } from "../api";
import type { PdfMeta, Transaction, AuditResult, AuditEmail } from "../types";
import { CATEGORY_COLORS } from "../types";

interface Props {
  transactions: Transaction[];
  onSyncComplete: () => void;
}

function parsePdfLabel(filename: string) {
  const parts = filename.replace(".pdf", "").split("_");
  return { bank: parts[0] ?? filename, month: parts[1] ?? "" };
}

function bankColor(bank: string): string {
  const colors: Record<string, string> = {
    SBI: "#22c55e", ICICI: "#f97316", HSBC: "#ef4444", HDFC: "#3b82f6",
  };
  return colors[bank] ?? "#94a3b8";
}

function actionBadge(action: AuditEmail["action"]) {
  if (action === "none")
    return <span className="text-xs text-green-500/80">OK</span>;
  if (action === "download")
    return <span className="text-xs font-medium text-red-400">Not downloaded</span>;
  if (action === "redownload_pdf")
    return <span className="text-xs font-medium text-amber-400">PDF missing</span>;
  if (action === "unlock")
    return <span className="text-xs font-medium text-sky-400">Needs unlock</span>;
}

// ── Audit panel shown before repair ───────────────────────────────────────────
function AuditPanel({
  audit,
  onRepair,
  onDismiss,
  repairing,
}: {
  audit: AuditResult;
  onRepair: () => void;
  onDismiss: () => void;
  repairing: boolean;
}) {
  const { summary, emails } = audit;
  const issues = emails.filter((e) => e.action !== "none");

  return (
    <div className="rounded-2xl bg-slate-900 border border-slate-700 p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">Gmail vs Local — Audit</h3>
        <button onClick={onDismiss} className="text-slate-600 hover:text-slate-400 text-xs">
          dismiss
        </button>
      </div>

      {/* Summary grid */}
      <div className="grid grid-cols-4 gap-2 text-center">
        {[
          { label: "In Gmail", value: summary.gmail_total, color: "text-slate-300" },
          { label: "Cached", value: summary.cached, color: summary.cached === summary.gmail_total ? "text-green-400" : "text-amber-400" },
          { label: "PDF saved", value: summary.pdf_saved, color: summary.pdf_saved >= summary.gmail_total ? "text-green-400" : "text-amber-400" },
          { label: "Unlocked", value: summary.pdf_unlocked, color: summary.pdf_unlocked >= summary.gmail_total ? "text-green-400" : "text-amber-400" },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-lg bg-slate-800 py-2 px-1">
            <p className={`text-lg font-bold ${color}`}>{value}</p>
            <p className="text-xs text-slate-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Actions needed */}
      {summary.all_good ? (
        <p className="text-sm text-green-400 text-center py-1">Everything is up to date</p>
      ) : (
        <div className="space-y-1">
          <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">Actions needed</p>
          {summary.needs_download > 0 && (
            <p className="text-xs text-red-400">
              {summary.needs_download} email(s) not downloaded — will fetch from Gmail
            </p>
          )}
          {summary.needs_redownload_pdf > 0 && (
            <p className="text-xs text-amber-400">
              {summary.needs_redownload_pdf} email(s) cached but PDF missing — will re-download
            </p>
          )}
          {summary.needs_unlock > 0 && (
            <p className="text-xs text-sky-400">
              {summary.needs_unlock} PDF(s) not unlocked — will unlock (no download needed)
            </p>
          )}
        </div>
      )}

      {/* Per-email table */}
      <div className="max-h-48 overflow-y-auto rounded-lg border border-slate-800">
        <table className="w-full text-xs">
          <thead className="bg-slate-800 sticky top-0">
            <tr className="text-slate-500 uppercase tracking-wider">
              <th className="px-3 py-1.5 text-left font-medium">Bank</th>
              <th className="px-3 py-1.5 text-left font-medium">Subject</th>
              <th className="px-3 py-1.5 text-center font-medium">Cached</th>
              <th className="px-3 py-1.5 text-center font-medium">PDF</th>
              <th className="px-3 py-1.5 text-center font-medium">Unlocked</th>
              <th className="px-3 py-1.5 text-right font-medium">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {emails.map((e) => (
              <tr key={e.id} className={e.action !== "none" ? "bg-slate-800/30" : ""}>
                <td className="px-3 py-1.5">
                  <span
                    className="text-xs font-bold px-1 py-0.5 rounded"
                    style={{ background: bankColor(e.bank) + "33", color: bankColor(e.bank) }}
                  >
                    {e.bank}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-slate-400 max-w-[180px] truncate" title={e.subject}>
                  {e.subject}
                </td>
                <td className="px-3 py-1.5 text-center">{e.in_cache ? "✓" : "✗"}</td>
                <td className="px-3 py-1.5 text-center">{e.pdf_saved ? "✓" : "✗"}</td>
                <td className="px-3 py-1.5 text-center">{e.pdf_unlocked ? "✓" : "✗"}</td>
                <td className="px-3 py-1.5 text-right">{actionBadge(e.action)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Action buttons */}
      {!summary.all_good && (
        <div className="flex gap-2 pt-1">
          <button
            onClick={onRepair}
            disabled={repairing}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold bg-brand-600 hover:bg-brand-500 text-white disabled:opacity-50 transition-colors"
          >
            {repairing ? (
              <>
                <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Repairing…
              </>
            ) : (
              `Repair (${issues.length} issue${issues.length !== 1 ? "s" : ""})`
            )}
          </button>
          <button
            onClick={onDismiss}
            disabled={repairing}
            className="px-3 py-2 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-400 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function DataTab({ transactions, onSyncComplete }: Props) {
  const [pdfs, setPdfs] = useState<PdfMeta[]>([]);
  const [selected, setSelected] = useState<PdfMeta | null>(null);
  const [loadingPdfs, setLoadingPdfs] = useState(true);

  // Audit state
  const [auditing, setAuditing] = useState(false);
  const [audit, setAudit] = useState<AuditResult | null>(null);
  const [repairing, setRepairing] = useState(false);

  const loadPdfs = useCallback((keepSelected?: PdfMeta) => {
    setLoadingPdfs(true);
    api.pdfs()
      .then((list) => {
        setPdfs(list);
        if (keepSelected) {
          const refreshed = list.find((p) => p.filename === keepSelected.filename);
          setSelected(refreshed ?? list[0] ?? null);
        } else if (!selected && list.length > 0) {
          setSelected(list[0]);
        }
      })
      .catch(() => setPdfs([]))
      .finally(() => setLoadingPdfs(false));
  }, [selected]);

  useEffect(() => { loadPdfs(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Step 1: audit what Gmail has vs what we have
  const handleAudit = async () => {
    setAuditing(true);
    setAudit(null);
    try {
      const result = await api.auditPdfs();
      setAudit(result);
    } finally {
      setAuditing(false);
    }
  };

  // Step 2: targeted repair based on audit results
  const handleRepair = async () => {
    setRepairing(true);
    try {
      await api.repairPdfs();
      // Poll until repair finishes
      await new Promise<void>((resolve) => {
        const iv = setInterval(async () => {
          const s = await api.syncStatus();
          if (!s.running) { clearInterval(iv); resolve(); }
        }, 2500);
      });
      onSyncComplete();
      loadPdfs(selected ?? undefined);
      setAudit(null); // dismiss panel after repair
    } finally {
      setRepairing(false);
    }
  };

  // Primary filter: exact pdf_file match
  let filteredTxns = selected
    ? transactions.filter((t) => t.pdf_file === selected.filename).sort((a, b) => b.date.localeCompare(a.date))
    : [];

  // Fallback: bank source + month when pdf_file not yet backfilled
  let fallbackActive = false;
  if (filteredTxns.length === 0 && selected) {
    const { bank, month } = parsePdfLabel(selected.filename);
    const fallback = transactions
      .filter((t) => (t.source ?? "").toUpperCase().includes(bank.toUpperCase()) && (t.date ?? "").startsWith(month))
      .sort((a, b) => b.date.localeCompare(a.date));
    if (fallback.length > 0) { filteredTxns = fallback; fallbackActive = true; }
  }

  const pdfUrl = selected ? `/api/pdfs/${encodeURIComponent(selected.filename)}` : null;
  const isLocked = selected ? !selected.unlocked : false;

  return (
    <div className="flex gap-4 h-[calc(100vh-12rem)]">
      {/* ── Left panel ────────────────────────────────────────────── */}
      <div className="flex flex-col w-[45%] gap-3 min-w-0">

        {/* Audit panel — shown when audit has been run */}
        {audit && (
          <AuditPanel
            audit={audit}
            onRepair={handleRepair}
            onDismiss={() => setAudit(null)}
            repairing={repairing}
          />
        )}

        {/* Statement selector */}
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Statement PDFs
            </p>
            <button
              onClick={handleAudit}
              disabled={auditing || repairing}
              title="Check Gmail vs local state, then repair what's missing"
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 disabled:opacity-50 transition-colors"
            >
              {auditing ? (
                <>
                  <span className="inline-block w-3 h-3 border-2 border-slate-500 border-t-slate-200 rounded-full animate-spin" />
                  Checking…
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
              <p className="text-slate-500 text-sm">No statement PDFs downloaded yet.</p>
              <p className="text-slate-600 text-xs leading-relaxed">
                Click{" "}
                <button onClick={handleAudit} disabled={auditing} className="text-brand-400 hover:underline disabled:opacity-50">
                  ↻ Refresh PDFs
                </button>{" "}
                to check Gmail and download statements.
              </p>
            </div>
          ) : (
            <>
              <div className="space-y-1.5 max-h-52 overflow-y-auto pr-0.5">
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
                        {!pdf.unlocked && <span className="text-xs text-slate-600" title="Password-protected">🔒</span>}
                      </span>
                      <span className="text-xs text-slate-500">
                        {pdf.transaction_count} txns · {pdf.size_kb} KB
                      </span>
                    </button>
                  );
                })}
              </div>
              {pdfs.some((p) => !p.unlocked) && (
                <p className="mt-3 text-xs text-amber-500/70 leading-relaxed">
                  🔒 Some PDFs need a password. Add <code className="text-amber-400/80">{"{BANK}_PDF_PASSWORD"}</code> to{" "}
                  <code className="text-amber-400/80">.env</code> then click ↻ Refresh PDFs.
                </p>
              )}
            </>
          )}
        </div>

        {/* PDF viewer */}
        <div className="flex-1 rounded-2xl bg-slate-900 border border-slate-800 overflow-hidden flex flex-col min-h-0">
          {pdfUrl ? (
            <>
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-800 flex-shrink-0">
                {isLocked ? (
                  <p className="text-xs text-amber-500/80 leading-snug">
                    🔒 Password-protected — can't render inline.<br />
                    Password: last 4 digits of registered mobile.
                  </p>
                ) : (
                  <p className="text-xs text-green-500/70">Unlocked — rendering below</p>
                )}
                <a
                  href={pdfUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors whitespace-nowrap ml-3 flex-shrink-0"
                >
                  Open ↗
                </a>
              </div>
              {isLocked ? (
                <div className="flex-1 flex flex-col items-center justify-center gap-3 text-slate-500 p-6">
                  <span className="text-4xl">🔒</span>
                  <p className="text-sm text-center">Password-protected PDF</p>
                  <p className="text-xs text-slate-600 text-center leading-relaxed">
                    Add the correct password to{" "}
                    <code className="text-slate-500">{"{BANK}_PDF_PASSWORD"}</code> in{" "}
                    <code className="text-slate-500">.env</code>, then click ↻ Refresh PDFs.
                  </p>
                  <a
                    href={pdfUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 px-4 py-2 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                  >
                    Open in browser (enter password manually) ↗
                  </a>
                </div>
              ) : (
                <iframe key={pdfUrl} src={pdfUrl} className="w-full flex-1" title="Statement PDF" />
              )}
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
              ) : "Transactions"}
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
                    <td className="px-5 py-2.5 text-slate-500 font-mono text-xs whitespace-nowrap">{t.date}</td>
                    <td className="px-5 py-2.5 text-slate-300 max-w-[240px] truncate" title={t.description}>{t.description}</td>
                    <td className="px-5 py-2.5">
                      <span
                        className="px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap"
                        style={{
                          backgroundColor: (CATEGORY_COLORS[t.category] ?? "#94a3b8") + "22",
                          color: CATEGORY_COLORS[t.category] ?? "#94a3b8",
                        }}
                      >{t.category}</span>
                    </td>
                    <td className={`px-5 py-2.5 text-right font-mono font-medium ${isCredit ? "text-green-400" : "text-slate-200"}`}>
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
                        <p className="text-slate-500">No transactions for this statement.</p>
                        <p className="text-slate-600 text-xs">
                          Click{" "}
                          <button onClick={handleAudit} disabled={auditing} className="text-brand-400 hover:underline disabled:opacity-50">
                            ↻ Refresh PDFs
                          </button>{" "}
                          to check for missing data.
                        </p>
                      </div>
                    ) : <p className="text-slate-500">Select a statement PDF to see transactions.</p>}
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
