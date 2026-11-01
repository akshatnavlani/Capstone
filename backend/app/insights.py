"""Chart data for the Insights page (1 Nov 2026). Read-only: collects numbers that already exist in the result files in models/ (nothing is computed here that is not in a file, and nothing changes a score).

Every block names its source file so a chart can always be traced back. Simulated results are marked "simulated": the frontend must label them so.
"""
import json
import statistics as st
from pathlib import Path
from typing import Any, Optional

MODELS = Path(__file__).resolve().parents[2] / "models"

# short labels for the spillover journey, keyed by the number of exposed observations of that run
JOURNEY_LABELS = {11: "30 Oct: fitness rule", 12: "30 Oct: after catch-up", 18: "30 Oct: all brands", 19: "30 Oct night: new links", 60: "31 Oct: mined collaborators", 74: "1 Nov: corrected labels"}
JOURNEY_KEEP = (12, 19, 60, 74)
SETTINGS = (("effect 1.0, clean", "effect1", "clean"), ("effect 1.0, trend", "effect1", "pretrend"), ("no effect, clean", "effect0", "clean"), ("no effect, trend", "effect0", "pretrend"))
METHODS = (("Naive difference", "Naive difference"), ("GNN predictor", "GNN predictor (no causal training)"), ("Doubly robust, no graph", "DR, no graph"),
           ("GAIL v1", "GAIL v1 (current)"), ("GAIL-R", "GAIL-R"), ("GAIL-R + placebo", "GAIL-R + placebo"))


def _load(name: str) -> Optional[Any]:
    try:
        return json.loads((MODELS / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _mean_error(rows: Any) -> Optional[float]:
    vals = [r["ate_error"] for r in (rows or []) if isinstance(r, dict) and r.get("ate_error") is not None]
    return round(st.mean(vals), 4) if vals else None


def build() -> dict:
    out: dict[str, Any] = {}

    runs = (_load("gail_real_results.json") or {}).get("runs", [])
    seen, journey = set(), []
    for r in sorted(runs, key=lambda r: r.get("exposed", 0)):
        n = r.get("exposed")
        if n in JOURNEY_KEEP and n not in seen and r.get("gail_r_ci95"):
            seen.add(n)
            journey.append({"label": JOURNEY_LABELS.get(n, r.get("name", "")[:40]), "exposed": n, "effect": r["gail_r_effect"], "lo": r["gail_r_ci95"][0], "hi": r["gail_r_ci95"][1]})
    out["spillover_journey"] = {"source": "models/gail_real_results.json", "rows": journey}

    files = {"effect1": _load("semisynth_new_graph_effect1.json"), "effect0": _load("semisynth_new_graph_effect0.json")}
    bench = []
    for label, key, scen in SETTINGS:
        block = (files.get(key) or {}).get(scen, {})
        bench.append({"setting": label, "errors": {m: _mean_error(block.get(src)) for m, src in METHODS}})
    out["benchmark"] = {"source": "models/semisynth_new_graph_effect*.json", "simulated": True, "metric": "average error of the estimated effect on the exposed (lower is better)", "methods": [m for m, _ in METHODS], "settings": bench}
    out["published_baselines"] = _load("published_baselines_eesha.json")

    p = _load("power_analysis.json") or {}
    shares = (p.get("real_structure") or {}).get("share_detected", {})
    out["power"] = {"source": "models/power_analysis.json", "simulated": True, "effects": [0.0, 0.25, 0.5, 0.75, 1.0, 1.5], "real_exposed": p.get("real_exposed"),
                    "series": [{"n": int(n), "share": v} for n, v in sorted(shares.items(), key=lambda kv: int(kv[0]))]}

    passport = _load("creator_passport.json") or {}
    creators = passport.get("creators", [])
    gaps = [{"gap": c["mood"]["gap"], "flagged": bool(c["mood"].get("significant"))} for c in creators if c.get("mood") and c["mood"].get("gap") is not None]
    speeds = [c["speed"]["share_first_24h"] for c in creators if c.get("speed")]
    grades = {g: sum(1 for c in creators if c["evidence"]["grade"] == g) for g in "ABCD"}
    summary = passport.get("summary", {})
    out["passport"] = {"source": "models/creator_passport.json", "as_of": passport.get("as_of"), "creators": len(creators), "mood_gaps": gaps, "speed_shares": speeds, "grades": grades,
                       "sponsored_response": summary.get("sponsored_response"), "prediction": summary.get("prediction"), "mood_gap_summary": summary.get("mood_gap"), "clash": summary.get("clash")}

    fs = _load("fusion_simulation.json") or {}
    out["fusion_simulation"] = {"source": "models/fusion_simulation.json", "simulated": True, "scenarios": fs.get("scenarios", {})}

    e45 = _load("e4_e5_results.json") or {}
    out["extensions"] = {"source": "models/e4_e5_results.json", "simulated": True, "e4": e45.get("e4_simulated"), "e5": e45.get("e5_simulated")}
    return out
