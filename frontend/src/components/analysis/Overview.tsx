"use client";

import CreatorGraph from "@/components/CreatorGraph";
import type { AnalysisData } from "@/types/analysis";
import { Card, Note, Verdict } from "./ui";
import type { Tone } from "./ui";

export type TabId = "overview" | "s1" | "s2" | "s3" | "s6" | "s7" | "s8";

const CHIP: Record<Tone, string> = {
  good: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  warn: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  bad: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300",
  info: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
};

export function Overview({ data, onSelect }: { data: AnalysisData; onSelect: (t: TabId) => void }) {
  const hr = data.s8.hand_review;
  const cards: { id: TabId; tag: string; title: string; status: string; tone: Tone; big: string; line: string }[] = [
    {
      id: "s1",
      tag: "S1",
      title: "Temporal analysis",
      status: "Built · lag not proven",
      tone: "warn",
      big: `${data.s1.sentiment.scored} mood scores · ${data.s1.alerts.length} live alerts`,
      line: "Audience mood is scored and risk spreads along real links. The 24-hour cross-platform lag could not be confirmed: only 13 creators have enough data.",
    },
    {
      id: "s2",
      tag: "S2",
      title: "Feature score (CLIP / BERT)",
      status: "Built and live",
      tone: "good",
      big: `AUC up to ${Math.max(...Object.values(data.s2.auc).flatMap((m) => Object.values(m))).toFixed(2)}`,
      line: "Each creator is scored against the brand's brief from thumbnails, text, engagement and reach. Strong on broad briefs, weaker on narrow ones.",
    },
    {
      id: "s3",
      tag: "S3",
      title: "Fusion calibration",
      status: "Fixed · weights are priors",
      tone: "warn",
      big: `${data.s3.calibration.ci_spans_whole_range} of ${data.s3.calibration.creators} intervals span 0-100`,
      line: "A scale bug that pinned 20 creators at 100 is fixed. No outcome data exists to fit the weights, so they stay documented priors.",
    },
    {
      id: "s6",
      tag: "S6",
      title: "Creator graph",
      status: "Built",
      tone: "good",
      big: "187 connected creators",
      line: "An interactive map of the collaboration and co-occurrence links the model reads. Click a creator to highlight their links.",
    },
    {
      id: "s7",
      tag: "S7",
      title: "Filter and cost analysis",
      status: "Audited · matchers fixed",
      tone: "warn",
      big: `Demo query: 0 → ${data.s7.demo_query_fixed[Object.keys(data.s7.demo_query_fixed)[0]].kept} results`,
      line: "The region and product filters were dropping Indian creators and every athlete. Both matchers are fixed; data clean-up is still open. The cost model barely changes the ranking.",
    },
    {
      id: "s8",
      tag: "S8",
      title: "Cross-platform linking",
      status: "Audited · fixes pending",
      tone: "warn",
      big: `${data.s8.cross_platform_pairs.measured_on_2plus} of ${data.s8.cross_platform_pairs.pairs} pairs on 2 platforms`,
      line: `The cross-platform claim rests on one pair. About a quarter of Reddit links are wrong and ${hr.non_creator_accounts.low}-${hr.non_creator_accounts.high} 'creators' are shops, gyms or news pages.`,
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <Verdict tone="info" label="One page for everything the Temporal and analysis work found">
        Every section opens with a plain verdict. Where the data was too thin to answer a question the page says so, instead of showing a result that is not there. Click a card to open its section.
      </Verdict>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((c) => (
          <button key={c.id} type="button" onClick={() => onSelect(c.id)} className="group flex flex-col gap-2 rounded-xl border border-zinc-200 bg-white p-4 text-left transition hover:-translate-y-0.5 hover:shadow-md dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex items-center justify-between">
              <span className="rounded-md bg-zinc-900 px-1.5 py-0.5 text-[10px] font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">{c.tag}</span>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${CHIP[c.tone]}`}>{c.status}</span>
            </div>
            <h3 className="text-sm font-semibold">{c.title}</h3>
            <div className="text-lg font-semibold tracking-tight">{c.big}</div>
            <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">{c.line}</p>
            <span className="mt-auto text-xs font-medium text-zinc-500 group-hover:text-zinc-900 dark:group-hover:text-zinc-100">Open →</span>
          </button>
        ))}
      </div>
      <Note>Generated {new Date(data.generated_at).toLocaleString()}. Rerun scripts/export_analysis_dashboard.py to refresh.</Note>
    </div>
  );
}

export function S6Graph() {
  return (
    <div className="flex flex-col gap-4">
      <Verdict tone="good" label="Creator graph: built, with live data from the feature store">
        The map of links the model reads: 170 collaboration pairs and 707 co-occurrence pairs between 187 connected creators (72 isolated creators are counted but not drawn). The API returns each link in both directions, so its 340 and 1,414 are directed counts.
      </Verdict>
      <Card>
        <CreatorGraph results={null} />
      </Card>
      <Note>
        The linking audit (S8) found that about half of the co-occurrence pairs come from a few auction and roster threads, so the dense blue block is mostly creators listed together, not creators working together. The graph shows raw link counts; the learned weight per relation type is not
        served by the API yet.
      </Note>
    </div>
  );
}
