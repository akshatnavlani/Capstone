"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { postRecommendations } from "@/lib/api";

// Field shape: BrandRecommendationRequest (src/types/index.ts), matching
// Track C's backend/app/schemas.py. On submit, POSTs to /recommendations
// and hands the response to /dashboard via sessionStorage (no shared state
// layer needed for a single-hop flow).

// Product categories to pick from. `value` is what is sent as product_category: plain keywords, because the backend matches each word against the
// creator's profile text and the CLIP/BERT feature score embeds the same words. Avoid filler words such as "and" (they would match almost every profile).
// 8 Nov 2026 (guide's request, user-friendly dropdown): the fitness and health products listed first, one option per kind of product.
const CATEGORIES = [
  { label: "Fitness and gym", value: "fitness gym workout" },
  { label: "Protein and supplements", value: "protein supplement whey nutrition" },
  { label: "Protein bars and healthy snacks", value: "protein healthy snack nutrition diet" },
  { label: "Energy and sports drinks", value: "energy drink hydration electrolyte" },
  { label: "Running and sports shoes", value: "shoes running sneakers footwear marathon" },
  { label: "Sportswear and gymwear", value: "sportswear activewear gymwear athleisure" },
  { label: "Gym and home workout equipment", value: "equipment dumbbell gym workout" },
  { label: "Yoga, meditation and wellness", value: "yoga meditation wellness" },
  { label: "Health, diet and physiotherapy", value: "health diet nutrition physiotherapy doctor" },
  { label: "Cricket and sports gear", value: "cricket sports gear" },
  { label: "Badminton, football and other sports", value: "badminton football tennis kabaddi athlete sports" },
  { label: "Healthy food and nutrition", value: "healthy food nutrition diet protein recipe" },
  { label: "Running, cycling and marathons", value: "running marathon cycling endurance" },
  // Fitness and health only (user, 8 Nov 2026): no perfume, gadgets, travel, gaming, finance, entertainment, makeup or fashion.
];
const OTHER = "__other";

export default function BrandInputPage() {
  const router = useRouter();
  const [categoryChoice, setCategoryChoice] = useState("");
  const [customCategory, setCustomCategory] = useState("");
  const productCategory = categoryChoice === OTHER ? customCategory.trim() : categoryChoice;
  const [budget, setBudget] = useState("");
  const [targetRegion, setTargetRegion] = useState("");
  const [targetDemographic, setTargetDemographic] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const response = await postRecommendations({
        product_category: productCategory,
        budget: Number(budget),
        target_region: targetRegion || undefined,
        target_demographic: targetDemographic || undefined,
      });
      sessionStorage.setItem("recommendationResult", JSON.stringify(response));
      router.push("/dashboard");
    } catch {
      setError(
        "Couldn't reach the recommendation API. Is the Track C backend running at " +
          (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000") +
          "?"
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 px-6 py-16">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Brand Input</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Tell us about the product and target audience for this sponsorship.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6 rounded-2xl border border-zinc-200 p-6 shadow-sm dark:border-zinc-800">
        <label className="flex flex-col gap-2 text-sm">
          <span className="font-medium">
            Product / Category<span className="text-red-500"> *</span>
          </span>
          <select
            value={categoryChoice}
            onChange={(e) => setCategoryChoice(e.target.value)}
            required
            className="rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm transition-colors hover:border-zinc-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30 dark:border-zinc-700 dark:hover:border-zinc-600"
          >
            <option value="" disabled>
              Choose a category
            </option>
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
            <option value={OTHER}>Other (type your own)</option>
          </select>
          {categoryChoice && categoryChoice !== OTHER && (
            <span className="text-xs text-zinc-500">Searches creators for: {categoryChoice.split(" ").join(", ")}</span>
          )}
        </label>
        {categoryChoice === OTHER && (
          <Field label="Your product" placeholder="e.g. running shoes" value={customCategory} onChange={setCustomCategory} required />
        )}
        <Field
          label="Budget (INR)"
          placeholder="e.g. 200000"
          value={budget}
          onChange={setBudget}
          type="number"
          required
        />
        <Field
          label="Target Region (proxy)"
          placeholder="e.g. IN-south — bio/comment language, hashtags, not direct audience analytics"
          value={targetRegion}
          onChange={setTargetRegion}
        />
        <Field
          label="Target Demographic (proxy)"
          placeholder="e.g. 18-24 fitness enthusiasts — posting-time/topic proxy"
          value={targetDemographic}
          onChange={setTargetDemographic}
        />

        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={isSubmitting || !productCategory || !budget}
          className="mt-2 w-fit rounded-full bg-accent px-5 py-3 text-sm font-medium text-background transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? "Getting recommendations…" : "Get Recommendations"}
        </button>
      </form>
    </main>
  );
}

function Field({
  label,
  placeholder,
  value,
  onChange,
  type = "text",
  required = false,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="flex flex-col gap-2 text-sm">
      <span className="font-medium">
        {label}
        {required && <span className="text-red-500"> *</span>}
      </span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm transition-colors placeholder:text-zinc-400 hover:border-zinc-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30 dark:border-zinc-700 dark:hover:border-zinc-600"
      />
    </label>
  );
}
