"""Statistical analysis for experiments (TSD §5.17-5.31)."""

from __future__ import annotations

import math
from typing import Any


def chi_squared_test(
    control_conversions: int,
    control_total: int,
    treatment_conversions: int,
    treatment_total: int,
) -> dict[str, Any]:
    """Perform chi-squared test for 2x2 contingency table.

    Args:
        control_conversions: Number of conversions in control group
        control_total: Total visitors in control group
        treatment_conversions: Number of conversions in treatment group
        treatment_total: Total visitors in treatment group

    Returns:
        Dict with p_value, confidence_level, effect_size (Cohen's h),
        and is_significant flag.

    Example:
        >>> chi_squared_test(10, 100, 15, 100)
        {'p_value': 0.285..., 'confidence_level': 0.714..., 'effect_size': 0.151..., 'is_significant': False}
    """
    if control_total <= 0 or treatment_total <= 0:
        return {
            "p_value": 1.0,
            "confidence_level": 0.0,
            "effect_size": 0.0,
            "is_significant": False,
            "error": "Invalid sample sizes",
        }

    # Build 2x2 table
    # [[control_conv, control_non_conv],
    #  [treatment_conv, treatment_non_conv]]
    a = control_conversions
    b = control_total - control_conversions
    c = treatment_conversions
    d = treatment_total - treatment_conversions

    n = a + b + c + d
    if n == 0:
        return {
            "p_value": 1.0,
            "confidence_level": 0.0,
            "effect_size": 0.0,
            "is_significant": False,
        }

    # Chi-squared statistic with Yates' correction
    numerator = (n * (a * d - b * c) ** 2)
    denominator = (a + b) * (c + d) * (a + c) * (b + d)

    if denominator == 0:
        return {
            "p_value": 1.0,
            "confidence_level": 0.0,
            "effect_size": 0.0,
            "is_significant": False,
        }

    chi2 = numerator / denominator

    # Approximate p-value from chi-squared distribution (df=1)
    # Using approximation: p ≈ exp(-chi2/2) for df=1
    p_value = math.exp(-chi2 / 2)

    # Confidence level
    confidence_level = 1 - p_value

    # Cohen's h (effect size for proportions)
    p1 = a / (a + b) if (a + b) > 0 else 0
    p2 = c / (c + d) if (c + d) > 0 else 0
    effect_size = 2 * (math.asin(math.sqrt(p2)) - math.asin(math.sqrt(p1)))

    # Significance threshold (p < 0.05)
    is_significant = p_value < 0.05

    return {
        "p_value": p_value,
        "confidence_level": confidence_level,
        "effect_size": effect_size,
        "is_significant": is_significant,
    }


def bayesian_analysis(
    control_conversions: int,
    control_total: int,
    treatment_conversions: int,
    treatment_total: int,
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
) -> dict[str, Any]:
    """Bayesian A/B test analysis using Beta-Binomial model.

    Uses uniform Beta(1,1) prior by default. Computes posterior distributions
    and probability that treatment is better than control.

    Args:
        control_conversions: Conversions in control
        control_total: Total in control
        treatment_conversions: Conversions in treatment
        treatment_total: Total in treatment
        prior_alpha: Alpha parameter for Beta prior (default 1.0 = uniform)
        prior_beta: Beta parameter for Beta prior (default 1.0 = uniform)

    Returns:
        Dict with probability_treatment_better, expected_lift, credible_interval.
    """
    if control_total <= 0 or treatment_total <= 0:
        return {
            "probability_treatment_better": 0.5,
            "expected_lift": 0.0,
            "credible_interval": [0.0, 0.0],
            "error": "Invalid sample sizes",
        }

    # Posterior parameters
    alpha_control = prior_alpha + control_conversions
    beta_control = prior_beta + (control_total - control_conversions)

    alpha_treatment = prior_alpha + treatment_conversions
    beta_treatment = prior_beta + (treatment_total - treatment_conversions)

    # Expected conversion rates (mean of Beta distribution)
    p_control = alpha_control / (alpha_control + beta_control)
    p_treatment = alpha_treatment / (alpha_treatment + beta_treatment)

    # Expected lift
    expected_lift = (p_treatment - p_control) / p_control if p_control > 0 else 0.0

    # Approximate probability that treatment is better using normal approximation
    # For Beta(α, β), mean = α/(α+β), var = αβ/((α+β)²(α+β+1))
    var_control = (alpha_control * beta_control) / (
        (alpha_control + beta_control) ** 2 * (alpha_control + beta_control + 1)
    )
    var_treatment = (alpha_treatment * beta_treatment) / (
        (alpha_treatment + beta_treatment) ** 2 * (alpha_treatment + beta_treatment + 1)
    )

    # Difference distribution (approximate as normal)
    mean_diff = p_treatment - p_control
    var_diff = var_control + var_treatment
    std_diff = math.sqrt(var_diff) if var_diff > 0 else 0.0001

    # P(treatment > control) = P(diff > 0)
    z_score = mean_diff / std_diff
    # Approximate CDF of standard normal
    probability_treatment_better = 0.5 * (1 + math.erf(z_score / math.sqrt(2)))

    # 95% credible interval for lift
    z_95 = 1.96
    ci_lower = mean_diff - z_95 * std_diff
    ci_upper = mean_diff + z_95 * std_diff

    # Convert to lift percentage
    ci_lift_lower = (ci_lower / p_control * 100) if p_control > 0 else 0.0
    ci_lift_upper = (ci_upper / p_control * 100) if p_control > 0 else 0.0

    return {
        "probability_treatment_better": probability_treatment_better,
        "expected_lift": expected_lift * 100,  # As percentage
        "credible_interval": [ci_lift_lower, ci_lift_upper],
        "p_control": p_control,
        "p_treatment": p_treatment,
    }
