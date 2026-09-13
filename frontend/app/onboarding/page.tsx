"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";

const CERTS = ["CCC", "Typing 30wpm", "Typing 35wpm", "Driving License", "GATE", "JEE"];
const DOMAINS = ["Banking", "SSC", "Railway", "State-PSC", "UPSC-CSE", "Engineering", "Teaching", "PSU", "Police", "Other"];

type Meta = { indian_states: string[]; categories: string[]; education_levels: string[] };

const empty = {
  date_of_birth: "",
  gender: "Male",
  category: "General",
  domicile_state: "Uttar Pradesh",
  highest_education: "Graduate",
  education_stream: "Arts",
  degree_name: "B.A.",
  specialization: "",
  percentage_or_cgpa: 60,
  certifications: [] as string[],
  cleared_exams: [] as { exam: string; year: number }[],
  experience_years: 0,
  experience_domain: "",
  sector_interest: ["Govt", "PSU"] as string[],
  domain_interest: ["Banking", "SSC"] as string[],
  notification_channels: ["email"] as string[],
};

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(empty);
  const [examName, setExamName] = useState("");
  const [examYear, setExamYear] = useState(2026);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [err, setErr] = useState("");
  const [editMode, setEditMode] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("ad_token")) router.push("/login");
    api<Meta>("/meta").then(setMeta).catch(() => {});
    api<typeof empty | null>("/profile")
      .then((p) => {
        if (p) {
          setForm({ ...empty, ...p, date_of_birth: String(p.date_of_birth).slice(0, 10) });
          setEditMode(true);
        }
      })
      .catch(() => {});
  }, [router]);

  function toggle(list: string[], item: string) {
    return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      await api("/profile", {
        method: "PUT",
        body: JSON.stringify({
          ...form,
          percentage_or_cgpa: Number(form.percentage_or_cgpa),
          experience_years: Number(form.experience_years),
        }),
      });
      router.push("/feed");
    } catch (ex) {
      setErr((ex as Error).message);
    }
  }

  const titles = ["Basic info", "Education", "Certifications", "Exams cleared", "Interests"];

  return (
    <form onSubmit={submit} className="mx-auto max-w-xl rounded-2xl border border-slate-200 bg-white p-6">
      <p className="text-xs uppercase tracking-wide text-slate-500">
        Step {step + 1} of 5 · {titles[step]}
      </p>
      <h1 className="mt-1 text-2xl font-semibold text-ink">{editMode ? "Update profile" : "Eligibility profile"}</h1>

      {step === 0 && (
        <div className="mt-4 space-y-3">
          <Field label="Date of birth">
            <input type="date" required className="w-full rounded-lg border px-3 py-2" value={form.date_of_birth} onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} />
          </Field>
          <Field label="Gender">
            <select className="w-full rounded-lg border px-3 py-2" value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })}>
              {["Male", "Female", "Other"].map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </Field>
          <Field label="Category">
            <select className="w-full rounded-lg border px-3 py-2" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              {(meta?.categories || ["General", "OBC", "SC", "ST", "EWS", "PwD"]).map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </Field>
          <Field label="Domicile state">
            <select className="w-full rounded-lg border px-3 py-2" value={form.domicile_state} onChange={(e) => setForm({ ...form, domicile_state: e.target.value })}>
              {(meta?.indian_states || []).map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
        </div>
      )}

      {step === 1 && (
        <div className="mt-4 space-y-3">
          <Field label="Highest education">
            <select className="w-full rounded-lg border px-3 py-2" value={form.highest_education} onChange={(e) => setForm({ ...form, highest_education: e.target.value })}>
              {(meta?.education_levels || ["10th", "12th", "Diploma", "Graduate", "Postgraduate"]).map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
          <Field label="Stream">
            <input className="w-full rounded-lg border px-3 py-2" value={form.education_stream} onChange={(e) => setForm({ ...form, education_stream: e.target.value })} placeholder="Arts / Science / Commerce / Engineering" />
          </Field>
          <Field label="Degree name">
            <input className="w-full rounded-lg border px-3 py-2" value={form.degree_name} onChange={(e) => setForm({ ...form, degree_name: e.target.value })} placeholder="B.A. / B.Tech / M.Sc" />
          </Field>
          <Field label="Specialization">
            <input className="w-full rounded-lg border px-3 py-2" value={form.specialization} onChange={(e) => setForm({ ...form, specialization: e.target.value })} placeholder="Computer Science" />
          </Field>
          <Field label="Percentage or CGPA">
            <input type="number" className="w-full rounded-lg border px-3 py-2" value={form.percentage_or_cgpa} onChange={(e) => setForm({ ...form, percentage_or_cgpa: Number(e.target.value) })} />
          </Field>
        </div>
      )}

      {step === 2 && (
        <div className="mt-4 space-y-2">
          {CERTS.map((c) => (
            <label key={c} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.certifications.includes(c)} onChange={() => setForm({ ...form, certifications: toggle(form.certifications, c) })} />
              {c}
            </label>
          ))}
        </div>
      )}

      {step === 3 && (
        <div className="mt-4 space-y-3">
          <p className="text-sm text-slate-600">Add exams already cleared so Mains-stage posts can match.</p>
          <div className="flex gap-2">
            <input className="flex-1 rounded-lg border px-3 py-2" placeholder="UPSC Prelims" value={examName} onChange={(e) => setExamName(e.target.value)} />
            <input type="number" className="w-24 rounded-lg border px-3 py-2" value={examYear} onChange={(e) => setExamYear(Number(e.target.value))} />
            <button
              type="button"
              className="rounded-lg border px-3"
              onClick={() => {
                if (!examName) return;
                setForm({ ...form, cleared_exams: [...form.cleared_exams, { exam: examName, year: examYear }] });
                setExamName("");
              }}
            >
              Add
            </button>
          </div>
          <ul className="text-sm">
            {form.cleared_exams.map((x, i) => (
              <li key={i} className="flex justify-between py-1">
                {x.exam} ({x.year})
                <button type="button" className="text-rose-600" onClick={() => setForm({ ...form, cleared_exams: form.cleared_exams.filter((_, j) => j !== i) })}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {step === 4 && (
        <div className="mt-4 space-y-4">
          <p className="text-sm font-medium">Sectors</p>
          {["Govt", "PSU", "Private"].map((s) => (
            <label key={s} className="mr-4 text-sm">
              <input type="checkbox" className="mr-1" checked={form.sector_interest.includes(s)} onChange={() => setForm({ ...form, sector_interest: toggle(form.sector_interest, s) })} />
              {s}
            </label>
          ))}
          <p className="text-sm font-medium">Domains</p>
          <div className="flex flex-wrap gap-2">
            {DOMAINS.map((d) => (
              <button
                type="button"
                key={d}
                onClick={() => setForm({ ...form, domain_interest: toggle(form.domain_interest, d) })}
                className={`rounded-full px-3 py-1 text-sm ${form.domain_interest.includes(d) ? "bg-ink text-white" : "bg-slate-100"}`}
              >
                {d}
              </button>
            ))}
          </div>
          <p className="text-sm font-medium">Notifications</p>
          {[
            { key: "email", label: "📧 Email" },
            { key: "telegram", label: "📱 Telegram" },
            { key: "whatsapp", label: "💬 WhatsApp" },
          ].map(({ key, label }) => (
            <label key={key} className="mr-4 text-sm">
              <input
                type="checkbox"
                className="mr-1"
                checked={form.notification_channels.includes(key)}
                onChange={() => setForm({ ...form, notification_channels: toggle(form.notification_channels, key) })}
              />
              {label}
            </label>
          ))}
        </div>
      )}

      {err && <p className="mt-3 text-sm text-rose-600">{err}</p>}
      <div className="mt-6 flex justify-between">
        <button type="button" disabled={step === 0} onClick={() => setStep(step - 1)} className="rounded-lg border px-4 py-2 disabled:opacity-40">
          Back
        </button>
        {step < 4 ? (
          <button type="button" onClick={() => setStep(step + 1)} className="rounded-lg bg-ink px-4 py-2 text-white">
            Next
          </button>
        ) : (
          <button className="rounded-lg bg-ink px-4 py-2 text-white">Save and match</button>
        )}
      </div>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      {label}
      <div className="mt-1">{children}</div>
    </label>
  );
}
