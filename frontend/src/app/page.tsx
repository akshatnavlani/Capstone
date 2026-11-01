"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import SpilloverPlayground from "@/components/home/SpilloverPlayground";

// Home (1 Nov 2026): one headline, one thing to play with, four doors. The headline's second line cycles through what the product promises.

const PROMISES = ["See both platforms.", "Know how sure we are.", "Check the evidence.", "Spot a brand clash."];

const FEATURES = [
  { href: "/passport", tag: "01", title: "Creator Passport", body: "One page per creator: both platforms, mood, speed and an evidence grade." },
  { href: "/insights", tag: "02", title: "Evidence room", body: "Interactive charts of what we found, and how much we could have seen." },
  { href: "/dashboard", tag: "03", title: "Ranked creators", body: "A brief in, a ranked list out, with ranges, grades and clash warnings." },
  { href: "/explainability", tag: "04", title: "Graph and scores", body: "Who links to whom, and how each score is built." },
];

const STEPS = [
  ["Brief", "Product and budget"],
  ["Rank", "Mood, fit, honest range"],
  ["Passport", "Both platforms"],
  ["Evidence", "What we know"],
];

/** A card with a soft light that follows the pointer. */
function SpotlightCard({ href, tag, title, body }: { href: string; tag: string; title: string; body: string }) {
  const ref = useRef<HTMLAnchorElement>(null);
  return (
    <Link
      ref={ref}
      href={href}
      onMouseMove={(e) => {
        const r = ref.current!.getBoundingClientRect();
        ref.current!.style.setProperty("--mx", `${e.clientX - r.left}px`);
        ref.current!.style.setProperty("--my", `${e.clientY - r.top}px`);
      }}
      className="group relative block overflow-hidden rounded-xl border border-line p-5"
      style={{ background: "radial-gradient(260px circle at var(--mx, 50%) var(--my, 0%), rgba(245,184,61,0.12), transparent 65%), var(--panel)" }}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] tracking-[0.16em] text-accent">{tag}</span>
        <span className="text-zinc-600 transition-all duration-200 group-hover:translate-x-1 group-hover:text-accent">→</span>
      </div>
      <h3 className="mt-3 text-lg font-semibold text-zinc-50">{title}</h3>
      <p className="mt-1 text-sm leading-relaxed text-zinc-400">{body}</p>
    </Link>
  );
}

export default function Home() {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t = setInterval(() => setI((v) => (v + 1) % PROMISES.length), 2800);
    return () => clearInterval(t);
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-20 px-5 py-12 sm:px-8 lg:py-20">
      <section className="grid items-center gap-10 lg:grid-cols-[1fr_1.05fr]">
        <div>
          <h1 className="text-5xl font-semibold leading-[1.04] text-zinc-50 sm:text-6xl">
            Pick the right creator.
            <span key={i} className="mt-1 block text-accent" style={{ animation: "rise 420ms cubic-bezier(0.2,0.7,0.2,1) both" }}>
              {PROMISES[i]}
            </span>
          </h1>
          <p className="mt-6 max-w-md text-lg leading-relaxed text-zinc-400">Rank influencers for a brand, compare YouTube and Instagram side by side, and see exactly how sure we are.</p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/brand-input" className="rounded-md bg-accent px-6 py-3 text-sm font-semibold text-[#1a1306] transition hover:-translate-y-0.5 hover:brightness-110">
              Start a brief
            </Link>
            <Link href="/insights" className="rounded-md border border-line px-6 py-3 text-sm font-medium text-zinc-200 transition hover:-translate-y-0.5 hover:border-accent hover:text-accent">
              Evidence room
            </Link>
            <Link href="/passport" className="px-2 py-3 text-sm text-zinc-400 transition-colors hover:text-signal">
              Open a Creator Passport →
            </Link>
          </div>
        </div>
        <SpilloverPlayground />
      </section>

      <section>
        <h2 className="text-2xl font-semibold text-zinc-50">Four ways in</h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {FEATURES.map((f) => (
            <SpotlightCard key={f.href} {...f} />
          ))}
        </div>
      </section>

      <section>
        <ol className="grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-4">
          {STEPS.map(([t, b], n) => (
            <li key={t} className="group bg-panel p-4 transition-colors hover:bg-zinc-900">
              <span className="font-mono text-[11px] text-zinc-500 transition-colors group-hover:text-accent">0{n + 1}</span>
              <div className="mt-1 text-sm font-semibold text-zinc-100">{t}</div>
              <div className="mt-0.5 text-xs text-zinc-400">{b}</div>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
