"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Opportunity } from "@/lib/api";
import { OpportunityCard } from "@/components/OpportunityUI";

export default function FeedPage() {
  const router = useRouter();
  const [items, setItems] = useState<Opportunity[]>([]);
  const [onlyMatches, setOnlyMatches] = useState(true);
  const [onboarded, setOnboarded] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("ad_token")) {
      router.push("/login");
      return;
    }
    load(onlyMatches);
  }, [onlyMatches, router]);

  async function load(matches: boolean) {
    try {
      const data = await api<{ items: Opportunity[]; onboarding_complete: boolean }>(`/feed?only_matches=${matches}`);
      setItems(data.items);
      setOnboarded(data.onboarding_complete);
    } catch (ex) {
      setErr((ex as Error).message);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-ink">Your feed</h1>
          <p className="text-slate-600">Only published, human-reviewed opportunities.</p>
        </div>
        <label className="text-sm">
          <input type="checkbox" className="mr-2" checked={onlyMatches} onChange={(e) => setOnlyMatches(e.target.checked)} />
          Show only matches
        </label>
      </div>
      {!onboarded && (
        <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm">
          Complete your <a className="underline" href="/onboarding">eligibility profile</a> to filter this list.
        </p>
      )}
      {err && <p className="mt-4 text-rose-600">{err}</p>}
      <div className="mt-6 grid gap-4">
        {items.map((opp) => (
          <OpportunityCard key={opp.id} opp={opp} href={`/opportunities/${opp.id}`} />
        ))}
        {items.length === 0 && <p className="text-slate-500">No opportunities in this view yet.</p>}
      </div>
    </div>
  );
}
