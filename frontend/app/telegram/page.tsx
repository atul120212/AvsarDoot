"use client";

import { useEffect, useState } from "react";
import { API } from "@/lib/api";
import { Nav } from "@/components/Nav";

type LinkTokenResponse = {
  token: string;
  deep_link: string;
  bot_username: string;
  already_linked: boolean;
};

type StatusResponse = {
  linked: boolean;
  chat_id: string | null;
};

export default function TelegramPage() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [linkData, setLinkData] = useState<LinkTokenResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [testSent, setTestSent] = useState(false);
  const [error, setError] = useState("");
  const [polling, setPolling] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("ad_token") : null;

  const headers = { Authorization: `Bearer ${token}` };

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API}/telegram/status`, { headers });
      if (res.ok) setStatus(await res.json());
    } catch {}
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  // Poll for link confirmation after user opens bot
  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(async () => {
      const res = await fetch(`${API}/telegram/status`, { headers });
      if (res.ok) {
        const data: StatusResponse = await res.json();
        setStatus(data);
        if (data.linked) {
          setPolling(false);
          clearInterval(interval);
        }
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [polling]);

  const generateLink = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/telegram/link-token`, { headers });
      if (!res.ok) {
        const err = await res.json();
        setError(err.detail || "Failed to generate link");
        return;
      }
      const data: LinkTokenResponse = await res.json();
      setLinkData(data);
      setPolling(true);
    } catch (e) {
      setError("Network error. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  const sendTest = async () => {
    setTestSent(false);
    const res = await fetch(`${API}/telegram/test`, { method: "POST", headers });
    if (res.ok) setTestSent(true);
    else setError("Test failed. Check backend logs.");
  };

  const unlink = async () => {
    if (!confirm("Unlink your Telegram account?")) return;
    await fetch(`${API}/telegram/unlink`, { method: "POST", headers });
    setStatus({ linked: false, chat_id: null });
    setLinkData(null);
    setTestSent(false);
  };

  return (
    <>
      <Nav />
      <main className="max-w-xl mx-auto px-4 py-12">
        <h1 className="text-3xl font-bold mb-2">📱 Telegram Alerts</h1>
        <p className="text-gray-400 mb-8">
          Get instant job & exam alerts directly in Telegram — faster than email.
        </p>

        {/* Status Badge */}
        {status && (
          <div
            className={`mb-6 rounded-xl px-5 py-4 flex items-center gap-3 border ${
              status.linked
                ? "bg-green-900/30 border-green-600 text-green-300"
                : "bg-gray-800 border-gray-700 text-gray-400"
            }`}
          >
            <span className="text-2xl">{status.linked ? "✅" : "⚪"}</span>
            <div>
              <div className="font-semibold text-white">
                {status.linked ? "Telegram Linked" : "Not Linked Yet"}
              </div>
              <div className="text-sm">
                {status.linked
                  ? `Alerts will be sent to your Telegram (Chat ID: ${status.chat_id})`
                  : "Follow the steps below to link your account."}
              </div>
            </div>
          </div>
        )}

        {/* Steps to link */}
        {!status?.linked && (
          <div className="bg-gray-900 rounded-xl border border-gray-700 p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">How to Link</h2>
            <ol className="space-y-4 text-gray-300">
              <li className="flex gap-3">
                <span className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-sm font-bold shrink-0">1</span>
                <span>Click <strong>"Generate Bot Link"</strong> below — it creates a secure one-time link.</span>
              </li>
              <li className="flex gap-3">
                <span className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-sm font-bold shrink-0">2</span>
                <span>Open the link in Telegram — it will open the AvsarDoot bot.</span>
              </li>
              <li className="flex gap-3">
                <span className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-sm font-bold shrink-0">3</span>
                <span>Press <strong>START</strong> in Telegram — your account links automatically.</span>
              </li>
              <li className="flex gap-3">
                <span className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-sm font-bold shrink-0">4</span>
                <span>This page updates to <strong>Linked ✅</strong> within seconds.</span>
              </li>
            </ol>

            <button
              onClick={generateLink}
              disabled={loading}
              className="mt-6 w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold py-3 rounded-lg transition"
            >
              {loading ? "Generating..." : "Generate Bot Link"}
            </button>
          </div>
        )}

        {/* Deep link card */}
        {linkData && !status?.linked && (
          <div className="bg-blue-900/20 border border-blue-600 rounded-xl p-5 mb-6">
            <p className="text-blue-300 font-semibold mb-3">
              {polling ? "⏳ Waiting for you to press START in Telegram..." : "Your one-time bot link:"}
            </p>
            <a
              href={linkData.deep_link}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full text-center bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-lg transition text-lg"
            >
              Open @{linkData.bot_username} in Telegram →
            </a>
            <p className="text-gray-500 text-xs mt-3 text-center">
              This link expires after use. Generate a new one if needed.
            </p>

            {polling && (
              <div className="mt-3 flex items-center gap-2 text-blue-400 text-sm justify-center">
                <span className="animate-spin">⟳</span> Checking for confirmation...
              </div>
            )}
          </div>
        )}

        {/* Linked actions */}
        {status?.linked && (
          <div className="space-y-3">
            <button
              onClick={sendTest}
              className="w-full bg-green-700 hover:bg-green-600 text-white font-semibold py-3 rounded-lg transition"
            >
              Send Test Message
            </button>
            {testSent && (
              <p className="text-green-400 text-center text-sm">
                ✅ Test message sent! Check your Telegram.
              </p>
            )}
            <button
              onClick={unlink}
              className="w-full bg-gray-800 hover:bg-red-900/40 border border-gray-600 hover:border-red-600 text-gray-400 hover:text-red-400 font-semibold py-3 rounded-lg transition"
            >
              Unlink Telegram
            </button>
          </div>
        )}

        {error && (
          <div className="mt-4 text-red-400 text-sm bg-red-900/20 border border-red-700 rounded-lg px-4 py-3">
            {error}
          </div>
        )}

        {/* Info box */}
        <div className="mt-8 bg-gray-900 border border-gray-700 rounded-xl p-5 text-sm text-gray-400">
          <p className="font-semibold text-gray-300 mb-2">What notifications will I get?</p>
          <ul className="space-y-1 list-disc list-inside">
            <li>New job/exam matches based on your profile</li>
            <li>Deadline reminders (5 days & 1 day before apply date)</li>
            <li>Status updates when results are announced</li>
          </ul>
        </div>
      </main>
    </>
  );
}
