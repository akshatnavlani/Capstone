// Wireframe shell only — one illustrative placeholder alert, not real/mock data.
// Wiring against the Temporal branch's sentiment-propagation output is a
// Weeks 16-17 objective. Shape documented in WIREFRAMES.md and
// src/types/index.ts (MonitoringAlert).

export default function MonitoringPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Monitoring &amp; Alerts</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Risk flags and sentiment alerts, including risk propagated from a
          collaborator&apos;s controversy.
        </p>
      </div>

      <ul className="flex flex-col gap-3">
        <li className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <div className="flex items-center justify-between">
            <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
              medium severity
            </span>
            <span className="text-xs text-zinc-500">detected_at placeholder</span>
          </div>
          <h2 className="mt-2 text-sm font-medium">Example Influencer Name</h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Placeholder alert description.
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            Propagated from collaborator: propagated_from_influencer_id slot
          </p>
        </li>
      </ul>
    </main>
  );
}
