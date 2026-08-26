import type {
  AlertResponse,
  BrandRecommendationRequest,
  BrandRecommendationResponse,
  CreatorSummary,
} from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

// Real shape per backend/app/schemas.py:65ec502 + API_CONTRACTS.md P1.6:
// InfluencerRecommendation now carries spillover_basis: "trained"|"inferred"|"placeholder"|"isolated"
// + confidence_low/high derived from honest small-N hw (trained ±13pts, inferred ±21pts, placeholder/isolated ±10pts
// via margin = hw*100*w1, clamped [0,100]). sentiment_risk_score remains placeholder 0.5 per CAPSTONE_NEXT_STEPS.md:822.

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

export async function getCreators(): Promise<CreatorSummary[]> {
  const res = await fetch(`${API_BASE_URL}/feature-store/creators`);
  if (!res.ok) {
    throw new Error(`GET /feature-store/creators failed: ${res.status}`);
  }
  return res.json();
}
