"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type SubStatus = {
  subscription_tier: string;
  is_premium: boolean;
  features: Record<string, boolean>;
};

export default function SubscriptionPage() {
  const router = useRouter();
  const [sub, setSub] = useState<SubStatus | null>(null);
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("ad_token")) {
      router.push("/login");
      return;
    }
    loadSub();
  }, [router]);

  async function loadSub() {
    try {
      const data = await api<SubStatus>("/subscription/tier");
      setSub(data);
    } catch (ex) {
      console.error(ex);
    }
  }

  async function upgrade(tier: "free" | "premium") {
    setLoading(true);
    setMsg("");
    try {
      const res = await api<{ message: string }>("/subscription/upgrade", {
        method: "POST",
        body: JSON.stringify({ tier }),
      });
      setMsg(res.message);
      await loadSub();
    } catch (ex) {
      setMsg((ex as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="py-8 max-w-4xl mx-auto">
      <div className="text-center">
        <span className="rounded-full bg-amber-100 px-3.5 py-1 text-xs font-semibold uppercase tracking-wider text-amber-800">
          Plans & Subscriptions
        </span>
        <h1 className="mt-3 text-4xl font-semibold text-ink">Choose the Right Alert Plan for Your Goal</h1>
        <p className="mt-2 text-slate-600">
          Get real-time notification alerts via Email or WhatsApp. Never miss a qualifying deadline.
        </p>
      </div>

      {msg && (
        <div className="mt-6 rounded-xl bg-emerald-50 p-4 text-center text-sm font-medium text-emerald-900 border border-emerald-200">
          {msg}
        </div>
      )}

      <div className="mt-10 grid gap-8 md:grid-cols-2">
        {/* Free Tier */}
        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold text-ink">Free Tier</h2>
              {sub?.subscription_tier === "free" && (
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">Active Plan</span>
              )}
            </div>
            <p className="mt-2 text-sm text-slate-600">Basic eligibility filtering and email alerts for all public jobs.</p>
            <div className="mt-6 text-3xl font-extrabold text-ink">₹0 <span className="text-sm font-normal text-slate-500">/ forever</span></div>

            <ul className="mt-6 space-y-3 text-sm text-slate-700">
              <li className="flex items-center gap-2">✓ Rule-based eligibility feed</li>
              <li className="flex items-center gap-2">✓ Standard Email alert digests</li>
              <li className="flex items-center gap-2">✓ Direct official link verification</li>
              <li className="flex items-center gap-2 text-slate-400">✗ Instant WhatsApp alerts</li>
              <li className="flex items-center gap-2 text-slate-400">✗ T-5 & T-1 SMS deadline reminders</li>
            </ul>
          </div>

          <button
            onClick={() => upgrade("free")}
            disabled={loading || sub?.subscription_tier === "free"}
            className="mt-8 w-full rounded-xl border border-slate-300 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {sub?.subscription_tier === "free" ? "Current Plan" : "Downgrade to Free"}
          </button>
        </div>

        {/* Premium Tier */}
        <div className="relative rounded-3xl border-2 border-saffron bg-white p-8 shadow-md flex flex-col justify-between">
          <div className="absolute -top-3.5 right-6 rounded-full bg-saffron px-3 py-0.5 text-xs font-semibold text-white uppercase tracking-wider">
            Recommended
          </div>

          <div>
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold text-ink">Premium Alert Tier</h2>
              {sub?.is_premium && (
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-800">Active Plan</span>
              )}
            </div>
            <p className="mt-2 text-sm text-slate-600">Instant WhatsApp alerts, deadline SMS, and candidate tracker analytics.</p>
            <div className="mt-6 text-3xl font-extrabold text-ink">₹149 <span className="text-sm font-normal text-slate-500">/ month</span></div>

            <ul className="mt-6 space-y-3 text-sm text-slate-700">
              <li className="flex items-center gap-2 font-medium text-emerald-800">✓ Everything in Free</li>
              <li className="flex items-center gap-2 font-medium text-emerald-800">✓ Instant WhatsApp Business alerts</li>
              <li className="flex items-center gap-2 font-medium text-emerald-800">✓ Urgent T-5 & T-1 Day deadline reminders</li>
              <li className="flex items-center gap-2 font-medium text-emerald-800">✓ Advanced Application Tracker</li>
              <li className="flex items-center gap-2 font-medium text-emerald-800">✓ Mains & Stage-II prerequisite alerts</li>
            </ul>
          </div>

          <button
            onClick={() => upgrade("premium")}
            disabled={loading || sub?.is_premium}
            className="mt-8 w-full rounded-xl bg-ink py-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {sub?.is_premium ? "Active Premium Plan" : "Upgrade to Premium (₹149)"}
          </button>
        </div>
      </div>
    </div>
  );
}
