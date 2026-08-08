"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { postRecommendations } from "@/lib/api";

// Field shape: BrandRecommendationRequest (src/types/index.ts), matching
// Track C's backend/app/schemas.py. On submit, POSTs to /recommendations
// and hands the response to /dashboard via sessionStorage (no shared state
// layer needed for a single-hop flow).

export default function BrandInputPage() {
  const router = useRouter();
  const [productCategory, setProductCategory] = useState("");
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
        <h1 className="text-2xl font-semibold tracking-tight">Brand Input</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Tell us about the product and target audience for this sponsorship.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <Field
          label="Product / Category"
          placeholder="e.g. Running shoes — fitness"
          value={productCategory}
          onChange={setProductCategory}
          required
        />
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
          className="mt-2 w-fit rounded-full bg-foreground px-5 py-3 text-sm font-medium text-background transition-opacity disabled:opacity-50"
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
        className="rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm placeholder:text-zinc-400 dark:border-zinc-700"
      />
    </label>
  );
}
