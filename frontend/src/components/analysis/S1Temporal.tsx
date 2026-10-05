"use client";

import { useMemo, useState } from "react";
import type { AnalysisData, Curve } from "@/types/analysis";
import { Bars, Card, Legend, LineChart, Note, Stat, Verdict } from "./ui";

function pearson(pairs: [number, number][]): number | null {
  if (pairs.length < 3) return null;
  const mx = pairs.reduce((a, p) => a + p[0], 0) / pairs.length;
  const my = pairs.reduce((a, p) => a + p[1], 0) / pairs.length;
  let sxy = 0;
  let sxx = 0;
  let syy = 0;
  for (const [x, y] of pairs) {
    sxy += (x - mx) * (y - my);
    sxx += (x - mx) ** 2;
    syy += (y - my) ** 2;
  }
  return sxx && syy ? sxy / Math.sqrt(sxx * syy) : null;
}

/** YouTube performance on day d paired with Instagram performance on day d + lag. */
function matchedPairs(c: Curve, lag: number): [number, number][] {
  const ig = new Map(c.instagram);
  return c.youtube.filter(([d]) => ig.has(d + lag)).map(([d, z]) => [z, ig.get(d + lag) as number]);
}

// short ranges read best as "Jul 26" (month and day), long ones as "Jul 2026"
const dayShort = (d: number) => new Date(d * 86400000).toLocaleDateString(undefined, { month: "short", day: "numeric" });
const dayLong = (d: number) => new Date(d * 86400000).toLocaleDateString(undefined, { month: "short", year: "numeric" });
const sev: Record<string, string> = {
  high: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  low: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
};

function LagExplorer({ data }: { data: AnalysisData }) {
  const curves = data.s1.curves;
  const lagData = data.s1.lag_same_creator;
  // open on the creator with the most matched days at lag 0 and +1, so the first view shows something
  const [idx, setIdx] = useState(() => {
    const score = (c: Curve) => matchedPairs(c, 0).length + matchedPairs(c, 1).length;
    let best = 0;
    curves.forEach((c, i) => {
      if (score(c) > score(curves[best])) best = i;
    });
    return best;
  });
  const [lag, setLag] = useState(1);
  const c = curves[idx];
  const pairs = useMemo(() => matchedPairs(c, lag), [c, lag]);
  const r = pearson(pairs);
  const shifted = useMemo(() => c.instagram.map(([d, z]) => [d - lag, z] as [number, number]), [c, lag]);
  const pooledAt = lagData.lags.indexOf(lag);
  const allDays = [...c.youtube, ...shifted].map((p) => p[0]);
  const longRange = Math.max(...allDays) - Math.min(...allDays) > 300;

  return (
    <Card
      title="Lag explorer: one creator, both platforms"
      subtitle="Each curve is how well the creator's posts did compared with their own normal (comments, adjusted for post age). Slide Instagram earlier or later and watch the match."
    >
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          <span className="text-xs text-zinc-500">Creator</span>
          <select value={idx} onChange={(e) => setIdx(Number(e.target.value))} className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900">
            {curves.map((cv, i) => (
              <option key={cv.name} value={i}>
                {cv.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-w-[14rem] flex-1 items-center gap-2">
          <span className="whitespace-nowrap text-xs text-zinc-500">Instagram trails YouTube by</span>
          <input type="range" min={-3} max={3} step={1} value={lag} onChange={(e) => setLag(Number(e.target.value))} className="w-full accent-amber-500" aria-label="lag in days" />
          <span className="w-20 whitespace-nowrap text-right font-mono text-sm">{lag > 0 ? "+" : ""}{lag} day{Math.abs(lag) === 1 ? "" : "s"}</span>
        </label>
      </div>

      <div className="mt-3">
        <LineChart
          height={200}
          series={[
            { name: "YouTube", points: c.youtube, className: "stroke-sky-500", dotClass: "fill-sky-500" },
            { name: "Instagram (shifted)", points: shifted, className: "stroke-amber-500", dotClass: "fill-amber-500" },
          ]}
          xTick={longRange ? dayLong : dayShort}
        />
        <Legend items={[{ label: "YouTube performance", className: "bg-sky-500" }, { label: `Instagram performance, moved ${lag === 0 ? "0" : lag > 0 ? `${lag} day${lag > 1 ? "s" : ""} earlier` : `${-lag} day${lag < -1 ? "s" : ""} later`}`, className: "bg-amber-500" }]} />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <Stat label="Matched days (this creator)" value={pairs.length} hint="days with both a YouTube and a shifted Instagram value" />
        <Stat label="Match (correlation)" value={r === null ? "too few" : r.toFixed(2)} hint="-1 opposite, 0 none, +1 identical" tone={r !== null && Math.abs(r) > 0.5 && pairs.length >= 8 ? "warn" : undefined} />
        <Stat label="All 13 creators pooled, same lag" value={pooledAt >= 0 && lagData.corr[pooledAt] !== null ? (lagData.corr[pooledAt] as number).toFixed(2) : "n/a"} hint={pooledAt >= 0 ? `${lagData.pairs[pooledAt]} matched days, placebo p = ${lagData.p[pooledAt].toFixed(2)}` : ""} />
      </div>
      <Note>
        A single creator has only a handful of matched days, so one creator can show a strong match by chance: try a few. The pooled number below is the one that counts, and its p-value says whether it beats a shuffled
        placebo.
      </Note>

      <h4 className="mt-4 text-xs font-semibold uppercase tracking-wide text-zinc-500">Pooled over all creators</h4>
      <div className="mt-2 grid grid-cols-7 gap-1">
        {lagData.lags.map((k, i) => {
          const v = lagData.corr[i] ?? 0;
          const active = k === lag;
          return (
            <button key={k} type="button" onClick={() => setLag(k)} className={`flex flex-col items-center rounded-md border px-1 py-2 text-xs ${active ? "border-amber-500 bg-amber-50 dark:bg-amber-950/30" : "border-zinc-200 dark:border-zinc-800"}`}>
              <span className="text-zinc-500">{k > 0 ? `+${k}d` : `${k}d`}</span>
              <span className="relative my-1 h-16 w-4 rounded bg-zinc-100 dark:bg-zinc-800">
                <span className={`absolute left-0 w-4 rounded ${v >= 0 ? "bottom-1/2 bg-emerald-500" : "top-1/2 bg-rose-400"}`} style={{ height: `${Math.min(50, Math.abs(v) * 50 * 1.5)}%` }} />
                <span className="absolute left-0 top-1/2 h-px w-4 bg-zinc-400" />
              </span>
              <span className="font-mono">{v.toFixed(2)}</span>
              <span className="text-[10px] text-zinc-400">p {lagData.p[i].toFixed(2)}</span>
              <span className="text-[10px] text-zinc-400">n {lagData.pairs[i]}</span>
            </button>
          );
        })}
      </div>
      <Note>
        The test could only detect a correlation of about 0.4 or more with this few matched days, so a small number here means &quot;cannot tell&quot;, not &quot;no lag&quot;. Click a bar to move the slider.
      </Note>
    </Card>
  );
}

export default function S1Temporal({ data }: { data: AnalysisData }) {
  const s = data.s1;
  const ctrl = data.s1.lag_event["positive_control"];
  const ev = data.s1.lag_event;
  const rows = [
    { key: "ALL CROSS-PLATFORM/day", label: "Cross-platform, date-level events", labels: ["event day", "next day", "day after"], off: 3 },
    { key: "ALL CROSS-PLATFORM/hour", label: "Cross-platform, timed events", labels: ["0-12h", "12-24h", "24-36h", "36-48h"], off: 4 },
    { key: "ALL SAME-PLATFORM/day", label: "Same platform, date-level events", labels: ["event day", "next day", "day after"], off: 3 },
    { key: "ALL SAME-PLATFORM/hour", label: "Same platform, timed events", labels: ["0-12h", "12-24h", "24-36h", "36-48h"], off: 4 },
  ];
  const sentMax = Math.max(...s.sentiment.histogram.map((h) => h.n));

  return (
    <div className="flex flex-col gap-4">
      <Verdict tone="warn" label="Cross-platform 24-hour lag: not proven (the data is too thin to tell)">
        Three different tests were run. The method itself works (it finds a real effect when one exists), but only 13 creators have enough measured posts on both platforms, so none of the tests can confirm or rule out a lag. The audience-mood score and the
        risk alerts, on the other hand, are built and live.
      </Verdict>

      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label="Creators with a mood score" value={`${s.sentiment.scored} / ${s.sentiment.total}`} hint="the rest stay neutral at 0.5" />
        <Stat label="Live risk alerts" value={s.alerts.length} hint="written to the Monitoring page" tone="good" />
        <Stat label="Creators on both platforms" value={s.curves.length} hint="enough measured posts for the lag test" tone="warn" />
        <Stat label="Lag verdict" value="Not proven" hint="underpowered, not disproven" tone="warn" />
      </div>

      <LagExplorer data={data} />

      <Card title="Does the tool work? A check where the answer must be yes" subtitle="A creator uploads a YouTube video: their own channel should get a burst of comments. If the method cannot see this, it is broken.">
        {ctrl && ctrl.excess && ctrl.p ? (
          <>
            <Bars
              rows={["0-12h", "12-24h", "24-36h", "36-48h"].map((l, i) => ({
                label: `${l} after upload`,
                value: Math.max(0, (ctrl.excess as number[])[4 + i]),
                note: `p ${(ctrl.p as number[])[4 + i] < 0.001 ? "<0.001" : (ctrl.p as number[])[4 + i].toFixed(3)}`,
                color: (ctrl.p as number[])[4 + i] < 0.05 ? "bg-emerald-500" : "bg-zinc-400",
              }))}
              format={(v) => `+${v.toFixed(1)}`}
            />
            <Note>
              Extra comments compared with the channel&apos;s normal rate, over {ctrl.usable} uploads. The effect is large and clearly real (p about 0.001), so the method can detect a real effect. The same method found nothing for collaborators or across platforms: that is
              a data-size limit, not a broken test.
            </Note>
          </>
        ) : (
          <Note>Control result not available.</Note>
        )}
      </Card>

      <Card title="After a creator's sponsored post, do their collaborators show extra activity?" subtitle="Extra activity versus each collaborator's own normal rate, with a shuffled-time placebo for the p-value. Date-level events can only be checked by day.">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-zinc-500">
                <th className="py-1 pr-2 font-medium">Group</th>
                <th className="py-1 pr-2 font-medium">Usable pairs</th>
                <th className="py-1 font-medium">Extra activity per window (placebo p)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const e = ev[r.key];
                if (!e || !e.excess || !e.p) return null;
                return (
                  <tr key={r.key} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="py-1.5 pr-2">{r.label}</td>
                    <td className="py-1.5 pr-2 tabular-nums">{e.usable}</td>
                    <td className="py-1.5">
                      <div className="flex flex-wrap gap-2">
                        {r.labels.map((l, i) => {
                          const p = (e.p as number[])[r.off + i];
                          return (
                            <span key={l} className={`rounded-md px-1.5 py-0.5 tabular-nums ${p < 0.05 ? "bg-amber-100 dark:bg-amber-900/30" : "bg-zinc-100 dark:bg-zinc-800"}`}>
                              {l}: {(e.excess as number[])[r.off + i] >= 0 ? "+" : ""}
                              {(e.excess as number[])[r.off + i].toFixed(2)} (p {p.toFixed(2)})
                            </span>
                          );
                        })}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <Note>
          Reading it: no cross-platform window beats the placebo (p between 0.27 and 0.98). The two highlighted same-platform cells have only 16 pairs and many windows were tested, so they are not evidence of anything. Only 9 of 62 sponsored events carry a time of day.
        </Note>
      </Card>

      <Card title="The first test: does posting on one platform lead to posting on another?" subtitle="Counts of posts per time bin for the same creator, pooled across creators.">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-zinc-500">
                <th className="py-1 pr-2 font-medium">From → to</th>
                <th className="py-1 pr-2 font-medium">Creators usable</th>
                <th className="py-1 pr-2 font-medium">Best lag</th>
                <th className="py-1 pr-2 font-medium">Match</th>
                <th className="py-1 pr-2 font-medium">Lag p</th>
                <th className="py-1 font-medium">Granger p</th>
              </tr>
            </thead>
            <tbody>
              {s.lag_posting.map((r) => (
                <tr key={`${r.cause}-${r.effect}`} className="border-t border-zinc-100 dark:border-zinc-800">
                  <td className="py-1.5 pr-2">
                    {r.cause.replace("_", " ")} → {r.effect.replace("_", " ")}
                    {r.effect === "yt_comments" && <span className="ml-1 rounded bg-emerald-100 px-1 text-[10px] text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">control</span>}
                  </td>
                  <td className="py-1.5 pr-2 tabular-nums">{r.creators_usable}</td>
                  <td className="py-1.5 pr-2 tabular-nums">{r.best_lag_hours} h</td>
                  <td className="py-1.5 pr-2 tabular-nums">{r.best_corr.toFixed(2)}</td>
                  <td className="py-1.5 pr-2 tabular-nums">{r.lag_p_value.toFixed(3)}</td>
                  <td className="py-1.5 tabular-nums">{r.granger_combined_p.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Note>
          The best lag is 0 hours almost everywhere: platforms move together at the same time, which is what you expect when both react to the same real-world event. &quot;Granger&quot; asks whether the past of one series helps predict the other. It is a prediction
          test, not proof of cause.
        </Note>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Audience mood across creators" subtitle="Safety score from comment sentiment: higher means a happier audience, so a safer pick.">
          <ul className="flex flex-col gap-1">
            {s.sentiment.histogram.map((h) => (
              <li key={h.lo} className="grid grid-cols-[4.5rem_1fr_2rem] items-center gap-2 text-xs">
                <span className="text-zinc-500">
                  {h.lo.toFixed(2)}-{h.hi.toFixed(2)}
                </span>
                <span className="h-3 rounded-full bg-zinc-100 dark:bg-zinc-800">
                  <span className={`block h-3 rounded-full ${h.hi <= 0.5 ? "bg-rose-400" : "bg-emerald-500"}`} style={{ width: `${(100 * h.n) / sentMax}%` }} />
                </span>
                <span className="text-right tabular-nums">{h.n}</span>
              </li>
            ))}
          </ul>
          <Note>
            {s.sentiment.scored} of {s.sentiment.total} creators have comments; the rest stay at a neutral 0.5. A creator with few comments is pulled towards 0.5 so three comments cannot give an extreme score. There is no ground truth that this mood means real brand risk.
          </Note>
        </Card>

        <Card title="Live risk alerts" subtitle="Risk spreads only along links with real evidence (a collaboration tag, or a post naming both creators in full).">
          <ul className="flex max-h-72 flex-col gap-1 overflow-y-auto pr-1">
            {s.alerts.map((a, i) => (
              <li key={i} className="flex items-center gap-2 text-xs">
                <span className={`w-14 rounded-full px-2 py-0.5 text-center text-[10px] font-medium ${sev[a.severity] ?? sev.low}`}>{a.severity}</span>
                <span className="font-medium">{a.creator}</span>
                <span className="text-zinc-500">← {a.source}</span>
              </li>
            ))}
          </ul>
          <Note>Severity is relative within the group and the risk values are small (0.01 to 0.02). The first version of these alerts used weak Reddit links and was discarded before it was written.</Note>
        </Card>
      </div>

      <Card title="What would settle the lag question">
        <ul className="list-disc space-y-1 pl-5 text-sm text-zinc-700 dark:text-zinc-300">
          <li>Follower and engagement snapshots every few hours for several days after each post, for creators on both platforms (the database keeps only one snapshot per account today).</li>
          <li>Instagram like counts (only 28% of posts have them) and the time of day of each post (most carry a date only).</li>
          <li>More creators on both platforms: only 13 qualify now.</li>
        </ul>
      </Card>
    </div>
  );
}
