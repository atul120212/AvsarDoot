import { Opportunity } from "@/lib/api";

const BADGE: Record<string, { label: string; cls: string }> = {
  ApplicationsOpen: { label: "Applications Open", cls: "bg-emerald-100 text-emerald-800" },
  ClosingSoon: { label: "Closing Soon", cls: "bg-amber-100 text-amber-800" },
  Closed: { label: "Closed", cls: "bg-rose-100 text-rose-800" },
  ResultDeclared: { label: "Result Declared", cls: "bg-sky-100 text-sky-800" },
  AdmitCardOut: { label: "Admit Card Released", cls: "bg-slate-200 text-slate-800" },
  Upcoming: { label: "Upcoming", cls: "bg-slate-100 text-slate-700" },
};

export function StatusBadge({ status }: { status: string }) {
  const b = BADGE[status] || { label: status, cls: "bg-slate-100 text-slate-700" };
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${b.cls}`}>{b.label}</span>;
}

export function daysLeft(end: string | null): number | null {
  if (!end) return null;
  const d = Math.ceil((new Date(end).getTime() - Date.now()) / 86400000);
  return d;
}

export function OpportunityCard({
  opp,
  href,
}: {
  opp: Opportunity;
  href: string;
}) {
  const left = daysLeft(opp.apply_end_date);
  const why = opp.match_reasons?.[0];
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-ink/10 px-2 py-0.5 text-xs font-medium text-ink">{opp.sector}</span>
        {opp.domain && <span className="text-xs text-slate-500">{opp.domain}</span>}
        <StatusBadge status={opp.status} />
      </div>
      <h3 className="mt-2 text-lg font-semibold text-ink">{opp.canonical_title}</h3>
      <p className="text-sm text-slate-600">{opp.org_name}</p>
      <p className="mt-3 text-sm text-slate-700">
        Education: {(opp.education_required || []).join(", ") || "See notification"} · Age{" "}
        {opp.age_min ?? "—"}–{opp.age_max ?? "—"}
      </p>
      <p className="mt-1 text-sm">
        Apply by {opp.apply_end_date || "TBA"}
        {left !== null && left >= 0 ? ` · ${left} days left` : ""}
      </p>
      {why && <p className="mt-2 text-sm text-leaf">You match because {why.replace(/^[^:]+:\s*/, "")}</p>}
      <div className="mt-4 flex flex-wrap gap-3">
        <a href={href} className="rounded-lg bg-ink px-3 py-1.5 text-sm text-white">
          View Details
        </a>
        <a
          href={opp.primary_source_url}
          target="_blank"
          rel="noreferrer"
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
        >
          Official Notification →
        </a>
      </div>
    </article>
  );
}

export function KVTable({ data }: { data: Record<string, unknown> | null }) {
  if (!data || Object.keys(data).length === 0) return <p className="text-sm text-slate-500">Not specified</p>;
  return (
    <table className="w-full max-w-md text-sm">
      <tbody>
        {Object.entries(data).map(([k, v]) => (
          <tr key={k} className="border-b border-slate-100">
            <td className="py-1.5 font-medium">{k}</td>
            <td className="py-1.5">{String(v)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
