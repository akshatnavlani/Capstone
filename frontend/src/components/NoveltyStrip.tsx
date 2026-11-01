import type { PassportStrip } from "@/types";

// A row of small facts under a dashboard card (1 Nov 2026): what the Creator Passport knows about this creator. Each chip says so when it has nothing to say; none of them changes the score.
type Tone = "good" | "warn" | "plain";

function Chip({ label, value, tone = "plain", title }: { label: string; value: string; tone?: Tone; title: string }) {
  const tones: Record<Tone, string> = {
    good: "border-signal/40 text-signal",
    warn: "border-accent/50 text-accent",
    plain: "border-line text-zinc-400",
  };
  return (
    <span title={title} className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] leading-none ${tones[tone]}`}>
      <span className="uppercase tracking-wider text-zinc-500">{label}</span>
      <span className="font-mono text-[11px]">{value}</span>
    </span>
  );
}

export default function NoveltyStrip({ s }: { s: PassportStrip | undefined }) {
  if (!s) return null;
  const gap = s.mood?.gap;
  return (
    <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Creator Passport facts">
      <Chip
        label="Mood gap"
        value={gap === null || gap === undefined ? "n/a" : `${gap >= 0 ? "+" : ""}${gap.toFixed(2)}`}
        tone={s.mood?.significant ? "warn" : "plain"}
        title={s.mood?.significant ? `${s.mood.label}. Instagram minus YouTube comment mood; flagged because it is large and beyond a worst-case error bound.` : gap === null || gap === undefined ? "Comment mood is not scored on both platforms." : "No clear difference between the platforms."}
      />
      <Chip
        label="Day-1 views"
        value={s.speed_first_24h === null ? "n/a" : `${Math.round(100 * s.speed_first_24h)}%`}
        title="Share of a video's first-week views that arrive in the first 24 hours (YouTube)."
      />
      <Chip
        label="Ad load"
        value={s.ad_load ? (s.ad_load.above_usual ? "above usual" : "usual") : "n/a"}
        tone={s.ad_load?.above_usual ? "warn" : "plain"}
        title={s.ad_load ? `${s.ad_load.sponsored_last_30d} sponsored posts in the last 30 days against ${s.ad_load.usual_per_30d.toFixed(1)} usual. Our group test finds no clear drop in views from heavier ad load, so this is a fact, not a forecast.` : "No detected sponsored posts."}
      />
      <Chip
        label="Sponsored"
        value={s.sponsored_views_percent === null ? "n/a" : `${s.sponsored_views_percent >= 0 ? "+" : ""}${Math.round(s.sponsored_views_percent)}% views`}
        title="Views of this creator's sponsored YouTube posts against their own organic posts of the same format. n/a when there are too few sponsored posts."
      />
      <Chip
        label="Links"
        value={String(s.linked_creators)}
        tone={s.linked_creators > 0 ? "good" : "plain"}
        title="Creators linked to this one by collaboration or @mention. Spillover is context only and does not change the score."
      />
    </div>
  );
}
