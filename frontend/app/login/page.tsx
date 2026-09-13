"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      const res = await api<{ access_token: string; role: string; onboarding_complete: boolean }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      localStorage.setItem("ad_token", res.access_token);
      localStorage.setItem("ad_role", res.role);
      if (res.role === "admin") router.push("/admin");
      else router.push(res.onboarding_complete ? "/feed" : "/onboarding");
    } catch (ex) {
      setErr((ex as Error).message);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-6">
      <h1 className="text-2xl font-semibold text-ink">Sign in</h1>
      <label className="mt-4 block text-sm">Email</label>
      <input className="mt-1 w-full rounded-lg border px-3 py-2" value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
      <label className="mt-3 block text-sm">Password</label>
      <input className="mt-1 w-full rounded-lg border px-3 py-2" value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
      {err && <p className="mt-3 text-sm text-rose-600">{err}</p>}
      <button className="mt-5 w-full rounded-lg bg-ink py-2 text-white">Continue</button>
      <p className="mt-3 text-xs text-slate-500">Demo admin: admin@avsardoot.local / admin123</p>
    </form>
  );
}
