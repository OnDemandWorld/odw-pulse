"""Pydantic v2 schemas for experiment endpoints (TSD §2.15, §4.14-4.19)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pulse.models.experiment import ExperimentStatus  # Re-export single source of truth

__all__ = [
    "ExperimentCreate",
    "ExperimentList",
    "ExperimentRead",
    "ExperimentResults",
    "ExperimentStatus",
    "ExperimentVariantCreate",
    "ExperimentVariantRead",
    "PerformanceEventCreate",
    "PerformanceEventBatchCreate",
    "PromoteWinnerResponse",
    "StatisticalAnalysis",
    "VariantResultRead",
    "WinnerRecommendation",
]


# ---------------------------------------------------------------------------
# Variant schemas
# ---------------------------------------------------------------------------


class ExperimentVariantCreate(BaseModel):
    """Schema for creating a variant within an experiment."""

    name: str = Field(..., description="Variant name (unique within experiment)")
    weight: float = Field(default=1.0, ge=0.0, description="Relative traffic weight")
    configuration: dict[str, Any] | None = Field(
        default=None, description="Variant-specific payload (prompt_id, temperature, etc.)"
    )
    is_control: bool = Field(
        default=False, description="Whether this variant is the control/baseline"
    )


class ExperimentVariantRead(BaseModel):
    """Public representation of an experiment variant."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    name: str
    weight: float
    configuration: dict[str, Any] | None = Field(default=None, alias="configuration")
    position: int


# ---------------------------------------------------------------------------
# Experiment schemas
# ---------------------------------------------------------------------------


class ExperimentCreate(BaseModel):
    """Schema for creating a new experiment."""

    name: str = Field(..., description="Experiment name")
    description: str | None = Field(default=None, description="Experiment description")
    hypothesis: str | None = Field(default=None, description="The hypothesis being tested")
    configuration: dict[str, Any] | None = Field(
        default=None, description="Randomisation unit, targeting rules, etc."
    )
    variants: list[ExperimentVariantCreate] = Field(
        default_factory=list, description="Variants to create with the experiment"
    )


class ExperimentRead(BaseModel):
    """Public representation of an experiment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    status: ExperimentStatus
    hypothesis: str | None
    configuration: dict[str, Any] | None = Field(default=None, alias="configuration")
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None
    variants: list[ExperimentVariantRead] = Field(default_factory=list)
    tracking_urls: dict[str, str] | None = Field(
        default=None, description="Variant name → tracking URL (populated after start)"
    )


class ExperimentList(BaseModel):
    """Paginated list of experiments."""

    items: list[ExperimentRead]
    total: int


# ---------------------------------------------------------------------------
# Results schemas
# ---------------------------------------------------------------------------


class VariantResultRead(BaseModel):
    """Aggregated metrics for a single variant."""

    variant_id: uuid.UUID
    variant_name: str
    is_control: bool
    visitor_count: int
    impressions: int
    clicks: int
    conversions: int
    conversion_rate: float = Field(
        default=0.0, description="Conversions / visitors"
    )


class StatisticalAnalysis(BaseModel):
    """Statistical comparison between control and treatment."""

    control_variant: str
    treatment_variant: str
    p_value: float
    confidence_level: float
    effect_size: float
    is_significant: bool


class WinnerRecommendation(BaseModel):
    """Winner recommendation based on statistical analysis."""

    recommended_variant: str | None
    confidence: float
    reason: str


class ExperimentResults(BaseModel):
    """Complete experiment results with winner recommendation."""

    experiment_id: uuid.UUID
    experiment_name: str
    variant_results: list[VariantResultRead]
    statistical_analyses: list[StatisticalAnalysis]
    winner_recommendation: WinnerRecommendation


# ---------------------------------------------------------------------------
# Performance event schemas
# ---------------------------------------------------------------------------


class PerformanceEventCreate(BaseModel):
    """Schema for ingesting a single performance event."""

    experiment_id: uuid.UUID = Field(..., description="Experiment ID")
    variant_id: uuid.UUID = Field(..., description="Variant ID")
    event_type: str = Field(
        ..., description="Event type: impression, click, conversion, revenue, custom"
    )
    visitor_hash: str | None = Field(
        default=None, description="Opaque visitor identifier"
    )
    value: float = Field(default=1.0, description="Numeric value of the metric")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata")


class PerformanceEventBatchCreate(BaseModel):
    """Schema for ingesting a batch of performance events."""

    events: list[PerformanceEventCreate] = Field(
        ..., description="Batch of events to ingest"
    )


# ---------------------------------------------------------------------------
# Promote winner response
# ---------------------------------------------------------------------------


class PromoteWinnerResponse(BaseModel):
    """Response from promoting a winner variant."""

    experiment_id: uuid.UUID
    winner_variant_id: uuid.UUID
    winner_variant_name: str
    confidence: float
    reason: str
