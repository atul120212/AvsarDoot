"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export function Nav() {
  const path = usePathname();
  const router = useRouter();
  const [role, setRole] = useState<string | null>(null);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    setAuthed(!!localStorage.getItem("ad_token"));
    setRole(localStorage.getItem("ad_role"));
  }, [path]);

  function logout() {
    localStorage.removeItem("ad_token");
    localStorage.removeItem("ad_role");
    router.push("/");
  }

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href={authed ? "/feed" : "/"} className="flex items-center gap-2 font-semibold text-ink">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-ink text-sm text-white">आ</span>
          AvsarDoot
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          {authed ? (
            <>
              <Link className={link(path, "/feed")} href="/feed">
                Feed
              </Link>
              <Link className={link(path, "/tracker")} href="/tracker">
                Tracker
              </Link>
              <Link className={link(path, "/profile")} href="/profile">
                Profile
              </Link>
              <Link className={link(path, "/subscription")} href="/subscription">
                Plans ⭐
              </Link>
              <Link className={link(path, "/telegram")} href="/telegram">
                📱 Telegram
              </Link>
              {role === "admin" && (
                <Link className={link(path, "/admin")} href="/admin">
                  Admin
                </Link>
              )}
              <button onClick={logout} className="text-slate-500 hover:text-ink">
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-slate-600 hover:text-ink">
                Sign in
              </Link>
              <Link href="/register" className="rounded-full bg-ink px-4 py-1.5 text-white">
                Get started
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}

function link(path: string, href: string) {
  return path.startsWith(href) ? "font-medium text-ink underline underline-offset-4" : "text-slate-600 hover:text-ink";
}
