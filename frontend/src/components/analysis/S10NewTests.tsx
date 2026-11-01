"use client";

import type { AnalysisData } from "@/types/analysis";
import { Card, Note, Stat, Verdict } from "./ui";

const lift = (logDiff: number) => `${logDiff >= 0 ? "+" : ""}${Math.round((Math.exp(logDiff) - 1) * 100)}%`;
const signed = (x: number, digits = 2) => `${x >= 0 ? "+" : ""}${x.toFixed(digits)}`;
const plain = (logDiff: number) => lift(logDiff).replace("+", ""); // for running text: "18%", not "+18%"
/** Stored notes are written as fragments; show them as sentences. */
const sentence = (t: string) => {
  const u = t.charAt(0).toUpperCase() + t.slice(1);
  return /[.!?]$/.test(u) ? u : `${u}.`;
};

export default function S10NewTests({ data }: { data: AnalysisData }) {
  const s = data.s10;
  if (!s) return <p className="text-sm text-zinc-500">No S10 data yet: rerun scripts/export_analysis_dashboard.py.</p>;
  const { pairs, ad_fatigue: fatigue, long_lag: lag, promotion, gail, power } = s;
  const counts = pairs.stronger_platform_counts;
  const detectAt = power.real_structure.min_detectable_80pct;
  const sizes = Object.keys(power.real_structure.share_detected);

  return (
    <div className="flex flex-col gap-4">
      <Verdict tone="info" label="What the newest tests found, in one place">
        Same creator on YouTube and Instagram within 24 hours: both directions of attention predict each other, and creators differ in which platform is stronger. The spillover test between creators found nothing, and the
        power table below shows it could only have seen large effects. Sponsored videos draw somewhat more buying-looking comments. Few sponsored videos carry an explicit disclosure. Ad fatigue was not detected.
      </Verdict>

      <Card title="1. Same creator, YouTube vs Instagram within 24 hours" subtitle={`${pairs.pairs} matched posts from ${pairs.creators_with_pairs} creators; each post compared with that creator's own usual on its platform`}>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Instagram stronger" value={counts["Instagram"] ?? 0} hint="creators" />
          <Stat label="YouTube stronger" value={counts["YouTube"] ?? 0} hint="creators" />
          <Stat label="About equal" value={counts["balanced"] ?? 0} hint="creators" />
          <Stat label="Not enough pairs" value={counts["not enough pairs"] ?? 0} hint="creators" tone="warn" />
        </div>
        <Note>
          Across all pairs Instagram comes out about {plain(pairs.median_difference_adjusted)} ahead. A placebo (pairing Instagram posts with YouTube videos 7 to 60 days away) showed Instagram looks ahead by {plain(pairs.calibration_subtracted)} even with no
          real pairing, so that bias is subtracted. The per-creator answer is the useful one: a brand should look at both platforms, as the platform line on each recommendation does. {pairs.pairs_with_text_overlap} pairs also share wording
          (same topic), where the gap is {plain(pairs.median_difference_with_overlap)} before the correction.
        </Note>
        <h4 className="mt-3 text-xs font-semibold">Does attention on one platform predict the other? (Granger test, placebo-checked)</h4>
        <table className="mt-1 w-full text-left text-xs">
          <thead className="text-zinc-500">
            <tr>
              <th className="pr-3 font-medium">Data used</th>
              <th className="pr-3 font-medium">Direction</th>
              <th className="pr-3 font-medium">F</th>
              <th className="pr-3 font-medium">Placebo F</th>
              <th className="font-medium">p</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(pairs.granger).flatMap(([set, g]) =>
              Object.entries(g.tests).map(([dir, t]) => (
                <tr key={set + dir} className="border-t border-zinc-200 dark:border-zinc-800">
                  <td className="py-1.5 pr-3">{set} ({g.creators} creators)</td>
                  <td className="py-1.5 pr-3">{dir}</td>
                  <td className="py-1.5 pr-3 tabular-nums">{t.F.toFixed(2)}</td>
                  <td className="py-1.5 pr-3 tabular-nums">{t.placebo_F_median.toFixed(2)}</td>
                  <td className="py-1.5 tabular-nums">{t.p_value.toFixed(3)}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
        <Note>Granger is prediction, not cause: both directions beat the placebo, consistent with a shared audience or shared posting rhythm. {sentence(pairs.limits)}</Note>
      </Card>

      <Card title="2. Delayed effects of Instagram posts (long-history lag test)" subtitle={`event study with a built-in control; the method check ${lag.method_check_passed ? "passed" : "FAILED"}`}>
        <table className="w-full text-left text-xs">
          <thead className="text-zinc-500">
            <tr>
              <th className="pr-3 font-medium">Question</th>
              <th className="pr-3 font-medium">Units</th>
              <th className="pr-3 font-medium">Creators</th>
              <th className="pr-3 font-medium">Smallest p</th>
              <th className="font-medium">Found?</th>
            </tr>
          </thead>
          <tbody>
            {lag.results.map((r) => (
              <tr key={r.name} className="border-t border-zinc-200 dark:border-zinc-800">
                <td className="py-1.5 pr-3">{r.name}</td>
                <td className="py-1.5 pr-3 tabular-nums">{r.n_units.toLocaleString()}</td>
                <td className="py-1.5 pr-3 tabular-nums">{r.n_creators}</td>
                <td className="py-1.5 pr-3 tabular-nums">{r.smallest_p_after_event ?? "-"} {r.window_of_smallest_p ? `(${r.window_of_smallest_p})` : ""}</td>
                <td className="py-1.5">{r.detected_after_correction ? "yes" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Note>
          The control (a YouTube upload followed by comments on that channel) is found, so the method works. An Instagram post is followed by more YouTube uploads within 12 hours (creators post on both together), but no extra comments on old
          YouTube videos were found. {sentence(lag.limits)}
        </Note>
      </Card>

      <Card title="3. Ad fatigue" subtitle={`${fatigue.creators} creators, ${fatigue.organic_videos.toLocaleString()} videos not detected as sponsored; sponsored load = sponsored videos in the previous ${fatigue.window_days} days`}>
        <table className="w-full text-left text-xs">
          <thead className="text-zinc-500">
            <tr>
              <th className="pr-3 font-medium">Outcome</th>
              <th className="pr-3 font-medium">Change per extra sponsored video</th>
              <th className="pr-3 font-medium">95% interval</th>
              <th className="font-medium">Placebo p</th>
            </tr>
          </thead>
          <tbody>
            {fatigue.results.map((r) => (
              <tr key={r.outcome} className="border-t border-zinc-200 dark:border-zinc-800">
                <td className="py-1.5 pr-3">{r.outcome.replace(" per extra sponsored video in the previous 30 days", "")}</td>
                <td className="py-1.5 pr-3 tabular-nums">{signed(r.median_slope * 100, 1)}%</td>
                <td className="py-1.5 pr-3 tabular-nums">
                  {signed(r.ci95[0] * 100, 1)}% to {signed(r.ci95[1] * 100, 1)}%
                </td>
                <td className="py-1.5 tabular-nums">{r.p_one_sided_fatigue.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Note>No sign that a creator&apos;s ordinary videos do worse after more sponsored ones (intervals include zero, placebo p above 0.05). {sentence(fatigue.limits)}</Note>
      </Card>

      <Card title="4. How creators promote, and how the audience reacts" subtitle="YouTube; Instagram has too few buying-looking comments (36) to compare">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Sponsored videos with an explicit disclosure" value={`${Math.round(promotion.disclosure.share_disclosed_overall * 100)}%`} hint={`of ${promotion.disclosure.sponsored_videos.toLocaleString()} detected`} tone="warn" />
          <Stat label="Median creator" value={promotion.disclosure.median_creator_share != null ? `${Math.round(promotion.disclosure.median_creator_share * 100)}%` : "-"} hint={`${promotion.disclosure.creators} creators with 5+`} />
          <Stat label="Buying-looking comments, sponsored vs other" value={promotion.response.median_ratio != null ? `${promotion.response.median_ratio.toFixed(1)}x` : "-"} hint={promotion.response.ci95_ratio ? `interval ${promotion.response.ci95_ratio[0]} to ${promotion.response.ci95_ratio[1]}` : ""} tone="good" />
          <Stat label="Placebo" value={promotion.response.placebo_median_ratio != null ? `${promotion.response.placebo_median_ratio.toFixed(2)}x` : "-"} hint={`p = ${promotion.response.p_one_sided_more_on_sponsored ?? "-"}, ${promotion.response.creators} creators`} />
        </div>
        <Note>
          Disclosure is a floor: a promotion found only from a brand name and discount code counts as not disclosed, and a disclosure made where the detector does not look is missed. Per creator, {promotion.response.creators_more} show more buying-looking
          comments on sponsored videos, {promotion.response.creators_same} about the same and {promotion.response.creators_fewer} fewer. This is a proxy for reaction, not sales. {sentence(promotion.limits)}
        </Note>
      </Card>

      <Card title="5. Spillover between creators on the real data (GAIL)" subtitle="effect on creators whose collaborator was sponsored, 30-day windows; GAIL-R estimate with a creator-level bootstrap">
        <table className="w-full text-left text-xs">
          <thead className="text-zinc-500">
            <tr>
              <th className="pr-3 font-medium">Run</th>
              <th className="pr-3 font-medium">Exposed</th>
              <th className="pr-3 font-medium">GAIL-R effect</th>
              <th className="pr-3 font-medium">95% interval</th>
              <th className="font-medium">Model-free check</th>
            </tr>
          </thead>
          <tbody>
            {gail.runs.map((r) => (
              <tr key={r.name} className="border-t border-zinc-200 dark:border-zinc-800">
                <td className="py-1.5 pr-3">{r.name}</td>
                <td className="py-1.5 pr-3 tabular-nums">{r.exposed} ({r.observations} observations)</td>
                <td className="py-1.5 pr-3 tabular-nums">{signed(r.gail_r_effect)}</td>
                <td className="py-1.5 pr-3 tabular-nums">
                  {signed(r.gail_r_ci95[0])} to {signed(r.gail_r_ci95[1])}
                </td>
                <td className="py-1.5 tabular-nums">{signed(r.matched_did)} (SE {r.matched_did_se.toFixed(2)})</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Verdict tone="warn" label="No spillover detected, and the test could only see large effects">
          Both runs have intervals that include zero. Held-out prediction with the older predictor (99 creators): {gail.held_out.verdict}. {gail.held_out_gail_r ? ` Held-out check of GAIL-R itself (split by creator): ${gail.held_out_gail_r.verdict}.` : ""} Acceptance test of the older estimator: passed {gail.acceptance.passed} of {gail.acceptance.of}.
        </Verdict>
        <h4 className="mt-3 text-xs font-semibold">What size of effect could the real data have detected? (planted effect on the real outcomes, {power.reps} runs per cell)</h4>
        <table className="mt-1 w-full text-left text-xs">
          <thead className="text-zinc-500">
            <tr>
              <th className="pr-3 font-medium">Exposed observations</th>
              {power.deltas.map((d) => (
                <th key={d} className="pr-3 font-medium">
                  {d === 0 ? "none (false alarm)" : `${signed(d)} (${lift(d)})`}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sizes.map((n) => (
              <tr key={n} className={`border-t border-zinc-200 dark:border-zinc-800 ${Number(n) === power.real_exposed ? "bg-amber-50 dark:bg-amber-950/20" : ""}`}>
                <td className="py-1.5 pr-3 tabular-nums">{n}</td>
                {power.real_structure.share_detected[n].map((v, i) => (
                  <td key={i} className="py-1.5 pr-3 tabular-nums">{Math.round(v * 100)}%</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <Note>
          Smallest tested effect found in 8 of 10 runs: {sizes.map((n) => `${n} exposed: ${detectAt[n] != null ? `${signed(detectAt[n] as number)} (${lift(detectAt[n] as number)})` : "none"}`).join("; ")}. The highlighted row is today&apos;s sample; larger rows repeat the same
          real observations, so treat them as a rough guide. {sentence(power.limits)}
        </Note>
        <h4 className="mt-3 text-xs font-semibold">Does the method work when an effect exists? (simulated effect on the real graph)</h4>
        <table className="mt-1 w-full text-left text-xs">
          <thead className="text-zinc-500">
            <tr>
              <th className="pr-3 font-medium">Setting</th>
              <th className="pr-3 font-medium">Method</th>
              <th className="pr-3 font-medium">Error in mean effect</th>
              <th className="font-medium">Per-creator error</th>
            </tr>
          </thead>
          <tbody>
            {gail.benchmark.rows.map((r) => (
              <tr key={r.setting + r.method} className="border-t border-zinc-200 dark:border-zinc-800">
                <td className="py-1.5 pr-3">{r.setting}</td>
                <td className="py-1.5 pr-3">{r.method}</td>
                <td className="py-1.5 pr-3 tabular-nums">{r.ate_error.toFixed(3)}</td>
                <td className="py-1.5 tabular-nums">{r.pehe != null ? r.pehe.toFixed(3) : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Note>SIMULATED, not a real result. {sentence(gail.benchmark.caveat)}</Note>
        {gail.benchmark_hard && (
          <>
            <h4 className="mt-3 text-xs font-semibold">Harder version: weaker planted effect, noisier outcomes (SIMULATED on the real graph)</h4>
            <table className="mt-1 w-full text-left text-xs">
              <thead className="text-zinc-500">
                <tr>
                  <th className="pr-3 font-medium">Planted / noise</th>
                  <th className="pr-3 font-medium">Case</th>
                  <th className="pr-3 font-medium">True mean effect</th>
                  <th className="pr-3 font-medium">Naive</th>
                  <th className="pr-3 font-medium">GAIL v1</th>
                  <th className="pr-3 font-medium">GAIL-R</th>
                  <th className="font-medium">GAIL-R + placebo</th>
                </tr>
              </thead>
              <tbody>
                {gail.benchmark_hard.rows.map((r) => (
                  <tr key={`${r.effect}-${r.noise}-${r.scenario}`} className="border-t border-zinc-200 dark:border-zinc-800">
                    <td className="py-1.5 pr-3 tabular-nums">{r.effect} / {r.noise}</td>
                    <td className="py-1.5 pr-3">{r.scenario}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{r.true_mean_effect.toFixed(3)}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{r.naive.toFixed(3)}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{r.gail_v1.toFixed(3)}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{r.gail_r.toFixed(3)}</td>
                    <td className="py-1.5 tabular-nums">{r.gail_r_placebo.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Note>Cells are the error in the estimated mean effect (smaller is better). {gail.benchmark_hard.reading}</Note>
          </>
        )}
      </Card>
    </div>
  );
}
