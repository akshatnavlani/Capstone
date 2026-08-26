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
    "Trained on GAIL labeled set (effective N=10, df=8, t=2.306, mse=1.84 → hw≈3.28 on 0-1 scale). Final CI = hw·100·w1 (w1=0.4) → ±13pts, clamped [0,100]. Still wide due small-N and propensity saturates 1.000 (CAPSTONE_NEXT_STEPS:795). See backend/app/fusion.py:57 + API_CONTRACTS.md P1.6. Do not present as validated beyond this N.",
  inferred:
    "Graph-connected but unlabeled — GAT inductive (no retrain). hw≈5.25 (1.6× trained, min 0.25) → ±21pts on final_score, clamped [0,100]. Wide interval reflects small-N and propensity 1.000 (CAPSTONE_NEXT_STEPS:795). Do not present as validated — wide CI by design.",
  placeholder:
    "Checkpoint missing or fallback 0.5 (hw 0.25 → ±10pts). No GAIL signal — honest placeholder, never fabricated.",
  isolated:
    'Isolated creator (degree 0 on collaborates_with + co_occurs_with). No spillover can be inferred — IsolatedCreatorError mapped to placeholder 0.5 (hw 0.25 → ±10pts). Shown as "no graph signal", never as inferred.',
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
            sentiment_risk_score is still placeholder 0.5 (Temporal 0% — CAPSTONE_NEXT_STEPS:822); only w1 real.
          </span>
        </span>
      )}
    </span>
  );
}

export function isolatedNote(): string {
  return "no graph signal — degree 0 on collaborates_with + co_occurs_with (IsolatedCreatorError → placeholder 0.5, never inferred)";
}
