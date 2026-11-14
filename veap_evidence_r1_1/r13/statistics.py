"""VEAP R1.3 scene-clustered statistical inference and prospective power analysis.

Treats independently authored scenes (not frames, seeds, or correlated condition
variants) as the primary unit of generalisation.
"""
from __future__ import annotations

import math
import random
from typing import Any


def wilson_ci_95(successes: int, total: int) -> tuple[float, float]:
    """Return 95% Wilson score confidence interval for a binomial proportion."""
    if total <= 0:
        return (0.0, 1.0)
    z = 1.959963984540054
    phat = successes / total
    denom = 1.0 + (z * z) / total
    center = (phat + (z * z) / (2.0 * total)) / denom
    half = (z * math.sqrt((phat * (1.0 - phat) + (z * z) / (4.0 * total)) / total)) / denom
    return (round(max(0.0, center - half), 6), round(min(1.0, center + half), 6))


def _exact_two_sided_sign_p_value(wins_a: int, wins_b: int) -> float:
    """Exact two-sided binomial sign test p-value on discordant scene pairs."""
    n = wins_a + wins_b
    if n == 0:
        return 1.0
    k = min(wins_a, wins_b)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2.0 ** n)
    return round(min(1.0, 2.0 * tail), 6)


def scene_cluster_paired_comparison(
    scene_scores_a: dict[str, float],
    scene_scores_b: dict[str, float],
    n_bootstrap: int = 1000,
    seed: int = 20261114,
) -> dict[str, Any]:
    """Compare two methods using scene clusters as the unit of independence."""
    scenes = sorted(set(scene_scores_a).intersection(scene_scores_b))
    n_scenes = len(scenes)
    if n_scenes == 0:
        raise ValueError("No overlapping scenes for paired comparison")

    diffs = [float(scene_scores_a[s]) - float(scene_scores_b[s]) for s in scenes]
    mean_a = sum(float(scene_scores_a[s]) for s in scenes) / n_scenes
    mean_b = sum(float(scene_scores_b[s]) for s in scenes) / n_scenes
    mean_diff = sum(diffs) / n_scenes

    wins_a = sum(1 for d in diffs if d > 1e-9)
    wins_b = sum(1 for d in diffs if d < -1e-9)
    ties = n_scenes - wins_a - wins_b

    rng = random.Random(seed)
    boot_means: list[float] = []
    for _ in range(n_bootstrap):
        sample = [diffs[rng.randrange(n_scenes)] for _ in range(n_scenes)]
        boot_means.append(sum(sample) / n_scenes)
    boot_means.sort()
    lo_idx = max(0, int(0.025 * n_bootstrap))
    hi_idx = min(n_bootstrap - 1, int(0.975 * n_bootstrap))

    return {
        "unit_of_analysis": "scene_cluster",
        "n_independent_scenes": n_scenes,
        "mean_score_a": round(mean_a, 6),
        "mean_score_b": round(mean_b, 6),
        "mean_paired_difference": round(mean_diff, 6),
        "bootstrap_95_ci": [round(boot_means[lo_idx], 6), round(boot_means[hi_idx], 6)],
        "discordant_scenes": {"a_better": wins_a, "b_better": wins_b, "tied": ties},
        "exact_sign_test_p_value": _exact_two_sided_sign_p_value(wins_a, wins_b),
    }


def prospective_scene_sample_size(
    pilot_sd: float = 0.25,
    minimum_detectable_effect: float = 0.10,
    alpha_two_sided: float = 0.05,
    power: float = 0.80,
) -> dict[str, Any]:
    """Compute required independent scene count N for confirmatory R1.3 evaluation."""
    if minimum_detectable_effect <= 0:
        raise ValueError("minimum_detectable_effect must be positive")
    # Standard normal quantiles for alpha=0.05 (1.96) and beta=0.20 (0.8416)
    z_alpha = 1.959963984540054 if abs(alpha_two_sided - 0.05) < 1e-6 else 2.5758293035489004
    z_beta = 0.8416212335729143 if abs(power - 0.80) < 1e-6 else 1.2815515655446004
    effective_sd = max(0.15, float(pilot_sd))
    raw_n = ((z_alpha + z_beta) * effective_sd / minimum_detectable_effect) ** 2
    # Add 15% finite-sample / non-parametric safety buffer and round up
    required_scenes = max(30, int(math.ceil(raw_n * 1.15)))
    return {
        "unit_of_generalisation": "independently_authored_scene",
        "alpha_two_sided": alpha_two_sided,
        "target_power": power,
        "assumed_scene_diff_sd": round(effective_sd, 4),
        "minimum_detectable_effect": round(minimum_detectable_effect, 4),
        "unadjusted_normal_n": int(math.ceil(raw_n)),
        "recommended_confirmatory_scenes": required_scenes,
        "total_condition_evaluations_4x": required_scenes * 4,
    }
