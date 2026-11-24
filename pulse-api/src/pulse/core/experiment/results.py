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
            "converting_visitors": set(),
            "impressions": 0,
            "clicks": 0,
        }

    # Count events. Audit finding #43: conversions are deduplicated per
    # visitor (repeat conversion events must not inflate rates above 100%).
    # Rows may carry a "count" from SQL pre-aggregation (audit finding #29).
    anon_seq = 0
    for event in events:
        vid = str(event.get("variant_id"))
        if vid not in variant_metrics:
            continue

        visitor = event.get("visitor_hash", "")
        event_type = event.get("event_type", "")
        count = int(event.get("count", 1))

        if visitor:
            variant_metrics[vid]["visitors"].add(visitor)

        if event_type == "conversion":
            if visitor:
                variant_metrics[vid]["converting_visitors"].add(visitor)
            else:
                # Anonymous server-side conversions: each counts as its own
                # visitor so conversion rates stay <= 1 (audit #10/#43).
                for _ in range(count):
                    anon_seq += 1
                    token = f"__anon_conversion_{anon_seq}"
                    variant_metrics[vid]["visitors"].add(token)
                    variant_metrics[vid]["converting_visitors"].add(token)
        elif event_type == "impression":
            variant_metrics[vid]["impressions"] += count
        elif event_type == "click":
            variant_metrics[vid]["clicks"] += count

    # Convert visitor sets to counts
    for metrics in variant_metrics.values():
        metrics["visitor_count"] = len(metrics["visitors"])
        metrics["conversions"] = len(metrics["converting_visitors"])
        del metrics["visitors"]  # Don't serialize sets
        del metrics["converting_visitors"]

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

    # Check if any analysis is statistically significant. Apply a Bonferroni
    # correction across the treatment comparisons (audit finding #44).
    alpha = 0.05 / max(1, len(statistical_analyses))
    significant_results = [
        a for a in statistical_analyses if a.get("p_value", 1.0) < alpha
    ]

    if significant_results:
        # Audit finding #44: prefer a significant analysis involving the
        # best-rate variant, and decide the winner from THAT pair's own
        # rates. The old code declared "control won" whenever the best-rate
        # arm differed from the first significant treatment — even when the
        # significant test showed the treatment beating control.
        involving_best = [
            a
            for a in significant_results
            if best_variant["name"] in (a.get("control_variant"), a.get("treatment_variant"))
        ]
        analysis = (involving_best or significant_results)[0]
        confidence = analysis.get("confidence_level", 0.0)

        by_name = {info["name"]: info for info in conversion_rates.values()}
        control_info = by_name.get(analysis.get("control_variant", ""))
        treatment_info = by_name.get(analysis.get("treatment_variant", ""))
        if control_info is not None and treatment_info is not None:
            winner = (
                treatment_info
                if treatment_info["rate"] > control_info["rate"]
                else control_info
            )
            return {
                "recommended_variant": winner["name"],
                "confidence": confidence,
                "reason": f"Statistically significant winner with {confidence:.1%} confidence",
            }
        # Names not resolvable to metrics — fall back to the best raw rate.
        return {
            "recommended_variant": best_variant["name"],
            "confidence": confidence,
            "reason": f"Statistically significant result with {confidence:.1%} confidence",
        }

    # No significant result yet
    return {
        "recommended_variant": best_variant["name"],
        "confidence": 0.0,
        "reason": f"Best performing variant ({best_variant['rate']:.1%} conversion rate) but not statistically significant yet",
        "conversion_rate": best_variant["rate"],
    }
