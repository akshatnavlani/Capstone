"use client";

import type { AnalysisData, S9Estimate } from "@/types/analysis";
import { Card, Note, Stat, Verdict } from "./ui";

const fmt = (v: number) => {
  const r = Math.abs(v) < 0.005 ? 0 : v; // never show "-0.00"
  return `${r >= 0 ? "+" : ""}${r.toFixed(2)}`;
};

function EstimateRow({ label, e, remark }: { label: string; e: S9Estimate; remark?: string }) {
  const [lo, hi] = e.difference_in_means_ci;
  return (
    <tr className="border-t border-zinc-200 dark:border-zinc-800">
      <td className="py-1.5 pr-3">{label}</td>
      <td className="py-1.5 pr-3 tabular-nums">
        {e.n_exposed} / {e.n_unexposed}
      </td>
      <td className="py-1.5 pr-3 tabular-nums">{fmt(e.difference_in_means)}</td>
      <td className="py-1.5 pr-3 tabular-nums">
        {fmt(lo)} to {fmt(hi)}
      </td>
      <td className="py-1.5">
        {e.difference_in_means_excludes_zero ? "effect found" : "no effect found"}
        {remark ? <span className="text-zinc-400"> · {remark}</span> : null}
      </td>
    </tr>
  );
}

export default function S9Results({ data }: { data: AnalysisData }) {
  const s9 = data.s9;
  if (!s9) return <Note>This tab needs scripts/export_analysis_dashboard.py to be re-run (the live-results block is missing).</Note>;
  const inv = s9.inventory;
  const sp = s9.spillover_restricted_150.shared_brand;
  const coll = s9.spillover_restricted_150.collaboration;
  const real = sp.real;
  const placebo = s9.placebo?.scopes?.in_the_150?.all;
  const lag = s9.lag;
  const pure = lag.results.find((r) => r.name.startsWith("ig_to_yt_pure"));
  const day = new Date(s9.as_of).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  const simLag = s9.sim_lag_power;
  const scored = (s9.spillover_basis_counts.trained ?? 0) + (s9.spillover_basis_counts.inferred ?? 0);

  return (
    <div className="flex flex-col gap-4">
      <Verdict tone="info" label={`Live results as of ${day}`}>
        Everything on this tab comes from real data collected so far, except the rows marked SIMULATED. Real results and simulated checks are never mixed.
      </Verdict>

      <Card title="Real result and simulated check, side by side" subtitle="the real data decides the result; the simulation only shows whether the method could have found something">
        <table className="w-full text-left text-xs">
          <thead className="text-zinc-500">
            <tr>
              <th className="py-1 pr-3 font-medium">Part</th>
              <th className="py-1 pr-3 font-medium">REAL data</th>
              <th className="py-1 pr-3 font-medium">SIMULATED on top of it</th>
              <th className="py-1 font-medium">Reading</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-t border-zinc-100 align-top">
              <td className="py-1.5 pr-3">Spillover</td>
              <td className="py-1.5 pr-3">
                {placebo?.per_neighbour
                  ? `${placebo.per_neighbour.median_of_means.toFixed(2)} (${placebo.per_neighbour.ci[0].toFixed(2)} to ${placebo.per_neighbour.ci[1].toFixed(2)}) over ${placebo.per_neighbour.n} neighbours`
                  : "see below"}
              </td>
              <td className="py-1.5 pr-3">
                {s9.semisynthetic
                  ? `a planted 0.25 is found in ${Math.round(s9.semisynthetic.table["0.25"].placebo.detects_effect_share * 100)}% of studies, ${Math.round(s9.semisynthetic.table["0.0"].placebo.detects_effect_share * 100)}% false alarms`
                  : "not run"}
              </td>
              <td className="py-1.5">No broad spillover; a localised one is not ruled out.</td>
            </tr>
            <tr className="border-t border-zinc-100 align-top">
              <td className="py-1.5 pr-3">Lag</td>
              <td className="py-1.5 pr-3">{pure ? `smallest p ${pure.smallest_p_after_event} in the ${pure.window_of_smallest_p} window, ${pure.detected_after_correction ? "confirmed" : "not confirmed"}` : "see below"}</td>
              <td className="py-1.5 pr-3">{simLag ? "finds +10% (all posts) to +25% (strict test) extra attention, no false alarms" : "not run"}</td>
              <td className="py-1.5">No large delayed effect in {lag.days_of_readings} days of readings.</td>
            </tr>
            <tr className="border-t border-zinc-100 align-top">
              <td className="py-1.5 pr-3">GAIL</td>
              <td className="py-1.5 pr-3">{`real spillover score for ${scored} of ${s9.graph_links.of} creators today`}</td>
              <td className="py-1.5 pr-3">acceptance check on simulated worlds: old model failed 0 of 4; to be re-run after retraining</td>
              <td className="py-1.5">Pending the retrain; about {s9.graph_links.with_shared_brand_and_mentions ?? s9.graph_links.with_shared_brand} of {s9.graph_links.of} creators can be linked.</td>
            </tr>
          </tbody>
        </table>
        <Note>Training uses real data only. Simulated rows never enter the database, the training set or a real result.</Note>
      </Card>

      <Card title="What the data is, today" subtitle="The 150 verified creators">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="YouTube videos" value={inv.youtube_videos.toLocaleString()} hint={`${inv.youtube_comments.toLocaleString()} comments`} />
          <Stat label="Growth readings" value={inv.growth_readings.toLocaleString()} hint={`over ${inv.days_of_readings} days`} />
          <Stat label="Instagram" value={`${inv.instagram_creators} creators`} hint={`${inv.instagram_posts.toLocaleString()} posts`} />
          <Stat
            label="Sponsorship events"
            value={inv.sponsorship_events}
            hint={`${inv.strong_evidence_events} with strong evidence · ${inv.sponsoring_creators} creators`}
            tone="warn"
          />
        </div>
        <Note>
          Most sponsorship events are a brand name or a promo code in the description; only the strong-evidence ones (paid-partnership label, disclosure tag, spoken, creator comment) are firm.
        </Note>
      </Card>

      {s9.label_quality ? (
        <Card title="How reliable are the sponsorship labels?" subtitle={`${s9.label_quality.pooled_precision_checked_flagged_events.checked} flagged events checked one by one by a person`}>
          <Verdict tone="warn" label="Strong tiers look reliable; the weak tiers are not settled">
            Of {s9.label_quality.pooled_precision_checked_flagged_events.checked} flagged events checked one by one, {s9.label_quality.pooled_precision_checked_flagged_events.real_ads} were real ads (95% interval{" "}
            {Math.round(s9.label_quality.pooled_precision_checked_flagged_events.wilson95[0] * 100)}% to {Math.round(s9.label_quality.pooled_precision_checked_flagged_events.wilson95[1] * 100)}%), but that is only about 4% of{" "}
            {s9.inventory.sponsorship_events.toLocaleString()} events. {s9.label_quality.claude_text_only_readings ? (
              <>
                A separate text-only reading of {s9.label_quality.claude_text_only_readings.decided_flagged_events} weak-tier events (by Claude, not a person) found only{" "}
                {Math.round(s9.label_quality.claude_text_only_readings.share * 100)}% look sponsored from the description alone. Text cannot hear a spoken sponsor, so the true figure for the weak tiers lies between about
                60% and 95% until more are checked by a person.{" "}
              </>
            ) : null}
            A text model trained on the checks could not tell real ads from false ones better than chance, so each event is scored by its tier&apos;s checked precision.
          </Verdict>
          <table className="mt-3 w-full text-left text-xs">
            <thead className="text-zinc-500">
              <tr>
                <th className="py-1 pr-3 font-medium">Evidence tier</th>
                <th className="py-1 pr-3 font-medium">Checked</th>
                <th className="py-1 font-medium">Real ads</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(s9.label_quality.human_checked_precision_by_tier).map(([tier, v]) => (
                <tr key={tier} className="border-t border-zinc-100">
                  <td className="py-1.5 pr-3">{tier.replace(/_/g, " ")}</td>
                  <td className="py-1.5 pr-3 tabular-nums">{v.checked}</td>
                  <td className="py-1.5 tabular-nums">{v.real_ads} ({Math.round(v.precision * 100)}%)</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : null}

      {s9.semisynthetic ? (
        <Card title="SIMULATED check: would our test have found a spillover?" subtitle={`built on the real network · ${s9.semisynthetic.real_neighbours} neighbours · ${s9.semisynthetic.real_rows.toLocaleString()} real event rows`}>
          <Verdict tone="info" label="SIMULATED, not a real result">
            A known spillover effect (and a fake pre-existing growth trend) is planted on top of the real events and the real noise, then two analysts try to find it. The naive analysis (is lift
            after the post above zero?) is off by about {s9.semisynthetic.table["0.0"].naive.error_vs_truth.toFixed(2)} and claims an effect even when there is none. The placebo test used on the real
            data stays within {Math.abs(s9.semisynthetic.table["0.0"].placebo.error_vs_truth).toFixed(2)} of the truth, raises {Math.round(s9.semisynthetic.table["0.0"].placebo.detects_effect_share * 100)}% false
            alarms, and finds an effect of 0.25 in {Math.round(s9.semisynthetic.table["0.25"].placebo.detects_effect_share * 100)}% of simulated studies. So the real result of about zero means no broad
            spillover of that size, not that the test was blind.
          </Verdict>
          <table className="mt-3 w-full text-left text-xs">
            <thead className="text-zinc-500">
              <tr>
                <th className="py-1 pr-3 font-medium">Planted effect</th>
                <th className="py-1 pr-3 font-medium">Naive: estimate · says &quot;effect&quot;</th>
                <th className="py-1 font-medium">Placebo test: estimate · says &quot;effect&quot;</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(s9.semisynthetic.table).map(([delta, v]) => (
                <tr key={delta} className="border-t border-zinc-100">
                  <td className="py-1.5 pr-3 tabular-nums">{Number(delta).toFixed(2)}</td>
                  <td className="py-1.5 pr-3 tabular-nums">
                    {v.naive.mean_estimate.toFixed(2)} · {Math.round(v.naive.detects_effect_share * 100)}%
                  </td>
                  <td className="py-1.5 tabular-nums">
                    {v.placebo.mean_estimate.toFixed(2)} · {Math.round(v.placebo.detects_effect_share * 100)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Note>
            Limit: if the effect reached only about 20% of neighbours, the placebo test would miss it (it finds an average effect of 0.20 in just{" "}
            {Math.round(s9.semisynthetic.table_effect_reaches_20_percent_of_neighbours["1.0"].placebo.detects_effect_share * 100)}% of studies). Finding which neighbours matter is what the attention in GAIL is
            for. Assumptions: trend per neighbour about 0.15 ± 0.15, the same effect for every affected row. Neural GAIL is not in this table (it needs a retraining run).
          </Note>
        </Card>
      ) : null}

      {simLag ? (
        <Card title="SIMULATED check: could the lag test have found a delayed effect?" subtitle="extra attention planted 12 to 36 hours after real Instagram posts, on the real growth readings">
          <Verdict tone="info" label="SIMULATED, not a real result">
            The planted extra views are a share of the creator&apos;s own normal attention. With the current readings the all-posts test finds an effect of about 10% of a normal day in most simulated
            studies and never raises a false alarm; the stricter test (posts with no YouTube upload nearby, fewer units) needs about 15–25%. So the real finding of no confirmed lag rules out a
            large delayed effect, but a small one could still hide in 15 days of data.
          </Verdict>
          <table className="mt-3 w-full text-left text-xs">
            <thead className="text-zinc-500">
              <tr>
                <th className="py-1 pr-3 font-medium">Extra attention</th>
                {Object.entries(simLag.sets).map(([name, v]) => (
                  <th key={name} className="py-1 pr-3 font-medium">
                    {name.split(" ")[0]} · {v.units} posts
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.keys(Object.values(simLag.sets)[0].by_size).map((size) => (
                <tr key={size} className="border-t border-zinc-100">
                  <td className="py-1.5 pr-3 tabular-nums">+{Math.round(Number(size) * 100)}%</td>
                  {Object.entries(simLag.sets).map(([name, v]) => (
                    <td key={name} className="py-1.5 pr-3 tabular-nums">
                      found in {Math.round(v.by_size[size].detected_share * 100)}%
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : null}

      <Card title="Lag: does an Instagram post lift YouTube attention?" subtitle={`${lag.days_of_readings} days of readings · ${lag.method_check}`}>
        <Verdict
          tone={pure?.detected_after_correction ? "warn" : "info"}
          label={pure?.detected_after_correction ? "An emerging delayed signal, not yet confirmed" : "No lag confirmed yet"}
        >
          {pure
            ? pure.detected_after_correction
              ? `Instagram posts with no YouTube upload nearby are followed by a rise in views on older videos, strongest 1.5 to 2 days later (${pure.n_units} posts, ${pure.n_creators} creators, p = ${pure.smallest_p_after_event} in the ${pure.window_of_smallest_p} window). The sample is small and the best window moved between runs, so it is re-tested as readings accumulate.`
              : `A small rise in views 1.5 to 2 days after an Instagram post is hinted at (${pure.n_units} posts, ${pure.n_creators} creators, p = ${pure.smallest_p_after_event} in the ${pure.window_of_smallest_p} window), but it does not survive the correction for looking at four windows. An earlier run that looked clearer (p = 0.002 on 51 posts) faded as more posts arrived, so it is treated as unconfirmed until more days of readings are in.`
            : "The method is checked against a known effect before any result is read."}
        </Verdict>
        <table className="mt-3 w-full text-left text-xs">
          <thead className="text-zinc-500">
            <tr>
              <th className="pr-3 font-medium">Test</th>
              <th className="pr-3 font-medium">Units / creators</th>
              <th className="pr-3 font-medium">Best p</th>
              <th className="font-medium">Result</th>
            </tr>
          </thead>
          <tbody>
            {lag.results.map((r) => (
              <tr key={r.name} className="border-t border-zinc-200 dark:border-zinc-800">
                <td className="py-1.5 pr-3">{r.name.split(":")[0]}</td>
                <td className="py-1.5 pr-3 tabular-nums">
                  {r.n_units} / {r.n_creators}
                </td>
                <td className="py-1.5 pr-3 tabular-nums">
                  {r.smallest_p_after_event} ({r.window_of_smallest_p})
                </td>
                <td className="py-1.5">{r.detected_after_correction ? "detected" : "not detected"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Note>{lag.limits}</Note>
      </Card>

      <Card
        title="Spillover: does a creator's engagement change when creators who promote the same brand are sponsored?"
        subtitle="Restricted to the verified 150 creators, shared-brand link. Two tests: each creator against itself, and exposed creators against unexposed ones."
      >
        {placebo && placebo.per_neighbour ? (
          <Verdict
            tone={placebo.per_neighbour.ci[0] > 0 || placebo.per_neighbour.ci[1] < 0 ? "warn" : "good"}
            label={
              placebo.per_neighbour.ci[0] > 0 || placebo.per_neighbour.ci[1] < 0
                ? `A difference remains when each creator is compared with itself: ${fmt(placebo.per_neighbour.median_of_means)} (${fmt(placebo.per_neighbour.ci[0])} to ${fmt(placebo.per_neighbour.ci[1])})`
                : `No spillover found when each creator is compared with itself: ${fmt(placebo.per_neighbour.median_of_means)} (${fmt(placebo.per_neighbour.ci[0])} to ${fmt(placebo.per_neighbour.ci[1])})`
            }
          >
            Test A (the main test) compares a creator&apos;s engagement change after a sponsored event with the same creator&apos;s change at ordinary dates months away, so creator-level growth cancels out. The event
            beat the ordinary dates for only {placebo.per_neighbour.events_beat_placebo} of {placebo.per_neighbour.n} creators, about what a coin flip gives.
          </Verdict>
        ) : null}
        <Verdict tone={real.difference_in_means_excludes_zero ? "warn" : "good"} label={`Test B, exposed vs unexposed creators: ${fmt(real.difference_in_means)} (${fmt(real.difference_in_means_ci[0])} to ${fmt(real.difference_in_means_ci[1])})`}>
          Based on {real.n_exposed} exposed and {real.n_unexposed} unexposed creators.
          {real.difference_in_means_excludes_zero
            ? " This looks like an effect, but it is not trusted on its own: the exposed creators were already growing faster at ordinary dates, so this comparison picks up what kind of creator they are, which Test A removes."
            : " Effects larger than about +0.3 would have been seen; smaller ones cannot be seen with this much data."}
        </Verdict>
        <table className="mt-3 w-full text-left text-xs">
          <thead className="text-zinc-500">
            <tr>
              <th className="pr-3 font-medium">Data</th>
              <th className="pr-3 font-medium">Exposed / unexposed</th>
              <th className="pr-3 font-medium">Estimate</th>
              <th className="pr-3 font-medium">95% interval</th>
              <th className="font-medium">Result</th>
            </tr>
          </thead>
          <tbody>
            <EstimateRow label="Test B, real data, shared-brand link" e={real} />
            <EstimateRow label="Test B, real data, collaboration links only" e={coll.real} remark={`only ${coll.real.n_exposed} exposed creators: too few to say`} />
            <EstimateRow label="SIMULATED: nothing planted" e={sp["beta_0.0"]} remark="check: should find nothing" />
            <EstimateRow label="SIMULATED: medium effect planted" e={sp["beta_0.5"]} remark="check: should find it" />
            <EstimateRow label="SIMULATED: large effect planted" e={sp["beta_1.0"]} remark="check: should find it" />
          </tbody>
        </table>
        <Note>
          The simulated rows plant a known effect on the real network to check that the estimator can see one. Exposure here means promoting the same brand as a sponsored creator, so niche
          overlap can also contribute; it is an exploratory link, not proof of cause.
        </Note>
      </Card>

      <Card
        title="How much data would see a smaller effect? (SIMULATED)"
        subtitle="Share of 300 simulated studies that detect the effect, by number of exposed creators. Engagement changes are heavy-tailed like the real ones."
      >
        <table className="w-full text-left text-xs">
          <thead className="text-zinc-500">
            <tr>
              <th className="pr-3 font-medium">Exposed creators</th>
              <th className="pr-3 font-medium">+0.25</th>
              <th className="pr-3 font-medium">+0.50</th>
              <th className="pr-3 font-medium">+0.75</th>
              <th className="pr-3 font-medium">+1.00</th>
              <th className="font-medium">False alarm</th>
            </tr>
          </thead>
          <tbody>
            {s9.power_curve.map((r) => (
              <tr key={r.exposed} className={`border-t border-zinc-200 dark:border-zinc-800 ${r.exposed === 19 ? "bg-amber-50 dark:bg-amber-950/20" : ""}`}>
                <td className="py-1.5 pr-3 tabular-nums">{r.exposed}</td>
                <td className="py-1.5 pr-3 tabular-nums">{r["effect_0.25"]}%</td>
                <td className="py-1.5 pr-3 tabular-nums">{r["effect_0.50"]}%</td>
                <td className="py-1.5 pr-3 tabular-nums">{r["effect_0.75"]}%</td>
                <td className="py-1.5 pr-3 tabular-nums">{r["effect_1.00"]}%</td>
                <td className="py-1.5 tabular-nums">{r.false_alarm}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Note>
          An effect of +0.5 means a creator&apos;s engagement rises by about half. About 81 exposed creators are needed to catch it 90% of the time. The highlighted row is roughly the earlier
          collaboration-only sample size.
        </Note>
      </Card>

      <Card title="Graph links behind the spillover score" subtitle="Creators of the 150 that have at least one link to another creator">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Collaboration + co-occurrence" value={`${s9.graph_links.today} / ${s9.graph_links.of}`} tone="bad" hint="what the saved model was trained on" />
          <Stat label="Plus shared-brand link" value={`${s9.graph_links.with_shared_brand} / ${s9.graph_links.of}`} tone="good" hint={`shared brand alone: ${s9.graph_links.shared_brand_alone} · available after retraining`} />
          {s9.graph_links.with_shared_brand_and_mentions != null ? (
            <Stat
              label="Plus @mentions of each other"
              value={`${s9.graph_links.with_shared_brand_and_mentions} / ${s9.graph_links.of}`}
              tone="good"
              hint={`mentions alone: ${s9.graph_links.mentions_alone ?? 0} · a creator tagging another creator we track · available after retraining`}
            />
          ) : null}
          <Stat label="Real spillover score now" value={`${scored} / ${s9.graph_links.of}`} tone="warn" hint="the rest show a neutral 0.5" />
        </div>
      </Card>
    </div>
  );
}
