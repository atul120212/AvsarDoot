"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, Opportunity } from "@/lib/api";

const empty: Partial<Opportunity> = {
  canonical_title: "",
  org_name: "",
  sector: "Govt",
  opportunity_type: "Job",
  domain: "SSC",
  education_required: ["Any Graduate"],
  age_min: 18,
  age_max: 32,
  age_relaxation_rules: { OBC: 3, SC: 5, ST: 5 },
  gender_restriction: "Any",
  domicile_required: "Any",
  status: "Upcoming",
  primary_source_url: "https://",
  raw_notification_text: "",
  published: false,
  reviewed_by_human: false,
};

const FORM_KEYS = [
  "canonical_title",
  "org_name",
  "opportunity_type",
  "domain",
  "sector",
  "education_required",
  "stream_required",
  "min_percentage",
  "age_min",
  "age_max",
  "age_relaxation_rules",
  "age_cutoff_date",
  "gender_restriction",
  "domicile_required",
  "certifications_required",
  "prerequisite_exams",
  "experience_required_years",
  "category_vacancies",
  "apply_start_date",
  "apply_end_date",
  "exam_date",
  "fee_structure",
];

export default function AdminEditPage() {
  const params = useParams<{ id: string }>();
  const isNew = params.id === "new";
  const router = useRouter();
  const [form, setForm] = useState<Record<string, unknown>>(empty);
  const [evidence, setEvidence] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [searching, setSearching] = useState(false);
  const [query, setQuery] = useState("");
  const [searchHits, setSearchHits] = useState<
    { snippet: string; llm?: { answer?: string; quotes?: string[]; not_found?: boolean; note?: string; error?: string } } | null
  >(null);
  const [verifyReport, setVerifyReport] = useState<{
    missing_fields_filled?: string[];
    discrepancies?: { field: string; existing: unknown; verified: unknown; explanation: string }[];
    is_single_notification?: boolean;
    reject_reason?: string | null;
    provider?: string;
  } | null>(null);
  const [approveResult, setApproveResult] = useState<{
    matched: number;
    notified_telegram: number;
    notified_email: number;
    recipients: { email: string; telegram: boolean; notified: boolean; channels: string[]; reasons: string[] }[];
  } | null>(null);


  useEffect(() => {
    if (localStorage.getItem("ad_role") !== "admin") router.push("/feed");
    if (!isNew) {
      api<Opportunity>(`/admin/opportunities/${params.id}`).then((o) => {
        setForm(o as unknown as Record<string, unknown>);
        setEvidence((o.extraction_evidence as Record<string, string>) || {});
      });
    }
  }, [isNew, params.id, router]);

  function set(k: string, v: unknown) {
    setForm({ ...form, [k]: v });
  }

  async function deleteRecord() {
    if (isNew) return;
    if (!confirm("Are you sure you want to permanently delete this record?")) return;
    try {
      await api(`/admin/opportunities/${params.id}`, { method: "DELETE" });
      router.push("/admin");
    } catch (ex) {
      setMsg(`Delete failed: ${(ex as Error).message}`);
    }
  }

  async function save(publishIntent?: "approve") {
    setMsg("");
    setApproveResult(null);
    const payload = {
      ...empty,
      ...form,
      education_required: Array.isArray(form.education_required)
        ? form.education_required
        : String(form.education_required || "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
      extraction_evidence: evidence,
    };
    try {
      if (isNew) {
        const created = await api<Opportunity>("/admin/opportunities", { method: "POST", body: JSON.stringify(payload) });
        if (publishIntent === "approve") {
          const result = await api<{ ok: boolean; matched: number; notified_telegram: number; notified_email: number; recipients: { email: string; telegram: boolean; notified: boolean; channels: string[]; reasons: string[] }[] }>(
            `/admin/opportunities/${created.id}/approve`,
            { method: "POST" }
          );
          setApproveResult(result);
          setMsg(`✅ Published! Notified ${result.matched} eligible candidates.`);
        } else {
          router.push("/admin");
        }
      } else {
        await api(`/admin/opportunities/${params.id}`, { method: "PUT", body: JSON.stringify({ ...payload, published: false }) });
        if (publishIntent === "approve") {
          const result = await api<{ ok: boolean; matched: number; notified_telegram: number; notified_email: number; recipients: { email: string; telegram: boolean; notified: boolean; channels: string[]; reasons: string[] }[] }>(
            `/admin/opportunities/${params.id}/approve`,
            { method: "POST" }
          );
          setApproveResult(result);
          setMsg(`✅ Published! Notified ${result.matched} eligible candidates.`);
        } else {
          setMsg("Saved.");
          router.push("/admin");
        }
      }
    } catch (ex) {
      setMsg((ex as Error).message);
    }
  }


  async function verifyWithLLM() {
    setVerifying(true);
    setMsg("");
    setVerifyReport(null);
    try {
      const res = await api<{
        is_single_notification: boolean;
        reject_reason?: string | null;
        verified_fields: Record<string, unknown>;
        evidence: Record<string, string>;
        missing_fields_filled: string[];
        discrepancies: { field: string; existing: unknown; verified: unknown; explanation: string }[];
        confidence: number;
        provider: string;
      }>("/admin/extract/verify", {
        method: "POST",
        body: JSON.stringify({
          raw_text: form.raw_notification_text || "",
          current_fields: form,
        }),
      });

      const next: Record<string, unknown> = {
        ...form,
        extraction_confidence: res.confidence,
      };

      for (const k of FORM_KEYS) {
        if (res.verified_fields[k] != null) {
          next[k] = res.verified_fields[k];
        }
      }
      if (res.verified_fields.official_apply_url) {
        next.primary_source_url = res.verified_fields.official_apply_url;
      }

      setForm(next);
      setEvidence(res.evidence || {});
      setVerifyReport({
        missing_fields_filled: res.missing_fields_filled,
        discrepancies: res.discrepancies,
        is_single_notification: res.is_single_notification,
        reject_reason: res.reject_reason,
        provider: res.provider,
      });

      if (!res.is_single_notification) {
        setMsg(`⚠️ Model flagged this as a category/hub page (${res.reject_reason || "not an individual job"}). Do not publish.`);
      } else {
        const filledCount = (res.missing_fields_filled || []).length;
        setMsg(
          `Verified via ${res.provider.toUpperCase()} (${Math.round(res.confidence * 100)}% confidence). Filled ${filledCount} missing fields.`
        );
      }
    } catch (ex) {
      setMsg(`LLM Verification failed: ${(ex as Error).message}`);
    } finally {
      setVerifying(false);
    }
  }

  async function extract() {
    await verifyWithLLM();
  }

  async function runSearch() {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const res = await api<{
        keyword_hits: { snippet: string }[];
        llm: { answer?: string; quotes?: string[]; not_found?: boolean; note?: string; error?: string } | null;
      }>("/admin/extract/search", {
        method: "POST",
        body: JSON.stringify({ raw_text: form.raw_notification_text || "", query }),
      });
      setSearchHits({
        snippet: res.keyword_hits.map((h) => h.snippet).join("\n---\n"),
        llm: res.llm || undefined,
      });
    } catch (ex) {
      setSearchHits({ snippet: "", llm: { error: (ex as Error).message } });
    } finally {
      setSearching(false);
    }
  }

  async function reject() {
    if (isNew) return;
    await api(`/admin/opportunities/${params.id}/reject`, { method: "POST" });
    router.push("/admin");
  }

  const edu = Array.isArray(form.education_required) ? (form.education_required as string[]).join(", ") : String(form.education_required || "");
  const missingEdu = !form.education_required || (Array.isArray(form.education_required) && form.education_required.length === 0);
  const missingAgeMax = form.age_max == null || form.age_max === "";
  const cannotApprove = missingEdu || missingAgeMax;
  const confidencePct = form.extraction_confidence != null ? Math.round(Number(form.extraction_confidence) * 100) : null;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-ink">{isNew ? "New opportunity" : "QA Review"}</h1>
          {confidencePct != null && (
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-mono font-medium text-slate-700">
              Confidence: {confidencePct}%
            </span>
          )}
        </div>
        <label className="mt-4 block text-sm font-medium text-slate-700">Raw notification (source of truth)</label>
        <textarea
          className="mt-1 h-64 w-full rounded-lg border border-slate-300 p-3 font-mono text-xs shadow-sm focus:border-ink focus:ring-1 focus:ring-ink"
          value={String(form.raw_notification_text || "")}
          onChange={(e) => set("raw_notification_text", e.target.value)}
        />
        <div className="mt-3 flex gap-2">
          <input
            className="flex-1 rounded-lg border px-3 py-1.5 text-sm"
            placeholder="Search in text, e.g. age limit, last date, B.Tech"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), runSearch())}
          />
          <button type="button" onClick={runSearch} disabled={searching} className="rounded-lg border px-3 py-1.5 text-sm">
            {searching ? "Searching…" : "Search + Gemini"}
          </button>
        </div>
        {searchHits && (
          <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs space-y-2">
            {searchHits.llm?.answer && (
              <p>
                <strong>Gemini:</strong> {searchHits.llm.answer}
              </p>
            )}
            {searchHits.llm?.quotes?.map((q) => (
              <blockquote key={q} className="border-l-2 border-ink pl-2 text-slate-600">
                “{q}”
              </blockquote>
            ))}
            {searchHits.llm?.note && <p className="text-amber-800">{searchHits.llm.note}</p>}
            {searchHits.llm?.error && <p className="text-rose-700">{searchHits.llm.error}</p>}
            {searchHits.snippet && (
              <pre className="whitespace-pre-wrap text-slate-600">{searchHits.snippet}</pre>
            )}
            {!searchHits.snippet && !searchHits.llm?.answer && <p className="text-slate-500">No keyword hits in this text.</p>}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={verifyWithLLM}
            disabled={verifying}
            className="flex items-center gap-1.5 rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {verifying ? "🤖 Verifying details with LLM..." : "✨ Run Auto-Extraction (LLM / Regex)"}
          </button>
        </div>

        {verifyReport && verifyReport.is_single_notification === false && (
          <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3.5 text-xs text-amber-900">
            <div className="font-semibold text-amber-950 flex items-center gap-1.5">
              ⚠️ Aggregator Hub / Category Page Detected
            </div>
            <p className="mt-1 text-amber-800">
              {verifyReport.reject_reason || "This record was scraped from a hub or category navigation page. It does not represent a single job opportunity."}
            </p>
            <button
              type="button"
              onClick={deleteRecord}
              className="mt-2.5 rounded bg-rose-600 px-3 py-1 text-xs font-semibold text-white hover:bg-rose-700 shadow-sm"
            >
              🗑️ Delete Junk Opportunity
            </button>
          </div>
        )}

        {verifyReport && (verifyReport.missing_fields_filled?.length || 0) > 0 && (
          <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900">
            <div className="font-semibold flex items-center gap-1.5">
              ✅ Verification Successful ({verifyReport.provider?.toUpperCase()}):
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {verifyReport.missing_fields_filled?.map((f) => (
                <span key={f} className="rounded bg-emerald-200/80 px-2 py-0.5 text-[11px] font-medium text-emerald-900">
                  + Filled: {f}
                </span>
              ))}
            </div>
          </div>
        )}

        <p className="mt-2 text-xs text-slate-500">
          Uses AI / smart parser to extract qualification, age limits, dates, and official apply links with verbatim evidence quotes.
        </p>
      </div>

      <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-ink border-b pb-2">Structured Opportunity Data</h2>
        {cannotApprove && (
          <div className="rounded-lg bg-rose-50 p-3 text-xs text-rose-800 border border-rose-200">
            ⚠️ QA Rule Block: Both education_required and age_max must be specified before approving.
          </div>
        )}
        <Input label="Title" value={String(form.canonical_title || "")} onChange={(v) => set("canonical_title", v)} quote={evidence.canonical_title} />
        <Input label="Organisation" value={String(form.org_name || "")} onChange={(v) => set("org_name", v)} quote={evidence.org_name} />
        <Input label="Official URL" value={String(form.primary_source_url || "")} onChange={(v) => set("primary_source_url", v)} quote={evidence.official_apply_url} />
        <div className="grid grid-cols-2 gap-2">
          <Input label="Sector" value={String(form.sector || "")} onChange={(v) => set("sector", v)} />
          <Input label="Domain" value={String(form.domain || "")} onChange={(v) => set("domain", v)} quote={evidence.domain} />
        </div>
        <Input label="Education required (comma-separated)" value={edu} onChange={(v) => set("education_required", v.split(",").map((s) => s.trim()).filter(Boolean))} quote={evidence.education_required} />
        <div className="grid grid-cols-2 gap-2">
          <Input label="Age min" value={String(form.age_min ?? "")} onChange={(v) => set("age_min", v ? Number(v) : null)} quote={evidence.age_min} />
          <Input label="Age max" value={String(form.age_max ?? "")} onChange={(v) => set("age_max", v ? Number(v) : null)} quote={evidence.age_max} />
        </div>
        <Input label="Age cutoff date" value={String(form.age_cutoff_date || "")} onChange={(v) => set("age_cutoff_date", v || null)} quote={evidence.age_cutoff_date} />
        <Input label="Apply start" value={String(form.apply_start_date || "")} onChange={(v) => set("apply_start_date", v || null)} quote={evidence.apply_start_date} />
        <Input label="Apply end" value={String(form.apply_end_date || "")} onChange={(v) => set("apply_end_date", v || null)} quote={evidence.apply_end_date} />
        <Input label="Domicile required" value={String(form.domicile_required || "Any")} onChange={(v) => set("domicile_required", v)} quote={evidence.domicile_required} />
        {msg && <p className="text-sm font-medium text-saffron">{msg}</p>}
        <div className="flex flex-wrap gap-2 pt-3 border-t">
          <button onClick={() => save()} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium">
            Save Draft
          </button>
          <button onClick={() => save("approve")} disabled={cannotApprove} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
            Approve &amp; Publish
          </button>
          {!isNew && (
            <>
              <button onClick={reject} className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white">
                Reject
              </button>
              <button onClick={deleteRecord} className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white">
                Delete
              </button>
            </>
          )}
        </div>

        {/* ── Notification results panel ── */}
        {approveResult && (
          <div className="mt-4 rounded-xl border border-emerald-500/40 bg-emerald-950/20 p-4 text-sm">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-emerald-600 dark:text-emerald-400 text-base">📣 Notification Report</h3>
              <button
                onClick={() => router.push("/admin")}
                className="rounded-lg bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700 shadow-sm"
              >
                ← Back to Queue
              </button>
            </div>

            {/* Summary stats */}
            <div className="mt-3 grid grid-cols-3 gap-3 text-center">
              <div className="rounded-lg bg-white dark:bg-slate-900 border border-emerald-300 dark:border-emerald-500/30 py-3 shadow-xs">
                <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{approveResult.matched}</div>
                <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 font-medium">Eligible Candidates</div>
              </div>
              <div className="rounded-lg bg-white dark:bg-slate-900 border border-blue-300 dark:border-blue-500/30 py-3 shadow-xs">
                <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{approveResult.notified_telegram}</div>
                <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 font-medium">📱 Telegram Sent</div>
              </div>
              <div className="rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 py-3 shadow-xs">
                <div className="text-2xl font-bold text-slate-600 dark:text-slate-300">{approveResult.notified_email}</div>
                <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 font-medium">✉️ Email Sent</div>
              </div>
            </div>

            {/* Per-recipient list */}
            {approveResult.recipients.length > 0 ? (
              <div className="mt-4">
                <p className="text-xs font-semibold text-emerald-700 dark:text-emerald-300 mb-2">Recipients:</p>
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  {approveResult.recipients.map((r, i) => (
                    <div key={i} className="flex items-start justify-between rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 px-3 py-2 text-xs">
                      <div>
                        <span className="font-medium text-slate-800 dark:text-slate-100">{r.email}</span>
                        <div className="mt-0.5 text-slate-500 dark:text-slate-400">
                          {r.reasons.slice(0, 2).join(" · ")}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1 ml-4 shrink-0">
                        {r.telegram ? (
                          <span className="rounded-full bg-blue-100 dark:bg-blue-900/60 border border-blue-200 dark:border-blue-500/40 px-2 py-0.5 text-[10px] font-medium text-blue-700 dark:text-blue-300">
                            📱 Telegram ✓
                          </span>
                        ) : (
                          <span className="rounded-full bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[10px] text-slate-500 dark:text-slate-400">
                            No Telegram
                          </span>
                        )}
                        {r.channels.includes("email") && (
                          <span className="rounded-full bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[10px] text-slate-600 dark:text-slate-300">
                            ✉️ Email
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                No eligible candidates found yet. Users need to complete their profile to be matched.
              </p>
            )}
          </div>
        )}

      </div>
    </div>
  );
}

function Input({
  label,
  value,
  onChange,
  quote,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  quote?: string;
}) {
  return (
    <label className="block text-xs font-medium text-slate-700">
      {label}
      <input className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-900" value={value} onChange={(e) => onChange(e.target.value)} />
      {quote && <p className="mt-1 font-normal italic text-slate-500">Source: “{quote}”</p>}
    </label>
  );
}
