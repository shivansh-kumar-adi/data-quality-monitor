"""Scorer: turns per-dimension check counts into 0-100 quality scores.

Input  (stats): {"completeness": {"checked": 100, "failed": 10}, ...}
Output (scores): {"completeness": 90.0, "validity": ..., "uniqueness": ..., "overall": ...}

Dimension score = (checked - failed) / checked * 100.
Overall score   = weighted average of the dimension scores. A dimension with
no checks is None and is left out; the remaining weights are re-normalised, so
a config with only a few rule types still gives a sensible overall score.
"""
from __future__ import annotations

DIMENSIONS = ("completeness", "validity", "uniqueness")
DEFAULT_WEIGHTS = {"completeness": 0.4, "validity": 0.4, "uniqueness": 0.2}


def stats_from_per_rule(per_rule: list[dict]) -> dict:
    """Add up checked/failed per dimension from the rules engine output."""
    stats: dict[str, dict] = {}
    for r in per_rule:
        d = stats.setdefault(r["dimension"], {"checked": 0, "failed": 0})
        d["checked"] += r["checked"]
        d["failed"] += r["failed"]
    return stats


def score(stats: dict, weights: dict | None = None) -> dict:
    weights = DEFAULT_WEIGHTS if weights is None else weights

    scores: dict[str, float | None] = {}
    for dim in DIMENSIONS:
        s = stats.get(dim)
        if s and s["checked"]:
            scores[dim] = round(100 * (s["checked"] - s["failed"]) / s["checked"], 2)
        else:
            scores[dim] = None

    used = {d: float(weights.get(d, 0)) for d in DIMENSIONS if scores[d] is not None}
    total = sum(used.values())
    scores["overall"] = round(sum(scores[d] * w for d, w in used.items()) / total, 2) if total > 0 else None
    return scores
