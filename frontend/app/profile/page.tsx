"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function ProfilePage() {
  const router = useRouter();
  const [me, setMe] = useState<{ email: string; role: string } | null>(null);

  useEffect(() => {
    if (!localStorage.getItem("ad_token")) {
      router.push("/login");
      return;
    }
    api<{ email: string; role: string }>("/profile/me").then(setMe);
  }, [router]);

  return (
    <div className="max-w-lg">
      <h1 className="text-3xl font-semibold text-ink">Your account</h1>
      <p className="mt-2 text-slate-600">{me?.email}</p>
      <p className="mt-4 text-sm">
        Date of birth, category, and education are used only for matching. They are not sold or shared with recruiters.
      </p>
      <Link href="/onboarding" className="mt-6 inline-block rounded-lg bg-ink px-4 py-2 text-white">
        Edit eligibility profile
      </Link>
    </div>
  );
}
