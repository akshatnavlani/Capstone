"use client";

import type { InfluencerRecommendation } from "@/types";

type Grade = NonNullable<InfluencerRecommendation["evidence_grade"]>;

const GRADE_META: Record<Grade, { label: string; className: string }> = {
  A: {
    label: "Evidence A — well covered",
    className: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800",
  },
  B: {
    label: "Evidence B — good",
    className: "bg-sky-100 text-sky-800 border-sky-200 dark:bg-sky-900/30 dark:text-sky-300 dark:border-sky-800",
  },
  C: {
    label: "Evidence C — thin",
    className: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800",
  },
  D: {
    label: "Evidence D — very thin",
    className: "bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-900/30 dark:text-rose-300 dark:border-rose-800",
  },
};

/** A-D: how much real data stands behind a score. Says how well we know the creator, not how good they are. */
export default function EvidenceBadge({ grade }: { grade: Grade }) {
  const meta = GRADE_META[grade];
  return (
    <span
      title="How much real data stands behind this score (comments, posts, platforms, graph links). It says how well we know the creator, not how good they are."
      className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${meta.className}`}
    >
      {meta.label}
    </span>
  );
}
