"use client";

import { useEffect, useState } from "react";
import { ForestPlot, GroupedBars, HBars, Histogram, PowerLines, SegmentBar } from "@/components/charts/Charts";
import { getInsights } from "@/lib/api";
import type { InsightsData } from "@/types";

// Insights (1 Nov 2026): the project's evidence on one page. Real results are unmarked; anything simulated carries a SIMULATED tag; a null is drawn as a null.

function Section({ n, title, lede, simulated, children }: { n: string; title: string; lede: string; simulated?: boolean; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-line p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl">
          <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent">{n}</div>
          <h2 className="mt-1 text-xl font-semibold text-zinc-50">{title}</h2>
          <p className="mt-1 text-sm leading-relaxed text-zinc-400">{lede}</p>
        </div>
        <span className={`rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider ${simulated ? "border-signal/50 text-signal" : "border-accent/50 text-accent"}`}>
          {simulated ? "simulated" : "real data"}
        </span>
      </div>
      {children}
    </section>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-xl border border-line p-4">
      <div className="text-[11px] uppercase tracking-[0.12em] text-zinc-500">{label}</div>
      <div className="mt-1.5 font-display text-3xl font-semibold text-zinc-50" style={{ fontFamily: "var(--font-display)" }}>{value}</div>
      <div className="mt-1 text-xs text-zinc-400">{sub}</div>
    </div>
  );
}

export default function InsightsPage() {
  const [d, setD] = useState<InsightsData | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    getInsights().then(setD).catch(() => setError(true));
  }, []);

  if (error) return <main className="mx-auto w-full max-w-5xl px-6 py-16 text-sm text-red-400">Couldn&apos;t load the insights. Is the backend running?</main>;
  if (!d) return <main className="mx-auto w-full max-w-5xl px-6 py-16 text-sm text-zinc-500">Loading the evidence…</main>;

  const j = d.spillover_journey.rows;
  const last = j[j.length - 1];
  const first = j[0];
  const widthFirst = first ? first.hi - first.lo : 0;
  const widthLast = last ? last.hi - last.lo : 0;
  const p = d.passport;
  const flagged = p.mood_gap_summary?.flagged ?? 0;
  const withBoth = p.mood_gap_summary?.creators_with_both ?? 0;
  const gradeColours: Record<string, string> = { A: "#35d6c0", B: "#5aa9e6", C: "#f5b83d", D: "#e0566b" };
  const sr = p.sponsored_response;
  const methodColours: Record<string, string> = { "GAIL-R": "#35d6c0", "GAIL-R + placebo": "#f5b83d" };
  const scenarios = Object.entries(d.fusion_simulation.scenarios);
  const firstScenario = scenarios[0];
  const e4 = d.extensions.e4;

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-5 py-10 sm:px-8">
      <header>
        <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-accent">Evidence room</div>
        <h1 className="mt-1 text-4xl font-semibold text-zinc-50">What the data shows, and how sure we are</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-zinc-400">
          Every chart below is drawn from a result file in this project. Tags say whether it is real data or a simulation with a known planted effect. The spillover result is shown as it is: a tight null.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Creators profiled" value={String(p.creators)} sub="each with a Passport" />
        <Kpi label="Exposed cases" value={String(last?.exposed ?? "n/a")} sub={`up from ${first?.exposed ?? "?"}, real collaborators`} />
        <Kpi label="Mood gaps flagged" value={`${flagged} / ${withBoth}`} sub="liked on one platform, not the other" />
        <Kpi label="Clash warnings" value={String(p.clash?.creators_with_recent_brand_posts ?? 0)} sub={`creators with a rival-brand post in ${p.clash?.window_days ?? 120} days`} />
      </div>

      <Section n="01 · Spillover" title="Five times the cases, half the uncertainty, and still no spillover" lede="The estimated effect of a collaborator's sponsored post on a creator's engagement, on the log scale, with its 95% interval. The dashed line is zero. An interval across zero means no detectable effect." >
        <ForestPlot
          rows={j.map((r, i) => ({ label: r.label, sub: `${r.exposed} exposed observations`, est: r.effect, lo: r.lo, hi: r.hi, accent: i === j.length - 1 }))}
          domain={[-1.4, 1.0]}
          hint="Hover a row for the numbers"
        />
        <p className="mt-3 rounded-lg border border-line bg-zinc-950/60 px-4 py-3 text-sm leading-relaxed text-zinc-300">
          The interval is now {widthLast.toFixed(2)} wide, from {widthFirst.toFixed(2)}. Effects larger than about a 1.5-fold change in engagement are ruled out. Smaller ones cannot be seen with this many cases, which is why more linked creators are the next step.
        </p>
      </Section>

      <Section n="02 · Method" title="The method against the others, on a known effect" lede="Average error in recovering a planted spillover effect on the real creator graph (lower is better). The planted effect is known, so the error is exact. Without the placebo penalty GAIL-R is fooled by a pre-existing trend; with it, it is not." simulated>
        <GroupedBars
          groups={d.benchmark.settings.map((s) => ({ label: s.setting, values: s.errors }))}
          methods={d.benchmark.methods}
          highlight={methodColours}
        />
        {d.published_baselines && (
          <div className="mt-4 overflow-x-auto rounded-lg border border-line">
            <table className="w-full text-left text-xs">
              <caption className="px-4 pt-3 text-left text-zinc-400">Published models run from the authors&apos; code on the same benchmark ({d.published_baselines.replicates} replicates, {d.published_baselines.graph}; per-creator error, lower is better)</caption>
              <thead className="text-zinc-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Method</th>
                  <th className="px-4 py-2 font-medium">No trend</th>
                  <th className="px-4 py-2 font-medium">Planted pre-trend</th>
                </tr>
              </thead>
              <tbody>
                {d.published_baselines.rows.map((r) => {
                  const ours = r.method.startsWith("GAIL-R");
                  return (
                    <tr key={r.method} className="border-t border-line">
                      <td className={`px-4 py-2 ${ours ? "font-medium text-accent" : "text-zinc-300"}`}>{r.method}</td>
                      <td className="tabular-nums px-4 py-2">{r.no_trend.toFixed(3)}</td>
                      <td className="tabular-nums px-4 py-2">{r.pre_trend.toFixed(3)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="px-4 py-3 text-[11px] text-zinc-500">{d.published_baselines.caveat}</p>
          </div>
        )}
      </Section>

      <Section n="03 · Power" title="What our data could have seen" lede="Chance of detecting a planted effect of each size, for different numbers of exposed observations, keeping the real outcomes. This is what makes a null believable: the test would have caught a large effect." simulated>
        <PowerLines effects={d.power.effects} series={d.power.series} highlightN={d.power.real_exposed} />
      </Section>

      <Section n="04 · Creator Passport" title="Where creators differ across platforms" lede="Mood gap is Instagram comment mood minus YouTube comment mood, per creator. Amber bars are the creators where the gap is large and beyond a worst-case error bound.">
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <h3 className="mb-2 text-sm font-medium text-zinc-200">Mood gap between platforms</h3>
            <Histogram values={p.mood_gaps.map((g) => g.gap)} flags={p.mood_gaps.map((g) => g.flagged)} domain={[-0.4, 0.5]} bins={15} label="Distribution of the mood gap" />
          </div>
          <div>
            <h3 className="mb-2 text-sm font-medium text-zinc-200">Attention speed on YouTube</h3>
            <Histogram values={p.speed_shares} domain={[0, 1]} bins={12} unit="" digits={1} label="Share of first-week views in the first 24 hours" />
            <p className="mt-1 text-[11px] text-zinc-500">Share of a video&apos;s first-week views that arrive in the first 24 hours, per creator.</p>
          </div>
        </div>
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div>
            <h3 className="mb-2 text-sm font-medium text-zinc-200">Evidence grade of every creator</h3>
            <SegmentBar parts={(["A", "B", "C", "D"] as const).map((g) => ({ label: g, value: p.grades[g], colour: gradeColours[g] }))} />
            <p className="mt-1 text-[11px] text-zinc-500">How much real data stands behind a score. It says how well we know a creator, not how good they are.</p>
          </div>
          <div>
            <h3 className="mb-2 text-sm font-medium text-zinc-200">Do sponsored posts get less response?</h3>
            {sr && (
              <ForestPlot
                rows={(["youtube_views", "youtube_likes", "instagram_likes"] as const).map((k) => ({
                  label: { youtube_views: "YouTube views", youtube_likes: "YouTube likes", instagram_likes: "Instagram likes" }[k],
                  sub: `${sr[k].creators} creators`,
                  est: sr[k].approx_percent ?? 0,
                  lo: sr[k].ci95_percent?.[0] ?? 0,
                  hi: sr[k].ci95_percent?.[1] ?? 0,
                  accent: k === "instagram_likes",
                }))}
                domain={[-80, 40]}
                unit="%"
                digits={1}
                hint="Sponsored post against the same creator's organic posts"
              />
            )}
            <p className="mt-1 text-[11px] text-zinc-500">YouTube shows no clear penalty (interval includes zero). Instagram has too few creators to say.</p>
          </div>
        </div>
      </Section>

      <Section n="05 · Scoring design" title="Does taking spillover out of the score cost anything?" lede="A planted-value test of the scoring rule: how well each rule recovers the true ordering of creators (Spearman with the planted truth, higher is better). Sentiment and feature informativeness are assumed, not measured." simulated>
        {firstScenario ? (
          <div className="grid gap-6 lg:grid-cols-2">
            {[firstScenario, scenarios[scenarios.length - 1]].map(([name, rules]) => (
              <div key={name}>
                <h3 className="mb-3 text-sm font-medium text-zinc-200">{name}</h3>
                <HBars max={0.5} rows={Object.entries(rules).map(([rule, m]) => ({ label: rule, value: m.spearman, accent: rule.startsWith("proposed") }))} digits={3} />
              </div>
            ))}
          </div>
        ) : null}
        <p className="mt-4 text-xs leading-relaxed text-zinc-400">
          With no spillover signal, as in the real data, the ranking is the same with or without the branch. If spillover did carry information, keeping it would help. The real data does not support that, so spillover is shown as context and does not move the score.
        </p>
      </Section>

      {e4 && (
        <Section n="06 · Extensions" title="Two model extensions, tested where the truth is known" lede="E4: what should train the attention. E5: correcting for sponsored posts our rules miss." simulated>
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <h3 className="mb-3 text-sm font-medium text-zinc-200">E4 · error of each creator&apos;s effect (lower is better)</h3>
              <HBars max={0.6} rows={Object.entries(e4).filter(([k]) => k.startsWith("clean") && !k.includes("shrink 10,") && !k.endsWith("shrink 10")).map(([k, v]) => ({ label: k.replace(", shrink 100", ""), value: v.pehe.mean, accent: k.includes("causal") }))} />
            </div>
            <div>
              <h3 className="mb-3 text-sm font-medium text-zinc-200">E5 · recovered effect when some labels are missed (truth {Object.values(d.extensions.e5 ?? {})[0]?.true_ate.toFixed(2)})</h3>
              <HBars max={0.4} rows={Object.entries(d.extensions.e5 ?? {}).flatMap(([rec, v]) => [{ label: `${Math.round(100 * Number(rec))}% detected: uncorrected`, value: v.naive_ate.mean }, { label: `${Math.round(100 * Number(rec))}% detected: corrected`, value: v.simex_ate.mean, accent: true }])} />
            </div>
          </div>
        </Section>
      )}

      <footer className="rounded-lg border border-line px-4 py-3 text-xs leading-relaxed text-zinc-500">
        Sources: {[d.spillover_journey.source, d.benchmark.source, d.power.source, d.passport.source, d.fusion_simulation.source, d.extensions.source].join(" · ")}. Simulated panels use the real creator graph with a planted effect and never feed a score.
      </footer>
    </main>
  );
}
