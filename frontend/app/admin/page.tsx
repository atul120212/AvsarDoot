"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Opportunity } from "@/lib/api";
import { StatusBadge } from "@/components/OpportunityUI";

export default function AdminPage() {
  const router = useRouter();
  const [items, setItems] = useState<Opportunity[]>([]);
  const [queue, setQueue] = useState<"all" | "qa" | "live">("qa");
  const [scraping, setScraping] = useState(false);
  const [purging, setPurging] = useState(false);
  const [scrapeMsg, setScrapeMsg] = useState("");
  const [llmInfo, setLlmInfo] = useState<{ active_provider: string; has_gemini: boolean } | null>(null);

  const load = useCallback(
    async (qMode: string) => {
      const q = qMode === "all" ? "" : `?queue=${qMode}`;
      try {
        const data = await api<{ items: Opportunity[] }>(`/admin/opportunities${q}`);
        setItems(data.items);
      } catch (ex) {
        console.error("Failed to load opportunities", ex);
      }
    },
    []
  );

  useEffect(() => {
    if (localStorage.getItem("ad_role") !== "admin") {
      router.push("/feed");
      return;
    }
    load(queue);
    api<{ active_provider: string; has_gemini: boolean }>("/admin/llm-status")
      .then(setLlmInfo)
      .catch(() => null);
  }, [queue, router, load]);

  async function purgeJunk() {
    setPurging(true);
    setScrapeMsg("Purging aggregator hub & category pages...");
    try {
      const res = await api<{ ok: boolean; purged_count: number }>("/admin/purge-junk", {
        method: "POST",
      });
      setScrapeMsg(`Cleaned up ${res.purged_count} category/hub pages from the QA queue.`);
      await load(queue);
    } catch (ex) {
      setScrapeMsg(`Purge failed: ${(ex as Error).message}`);
    } finally {
      setPurging(false);
    }
  }

  async function triggerScraper() {
    setScraping(true);
    setScrapeMsg("Scraping SarkariResult & FreeJobAlert adapters (strictly filtering hub pages)...");
    try {
      const res = await api<{
        ok: boolean;
        stats: {
          scraped: number;
          ingested: number;
          skipped: number;
          skipped_listing?: number;
          purged_listing?: number;
          extractor?: string;
        };
      }>("/admin/scrape?limit=6", {
        method: "POST",
      });
      const { scraped, ingested, skipped, skipped_listing, purged_listing, extractor } = res.stats;
      setScrapeMsg(
        `Scraper (${extractor || "auto"}): ${scraped} pages checked, ${ingested} queued for QA, ${skipped} duplicates, ${skipped_listing || 0} category/hub pages rejected, ${purged_listing || 0} old hub records cleaned.`
      );
      await load(queue);
    } catch (ex) {
      setScrapeMsg(`Scraper failed: ${(ex as Error).message}`);
    } finally {
      setScraping(false);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-semibold text-ink">Admin / QA Dashboard</h1>
            {llmInfo && (
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${llmInfo.has_gemini ? "bg-purple-100 text-purple-800" : "bg-slate-100 text-slate-700"}`}>
                {llmInfo.has_gemini ? "✨ Gemini AI Extraction Active" : "⚡ Heuristic Extractor"}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-slate-600">Review auto-extracted records or publish verified opportunities.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={purgeJunk}
            disabled={purging}
            className="rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-2 text-sm font-medium text-rose-700 hover:bg-rose-100 disabled:opacity-50"
            title="Removes hub pages like 'Admit Card', 'Latest job', 'Results' from QA"
          >
            {purging ? "Purging..." : "🧹 Purge Hub / Category Pages"}
          </button>
          <button
            onClick={triggerScraper}
            disabled={scraping}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {scraping ? "Running Scrapers..." : "Run Job Scrapers (Strict Filter)"}
          </button>
          <Link href="/admin/new" className="rounded-lg bg-ink px-4 py-2 text-sm text-white">
            + New opportunity
          </Link>
        </div>
      </div>

      {scrapeMsg && (
        <div className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900 border border-amber-200">
          {scrapeMsg}
        </div>
      )}

      <div className="mt-6 flex gap-2">
        {(["qa", "live", "all"] as const).map((q) => (
          <button
            key={q}
            onClick={() => setQueue(q)}
            className={`rounded-full px-3.5 py-1 text-sm font-medium ${
              queue === q ? "bg-ink text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
            }`}
          >
            {q === "qa" ? "Needs QA Review" : q === "live" ? "Published Live" : "All Records"}
          </button>
        ))}
      </div>

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600 border-b">
            <tr>
              <th className="py-3 px-4">Title</th>
              <th className="px-4">Status</th>
              <th className="px-4">Confidence</th>
              <th className="px-4">QA Reviewed</th>
              <th className="px-4">Published</th>
            </tr>
          </thead>
          <tbody>
            {items.map((o) => (
              <tr key={o.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                <td className="py-3 px-4 font-medium">
                  <Link className="text-ink hover:underline" href={`/admin/${o.id}`}>
                    {o.canonical_title}
                  </Link>
                  <div className="text-xs text-slate-500 font-normal">{o.org_name}</div>
                </td>
                <td className="px-4">
                  <StatusBadge status={o.status} />
                </td>
                <td className="px-4 text-xs font-mono">
                  {o.extraction_confidence != null ? `${Math.round(o.extraction_confidence * 100)}%` : "Manual"}
                </td>
                <td className="px-4">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${o.reviewed_by_human ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>
                    {o.reviewed_by_human ? "Verified" : "Pending QA"}
                  </span>
                </td>
                <td className="px-4 text-xs font-medium">
                  {o.published ? "Live" : "Draft"}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={5} className="py-8 text-center text-slate-500">
                  No opportunities in this queue.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
