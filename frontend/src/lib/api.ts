import type { AlertResponse, BrandRecommendationRequest, BrandRecommendationResponse } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function postRecommendations(
  body: BrandRecommendationRequest
): Promise<BrandRecommendationResponse> {
  const res = await fetch(`${API_BASE_URL}/recommendations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`POST /recommendations failed: ${res.status}`);
  }
  return res.json();
}

export async function getAlerts(): Promise<AlertResponse[]> {
  const res = await fetch(`${API_BASE_URL}/alerts`);
  if (!res.ok) {
    throw new Error(`GET /alerts failed: ${res.status}`);
  }
  return res.json();
}
