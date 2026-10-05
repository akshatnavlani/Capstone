import type {
  AlertResponse,
  BrandRecommendationRequest,
  BrandRecommendationResponse,
  CreatorSummary,
  GraphEdge,
} from "@/types";
import type { AnalysisData } from "@/types/analysis";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

// Real shape per backend/app/schemas.py:65ec502 + API_CONTRACTS.md P1.6:
// InfluencerRecommendation now carries spillover_basis: "trained"|"inferred"|"placeholder"|"isolated"
// + confidence_low/high combining the uncertainty of all three branches (spillover, sentiment, creator feature)
// in quadrature, clamped [0,100] (backend/app/fusion.py). spillover_score is the 0-1 percentile of the GAIL lift.

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

export async function getCollaborationEdges(): Promise<GraphEdge[]> {
  const res = await fetch(`${API_BASE_URL}/feature-store/edges/collaborations`);
  if (!res.ok) {
    throw new Error(`GET /feature-store/edges/collaborations failed: ${res.status}`);
  }
  return res.json();
}

export async function getCoOccurrenceEdges(): Promise<GraphEdge[]> {
  const res = await fetch(`${API_BASE_URL}/feature-store/edges/co-occurrence`);
  if (!res.ok) {
    throw new Error(`GET /feature-store/edges/co-occurrence failed: ${res.status}`);
  }
  return res.json();
}

export async function getAnalysis(): Promise<AnalysisData> {
  const res = await fetch(`${API_BASE_URL}/analysis`);
  if (!res.ok) {
    throw new Error(`GET /analysis failed: ${res.status}`);
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
