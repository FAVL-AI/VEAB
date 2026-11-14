"""Statistical power analysis for autonomous embodied agent benchmarking.

Determines the minimum number of seeds/scenarios (N) required to detect
statistically significant reliability differences between agents at specified
alpha (Type I error) and power (1 - beta).
"""
from __future__ import annotations
import math
from typing import Any
from pydantic import BaseModel, Field


class PowerAnalysisResult(BaseModel):
    effect_size_delta: float = Field(description="Minimum detectable difference in verified completion rate (p1 - p2)")
    alpha: float = Field(default=0.05, description="Significance level (Type I error rate)")
    power: float = Field(default=0.80, description="Statistical power (1 - Type II error rate)")
    p1: float = Field(description="Baseline agent verified completion rate")
    p2: float = Field(description="Candidate agent verified completion rate")
    required_seeds_per_scenario: int = Field(description="Minimum seeds per scenario")
    total_trials_needed: int = Field(description="Total trials across all scenarios")
    recommendation: str


def _normal_quantile(p: float) -> float:
    """Rational approximation for normal distribution quantile function (probit)."""
    if p <= 0.0 or p >= 1.0:
        raise ValueError("Probability must be in (0, 1)")
    # Abramowitz and Stegun approximation
    if p < 0.5:
        t = math.sqrt(-2.0 * math.log(p))
        c0, c1, c2 = 2.515517, 0.802853, 0.010328
        d1, d2, d3 = 1.432788, 0.189269, 0.001308
        return -(t - ((c2 * t + c1) * t + c0) / (((d3 * t + d2) * t + d1) * t + 1.0))
    else:
        t = math.sqrt(-2.0 * math.log(1.0 - p))
        c0, c1, c2 = 2.515517, 0.802853, 0.010328
        d1, d2, d3 = 1.432788, 0.189269, 0.001308
        return t - ((c2 * t + c1) * t + c0) / (((d3 * t + d2) * t + d1) * t + 1.0)


def compute_sample_size(
    p1: float = 0.60,
    p2: float = 0.90,
    alpha: float = 0.05,
    power: float = 0.80,
    scenario_count: int = 5
) -> PowerAnalysisResult:
    """Calculate the required seeds per scenario using two-proportion sample size formula."""
    delta = abs(p2 - p1)
    if delta < 0.01:
        raise ValueError("Effect size delta must be >= 0.01")
        
    z_alpha = _normal_quantile(1.0 - alpha / 2.0)
    z_beta = _normal_quantile(power)
    
    # Pooled variance under null + variance under alternative
    p_bar = (p1 + p2) / 2.0
    v_null = 2.0 * p_bar * (1.0 - p_bar)
    v_alt = p1 * (1.0 - p1) + p2 * (1.0 - p2)
    
    # Fleiss / Lehr formulation
    n_total = ((z_alpha * math.sqrt(v_null) + z_beta * math.sqrt(v_alt)) / delta) ** 2
    n_per_group = max(3, math.ceil(n_total))
    
    seeds_per_sc = max(3, math.ceil(n_per_group / max(1, scenario_count)))
    total_trials = seeds_per_sc * scenario_count
    
    rec = (
        f"To detect a {delta:.0%} difference (from {p1:.0%} to {p2:.0%}) at alpha={alpha} "
        f"and power={power:.0%}, evaluate at least {seeds_per_sc} seeds per scenario "
        f"({total_trials} total trials per policy across {scenario_count} scenarios)."
    )
    
    return PowerAnalysisResult(
        effect_size_delta=round(delta, 4),
        alpha=alpha,
        power=power,
        p1=p1,
        p2=p2,
        required_seeds_per_scenario=seeds_per_sc,
        total_trials_needed=total_trials,
        recommendation=rec
    )

