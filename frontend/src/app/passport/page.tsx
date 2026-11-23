"use client";

import Avatar from "@/components/Avatar";
import Icon from "@/components/Icon";
import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import EvidenceBadge from "@/components/EvidenceBadge";
import { getPassport, getPassportCreators, getPassportSummary } from "@/lib/api";
import type { PassportCreatorLite, PassportPenalty, PassportRecord, PassportSummary } from "@/types";

// Creator Passport (1 Nov 2026): what we know about one creator across platforms, each part with its own sample size and a plain "not enough data" where that is the truth.
// The group-level findings sit on top; every number comes from models/creator_passport.json (scripts/build_creator_passport.py). Nothing here changes a score.

const pct = (x: number, digits = 0) => `${x >= 0 ? "+" : ""}${x.toFixed(digits)}%`;

export default function PassportPage() {
  return (
    <Suspense fallback={<main className="mx-auto w-full max-w-5xl px-6 py-16 text-sm text-zinc-500">Loading…</main>}>
      <PassportView />
    </Suspense>
  );
}

function PassportView() {
  const router = useRouter();
  const params = useSearchParams();
  const selected = params.get("creator");
  const [summary, setSummary] = useState<PassportSummary | null>(null);
  const [creators, setCreators] = useState<PassportCreatorLite[]>([]);
  const [fetched, setFetched] = useState<PassportRecord | null>(null);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    Promise.all([getPassportSummary(), getPassportCreators()])
      .then(([s, c]) => {
        setSummary(s);
        setCreators(c);
      })
      .catch(() => setError(true));
  }, []);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    getPassport(selected)
      .then((p) => !cancelled && setFetched(p))
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [selected]);

  // Only show a passport that belongs to the creator now selected.
  const record = selected && fetched && fetched.creator_id === selected ? fetched : null;
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pool = q ? creators.filter((c) => c.name.toLowerCase().includes(q)) : [...creators].sort((x, y) => y.sections_filled - x.sections_filled);
    return pool.slice(0, 8);
  }, [creators, query]);

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-6 py-12">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Creator Passport</h1>
        <p className="mt-1 max-w-3xl text-sm text-zinc-600 dark:text-zinc-400">
          Not one number, but what we know about a creator on each platform, how sure we are, and where the evidence is thin. Every part states its own sample size.
        </p>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">Couldn&apos;t load the passport. Is the backend running, and has scripts/build_creator_passport.py been run?</p>}

      {summary && <Findings s={summary} creators={creators} onOpen={(id) => router.push(`/passport?creator=${id}`)} />}

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium">Look up a creator</h2>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name"
          className="w-full max-w-sm rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm dark:border-zinc-700"
        />
        <div className="flex flex-wrap gap-2">
          {!query && <span className="self-center text-xs text-zinc-500">Examples with the most complete passports:</span>}
          {matches.map((c) => (
            <button
              key={c.creator_id}
              onClick={() => router.push(`/passport?creator=${c.creator_id}`)}
              className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                selected === c.creator_id ? "border-accent bg-accent-soft text-accent" : "border-zinc-300 hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
              }`}
            >
              <span className="flex items-center gap-1.5"><Avatar creatorId={c.creator_id} name={c.name} size={20} />{c.name}</span>
            </button>
          ))}
          {query && matches.length === 0 && <span className="text-xs text-zinc-500">No creator with that name.</span>}
        </div>
      </section>

      {record ? <Passport p={record} /> : selected && !error ? <p className="text-sm text-zinc-500">Loading passport…</p> : null}

      {summary && (
        <details className="text-xs text-zinc-500">
          <summary className="cursor-pointer">Limits that apply to every passport</summary>
          <ul className="mt-1 list-disc pl-5">
            {summary.limits.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </details>
      )}
    </main>
  );
}

function Findings({ s, creators, onOpen }: { s: PassportSummary; creators: PassportCreatorLite[]; onOpen: (id: string) => void }) {
  const x = s.summary;
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-medium">Good to know before you book</h2>
      <div className="grid gap-3 md:grid-cols-3">
        {x.speed.median_share_first_24h != null && <SpeedCard share={x.speed.median_share_first_24h} videos={x.speed.videos} />}
        <ClashCard n={x.clash.creators_with_recent_brand_posts} days={x.clash.window_days} creators={creators.filter((c) => c.has_recent_brand_posts)} onOpen={onOpen} />
        <BusyCard n={x.fatigue.creators_above_usual} creators={creators.filter((c) => c.ad_load_above_usual)} onOpen={onOpen} />
      </div>
    </section>
  );
}

/** Counts up from 0 to `target` once, on mount (jumps straight there under reduced motion). */
function useCountUp(target: number, ms = 900) {
  const [v, setV] = useState(0);
  useEffect(() => {
    let id = 0;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      id = requestAnimationFrame(() => setV(target));
      return () => cancelAnimationFrame(id);
    }
    const t0 = performance.now();
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / ms);
      setV(Math.round(target * (1 - Math.pow(1 - k, 3))));
      if (k < 1) id = requestAnimationFrame(step);
    };
    id = requestAnimationFrame(step);
    return () => cancelAnimationFrame(id);
  }, [target, ms]);
  return v;
}

function Card({ icon, title, children }: { icon: string; title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col rounded-xl border border-line bg-panel p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-zinc-100">
        <span className="grid h-7 w-7 place-items-center rounded-full bg-accent-soft text-accent" aria-hidden>
          <Icon name={icon} size={16} />
        </span>
        {title}
      </div>
      {children}
    </div>
  );
}

function SpeedCard({ share, videos }: { share: number; videos: number }) {
  const shown = useCountUp(Math.round(share * 100));
  const [focus, setFocus] = useState<"day1" | "rest">("day1");
  const R = 44;
  const C = 2 * Math.PI * R;
  const day1 = (shown / 100) * C;
  return (
    <Card icon="bolt" title="Post on day one">
      <div className="mt-3 flex items-center gap-4">
        <svg viewBox="0 0 110 110" className="h-28 w-28 shrink-0" role="img" aria-label={`${Math.round(share * 100)}% of first-week views on day one`}>
          <g transform="rotate(-90 55 55)">
            <circle cx="55" cy="55" r={R} fill="none" stroke="var(--line)" strokeWidth="12" />
            <circle
              cx="55"
              cy="55"
              r={R}
              fill="none"
              strokeWidth="12"
              strokeLinecap="round"
              stroke={focus === "rest" ? "#2e3c4a" : "var(--accent)"}
              strokeDasharray={`${day1} ${C}`}
              className="cursor-pointer transition-[stroke] duration-300"
              onMouseEnter={() => setFocus("day1")}
            />
            <circle
              cx="55"
              cy="55"
              r={R}
              fill="none"
              strokeWidth="12"
              stroke={focus === "rest" ? "var(--signal)" : "transparent"}
              strokeDasharray={`${Math.max(0, C - day1 - 8)} ${C}`}
              strokeDashoffset={-day1 - 4}
              className="cursor-pointer transition-[stroke] duration-300"
              onMouseEnter={() => setFocus("rest")}
            />
          </g>
          <text x="55" y="55" textAnchor="middle" dominantBaseline="central" fill="var(--foreground)" fontSize="22" fontWeight={600}>
            {focus === "day1" ? shown : 100 - shown}%
          </text>
        </svg>
        <div className="flex flex-col gap-1.5 text-xs">
          {(["day1", "rest"] as const).map((k) => (
            <button
              key={k}
              onMouseEnter={() => setFocus(k)}
              onClick={() => setFocus(k)}
              className={`flex items-center gap-2 rounded-md px-2 py-1 text-left transition-colors ${focus === k ? "bg-line text-zinc-50" : "text-zinc-400"}`}
            >
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: k === "day1" ? "var(--accent)" : "var(--signal)" }} />
              {k === "day1" ? "Day 1" : "Days 2 to 7"}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-3 text-sm text-zinc-300">Most of a video&apos;s first-week views come on the first day. Launch offers on day one.</p>
      <p className="mt-auto pt-2 text-[11px] text-zinc-500">YouTube, {videos.toLocaleString()} videos</p>
    </Card>
  );
}

function CreatorChip({ c, onOpen }: { c: PassportCreatorLite; onOpen: (id: string) => void }) {
  return (
    <button
      onClick={() => onOpen(c.creator_id)}
      title={`Open ${c.name}'s passport`}
      className="flex items-center gap-1.5 rounded-full border border-line py-0.5 pl-0.5 pr-2.5 text-xs text-zinc-300 transition-colors hover:border-accent hover:text-accent"
    >
      <Avatar creatorId={c.creator_id} name={c.name} size={20} />
      {c.name}
    </button>
  );
}

function ClashCard({ n, days, creators, onOpen }: { n: number; days: number; creators: PassportCreatorLite[]; onOpen: (id: string) => void }) {
  const shown = useCountUp(n);
  const [open, setOpen] = useState(false);
  const faces = creators.slice(0, 7);
  return (
    <Card icon="shield" title="Rival brand check">
      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-4xl font-semibold tracking-tight text-accent">{shown}</span>
        <span className="text-sm text-zinc-400">creators promoted a brand in the last {days} days</span>
      </div>
      <button onClick={() => setOpen((o) => !o)} className="mt-3 flex items-center -space-x-2 self-start" aria-expanded={open}>
        {faces.map((c) => (
          <span key={c.creator_id} className="rounded-full ring-2 ring-[var(--panel)] transition-transform hover:-translate-y-1">
            <Avatar creatorId={c.creator_id} name={c.name} size={28} />
          </span>
        ))}
        {creators.length > faces.length && (
          <span className="grid h-7 place-items-center rounded-full bg-line px-2 text-[11px] text-zinc-300 ring-2 ring-[var(--panel)]">
            +{creators.length - faces.length}
          </span>
        )}
        <span className="pl-4 text-xs text-zinc-500">{open ? "hide" : "see who"}</span>
      </button>
      {open && (
        <div className="mt-2 flex max-h-32 flex-wrap gap-1.5 overflow-y-auto">
          {creators.map((c) => (
            <CreatorChip key={c.creator_id} c={c} onOpen={onOpen} />
          ))}
        </div>
      )}
      <p className="mt-3 text-sm text-zinc-300">We warn you if a creator recently worked with your rival.</p>
      <Link href="/brand-input" className="mt-auto pt-2 text-xs font-medium text-accent hover:underline">
        Check with my brand →
      </Link>
    </Card>
  );
}

function BusyCard({ n, creators, onOpen }: { n: number; creators: PassportCreatorLite[]; onOpen: (id: string) => void }) {
  const shown = useCountUp(n);
  return (
    <Card icon="megaphone" title="Busy with ads right now">
      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-4xl font-semibold tracking-tight text-accent">{shown}</span>
        <span className="text-sm text-zinc-400">creators are posting twice their usual ads this month</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {creators.map((c) => (
          <CreatorChip key={c.creator_id} c={c} onOpen={onOpen} />
        ))}
      </div>
      <p className="mt-auto pt-3 text-[11px] text-zinc-500">Good to know when booking. Our data shows no clear drop in their views from it.</p>
    </Card>
  );
}

function Passport({ p }: { p: PassportRecord }) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="flex items-center gap-3 text-xl font-semibold tracking-tight"><Avatar creatorId={p.creator_id} name={p.name} size={48} />{p.name}</h2>
        <span className="rounded-full border border-zinc-300 px-2 py-0.5 text-[11px] text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">{p.category.replace("_", " ")}</span>
        <EvidenceBadge grade={p.evidence.grade} />
        <span className="text-xs text-zinc-500">
          {p.coverage.youtube_videos} YouTube videos · {p.coverage.instagram_posts} Instagram posts · {p.coverage.growth_readings.toLocaleString()} growth readings
        </span>
      </div>
      <ul className="list-disc pl-5 text-xs text-zinc-500">
        {p.evidence.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>

      <div className="grid gap-4 md:grid-cols-2">
        <Section title="Platform strength" sub="each platform against the creator's own usual">
          {p.platform_strength ? (
            <>
              {["YouTube", "Instagram"].includes(p.platform_strength.stronger_platform) ? (
                <p className="text-sm">
                  Stronger on <span className="font-medium">{p.platform_strength.stronger_platform}</span> ({p.platform_strength.pairs} matched posts).
                </p>
              ) : p.platform_strength.stronger_platform === "balanced" ? (
                <p className="text-sm">About equally strong on both ({p.platform_strength.pairs} matched posts).</p>
              ) : (
                <p className="text-sm text-zinc-500">
                  Only {p.platform_strength.pairs} matched post{p.platform_strength.pairs === 1 ? "" : "s"}: too few for a fair comparison. Shown for information only.
                </p>
              )}
              <Row k="YouTube vs usual" v={p.platform_strength.youtube_vs_usual_median.toFixed(2)} />
              <Row k="Instagram vs usual" v={p.platform_strength.instagram_vs_usual_median.toFixed(2)} />
              {p.platform_strength.basis.length > 0 && <p className="mt-1 text-[11px] text-zinc-500">{p.platform_strength.basis.join("; ")}</p>}
            </>
          ) : (
            <Empty>No same-content posts within 24 hours on both platforms, so no fair comparison.</Empty>
          )}
        </Section>

        <Section title="Mood" sub="comment sentiment per platform, 0 negative to 1 positive">
          {p.mood?.youtube || p.mood?.instagram ? (
            <>
              {p.mood.youtube && <Bar label="YouTube" score={p.mood.youtube.score} n={p.mood.youtube.n} />}
              {p.mood.instagram && <Bar label="Instagram" score={p.mood.instagram.score} n={p.mood.instagram.n} />}
              <p className={`mt-2 text-xs ${p.mood.significant ? "font-medium text-amber-700 dark:text-amber-400" : "text-zinc-500"}`}>
                {p.mood.significant ? `Mood gap: ${p.mood.label} (${(p.mood.gap ?? 0) > 0 ? "+" : ""}${(p.mood.gap ?? 0).toFixed(2)})` : p.mood.label}
              </p>
            </>
          ) : (
            <Empty>No scored comments on YouTube or Instagram.</Empty>
          )}
        </Section>

        <Section title="Speed" sub="share of a video's first-week views that arrive in 24 hours">
          {p.speed ? (
            <p className="text-sm">
              <span className="text-2xl font-semibold text-accent">{Math.round(100 * p.speed.share_first_24h)}%</span> in the first day (median of {p.speed.videos} videos, YouTube).
            </p>
          ) : (
            <Empty>Fewer than 3 videos followed through a full first week.</Empty>
          )}
        </Section>

        <Section title="Sponsored response" sub="sponsored posts against this creator's own organic posts of the same format">
          <Penalty label="YouTube views" x={p.sponsored.youtube_views} />
          <Penalty label="YouTube likes" x={p.sponsored.youtube_likes} />
          <Penalty label="Instagram likes" x={p.sponsored.instagram_likes} />
          {p.sponsored.buying_signals && (
            <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
              Buying signals in comments: {p.sponsored.buying_signals.intent_per_1000_sponsored.toFixed(1)} per 1,000 on sponsored videos vs {p.sponsored.buying_signals.intent_per_1000_other.toFixed(1)} on others ({p.sponsored.buying_signals.verdict}).
            </p>
          )}
          {p.sponsored.disclosure && (
            <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              Disclosure: {p.sponsored.disclosure.disclosed} of {p.sponsored.disclosure.sponsored_videos} detected sponsored videos carry an explicit label ({p.sponsored.disclosure.label}).
            </p>
          )}
        </Section>

        <Section title="Ad load" sub="sponsored posts in the last 30 days against the creator's usual">
          {p.fatigue ? (
            <p className="text-sm">
              {p.fatigue.sponsored_last_30d} now vs {p.fatigue.usual_per_30d.toFixed(1)} usual per 30 days.{" "}
              {p.fatigue.above_usual && <span className="font-medium text-amber-700 dark:text-amber-400">Above their usual ad load.</span>}
              <span className="block text-[11px] text-zinc-500">Our group test finds no clear drop in views from heavier ad load, so treat this as a fact, not a forecast.</span>
            </p>
          ) : (
            <Empty>No detected sponsored posts.</Empty>
          )}
        </Section>

        <Section title="Network" sub="links to other creators we track">
          <Row k="Linked creators (collaboration or @mention)" v={String(p.network.linked_creators)} />
          <Row k="…of which sponsored in the last 30 days" v={String(p.network.linked_sponsored_last_30d)} />
          <Row k="Creators sharing a recent brand" v={String(p.network.shared_brand_creators)} />
          <p className="mt-1 text-[11px] text-zinc-500">Links are shown as context: who this creator is connected to, and which brands they share.</p>
        </Section>

        <Section title="Recent brands" sub="brands promoted in the last 120 days (basis of the clash warning)">
          {p.clash_events.length > 0 ? (
            <ul className="text-xs">
              {p.clash_events.slice(0, 6).map((e) => (
                <li key={e.brand} className="flex justify-between border-t border-zinc-200 py-1 first:border-t-0 dark:border-zinc-800">
                  <span>
                    {e.brand} <span className="text-zinc-500">({e.category})</span>
                  </span>
                  <span className="tabular-nums text-zinc-500">{e.last_seen}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>No detected brand posts in the last 120 days.</Empty>
          )}
        </Section>

        <Section title="Missing platform" sub="estimated from the other platform">
          {p.predicted_instagram ? (
            <p className="text-sm">
              No Instagram data collected. From YouTube we estimate typical Instagram likes of about{" "}
              <span className="font-semibold">{p.predicted_instagram.typical_likes.toLocaleString()}</span> (80% range {p.predicted_instagram.range_80[0].toLocaleString()} to {p.predicted_instagram.range_80[1].toLocaleString()}).
              <span className="block text-[11px] text-zinc-500">An estimate tested leave-one-out on creators who have both; wide on purpose. Not collected data.</span>
            </p>
          ) : (
            <Empty>{p.coverage.instagram_posts > 0 ? "Instagram data exists, so nothing is estimated." : "Too little YouTube data to estimate an Instagram level."}</Empty>
          )}
        </Section>
      </div>

      <Link href="/brand-input" className="text-xs underline">
        Start a brand request to see this creator ranked for a product
      </Link>
    </section>
  );
}

function Section({ title, sub, children }: { title: string; sub: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="text-sm font-medium">{title}</h3>
      <p className="mb-2 text-[11px] text-zinc-500">{sub}</p>
      {children}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between border-t border-zinc-200 py-1 text-xs first:border-t-0 dark:border-zinc-800">
      <span className="text-zinc-600 dark:text-zinc-400">{k}</span>
      <span className="font-medium tabular-nums">{v}</span>
    </div>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-zinc-500">{children}</p>;
}

function Bar({ label, score, n }: { label: string; score: number; n: number }) {
  return (
    <div className="mb-1.5 text-xs">
      <div className="flex justify-between">
        <span>{label}</span>
        <span className="tabular-nums text-zinc-500">
          {score.toFixed(2)} · {n} comments
        </span>
      </div>
      <div className="mt-0.5 h-1.5 rounded-full bg-zinc-200 dark:bg-zinc-800">
        <div className="h-1.5 rounded-full bg-accent" style={{ width: `${Math.max(2, Math.min(100, 100 * score))}%` }} />
      </div>
    </div>
  );
}

function Penalty({ label, x }: { label: string; x: PassportPenalty | null }) {
  if (!x) return <Row k={label} v="not enough sponsored posts" />;
  return <Row k={`${label} (${x.matched} sponsored posts matched)`} v={`${pct(x.approx_percent, 0)}${x.enough ? "" : " · few posts"}`} />;
}
