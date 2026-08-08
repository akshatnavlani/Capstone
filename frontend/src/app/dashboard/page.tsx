// Wireframe shell only — one illustrative placeholder card, not real/mock data.
// Ranked-list wiring against the Fusion Layer API is a Weeks 13-15 objective.
// Shape documented in WIREFRAMES.md and src/types/index.ts (InfluencerRecommendation).

export default function DashboardPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Recommendation Dashboard</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Ranked influencer list, one card per influencer, sorted by overall score.
        </p>
      </div>

      <ul className="flex flex-col gap-4">
        <li className="rounded-lg border border-zinc-200 p-5 dark:border-zinc-800">
          <div className="flex items-start justify-between gap-4">
            <div>
              <span className="text-xs font-medium text-zinc-500">#1</span>
              <h2 className="text-lg font-medium">Example Influencer Name</h2>
              <p className="text-xs text-zinc-500">@youtube · @instagram · @reddit</p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-semibold">78</div>
              <div className="text-xs text-zinc-500">confidence 72–84</div>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
            <ScorePart label="Spillover" value="—" />
            <ScorePart label="Sentiment / Risk" value="—" />
            <ScorePart label="Feature Score" value="—" />
          </div>

          <div className="mt-4 flex gap-2">
            <span className="rounded-full border border-zinc-300 px-2 py-1 text-xs text-zinc-500 dark:border-zinc-700">
              risk-flag badge slot
            </span>
          </div>
        </li>
      </ul>
    </main>
  );
}

function ScorePart({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-zinc-50 px-3 py-2 dark:bg-zinc-900">
      <div className="text-zinc-500">{label}</div>
      <div className="mt-1 font-medium">{value}</div>
    </div>
  );
}
