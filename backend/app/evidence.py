"""Evidence grade for a recommendation: how much real data stands behind the score, in four steps (A best, D thinnest).

The score is a blend of three branches, and a creator can have a high score on thin evidence. The grade says so, with the reasons in plain words. It does NOT say the
creator is good: it says how well we know. Points (0-7):

  sentiment   2 = 200+ scored comments, 1 = 20-199, 0 = fewer or none
  feature     2 = scored against the brief (CLIP/BERT with real posts), 0 = neutral placeholder
  platforms   2 = YouTube and Instagram data, 1 = one platform, 0 = none
  spillover   1 = the creator has graph links (trained or inferred), 0 = isolated or placeholder; capped at 1 on purpose: the spillover branch found no effect on the
              real data (30 Oct 2026 tests), so it never counts as strong evidence on its own

A >= 6, B 4-5, C 2-3, D 0-1. Thresholds are judgement calls, not fitted.
"""

from typing import Literal

EvidenceGrade = Literal["A", "B", "C", "D"]

STRONG_COMMENTS = 200
SOME_COMMENTS = 20


def grade_evidence(
    spillover_basis: str,
    temporal_info: dict | None,
    feature_info: dict | None,
    data_coverage: str,
) -> tuple[EvidenceGrade, list[str]]:
    points, notes = 0, []

    n = int(temporal_info.get("n_comments", 0)) if temporal_info and temporal_info.get("basis") == "scored" else 0
    if n >= STRONG_COMMENTS:
        points += 2
        notes.append(f"sentiment from {n:,} scored comments")
    elif n >= SOME_COMMENTS:
        points += 1
        notes.append(f"sentiment from only {n} scored comments")
    else:
        notes.append("no scored comments, sentiment is a neutral placeholder")

    if feature_info and feature_info.get("basis") == "scored":
        points += 2
        notes.append("content match scored from real posts")
    else:
        notes.append("content match is a neutral placeholder")

    platforms = 2 if data_coverage == "youtube+instagram" else 1 if data_coverage in ("youtube", "instagram") else 0
    points += platforms
    notes.append({2: "YouTube and Instagram data collected", 1: f"only {data_coverage} data collected", 0: "no platform data collected"}[platforms])

    if spillover_basis in ("trained", "inferred"):
        points += 1
        notes.append("has graph links; the spillover signal is unvalidated (no effect found on the real data)")
    else:
        notes.append("no graph links, so no spillover signal")

    grade: EvidenceGrade = "A" if points >= 6 else "B" if points >= 4 else "C" if points >= 2 else "D"
    return grade, notes
