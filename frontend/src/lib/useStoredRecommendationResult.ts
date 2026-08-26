import { useSyncExternalStore } from "react";
import type { BrandRecommendationResponse } from "@/types";

// sessionStorage is browser-only and can't be read during server prerender;
// useSyncExternalStore is the hydration-safe way to read it (getServerSnapshot
// returns null on the server, then React reconciles with the real client
// value after hydration) without a synchronous setState-in-effect. Shared by
// /dashboard and /explainability, which both read the same brand-input result.
export function useStoredRecommendationResult(): BrandRecommendationResponse | null {
  const raw = useSyncExternalStore(
    () => () => {},
    () => sessionStorage.getItem("recommendationResult"),
    () => null
  );
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as BrandRecommendationResponse;
    // Defensive: old sessionStorage (pre-65ec502) lacks spillover_basis → fallback to "placeholder"
    // so stale cache never crashes rendering. New responses always carry the field.
    if (parsed.results) {
      for (const r of parsed.results) {
        if (!r.spillover_basis) r.spillover_basis = "placeholder";
      }
    }
    return parsed;
  } catch {
    return null;
  }
}
