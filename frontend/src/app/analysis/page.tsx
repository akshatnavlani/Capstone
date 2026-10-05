"use client";

import { useEffect, useState } from "react";
import { getAnalysis } from "@/lib/api";
import { Overview, S6Graph } from "@/components/analysis/Overview";
import type { TabId } from "@/components/analysis/Overview";
import S1Temporal from "@/components/analysis/S1Temporal";
import { S2Feature, S3Fusion } from "@/components/analysis/S2S3";
import { S7Filters, S8Linking } from "@/components/analysis/S7S8";
import type { AnalysisData } from "@/types/analysis";

const TABS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "s1", label: "S1 Temporal" },
  { id: "s2", label: "S2 Feature score" },
  { id: "s3", label: "S3 Fusion" },
  { id: "s6", label: "S6 Graph" },
  { id: "s7", label: "S7 Filters & cost" },
  { id: "s8", label: "S8 Linking" },
];

export default function AnalysisPage() {
  const [data, setData] = useState<AnalysisData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("overview");

  useEffect(() => {
    let cancelled = false;
    getAnalysis()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-5 px-6 py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Analysis</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Temporal analysis and the evidence behind the scores: what was built, what was measured, and where the data is too thin to answer.
        </p>
      </div>

      <div role="tablist" aria-label="Analysis sections" className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`whitespace-nowrap rounded-full border px-3.5 py-1.5 text-sm transition ${
              tab === t.id ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900" : "border-zinc-300 text-zinc-600 hover:border-zinc-500 dark:border-zinc-700 dark:text-zinc-400"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <p className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300">
          Could not load the analysis data: {error}. Is the backend running, and was scripts/export_analysis_dashboard.py run?
        </p>
      )}
      {!error && !data && <p className="text-sm text-zinc-500">Loading…</p>}

      {data && (
        <div role="tabpanel">
          {tab === "overview" && <Overview data={data} onSelect={setTab} />}
          {tab === "s1" && <S1Temporal data={data} />}
          {tab === "s2" && <S2Feature data={data} />}
          {tab === "s3" && <S3Fusion data={data} />}
          {tab === "s6" && <S6Graph />}
          {tab === "s7" && <S7Filters data={data} />}
          {tab === "s8" && <S8Linking data={data} />}
        </div>
      )}
    </main>
  );
}
