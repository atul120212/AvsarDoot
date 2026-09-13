"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, Opportunity } from "@/lib/api";
import { KVTable, StatusBadge, daysLeft } from "@/components/OpportunityUI";

export default function DetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [opp, setOpp] = useState<Opportunity | null>(null);
  const [related, setRelated] = useState<Opportunity[]>([]);
  const [disclaimer, setDisclaimer] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("ad_token")) {
      router.push("/login");
      return;
    }
    api<{ opportunity: Opportunity; related: Opportunity[]; disclaimer: string }>(`/opportunities/${id}`).then((d) => {
      setOpp(d.opportunity);
      setRelated(d.related);
      setDisclaimer(d.disclaimer);
    });
  }, [id, router]);

  async function clickOfficial() {
    await api(`/opportunities/${id}/action`, { method: "POST", body: JSON.stringify({ action: "clicked_official_link" }) }).catch(() => {});
  }

  if (!opp) return <p>Loading…</p>;
  const left = daysLeft(opp.apply_end_date);

  return (
    <article className="space-y-10">
      <header>
        <div className="flex flex-wrap gap-2">
          <span className="rounded bg-ink/10 px-2 py-0.5 text-xs">{opp.sector}</span>
          <span className="text-xs text-slate-500">{opp.domain}</span>
          <StatusBadge status={opp.status} />
        </div>
        <h1 className="mt-2 text-3xl font-semibold text-ink">{opp.canonical_title}</h1>
        <p className="text-slate-600">{opp.org_name}</p>
        <a
          href={opp.primary_source_url}
          target="_blank"
          rel="noreferrer"
          onClick={clickOfficial}
          className="mt-4 inline-block rounded-lg bg-ink px-4 py-2 text-white"
        >
          Official notification / apply →
        </a>
      </header>

      <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">{disclaimer}</p>

      <Section n="1" title="Overview">
        <p>Type: {opp.opportunity_type} · Stage: {opp.exam_stage || "—"}</p>
        <p>Education: {(opp.education_required || []).join(", ") || "See official notification"}</p>
      </Section>

      <Section n="2" title="Important Dates">
        <ol className="relative border-l border-slate-200 pl-4 text-sm">
          {[
            ["Notified", opp.notified_at],
            ["Apply start", opp.apply_start_date],
            ["Apply end", opp.apply_end_date],
            ["Exam", opp.exam_date],
            ["Result", opp.result_date],
          ].map(([l, v]) => (
            <li key={l} className="mb-3">
              <strong>{l}:</strong> {v || "TBA"}
              {l === "Apply end" && left !== null ? ` (${left} days left)` : ""}
            </li>
          ))}
        </ol>
      </Section>

      <Section n="3" title="Eligibility Criteria">
        <p>Age: {opp.age_min ?? "—"} to {opp.age_max ?? "—"} as on {opp.age_cutoff_date || "see notification"}</p>
        <p className="mt-2 text-sm font-medium">Category age relaxation</p>
        <KVTable data={opp.age_relaxation_rules} />
        <p className="mt-2">Gender: {opp.gender_restriction || "Any"} · Domicile: {opp.domicile_required || "Any"}</p>
        <p>Certifications: {(opp.certifications_required || []).join(", ") || "None specified"}</p>
        <p>
          Prerequisites:{" "}
          {(opp.prerequisite_exams || []).map((e) => e.exam).join(", ") || "None"}
        </p>
        {opp.experience_required_years ? <p>Experience: {opp.experience_required_years}+ years</p> : null}
      </Section>

      <Section n="4" title="Vacancy Breakdown">
        <KVTable data={opp.category_vacancies} />
      </Section>

      <Section n="5" title="Application Fee">
        <KVTable data={opp.fee_structure} />
      </Section>

      <Section n="6" title="How to Apply">
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          <li>Read the official notification in full.</li>
          <li>Confirm eligibility (category, age cutoff date, documents).</li>
          <li>Apply only on the official portal linked below.</li>
        </ol>
        <a className="mt-3 inline-block text-saffron underline" href={opp.primary_source_url} target="_blank" rel="noreferrer" onClick={clickOfficial}>
          {opp.primary_source_url}
        </a>
      </Section>

      <Section n="7" title="Why This Matched You">
        {opp.match_reasons && opp.match_reasons.length ? (
          <ul className="list-disc pl-5 text-sm">
            {opp.match_reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">Complete your profile to see personalized match reasons.</p>
        )}
      </Section>

      <Section n="8" title="Related Opportunities">
        <ul className="space-y-2 text-sm">
          {related.map((r) => (
            <li key={r.id}>
              <a className="text-ink underline" href={`/opportunities/${r.id}`}>
                {r.canonical_title}
              </a>
            </li>
          ))}
          {related.length === 0 && <li className="text-slate-500">None right now</li>}
        </ul>
      </Section>
    </article>
  );
}

function Section({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-xl font-semibold text-ink">
        {n}. {title}
      </h2>
      <div className="mt-2">{children}</div>
    </section>
  );
}
