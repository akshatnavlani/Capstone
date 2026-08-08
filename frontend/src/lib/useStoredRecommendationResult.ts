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
  return raw ? (JSON.parse(raw) as BrandRecommendationResponse) : null;
}
