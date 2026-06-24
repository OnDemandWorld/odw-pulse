"""Compute experiment results and recommend winners (TSD §5.17-5.31)."""

from __future__ import annotations

from typing import Any

from pulse.core.experiment.statistics import chi_squared_test


def compute_results(
    experiment: dict[str, Any],
    variants: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute experiment results and recommend a winner.

    Args:
        experiment: Dict with experiment metadata (id, name, hypothesis, etc.)
        variants: List of variant dicts, each with id, name, is_control flag
        events: List of event dicts with variant_id, event_type, visitor_hash

    Returns:
        Dict with variant_results, statistical_analysis, winner_recommendation.
    """
    # Aggregate metrics per variant
    variant_metrics: dict[str, dict[str, Any]] = {}

    for variant in variants:
        vid = str(variant["id"])
        variant_metrics[vid] = {
            "variant_id": vid,
            "variant_name": variant["name"],
            "is_control": variant.get("is_control", False),
            "visitors": set(),
            "conversions": 0,
            "impressions": 0,
            "clicks": 0,
        }

    # Count events
    for event in events:
        vid = str(event.get("variant_id"))
        if vid not in variant_metrics:
            continue

        visitor = event.get("visitor_hash", "")
        event_type = event.get("event_type", "")

        if visitor:
            variant_metrics[vid]["visitors"].add(visitor)

        if event_type == "conversion":
            variant_metrics[vid]["conversions"] += 1
        elif event_type == "impression":
            variant_metrics[vid]["impressions"] += 1
        elif event_type == "click":
            variant_metrics[vid]["clicks"] += 1

    # Convert visitor sets to counts
    for metrics in variant_metrics.values():
        metrics["visitor_count"] = len(metrics["visitors"])
        del metrics["visitors"]  # Don't serialize sets

    # Find control and treatment
    control = None
    treatments = []

    for metrics in variant_metrics.values():
        if metrics["is_control"]:
            control = metrics
        else:
            treatments.append(metrics)

    # Statistical analysis
    statistical_analyses = []

    if control and treatments:
        for treatment in treatments:
            analysis = chi_squared_test(
                control_conversions=control["conversions"],
                control_total=control["visitor_count"],
                treatment_conversions=treatment["conversions"],
                treatment_total=treatment["visitor_count"],
            )
            statistical_analyses.append({
                "control_variant": control["variant_name"],
                "treatment_variant": treatment["variant_name"],
                **analysis,
            })

    # Determine winner
    winner_recommendation = _recommend_winner(variant_metrics, statistical_analyses)

    return {
        "experiment_id": experiment.get("id"),
        "experiment_name": experiment.get("name"),
        "variant_results": list(variant_metrics.values()),
        "statistical_analyses": statistical_analyses,
        "winner_recommendation": winner_recommendation,
    }


def _recommend_winner(
    variant_metrics: dict[str, dict[str, Any]],
    statistical_analyses: list[dict[str, Any]],
) -> dict[str, Any]:
    """Recommend a winner based on conversion rates and statistical significance.

    Returns:
        Dict with recommended_variant, confidence, reason.
    """
    if not variant_metrics:
        return {
            "recommended_variant": None,
            "confidence": 0.0,
            "reason": "No variants to analyze",
        }

    # Calculate conversion rates
    conversion_rates = {}
    for vid, metrics in variant_metrics.items():
        visitors = metrics["visitor_count"]
        conversions = metrics["conversions"]
        rate = conversions / visitors if visitors > 0 else 0.0
        conversion_rates[vid] = {
            "rate": rate,
            "name": metrics["variant_name"],
            "is_control": metrics["is_control"],
            "conversions": conversions,
            "visitors": visitors,
        }

    # Find best performing variant
    best_vid = max(conversion_rates, key=lambda k: conversion_rates[k]["rate"])
    best_variant = conversion_rates[best_vid]

    # Check if any analysis is statistically significant
    significant_results = [a for a in statistical_analyses if a.get("is_significant", False)]

    if significant_results:
        # Use the first significant result
        analysis = significant_results[0]
        confidence = analysis.get("confidence_level", 0.0)
        treatment_name = analysis.get("treatment_variant")

        # Determine which variant won in the significant result
        if treatment_name == best_variant["name"]:
            return {
                "recommended_variant": best_variant["name"],
                "confidence": confidence,
                "reason": f"Statistically significant winner with {confidence:.1%} confidence",
            }
        else:
            # Control won
            control_name = analysis.get("control_variant")
            return {
                "recommended_variant": control_name,
                "confidence": confidence,
                "reason": f"Control is statistically significantly better with {confidence:.1%} confidence",
            }

    # No significant result yet
    return {
        "recommended_variant": best_variant["name"],
        "confidence": 0.0,
        "reason": f"Best performing variant ({best_variant['rate']:.1%} conversion rate) but not statistically significant yet",
        "conversion_rate": best_variant["rate"],
    }
