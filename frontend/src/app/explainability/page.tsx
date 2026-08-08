// Placeholder only. Per PROJECT_PLAN.md Section 5, explainability is built
// after the recommendation engine + fusion layer are stable (timeline rows
// 18-19), and is the layer most likely to flex if the schedule tightens.

export default function ExplainabilityPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Explainability</h1>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Network-graph visualization of influencer/brand connections and
        causal insights (e.g. posting-time/lag effects from the Granger
        causality step) — planned for later in the timeline, once the
        recommendation engine and fusion layer are stable.
      </p>
    </main>
  );
}
