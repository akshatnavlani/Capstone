import Link from "next/link";

// Team workspace (22 Nov 2026): research views kept out of the brand menu. Brands see creators, the network and risk;
// these pages explain how the system was built and tested.

const TOOLS = [
  { href: "/insights", title: "Insights", body: "Evidence charts: spillover results, benchmark against published methods, power, passport statistics." },
  { href: "/explainability", title: "Graph and scores", body: "The creator graph the model reads and the fusion formula for each score." },
  // 23 Nov 2026: the full tabbed analysis (S1-S10) moved here; the brand Analysis page keeps only what brands use.
  { href: "/research/analysis", title: "Detailed analysis", body: "Every analysis section (S1 to S10): temporal tests, feature score, fusion calibration, graph, linking audits, live results." },
];

export default function ResearchPage() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-8 px-6 py-12">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-signal">Team workspace · not shown to brands</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
          Research views
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-zinc-400">How the system was built and tested. These pages are not in the brand menu.</p>
      </header>
      <ul className="grid gap-4 sm:grid-cols-2">
        {TOOLS.map((t) => (
          <li key={t.href}>
            <Link href={t.href} className="block h-full rounded-xl border border-line bg-panel p-5 transition-colors hover:border-accent">
              <h2 className="text-lg font-semibold text-zinc-50">{t.title}</h2>
              <p className="mt-1 text-sm text-zinc-400">{t.body}</p>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
