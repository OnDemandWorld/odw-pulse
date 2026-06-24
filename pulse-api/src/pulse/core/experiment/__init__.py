"""Experiment engine core logic (TSD §2.15, §4.14-4.19, §5.17-5.31)."""

from pulse.core.experiment.assignment import assign_variant
from pulse.core.experiment.results import compute_results
from pulse.core.experiment.statistics import bayesian_analysis, chi_squared_test
from pulse.core.experiment.tracking import generate_tracking_url

__all__ = [
    "assign_variant",
    "bayesian_analysis",
    "chi_squared_test",
    "compute_results",
    "generate_tracking_url",
]
