"use client";

import { useState, useRef, useId } from "react";
import type { SpilloverBasis } from "@/types";

const BASIS_META: Record<
  SpilloverBasis,
  { label: string; className: string; short: string }
> = {
  trained: {
    label: "Trained — N=10",
    short: "Trained",
    className:
      "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800",
  },
  inferred: {
    label: "Inferred — wide CI",
    short: "Inferred — wide CI",
    className:
      "bg-violet-100 text-violet-800 border-violet-200 dark:bg-violet-900/30 dark:text-violet-300 dark:border-violet-800",
  },
  placeholder: {
    label: "Placeholder",
    short: "Placeholder",
    className:
      "bg-zinc-100 text-zinc-700 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:border-zinc-700",
  },
  isolated: {
    label: "Placeholder — no graph signal",
    short: "Isolated — no signal",
    className:
      "bg-zinc-100 text-zinc-600 border-zinc-300 border-dashed dark:bg-zinc-800 dark:text-zinc-500 dark:border-zinc-600",
  },
};

const TOOLTIP_COPY: Record<SpilloverBasis, string> = {
  trained:
    "Trained on the GAIL labeled set (effective N=10). The score shown is the creator's percentile among graph-connected creators; the interval is the GAIL prediction interval (small-N, so wide) mapped to the same percentile scale. Do not present as validated beyond this N.",
  inferred:
    "Graph-connected but unlabeled — GAT inductive (no retrain). Shown as a percentile among graph-connected creators; the interval is 1.6× the trained one. Do not present as validated — wide CI by design.",
  placeholder:
    "Checkpoint missing or fallback: neutral 0.5 with the widest interval. No GAIL signal — honest placeholder, never fabricated.",
  isolated:
    'Isolated creator (degree 0 on collaborates_with + co_occurs_with). No spillover can be inferred — IsolatedCreatorError mapped to neutral 0.5 with the widest interval. Shown as "no graph signal", never as inferred.',
};

export function basisLabel(basis: SpilloverBasis): string {
  return BASIS_META[basis]?.label ?? basis;
}

export default function SpilloverBadge({
  basis,
  compact = false,
}: {
  basis: SpilloverBasis;
  compact?: boolean;
}) {
  const meta = BASIS_META[basis] ?? BASIS_META.placeholder;
  const copy = TOOLTIP_COPY[basis] ?? TOOLTIP_COPY.placeholder;
  const [open, setOpen] = useState(false);
  const id = useId();
  const tooltipId = `spillover-tip-${id}`;
  const triggerRef = useRef<HTMLButtonElement>(null);

  return (
    <span className="relative inline-flex">
      <button
        ref={triggerRef}
        type="button"
        aria-describedby={open ? tooltipId : undefined}
        aria-expanded={open}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((v) => !v)}
        className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400 ${meta.className}`}
      >
        {compact ? meta.short : meta.label}
        <span
          aria-hidden
          className="ml-0.5 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-white/60 text-[10px] leading-none dark:bg-black/20"
        >
          ?
        </span>
      </button>
      {open && (
        <span
          id={tooltipId}
          role="tooltip"
          className="absolute left-1/2 top-full z-20 mt-2 w-72 -translate-x-1/2 rounded-md border border-zinc-200 bg-white px-3 py-2 text-xs leading-relaxed text-zinc-700 shadow-lg dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
        >
          <span className="font-medium">{meta.label}:</span> {copy}
          <span className="mt-1 block text-[11px] text-zinc-500 dark:text-zinc-400">
            The final score also uses sentiment (Temporal) and creator feature (CLIP/BERT); the interval combines all three.
          </span>
        </span>
      )}
    </span>
  );
}

export function isolatedNote(): string {
  return "no graph signal — degree 0 on collaborates_with + co_occurs_with (IsolatedCreatorError → placeholder 0.5, never inferred)";
}
