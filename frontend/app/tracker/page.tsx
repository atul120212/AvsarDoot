"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Opportunity } from "@/lib/api";
import { StatusBadge, daysLeft } from "@/components/OpportunityUI";

type TrackedMap = {
  applied: Opportunity[];
  shortlisted: Opportunity[];
  saved: Opportunity[];
  dismissed: Opportunity[];
  other: Opportunity[];
};

export default function TrackerPage() {
  const router = useRouter();
  const [tracker, setTracker] = useState<TrackedMap>({
    applied: [],
    shortlisted: [],
    saved: [],
    dismissed: [],
    other: [],
  });
  const [activeTab, setActiveTab] = useState<"applied" | "saved" | "shortlisted" | "dismissed">("applied");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("ad_token")) {
      router.push("/login");
      return;
    }
    loadTracker();
  }, [router]);

  async function loadTracker() {
    setLoading(true);
    try {
      const data = await api<{ tracker: TrackedMap }>("/tracker");
      setTracker(data.tracker);
    } catch (ex) {
      setErr((ex as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function updateAction(oppId: string, newAction: string) {
    try {
      await api(`/opportunities/${oppId}/action`, {
        method: "POST",
        body: JSON.stringify({ action: newAction }),
      });
      await loadTracker();
    } catch (ex) {
      alert((ex as Error).message);
    }
  }

  const items = tracker[activeTab] || [];

  return (
    <div className="py-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-ink">Application Tracker</h1>
          <p className="mt-1 text-sm text-slate-600">Track saved opportunities, pending applications, and shortcuts.</p>
        </div>
      </div>

      {err && <p className="mt-4 text-rose-600">{err}</p>}

      <div className="mt-6 flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        {(["applied", "saved", "shortlisted", "dismissed"] as const).map((tab) => {
          const count = (tracker[tab] || []).length;
          return (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                activeTab === tab ? "bg-ink text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)} ({count})
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="py-12 text-center text-slate-500">Loading candidate tracker pipeline...</div>
      ) : (
        <div className="mt-6 grid gap-4">
          {items.map((opp) => {
            const left = daysLeft(opp.apply_end_date);
            return (
              <div key={opp.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-800">{opp.sector}</span>
                    {opp.domain && <span className="text-xs text-slate-500">{opp.domain}</span>}
                    <StatusBadge status={opp.status} />
                  </div>
                  <span className="text-xs text-slate-400 font-mono">ID: {opp.id.slice(0, 8)}</span>
                </div>

                <h3 className="mt-3 text-lg font-semibold text-ink">{opp.canonical_title}</h3>
                <p className="text-sm text-slate-600">{opp.org_name}</p>

                <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-slate-700">
                  <div>
                    <strong className="font-medium text-slate-900">Apply Deadline:</strong> {opp.apply_end_date || "TBA"}
                    {left !== null && left >= 0 ? ` (${left} days remaining)` : ""}
                  </div>
                  {opp.exam_date && (
                    <div>
                      <strong className="font-medium text-slate-900">Exam Date:</strong> {opp.exam_date}
                    </div>
                  )}
                </div>

                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100">
                  <div className="flex flex-wrap gap-2 text-xs">
                    {activeTab !== "applied" && (
                      <button
                        onClick={() => updateAction(opp.id, "applied")}
                        className="rounded-lg bg-emerald-50 px-2.5 py-1 font-medium text-emerald-800 border border-emerald-200 hover:bg-emerald-100"
                      >
                        ✓ Mark Applied
                      </button>
                    )}
                    {activeTab !== "shortlisted" && (
                      <button
                        onClick={() => updateAction(opp.id, "shortlisted")}
                        className="rounded-lg bg-sky-50 px-2.5 py-1 font-medium text-sky-800 border border-sky-200 hover:bg-sky-100"
                      >
                        ★ Shortlist
                      </button>
                    )}
                    {activeTab !== "saved" && (
                      <button
                        onClick={() => updateAction(opp.id, "saved")}
                        className="rounded-lg bg-slate-100 px-2.5 py-1 font-medium text-slate-700 hover:bg-slate-200"
                      >
                        Save for later
                      </button>
                    )}
                    {activeTab !== "dismissed" && (
                      <button
                        onClick={() => updateAction(opp.id, "dismissed")}
                        className="rounded-lg bg-rose-50 px-2.5 py-1 font-medium text-rose-700 hover:bg-rose-100"
                      >
                        Remove
                      </button>
                    )}
                  </div>

                  <a
                    href={opp.primary_source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Official Portal →
                  </a>
                </div>
              </div>
            );
          })}

          {items.length === 0 && (
            <div className="rounded-2xl border border-dashed border-slate-200 p-12 text-center text-slate-500">
              No opportunities tracked under <strong>{activeTab}</strong> yet. You can mark items directly from your Feed!
            </div>
          )}
        </div>
      )}
    </div>
  );
}
