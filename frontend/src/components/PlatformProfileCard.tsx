"use client";

import { useState } from "react";
import { getPlatformProfile } from "@/lib/api";
import type { PlatformProfile, PlatformSide, PlatformStatus } from "@/types";

const STATUS_STYLE: Record<PlatformStatus, string> = {
  strong: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  typical: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  weak: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  unknown: "border border-zinc-300 text-zinc-500 dark:border-zinc-700",
};

const num = (v: number | null, digits = 0) => (v == null ? "unknown" : v.toLocaleString(undefined, { maximumFractionDigits: digits }));
const pct = (v: number | null) => (v == null ? "unknown" : `${(v * 100).toFixed(1)}%`);

function Side({ side }: { side: PlatformSide }) {
  const youtube = side.platform === "youtube";
  return (
    <div className="rounded-md bg-zinc-50 px-3 py-2 dark:bg-zinc-900">
      <div className="flex items-center justify-between">
        <span className="font-medium">{youtube ? "YouTube" : "Instagram"}</span>
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLE[side.status]}`}>
          {side.status === "unknown" ? "not enough data" : `${side.status} engagement`}
          {side.percentile != null ? ` · top ${Math.round(100 - side.percentile)}%` : ""}
        </span>
      </div>
      {!side.available ? (
        <p className="mt-2 text-zinc-500">{side.notes[0]}</p>
      ) : (
        <>
          <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
            <dt className="text-zinc-500">{youtube ? "Subscribers" : "Followers"}</dt>
            <dd>{num(side.audience)}</dd>
            {youtube ? (
              <>
                <dt className="text-zinc-500">Typical views</dt>
                <dd>{num(side.typical_views)}</dd>
              </>
            ) : null}
            <dt className="text-zinc-500">Typical likes</dt>
            <dd>{num(side.typical_likes)}</dd>
            <dt className="text-zinc-500">Typical comments</dt>
            <dd>{num(side.typical_comments)}</dd>
            <dt className="text-zinc-500">Engagement rate</dt>
            <dd>{pct(side.engagement_rate)}</dd>
            <dt className="text-zinc-500">Posts, last 90 days</dt>
            <dd>{side.items_last_90_days}</dd>
            <dt className="text-zinc-500">Counts known for</dt>
            <dd>
              {side.items_with_counts} of {side.items_total}
            </dd>
            <dt className="text-zinc-500">Sponsored vs usual</dt>
            <dd>{side.sponsored_vs_usual == null ? "unknown" : `${side.sponsored_vs_usual.toFixed(2)}×`}</dd>
            <dt className="text-zinc-500">First 24 hours</dt>
            <dd>
              {side.first_day
                ? `${num(side.first_day.median_value_at_24h)} ${youtube ? "views" : "likes"} (${pct(side.first_day.median_share_of_current_total)} of today's total, ${side.first_day.items_with_a_first_day_reading} posts)`
                : "unknown"}
            </dd>
          </dl>
          {side.notes.map((n) => (
            <p key={n} className="mt-1 text-[11px] text-zinc-500">
              {n}
            </p>
          ))}
        </>
      )}
    </div>
  );
}

/** Loads the creator's YouTube and Instagram status on demand, so a result list does not fire dozens of requests. */
export default function PlatformProfileCard({ creatorId }: { creatorId: string }) {
  const [profile, setProfile] = useState<PlatformProfile | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");

  async function load() {
    setState("loading");
    try {
      setProfile(await getPlatformProfile(creatorId));
      setState("idle");
    } catch {
      setState("error");
    }
  }

  if (!profile) {
    return (
      <div className="mt-3">
        <button
          type="button"
          onClick={load}
          disabled={state === "loading"}
          className="rounded-md border border-zinc-300 px-3 py-1 text-xs text-zinc-700 hover:bg-zinc-50 disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          {state === "loading" ? "Loading platform status…" : "Show YouTube vs Instagram status"}
        </button>
        {state === "error" && <span className="ml-2 text-xs text-red-600">could not load</span>}
      </div>
    );
  }
  return (
    <div className="mt-3 text-xs">
      <p className="mb-2 font-medium">{profile.summary}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Side side={profile.youtube} />
        <Side side={profile.instagram} />
      </div>
      <p className="mt-1 text-[11px] text-zinc-500">
        Status compares engagement rate with the other creators we track on that platform. Numbers are medians of the latest posts; nothing is estimated where the data is missing.
      </p>
    </div>
  );
}
