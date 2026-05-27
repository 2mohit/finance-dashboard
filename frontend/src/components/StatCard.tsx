interface Props {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}

export default function StatCard({ label, value, sub, accent = "text-white" }: Props) {
  return (
    <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5">
      <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accent}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}
