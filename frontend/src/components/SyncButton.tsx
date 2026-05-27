import { useState, useEffect } from "react";
import { api } from "../api";
import type { SyncStatus } from "../types";

interface Props {
  onSyncComplete: () => void;
}

export default function SyncButton({ onSyncComplete }: Props) {
  const [status, setStatus] = useState<SyncStatus>({ running: false, last_result: null });

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (status.running) {
      interval = setInterval(async () => {
        const s = await api.syncStatus();
        setStatus(s);
        if (!s.running) {
          onSyncComplete();
          clearInterval(interval);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [status.running, onSyncComplete]);

  const handleSync = async () => {
    await api.triggerSync("all");
    setStatus((s) => ({ ...s, running: true }));
  };

  return (
    <div className="flex items-center gap-3">
      {status.last_result && (
        <span className="text-xs text-slate-500">
          +{status.last_result.new_transactions} new · {status.last_result.total_transactions} total
        </span>
      )}
      <button
        onClick={handleSync}
        disabled={status.running}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
      >
        {status.running ? (
          <>
            <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Syncing…
          </>
        ) : (
          <>
            <span>↻</span>
            Sync Emails
          </>
        )}
      </button>
    </div>
  );
}
