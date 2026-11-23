"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

// Field shape: BrandRecommendationRequest (src/types/index.ts), matching
// Track C's backend/app/schemas.py. On submit, the request goes to /match
// (Live Match) via sessionStorage; /match POSTs to /recommendations and hands
// the response to /dashboard the same way.
// 23 Nov 2026 (brand-friendly version): picture tiles for the product, a budget slider with a plain "what this buys" line
// (published Indian rate-card mid prices, data/cost_rate_card.csv, the same estimates the scores use), the platform choice
// (platform_preference: a hard filter on having a handle there), and the region / audience words folded away with an
// honest note (they are soft keyword filters on bios and channel text, routers/influencers.py).

// Product categories to pick from. `value` is what is sent as product_category: plain keywords, because the backend matches each word against the
// creator's profile text and the CLIP/BERT feature score embeds the same words. Avoid filler words such as "and" (they would match almost every profile).
// 8 Nov 2026 (guide's request, user-friendly dropdown): the fitness and health products listed first, one option per kind of product.
const CATEGORIES = [
  { label: "Fitness and gym", icon: "🏋️", value: "fitness gym workout" },
  { label: "Protein and supplements", icon: "🥤", value: "protein supplement whey nutrition" },
  { label: "Protein bars and healthy snacks", icon: "🍫", value: "protein healthy snack nutrition diet" },
  { label: "Energy and sports drinks", icon: "⚡", value: "energy drink hydration electrolyte" },
  { label: "Running and sports shoes", icon: "👟", value: "shoes running sneakers footwear marathon" },
  { label: "Sportswear and gymwear", icon: "👕", value: "sportswear activewear gymwear athleisure" },
  { label: "Gym and home workout equipment", icon: "🏠", value: "equipment dumbbell gym workout" },
  { label: "Yoga, meditation and wellness", icon: "🧘", value: "yoga meditation wellness" },
  { label: "Health, diet and physiotherapy", icon: "🩺", value: "health diet nutrition physiotherapy doctor" },
  { label: "Cricket and sports gear", icon: "🏏", value: "cricket sports gear" },
  { label: "Badminton, football and other sports", icon: "⚽", value: "badminton football tennis kabaddi athlete sports" },
  { label: "Healthy food and nutrition", icon: "🥗", value: "healthy food nutrition diet protein recipe" },
  { label: "Running, cycling and marathons", icon: "🚴", value: "running marathon cycling endurance" },
  // Fitness and health only (user, 8 Nov 2026): no perfume, gadgets, travel, gaming, finance, entertainment, makeup or fashion.
];
const OTHER = "__other";

// Mid price of one Instagram post or YouTube Short by audience size: the geometric middle of each published range
// (data/cost_rate_card.csv: nano 2k-8k, micro 8k-80k, mid 50k-3.5L, macro 2L-12L), as ml/cost_estimate.py computes it.
const TIERS = [
  { label: "Small creators", size: "10K–100K followers", price: 25298 },
  { label: "Mid-size creators", size: "100K–500K", price: 132288 },
  { label: "Big creators", size: "500K–2M", price: 489898 },
];
const PRESETS = [25000, 50000, 100000, 300000, 500000, 1000000];
const MIN_B = 10000, MAX_B = 2000000;
const toSlider = (b: number) => (100 * Math.log(b / MIN_B)) / Math.log(MAX_B / MIN_B);
const fromSlider = (s: number) => Math.round((MIN_B * Math.pow(MAX_B / MIN_B, s / 100)) / 5000) * 5000 || MIN_B;
const inr = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;
const short = (n: number) => (n >= 1e5 ? `₹${Number((n / 1e5).toFixed(1))}L` : `₹${Math.round(n / 1e3)}K`);
const PLATFORMS = [
  { key: "both", label: "Both", icon: "✨", pref: undefined },
  { key: "youtube", label: "YouTube", icon: "▶️", pref: ["youtube"] as ("youtube" | "instagram")[] },
  { key: "instagram", label: "Instagram", icon: "📸", pref: ["instagram"] as ("youtube" | "instagram")[] },
];

export default function BrandInputPage() {
  const router = useRouter();
  const [categoryChoice, setCategoryChoice] = useState("");
  const [customCategory, setCustomCategory] = useState("");
  const productCategory = categoryChoice === OTHER ? customCategory.trim() : categoryChoice;
  const [budget, setBudget] = useState(300000);
  const [platform, setPlatform] = useState("both");
  const [targetRegion, setTargetRegion] = useState("");
  const [targetDemographic, setTargetDemographic] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const chosen = CATEGORIES.find((c) => c.value === categoryChoice);
  const plat = PLATFORMS.find((p) => p.key === platform)!;
  const ready = !!productCategory && budget > 0;

  // 23 Nov 2026: the request is sent from /match (Live Match), which plays the real matching steps while the backend
  // works and then saves the answer for /dashboard as before.
  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ready) return;
    setError(null);
    setIsSubmitting(true);
    try {
      sessionStorage.setItem(
        "liveMatchRequest",
        JSON.stringify({
          product_category: productCategory,
          budget,
          target_region: targetRegion.trim() || undefined,
          target_demographic: targetDemographic.trim() || undefined,
          platform_preference: plat.pref,
        }),
      );
      router.push("/match");
    } catch {
      setError("Couldn't start the match in this browser.");
      setIsSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-12">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-signal">New brief</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
          Tell us about your campaign
        </h1>
        <p className="mt-2 text-sm text-zinc-400">Three quick choices. We&apos;ll find the creators who fit, and you can watch the search live.</p>
      </header>

      <form onSubmit={handleSubmit} className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="flex flex-col gap-6">
          {/* 1. product */}
          <Step n={1} title="What are you promoting?" done={!!productCategory}>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
              {[...CATEGORIES, { label: "Something else", icon: "✍️", value: OTHER }].map((c, i) => {
                const on = categoryChoice === c.value;
                return (
                  <button
                    key={c.value}
                    type="button"
                    onClick={() => setCategoryChoice(c.value)}
                    aria-pressed={on}
                    className={`lm-row flex items-center gap-2.5 rounded-xl border px-3 py-3 text-left text-sm transition-all hover:-translate-y-0.5 ${
                      on ? "border-accent bg-accent/10 text-zinc-50 shadow-[0_0_20px_rgba(245,184,61,0.25)]" : "border-line bg-background/50 text-zinc-300 hover:border-zinc-500"
                    }`}
                    style={{ animationDelay: `${i * 30}ms` }}
                  >
                    <span className={`text-2xl transition-transform ${on ? "scale-110" : ""}`} aria-hidden>
                      {c.icon}
                    </span>
                    <span className="leading-tight">{c.label}</span>
                  </button>
                );
              })}
            </div>
            {categoryChoice === OTHER && (
              <input
                autoFocus
                value={customCategory}
                onChange={(e) => setCustomCategory(e.target.value)}
                placeholder="e.g. running shoes, protein bars, yoga mats"
                className="lm-fade mt-3 w-full rounded-lg border border-line bg-background px-3 py-2.5 text-sm text-zinc-100 focus:border-accent focus:outline-none"
              />
            )}
            {chosen && <p className="mt-2 text-xs text-zinc-500">We&apos;ll look for creators who talk about: {chosen.value.split(" ").join(", ")}</p>}
          </Step>

          {/* 2. budget */}
          <Step n={2} title="What's your budget?" done={budget > 0}>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-mono text-3xl font-semibold text-zinc-50">{inr(budget)}</span>
              <input
                type="number"
                min={MIN_B}
                step={5000}
                value={budget}
                onChange={(e) => setBudget(Math.max(0, Number(e.target.value) || 0))}
                aria-label="Budget in rupees"
                className="w-36 rounded-lg border border-line bg-background px-3 py-1.5 text-sm text-zinc-100 focus:border-accent focus:outline-none"
              />
            </div>
            <input
              type="range"
              min={0}
              max={100}
              step={0.5}
              value={toSlider(Math.min(MAX_B, Math.max(MIN_B, budget)))}
              onChange={(e) => setBudget(fromSlider(Number(e.target.value)))}
              aria-label="Budget"
              className="mt-3 w-full"
              style={{ accentColor: "#f5b83d" }}
            />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setBudget(p)}
                  className={`rounded-full border px-3 py-1 text-xs transition-colors ${budget === p ? "border-accent bg-accent text-background" : "border-line text-zinc-300 hover:border-accent hover:text-accent"}`}
                >
                  {short(p)}
                </button>
              ))}
            </div>
            <div className="mt-4 grid gap-2 sm:grid-cols-3">
              {TIERS.map((t) => {
                const n = Math.floor(budget / t.price);
                return (
                  <div key={t.label} className={`rounded-xl border p-3 transition-colors ${n > 0 ? "border-signal/40 bg-signal/5" : "border-line opacity-60"}`}>
                    <div className="flex items-baseline gap-1.5">
                      <span className="font-mono text-2xl font-semibold text-zinc-50">{n}</span>
                      <span className="text-xs text-zinc-400">post{n === 1 ? "" : "s"}</span>
                    </div>
                    <div className="text-xs text-zinc-300">{t.label}</div>
                    <div className="text-[11px] text-zinc-500">
                      {t.size} · about {short(t.price)} each
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="mt-2 text-[11px] text-zinc-500">What your budget buys, roughly: one Instagram post or YouTube Short, mid prices from published Indian rate cards.</p>
          </Step>

          {/* 3. platform */}
          <Step n={3} title="Where do you want to post?" done>
            <div className="flex flex-wrap gap-2">
              {PLATFORMS.map((p) => (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => setPlatform(p.key)}
                  aria-pressed={platform === p.key}
                  className={`flex items-center gap-2 rounded-xl border px-5 py-3 text-sm transition-all hover:-translate-y-0.5 ${
                    platform === p.key ? "border-accent bg-accent/10 text-zinc-50 shadow-[0_0_20px_rgba(245,184,61,0.25)]" : "border-line bg-background/50 text-zinc-300 hover:border-zinc-500"
                  }`}
                >
                  <span className="text-xl" aria-hidden>
                    {p.icon}
                  </span>
                  {p.label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-zinc-500">{platform === "both" ? "Creators on either platform." : `Only creators who are on ${plat.label}.`}</p>
          </Step>

          <details className="rounded-2xl border border-line bg-panel p-5">
            <summary className="cursor-pointer text-sm font-medium text-zinc-200">Fine-tune who you reach (optional)</summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-xs text-zinc-400">
                Region words
                <input
                  value={targetRegion}
                  onChange={(e) => setTargetRegion(e.target.value)}
                  placeholder="e.g. Mumbai, Bengaluru, Tamil"
                  className="rounded-lg border border-line bg-background px-3 py-2 text-sm text-zinc-100 focus:border-accent focus:outline-none"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-zinc-400">
                Audience words
                <input
                  value={targetDemographic}
                  onChange={(e) => setTargetDemographic(e.target.value)}
                  placeholder="e.g. women, beginners, students"
                  className="rounded-lg border border-line bg-background px-3 py-2 text-sm text-zinc-100 focus:border-accent focus:outline-none"
                />
              </label>
            </div>
            <p className="mt-2 text-[11px] text-zinc-500">
              We look for these words in creators&apos; bios and channel descriptions. A creator whose bio doesn&apos;t mention them is left out, so leave these empty for the widest
              choice.
            </p>
          </details>
        </div>

        {/* live summary */}
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <div className="flex flex-col gap-4 rounded-2xl border border-accent/40 bg-panel p-5 shadow-[0_0_40px_-20px_rgba(245,184,61,0.6)]">
            <h2 className="text-sm font-semibold uppercase tracking-[0.12em] text-accent">Your brief</h2>
            <Row icon={chosen?.icon ?? (categoryChoice === OTHER ? "✍️" : "❔")} label="Promoting" value={chosen?.label ?? (categoryChoice === OTHER ? customCategory || "Something else" : "Pick a product")} muted={!productCategory} />
            <Row icon="💰" label="Budget" value={inr(budget)} />
            <Row icon={plat.icon} label="Platform" value={plat.label === "Both" ? "YouTube and Instagram" : plat.label} />
            {(targetRegion || targetDemographic) && <Row icon="🎯" label="Reach" value={[targetRegion, targetDemographic].filter(Boolean).join(" · ")} />}
            {error && <p className="text-sm text-red-400">{error}</p>}
            <button
              type="submit"
              disabled={!ready || isSubmitting}
              className="group flex items-center justify-center gap-2 rounded-full bg-accent px-5 py-3.5 text-base font-semibold text-background transition hover:shadow-[0_0_24px_rgba(245,184,61,0.55)] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isSubmitting ? "Starting…" : "Find my creators"}
              <span className="transition-transform group-hover:translate-x-1" aria-hidden>
                →
              </span>
            </button>
            <p className="text-center text-[11px] text-zinc-500">{ready ? "Takes about 20 seconds, and you can watch the search live." : "Pick what you're promoting to continue."}</p>
          </div>
        </aside>
      </form>
    </main>
  );
}

function Step({ n, title, done, children }: { n: number; title: string; done: boolean; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-panel p-5">
      <h2 className="mb-4 flex items-center gap-3 text-lg font-semibold text-zinc-50">
        <span className={`grid h-8 w-8 place-items-center rounded-full text-sm font-bold transition-colors ${done ? "bg-signal text-background" : "bg-line text-zinc-300"}`}>{done ? "✓" : n}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

function Row({ icon, label, value, muted }: { icon: string; label: string; value: string; muted?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-background text-xl" aria-hidden>
        {icon}
      </span>
      <div className="min-w-0">
        <div className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</div>
        <div className={`truncate text-sm ${muted ? "text-zinc-500" : "font-medium text-zinc-100"}`}>{value}</div>
      </div>
    </div>
  );
}
