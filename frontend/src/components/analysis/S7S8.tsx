"use client";

import { useState } from "react";
import type { AnalysisData } from "@/types/analysis";
import { Bars, Card, Legend, Note, Stat, Verdict, pct } from "./ui";

function Stack({ parts }: { parts: { label: string; value: number; className: string }[] }) {
  const total = parts.reduce((a, p) => a + p.value, 0) || 1;
  return (
    <>
      <div className="flex h-6 w-full overflow-hidden rounded-md">
        {parts.map((p) => (
          <div key={p.label} className={`flex items-center justify-center text-[10px] font-medium text-white ${p.className}`} style={{ width: `${(100 * p.value) / total}%` }} title={`${p.label}: ${p.value}`}>
            {p.value / total > 0.07 ? p.value : ""}
          </div>
        ))}
      </div>
      <div className="mt-1.5">
        <Legend items={parts.map((p) => ({ label: `${p.label} (${p.value})`, className: p.className }))} />
      </div>
    </>
  );
}

export function S7Filters({ data }: { data: AnalysisData }) {
  const s7 = data.s7;
  const models = Object.keys(s7.demo_query);
  const [model, setModel] = useState(models[0]);
  const [phase, setPhase] = useState<"before" | "after">("after");
  const budgets = Array.from(new Set(s7.cost_stability.map((r) => r.budget)));
  const [budget, setBudget] = useState(5_000_000);
  const d = (phase === "after" ? s7.demo_query_fixed : s7.demo_query)[model];
  const afterBudget = d.considered - d.budget;
  const afterRegion = afterBudget - d.region;
  const afterProduct = afterRegion - d.product;
  const reg = s7.region;
  const hr = s7.hand_review;
  const prod = Object.entries(s7.product);
  const kept = prod.map(([, v]) => v.current).sort((a, b) => a - b);
  const keptFixed = prod.map(([, v]) => v.fixed).sort((a, b) => a - b);

  return (
    <div className="flex flex-col gap-4">
      <Verdict tone="warn" label="Filters: audited, then the region and product matching were fixed. The demo query went from 0 results to 86.">
        The audit found that most of what the soft filters dropped should have survived (a region test that needed the English word &quot;india&quot;, and a product test that could not match &quot;athletic&quot; to &quot;athlete&quot;). Both matchers are fixed and tested. Still open: cleaning the shop, gym and
        news accounts out of the creator list, and turning the product filter into a soft ranking penalty (a decision for the team).
      </Verdict>

      <Card title="Where the 259 creators go" subtitle="The standing demo query. A creator is counted under the first filter that drops it.">
        <div className="mb-2 flex gap-1" role="group" aria-label="before or after the fix">
          {(["before", "after"] as const).map((p) => (
            <button key={p} type="button" onClick={() => setPhase(p)} className={`rounded-md border px-3 py-1 text-xs font-medium ${p === phase ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900" : "border-zinc-300 dark:border-zinc-700"}`}>
              {p === "before" ? "Before the fix" : "After the fix"}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          {models.map((m) => (
            <button key={m} type="button" onClick={() => setModel(m)} className={`rounded-full border px-3 py-1 text-xs ${m === model ? "border-sky-500 bg-sky-50 text-sky-900 dark:bg-sky-950/40 dark:text-sky-200" : "border-zinc-300 dark:border-zinc-700"}`}>
              {m}
            </button>
          ))}
        </div>
        <div className="mt-3">
          <Bars
            max={d.considered}
            rows={[
              { label: "Considered", value: d.considered, color: "bg-zinc-400" },
              { label: `After budget (−${d.budget})`, value: afterBudget, color: "bg-sky-500" },
              { label: `After region (−${d.region})`, value: afterRegion, color: "bg-amber-500" },
              { label: `After product (−${d.product})`, value: afterProduct, color: afterProduct > 0 ? "bg-emerald-500" : "bg-rose-500" },
            ]}
          />
        </div>
        <Note>{phase === "after" ? `After the fix the same query returns ${d.kept} creators instead of 0.` : "Before the fix every creator was dropped and the query returned nothing."} The flat 0.5 per follower is what this branch ships; the tiered cost lives on the review-1 branch. The Review 1 notes call the counts &quot;tiered&quot;, but they match the flat model exactly.</Note>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Region filter ('India'): who gets dropped" subtitle={`Before the fix: ${reg.dropped} creators dropped for missing the word "india"`}>
          <Stack
            parts={[
              { label: "clear India evidence in the data", value: reg.india_evidence, className: "bg-emerald-500" },
              { label: "cannot tell from the data", value: reg.unknown, className: "bg-zinc-400" },
              { label: "clearly elsewhere", value: reg.foreign, className: "bg-sky-500" },
            ]}
          />
          <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-zinc-700 dark:text-zinc-300">
            <li>{reg.iso_code_IN} have the YouTube country code &quot;IN&quot;, which is never equal to the word &quot;india&quot;.</li>
            <li>{reg.india_in_name.length} have India or Indian in their own name, but names are never read.</li>
            <li>
              Hand review of the {hr.region_unknown_split.n} undecided: {hr.region_unknown_split.india} look Indian, {hr.region_unknown_split.foreign} foreign, {hr.region_unknown_split.cannot_tell} unclear. That puts the false drops at roughly{" "}
              <strong>{pct(reg.india_evidence + hr.region_unknown_split.india, reg.dropped)}</strong> (a judgement, not data).
            </li>
            <li>
              <strong>After the fix</strong> the region filter drops {s7.region_fixed.dropped} instead of {reg.dropped}; {s7.region_fixed.still_with_india_evidence} of those still show India evidence (such as place names like Mumbai, which the filter does not read yet).
            </li>
            <li>{s7.noop.no_region_signal} of {s7.noop.creators} creators ({pct(s7.noop.no_region_signal, s7.noop.creators)}) have no region text at all, so the filter is a no-op for them.</li>
          </ul>
        </Card>

        <Card title="Product filter: creators kept per brief, before and after the fix" subtitle="Of 259, for ten realistic briefs, under four matchers.">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="text-zinc-500">
                  <th className="py-1 pr-2 font-medium">Brief</th>
                  <th className="py-1 pr-2 text-right font-medium">Before</th>
                  <th className="py-1 pr-2 text-right font-medium">Whole word</th>
                  <th className="py-1 pr-2 text-right font-medium">Stemmed</th>
                  <th className="py-1 text-right font-medium">After fix</th>
                </tr>
              </thead>
              <tbody>
                {prod.map(([b, v]) => (
                  <tr key={b} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="py-1 pr-2">{b}</td>
                    <td className="py-1 pr-2 text-right tabular-nums">{v.current}</td>
                    <td className="py-1 pr-2 text-right tabular-nums">{v.whole_word}</td>
                    <td className="py-1 pr-2 text-right tabular-nums">{v.stemmed}</td>
                    <td className={`py-1 text-right font-semibold tabular-nums ${v.fixed > v.current ? "text-emerald-600" : v.fixed < v.current ? "text-amber-600" : ""}`}>{v.fixed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-zinc-700 dark:text-zinc-300">
            <li>
              Median creators left per brief: <strong>{kept[Math.floor(kept.length / 2)]}</strong> before, <strong>{keptFixed[Math.floor(keptFixed.length / 2)]}</strong> after the fix (of 259). &quot;yoga mat&quot; went from 18 to 6 because &quot;mat&quot; no longer matches inside &quot;cinematic&quot;.
            </li>
            <li>&quot;athlete&quot; is not a substring of &quot;athletic&quot;: stemming recovers 102 athletes; {hr.product_recovered_sensible.correct} of {hr.product_recovered_sensible.n} sampled were sensible.</li>
            <li>3-letter words match inside others (&quot;mat&quot; in &quot;cinematic&quot;): {hr.substring_only_keeps.accidents} of {hr.substring_only_keeps.n} sampled substring-only keeps were accidents.</li>
          </ul>
        </Card>
      </div>

      <Card title="Does the cost model change who ranks on top?" subtitle="Cost only decides who is eligible; ranking is by fusion score. Compared with the flat model.">
        <div className="flex flex-wrap gap-2">
          {budgets.map((b) => (
            <button key={b} type="button" onClick={() => setBudget(b)} className={`rounded-full border px-3 py-1 text-xs ${b === budget ? "border-sky-500 bg-sky-50 text-sky-900 dark:bg-sky-950/40 dark:text-sky-200" : "border-zinc-300 dark:border-zinc-700"}`}>
              ₹{b / 1_000_000}M
            </button>
          ))}
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-zinc-500">
                <th className="py-1 pr-2 font-medium">Model</th>
                <th className="py-1 pr-2 text-right font-medium">Eligible</th>
                <th className="py-1 pr-2 text-right font-medium">Creators flip</th>
                <th className="py-1 font-medium">Top 10 shared with flat</th>
              </tr>
            </thead>
            <tbody>
              {s7.cost_stability.filter((r) => r.budget === budget).map((r) => (
                <tr key={r.model} className="border-t border-zinc-100 dark:border-zinc-800">
                  <td className="py-1.5 pr-2">{r.model}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">
                    {r.eligible} <span className="text-zinc-400">(flat {r.eligible_flat})</span>
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">{r.flips}</td>
                  <td className="py-1.5">
                    <span className="flex items-center gap-2">
                      <span className="h-2.5 w-24 rounded-full bg-zinc-100 dark:bg-zinc-800">
                        <span className={`block h-2.5 rounded-full ${r.top10_overlap >= 9 ? "bg-emerald-500" : "bg-amber-500"}`} style={{ width: `${r.top10_overlap * 10}%` }} />
                      </span>
                      <span className="tabular-nums">{r.top10_overlap}/10</span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Note>Category tiering barely changes anything. The follower-tiered row is a hypothetical stand-in for a future rate card (real pricing falls per follower as reach grows), not a prediction.</Note>
      </Card>
    </div>
  );
}

export function S8Linking({ data }: { data: AnalysisData }) {
  const s8 = data.s8;
  const hr = s8.hand_review;
  const cp = s8.cross_platform_pairs;
  const rd = s8.reddit;
  const weakLinks = rd.links - rd.name_evidenced_strict;
  const estWrong = (weakLinks * hr.reddit_weak_sample.wrong) / hr.reddit_weak_sample.n;
  const po = s8.post_ownership;
  const ppl = s8.coverage.platforms_per_creator;

  return (
    <div className="flex flex-col gap-4">
      <Verdict tone="warn" label="Cross-platform linking: audited. The cross-platform claim rests on a single measured pair, and about a quarter of Reddit links are wrong.">
        Nothing was changed in the data. Every number below is measured on the live database, with small hand-reviewed samples where there is no ground truth.
      </Verdict>

      <Card title="How much cross-platform evidence is there?" subtitle="From 54 (event, neighbour) training pairs to pairs measured on more than one platform.">
        <Bars
          max={cp.pairs}
          rows={[
            { label: "Training pairs", value: cp.pairs, color: "bg-zinc-400" },
            { label: "With a measurable lift", value: cp.pair_count_meta.same_platform_computable, color: "bg-sky-500" },
            { label: "Measured on 2+ platforms", value: cp.measured_on_2plus, color: "bg-rose-500" },
          ]}
        />
        <Note>
          {cp.pair_count_meta.cross_platform_only} pairs ({pct(cp.pair_count_meta.cross_platform_only, cp.pairs)}) are dropped because the neighbour&apos;s activity before and after the event is never on the same platform. Only {s8.coverage.multi_platform} of {s8.coverage.creators} creators have handles on 2+
          platforms. Cross-platform interference is a design capability here, not a demonstrated result.
        </Note>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Platforms per creator">
          <Bars
            rows={Object.entries(ppl).map(([k, v]) => ({ label: `${k} platform${k === "1" ? "" : "s"}`, value: v, color: k === "1" ? "bg-zinc-400" : "bg-emerald-500" }))}
          />
          <Note>YouTube handles exist for {s8.coverage.youtube} creators, Instagram for {s8.coverage.instagram}. {s8.instagram.never_fetched} Instagram handles were never fetched, so nothing has checked them.</Note>
        </Card>

        <Card title="YouTube links: how well supported?" subtitle={`${s8.youtube.links} links, all reviewed`}>
          <Bars labelWidth="15rem" rows={Object.entries(s8.youtube.evidence).map(([k, v]) => ({ label: k.replace(/ \(.*\)/, ""), value: v, color: k.startsWith("corroborated") ? "bg-emerald-500" : k.startsWith("name") ? "bg-sky-500" : "bg-amber-500" }))} />
          <Note>
            By hand, {hr.youtube_doubtful.low} to {hr.youtube_doubtful.high} of {hr.youtube_doubtful.links} are doubtful: one channel calls itself a fan club, one is a podcast and not the person, two rest on identical handle text only.
          </Note>
        </Card>
      </div>

      <Card title="Reddit post-to-creator links" subtitle={`${rd.links} links made by keyword search`}>
        <Stack
          parts={[
            { label: "full name or handle in the post", value: rd.name_evidenced_strict, className: "bg-emerald-500" },
            { label: "no full name", value: weakLinks, className: "bg-rose-400" },
          ]}
        />
        <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-zinc-700 dark:text-zinc-300">
          <li>
            Hand review: all {hr.reddit_strict_sample.correct} of {hr.reddit_strict_sample.n} sampled links with the full name were correct. Of {hr.reddit_weak_sample.n} sampled links without it: {hr.reddit_weak_sample.correct} correct, <strong>{hr.reddit_weak_sample.wrong} wrong</strong>,{" "}
            {hr.reddit_weak_sample.unclear} unclear.
          </li>
          <li>
            Estimated wrong: about <strong>{pct(Math.round(estWrong), rd.links)}</strong> of all links (95% interval roughly 18% to 28%). Typical causes: generic words (&quot;night&quot;, &quot;will&quot;), team names matched on a place, and a different person with the same name.
          </li>
          <li>
            <strong>{s8.reddit_roster_posts.pairs_only_from_them} of {s8.reddit_roster_posts.pairs}</strong> co-occurrence pairs ({pct(s8.reddit_roster_posts.pairs_only_from_them, s8.reddit_roster_posts.pairs)}) exist only because of {s8.reddit_roster_posts.posts_8plus} roster or auction posts that name 8 or more creators: being listed
            together is a mention, not a relationship.
          </li>
        </ul>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Collaboration edges" subtitle={`${s8.collaboration_edges.pairs} pairs from ${s8.collaboration_edges.related_rows} related-account rows`}>
          <Bars
            max={s8.collaboration_edges.pairs}
            rows={[
              { label: "Involve a team or league", value: s8.collaboration_edges.team_or_league_pairs, color: "bg-violet-500" },
              { label: "Listed by both creators", value: s8.collaboration_edges.mutual, color: "bg-emerald-500" },
              { label: "Same entity on both ends", value: s8.collaboration_edges.same_entity.length, color: "bg-rose-500" },
            ]}
          />
          <Note>
            Mostly affiliations (a player on a club&apos;s collab post), not two creators working together. Most connected: {s8.collaboration_edges.top_hubs.slice(0, 4).map((h) => `${h[0]} (${h[1]})`).join(", ")}. Hand review of {hr.collab_pairs_sample.n} pairs found none clearly false.
          </Note>
        </Card>

        <Card title="Instagram posts filed under the wrong account" subtitle="Track A's ownership audit, re-checked against today's data">
          <Bars
            max={100}
            rows={[
              { label: "Fetched before the filter", value: (100 * po.wrong_pre_filter[0]) / po.wrong_pre_filter[1], note: `${po.wrong_pre_filter[0]}/${po.wrong_pre_filter[1]}`, color: "bg-rose-400" },
              { label: "Fetched after the filter", value: (100 * po.wrong_post_filter[0]) / po.wrong_post_filter[1], note: `${po.wrong_post_filter[0]}/${po.wrong_post_filter[1]}`, color: "bg-emerald-500" },
            ]}
            format={(v) => `${v.toFixed(1)}%`}
          />
          <Note>
            All {po.wrong_at_audit} wrong posts were re-attributed ({po.still_wrong_today} still wrong). Still unmeasured: {po.unaudited_pre_filter} posts fetched before the filter were never audited, {po.unaudited_sponsored_pre_filter} of them sponsored. Also, {s8.null_creator_events.events_without_creator} of{" "}
            {s8.null_creator_events.events} sponsorship events have no creator.
          </Note>
        </Card>
      </div>

      <Card title="Are all 'creators' really creators?">
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="Not creators (hand review)" value={`${hr.non_creator_accounts.low}-${hr.non_creator_accounts.high}`} hint={`of ${hr.non_creator_accounts.reviewed} reviewed`} tone="warn" />
          <Stat label="Flagged by the classifier" value={hr.non_creator_accounts.classifier_flags} hint="Track A's classifier caught none" tone="bad" />
          <Stat label="Examples" value="shops, gyms, news" hint="e.g. a clothing store, a gym chain, a news page" />
        </div>
        <Note>These accounts are the main source of wrong Reddit links and generic-word product matches. The athlete, team and league rows were not reviewed.</Note>
      </Card>
    </div>
  );
}
