import type {
  AlertResponse,
  BrandRecommendationRequest,
  BrandRecommendationResponse,
  ClashResult,
  CreatorSummary,
  GraphEdge,
  InsightsData,
  PassportCreatorLite,
  PassportRecord,
  PassportStrip,
  PassportSummary,
  PlatformProfile,
  SpilloverScenario,
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
    // A full list by default; a caller can still pass include_broader_matches: false.
    body: JSON.stringify({ include_broader_matches: true, ...body }),
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

export async function getSpilloverScenario(effect: number): Promise<SpilloverScenario> {
  const res = await fetch(`${API_BASE_URL}/scenario/spillover?effect=${effect}`);
  if (!res.ok) {
    throw new Error(`GET /scenario/spillover failed: ${res.status}`);
  }
  return res.json();
}

export async function getSharedBrandEdges(): Promise<GraphEdge[]> {
  const res = await fetch(`${API_BASE_URL}/feature-store/edges/shared-brand`);
  if (!res.ok) {
    throw new Error(`GET /feature-store/edges/shared-brand failed: ${res.status}`);
  }
  return res.json();
}

export async function getMentionEdges(): Promise<GraphEdge[]> {
  const res = await fetch(`${API_BASE_URL}/feature-store/edges/mentions`);
  if (!res.ok) {
    throw new Error(`GET /feature-store/edges/mentions failed: ${res.status}`);
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

export async function getCreatorSummaries(): Promise<CreatorSummary[]> {
  const res = await fetch(`${API_BASE_URL}/feature-store/creators/summary`);
  if (!res.ok) {
    throw new Error(`GET /feature-store/creators/summary failed: ${res.status}`);
  }
  return res.json();
}

export async function getPlatformProfile(creatorId: string): Promise<PlatformProfile> {
  const res = await fetch(`${API_BASE_URL}/platform-profiles/${creatorId}`);
  if (!res.ok) {
    throw new Error(`GET /platform-profiles/${creatorId} failed: ${res.status}`);
  }
  return res.json();
}

export async function getPassportSummary(): Promise<PassportSummary> {
  const res = await fetch(`${API_BASE_URL}/passport/summary`);
  if (!res.ok) {
    throw new Error(`GET /passport/summary failed: ${res.status}`);
  }
  return res.json();
}

export async function getPassportCreators(): Promise<PassportCreatorLite[]> {
  const res = await fetch(`${API_BASE_URL}/passport/creators`);
  if (!res.ok) {
    throw new Error(`GET /passport/creators failed: ${res.status}`);
  }
  return res.json();
}

export async function getPassport(creatorId: string): Promise<PassportRecord> {
  const res = await fetch(`${API_BASE_URL}/passport/${creatorId}`);
  if (!res.ok) {
    throw new Error(`GET /passport/${creatorId} failed: ${res.status}`);
  }
  return res.json();
}

export async function getClash(product: string): Promise<ClashResult> {
  const res = await fetch(`${API_BASE_URL}/passport/clash?product=${encodeURIComponent(product)}`);
  if (!res.ok) {
    throw new Error(`GET /passport/clash failed: ${res.status}`);
  }
  return res.json();
}

export async function getInsights(): Promise<InsightsData> {
  const res = await fetch(`${API_BASE_URL}/passport/insights`);
  if (!res.ok) {
    throw new Error(`GET /passport/insights failed: ${res.status}`);
  }
  return res.json();
}

export async function getPassportStrip(creatorIds: string[]): Promise<Record<string, PassportStrip>> {
  const qs = creatorIds.map((id) => `ids=${encodeURIComponent(id)}`).join("&");
  const res = await fetch(`${API_BASE_URL}/passport/strip?${qs}`);
  if (!res.ok) {
    throw new Error(`GET /passport/strip failed: ${res.status}`);
  }
  return res.json();
}
