"use client";

import { useMemo, useState } from "react";
import type { AnalysisData } from "@/types/analysis";
import { Bars, Card, Note, Stat, Verdict, pct } from "./ui";

export function S2Feature({ data }: { data: AnalysisData }) {
  const s2 = data.s2;
  const briefs = Object.keys(s2.briefs);
  const [brief, setBrief] = useState(briefs[0]);
  const top = s2.briefs[brief];
  const aucBriefs = Object.keys(s2.auc);

  return (
    <div className="flex flex-col gap-4">
      <Verdict tone="good" label="Feature score: built and live in the recommendations">
        Every creator gets a score for the brand&apos;s brief: how close their thumbnails and text are to the brief (70%), plus their engagement and reach (30%). It works well for broad briefs and is weaker for narrow ones. Creators with nothing known stay at a neutral 0.5.
      </Verdict>

      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label="Creators with text" value={s2.coverage.with_text} hint={`of ${s2.coverage.creators}`} />
        <Stat label="With thumbnails" value={s2.coverage.with_thumbnails} hint="YouTube only" />
        <Stat label="Nothing known (neutral 0.5)" value={s2.coverage.with_neither} hint={pct(s2.coverage.with_neither, s2.coverage.creators) + " of creators"} tone="warn" />
        <Stat label="With engagement / reach" value={`${s2.coverage.with_engagement} / ${s2.coverage.with_reach}`} />
      </div>

      <Card title="Try a brief" subtitle="Top 10 creators for the brief, and what each score is built from.">
        <div className="flex flex-wrap gap-2">
          {briefs.map((b) => (
            <button key={b} type="button" onClick={() => setBrief(b)} className={`rounded-full border px-3 py-1 text-xs ${b === brief ? "border-violet-500 bg-violet-50 text-violet-900 dark:bg-violet-950/40 dark:text-violet-200" : "border-zinc-300 dark:border-zinc-700"}`}>
              {b}
            </button>
          ))}
        </div>
        <ul className="mt-3 flex flex-col gap-1.5">
          {top.map((t, i) => (
            <li key={t.name} className="grid grid-cols-[1.5rem_minmax(0,11rem)_1fr_auto] items-center gap-2 text-xs">
              <span className="text-zinc-400">{i + 1}</span>
              <span className="truncate font-medium" title={t.name}>
                {t.name}
              </span>
              <span className="h-3 rounded-full bg-zinc-100 dark:bg-zinc-800">
                <span className="block h-3 rounded-full bg-violet-500" style={{ width: `${t.score * 100}%` }} />
              </span>
              <span className="flex items-center gap-1 whitespace-nowrap">
                <span className="w-9 text-right tabular-nums">{t.score.toFixed(2)}</span>
                {t.has_image && <span className="rounded bg-sky-100 px-1 text-[10px] text-sky-800 dark:bg-sky-900/40 dark:text-sky-300">image</span>}
                {t.has_text && <span className="rounded bg-emerald-100 px-1 text-[10px] text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">text</span>}
                {t.engagement !== null && <span className="rounded bg-amber-100 px-1 text-[10px] text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">eng</span>}
                {t.reach !== null && <span className="rounded bg-zinc-100 px-1 text-[10px] text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">reach</span>}
              </span>
            </li>
          ))}
        </ul>
        <Note>The badges show which kinds of evidence exist for that creator. A creator with only a reach badge is ranked on audience size alone. On a narrow brief such as cricket the top 10 includes some non-cricketers: the score is a ranking aid, and it is weakest exactly where the AUC below is low.</Note>
      </Card>

      <Card title="How well does each text method rank the right creators?" subtitle="AUC against category-based relevance: 1.0 is perfect, 0.5 is a coin flip. Measured on two briefs.">
        <div className="grid gap-4 md:grid-cols-2">
          {aucBriefs.map((b) => (
            <div key={b}>
              <h4 className="mb-1 text-xs font-semibold">{b}</h4>
              <Bars
                max={1}
                rows={Object.entries(s2.auc[b]).map(([m, v]) => ({ label: m, value: v, color: m.includes("(used)") ? "bg-violet-500" : "bg-zinc-400" }))}
                format={(v) => v.toFixed(2)}
              />
            </div>
          ))}
        </div>
        <Note>
          The method in use (CLIP text plus BERT mean-pooled) is the best on the broad fitness brief (0.85) and much weaker on the narrow cricket brief (0.57, only 6 matching creators). The first version, BERT&apos;s pooler output, was close to brief-blind and was replaced after this measurement.
        </Note>
      </Card>
    </div>
  );
}

const NAMES = ["Spillover (GAIL)", "Sentiment / risk", "Creator feature"];
const SEG = ["bg-violet-500", "bg-emerald-500", "bg-sky-500"];

export function S3Fusion({ data }: { data: AnalysisData }) {
  const s3 = data.s3;
  const cal = s3.calibration;
  const briefs = Object.keys(s3.briefs);
  const [brief, setBrief] = useState(briefs[0]);
  const [w, setW] = useState<number[]>(s3.baseline_weights.map((x) => Math.round(x * 100)));
  const total = w.reduce((a, b) => a + b, 0) || 1;
  const nw = w.map((x) => x / total);

  const rank = useMemo(() => {
    const b = s3.briefs[brief];
    const score = (weights: number[], i: number) => {
      const raw = 100 * (weights[0] * b.spillover[i] + weights[1] * b.sentiment[i] + weights[2] * b.feature[i]) + (b.sentiment[i] < 0.3 ? -10 : 0);
      return Math.max(0, Math.min(100, raw));
    };
    const order = (weights: number[]) =>
      s3.creators
        .map((_, i) => i)
        .sort((a, c) => score(weights, c) - score(weights, a))
        .slice(0, 10);
    const base = order(s3.baseline_weights);
    const now = order(nw);
    return { base, now, score: (i: number) => score(nw, i), baseScore: (i: number) => score(s3.baseline_weights, i), shared: now.filter((i) => base.includes(i)).length };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [brief, w, s3]);

  const sens = cal.per_brief;
  const association = cal.association_with_lift;

  return (
    <div className="flex flex-col gap-4">
      <Verdict tone="warn" label="Fusion layer: fixed and calibrated as far as the data allows. The weights are documented priors, not fitted.">
        A scale bug was found and fixed: spillover (an engagement lift from -1 to +23) was multiplied straight into a 0-100 score, so 20 creators sat at exactly 100 and every interval spanned the whole range. Spillover is now a percentile, and the interval covers all three branches. There is no
        outcome data to fit the weights to, so they stay 0.4 / 0.3 / 0.3.
      </Verdict>

      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label="Labelled outcomes" value={cal.labelled_outcomes} hint="creators with an observed lift" tone="warn" />
        <Stat label="Intervals spanning 0-100" value={`${cal.ci_spans_whole_range} / ${cal.creators}`} hint="was 187 of 187 before the fix" tone="good" />
        <Stat label="Interval width (points)" value={`${cal.ci_width_points.min.toFixed(0)}-${cal.ci_width_points.max.toFixed(0)}`} hint={`median ${cal.ci_width_points.median.toFixed(0)}`} />
        <Stat label="Sentiment vs observed lift" value={association["sentiment"] ? association["sentiment"].spearman.toFixed(2) : "n/a"} hint={association["sentiment"] ? `p = ${association["sentiment"].perm_p.toFixed(2)}: no link` : ""} tone="warn" />
      </div>

      <Card title="What if the weights were different?" subtitle="Move the sliders and the top 10 re-ranks live. This is exactly how much the choice of weights matters.">
        <div className="flex flex-wrap gap-2">
          {briefs.map((b) => (
            <button key={b} type="button" onClick={() => setBrief(b)} className={`rounded-full border px-3 py-1 text-xs ${b === brief ? "border-violet-500 bg-violet-50 text-violet-900 dark:bg-violet-950/40 dark:text-violet-200" : "border-zinc-300 dark:border-zinc-700"}`}>
              {b}
            </button>
          ))}
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {NAMES.map((n, i) => (
            <label key={n} className="flex flex-col gap-1 text-xs">
              <span className="flex justify-between">
                <span className="flex items-center gap-1.5">
                  <span className={`inline-block h-2.5 w-2.5 rounded-full ${SEG[i]}`} />
                  {n}
                </span>
                <span className="font-mono">{(nw[i] * 100).toFixed(0)}%</span>
              </span>
              <input type="range" min={0} max={100} value={w[i]} onChange={(e) => setW(w.map((x, j) => (j === i ? Number(e.target.value) : x)))} className="w-full" aria-label={`${n} weight`} />
            </label>
          ))}
        </div>
        <div className="mt-2 flex items-center gap-3 text-xs">
          <button type="button" onClick={() => setW(s3.baseline_weights.map((x) => Math.round(x * 100)))} className="rounded-md border border-zinc-300 px-2 py-1 dark:border-zinc-700">
            Reset to 40 / 30 / 30
          </button>
          <span className="text-zinc-500">
            Top-10 shared with the default weights: <strong className={rank.shared >= 8 ? "text-emerald-600" : rank.shared >= 5 ? "text-amber-600" : "text-rose-600"}>{rank.shared} / 10</strong>
          </span>
        </div>
        <ol className="mt-3 flex flex-col gap-1.5">
          {rank.now.map((i, pos) => {
            const b = s3.briefs[brief];
            const moved = rank.base.indexOf(i);
            return (
              <li key={i} className="grid grid-cols-[1.5rem_minmax(0,11rem)_1fr_auto] items-center gap-2 text-xs">
                <span className="text-zinc-400">{pos + 1}</span>
                <span className="truncate font-medium" title={s3.creators[i].name}>
                  {s3.creators[i].name}
                </span>
                <span className="flex h-3 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800" title="contribution of each branch">
                  {[b.spillover[i] * nw[0], b.sentiment[i] * nw[1], b.feature[i] * nw[2]].map((v, k) => (
                    <span key={k} className={`block h-3 ${SEG[k]}`} style={{ width: `${v * 100}%` }} />
                  ))}
                </span>
                <span className="flex items-center gap-2 whitespace-nowrap">
                  <span className="w-9 text-right tabular-nums">{rank.score(i).toFixed(0)}</span>
                  <span className={`w-12 text-[10px] ${moved === -1 ? "text-emerald-600" : moved === pos ? "text-zinc-400" : moved > pos ? "text-emerald-600" : "text-rose-600"}`}>
                    {moved === -1 ? "new" : moved === pos ? "same" : moved > pos ? `▲ ${moved - pos}` : `▼ ${pos - moved}`}
                  </span>
                </span>
              </li>
            );
          })}
        </ol>
        <Note>Bars show how much each branch contributes to the score. Arrows compare with the default weights.</Note>
      </Card>

      <Card title="How stable is the ranking when weights change?" subtitle="Measured on six briefs over a grid of weight combinations.">
        <Bars
          max={10}
          labelWidth="17rem"
          rows={briefs.flatMap((b) => [
            { label: `${b}: each weight moved up to 0.1`, value: sens[b].near.top10_overlap_median * 10, color: "bg-emerald-500" },
            { label: `${b}: any weights at all`, value: sens[b].all.top10_overlap_median * 10, color: "bg-amber-500" },
          ])}
          format={(v) => `${v.toFixed(1)}/10`}
        />
        <Note>
          Moving each weight by up to 0.1 keeps a median 9 of the top 10. Only extreme weightings (nearly all weight on one branch) change the ranking a lot. That makes 0.4 / 0.3 / 0.3 a reasonable prior, but it is not fitted: only {cal.labelled_outcomes} creators have an observed outcome, they are what the model was trained on, and
          sentiment shows no link to that outcome.
        </Note>
      </Card>
    </div>
  );
}
