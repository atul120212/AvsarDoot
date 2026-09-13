import Link from "next/link";

export default function Home() {
  return (
    <div className="py-10">
      <p className="text-sm font-medium uppercase tracking-wide text-saffron">India · Jobs · Admissions</p>
      <h1 className="mt-2 max-w-3xl text-4xl font-semibold leading-tight text-ink md:text-5xl">
        Fill your eligibility profile once. See only the opportunities you qualify for.
      </h1>
      <p className="mt-4 max-w-2xl text-lg text-slate-600">
        AvsarDoot is a filtering and notification layer on public notifications — government, PSU, and private.
        We do not host applications and we are not a recruiting authority.
      </p>
      <div className="mt-8 flex gap-3">
        <Link href="/register" className="rounded-full bg-ink px-6 py-2.5 text-white">
          Create profile
        </Link>
        <Link href="/login" className="rounded-full border border-slate-300 px-6 py-2.5">
          Sign in
        </Link>
      </div>
      <ul className="mt-12 grid gap-4 md:grid-cols-3">
        {[
          ["One profile", "Education, age, category, domicile, certifications, and exams already cleared."],
          ["Rule-based matching", "Deterministic eligibility — you can always see why something matched."],
          ["Official links only", "Every card points to the official notification. Always verify before applying."],
        ].map(([t, d]) => (
          <li key={t} className="rounded-2xl border border-slate-200 bg-white p-5">
            <h2 className="font-semibold text-ink">{t}</h2>
            <p className="mt-2 text-sm text-slate-600">{d}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
