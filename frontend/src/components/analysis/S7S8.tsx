"use client";

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
