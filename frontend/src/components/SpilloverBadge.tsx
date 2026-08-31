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

function tooltipCopy(basis: SpilloverBasis, influencerName?: string): string {
  const name = influencerName ? ` for ${influencerName}` : "";
  switch (basis) {
    case "trained":
      return `Based on real collaboration data${name} — this score was directly learned from labeled examples.`;
    case "inferred":
      return `Estimated${name} from similar creators they collaborate with — not directly trained, so treat the score as a wider estimate.`;
    case "isolated":
      return `No collaboration data available${name} — we show a neutral default instead of guessing.`;
    case "placeholder":
    default:
      return `Default score${name} — no collaboration signal was available to personalize this.`;
  }
}

export function basisLabel(basis: SpilloverBasis): string {
  return BASIS_META[basis]?.label ?? basis;
}

export default function SpilloverBadge({
  basis,
  compact = false,
  influencerName,
}: {
  basis: SpilloverBasis;
  compact?: boolean;
  influencerName?: string;
}) {
  const meta = BASIS_META[basis] ?? BASIS_META.placeholder;
  const copy = tooltipCopy(basis, influencerName);
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
        </span>
      )}
    </span>
  );
}

export function isolatedNote(): string {
  return "no graph signal — degree 0 on collaborates_with + co_occurs_with (IsolatedCreatorError → placeholder 0.5, never inferred)";
}
