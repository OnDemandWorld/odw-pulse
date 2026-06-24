"""Experiment management endpoints (TSD §2.15, §4.14-4.19).

* ``POST   /experiments``                     — create experiment
* ``GET    /experiments``                     — list experiments
* ``GET    /experiments/{id}``                — get experiment
* ``PUT    /experiments/{id}``                — update experiment
* ``POST   /experiments/{id}/start``          — start experiment
* ``POST   /experiments/{id}/pause``          — pause experiment
* ``POST   /experiments/{id}/stop``           — stop experiment
* ``GET    /experiments/{id}/results``        — get results
* ``POST   /experiments/{id}/promote-winner`` — promote winner
* ``POST   /performance-events``              — ingest single event
* ``POST   /performance-events/batch``        — ingest batch of events
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.api.deps import CurrentUser, get_db
from pulse.api.schemas.experiment import (
    ExperimentCreate,
    ExperimentList,
    ExperimentRead,
    ExperimentResults,
    PerformanceEventBatchCreate,
    PerformanceEventCreate,
    PromoteWinnerResponse,
    StatisticalAnalysis,
    VariantResultRead,
    WinnerRecommendation,
)
from pulse.services.experiment_service import ExperimentService

router = APIRouter(tags=["experiments"])

_experiment_service = ExperimentService()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _experiment_to_read(
    experiment: object, tracking_urls: dict[str, str] | None = None
) -> ExperimentRead:
    """Convert an Experiment ORM object to an ExperimentRead schema."""
    result = ExperimentRead.model_validate(experiment, from_attributes=True)
    if tracking_urls is not None:
        result.tracking_urls = tracking_urls
    return result


# ---------------------------------------------------------------------------
# POST /experiments
# ---------------------------------------------------------------------------


@router.post(
    "/experiments",
    response_model=ExperimentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_experiment(
    data: ExperimentCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ExperimentRead:
    """Create a new experiment with optional initial variants."""
    experiment = await _experiment_service.create_experiment(
        db=db,
        workspace_id=current_user.workspace_id,
        data=data,
        created_by=current_user.user_id,
    )
    return _experiment_to_read(experiment)


# ---------------------------------------------------------------------------
# GET /experiments
# ---------------------------------------------------------------------------


@router.get("/experiments", response_model=ExperimentList)
async def list_experiments(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ExperimentList:
    """List experiments for the current workspace."""
    items, total = await _experiment_service.list_experiments(
        db=db,
        workspace_id=current_user.workspace_id,
        limit=limit,
        offset=offset,
    )
    return ExperimentList(
        items=[_experiment_to_read(item) for item in items],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /experiments/{id}
# ---------------------------------------------------------------------------


@router.get("/experiments/{experiment_id}", response_model=ExperimentRead)
async def get_experiment(
    experiment_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ExperimentRead:
    """Get an experiment by ID."""
    experiment = await _experiment_service.get_experiment(
        db=db,
        experiment_id=experiment_id,
        workspace_id=current_user.workspace_id,
    )
    return _experiment_to_read(experiment)


# ---------------------------------------------------------------------------
# PUT /experiments/{id}
# ---------------------------------------------------------------------------


@router.put("/experiments/{experiment_id}", response_model=ExperimentRead)
async def update_experiment(
    experiment_id: uuid.UUID,
    data: ExperimentCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ExperimentRead:
    """Update an experiment (only DRAFT experiments can be updated)."""
    experiment = await _experiment_service.get_experiment(
        db=db,
        experiment_id=experiment_id,
        workspace_id=current_user.workspace_id,
    )

    from pulse.models.experiment import ExperimentStatus

    if experiment.status != ExperimentStatus.DRAFT:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft experiments can be updated",
        )

    # Update fields
    experiment.name = data.name
    experiment.description = data.description
    experiment.hypothesis = data.hypothesis
    experiment.configuration = data.configuration

    # Replace variants
    from datetime import UTC, datetime

    from sqlalchemy import delete

    from pulse.models.experiment import ExperimentVariant

    await db.execute(
        delete(ExperimentVariant).where(
            ExperimentVariant.experiment_id == experiment_id
        )
    )

    for position, variant_data in enumerate(data.variants):
        variant = ExperimentVariant(
            id=uuid.uuid4(),
            experiment_id=experiment.id,
            name=variant_data.name,
            weight=variant_data.weight,
            configuration=variant_data.configuration,
            position=position,
        )
        db.add(variant)

    experiment.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(experiment)

    # Reload with variants
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(type(experiment))
        .options(selectinload(type(experiment).variants))
        .where(type(experiment).id == experiment_id)
    )
    experiment = result.scalar_one()

    return _experiment_to_read(experiment)


# ---------------------------------------------------------------------------
# POST /experiments/{id}/start
# ---------------------------------------------------------------------------


@router.post("/experiments/{experiment_id}/start", response_model=ExperimentRead)
async def start_experiment(
    experiment_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    base_url: str = Query(
        "https://example.com",
        description="Base URL for generating tracking URLs",
    ),
) -> ExperimentRead:
    """Start an experiment and generate tracking URLs."""
    experiment = await _experiment_service.start_experiment(
        db=db,
        experiment_id=experiment_id,
        workspace_id=current_user.workspace_id,
        base_url=base_url,
    )

    # Generate tracking URLs
    tracking_urls = await _experiment_service.generate_tracking_urls(
        db=db,
        experiment_id=experiment_id,
        workspace_id=current_user.workspace_id,
        base_url=base_url,
    )

    return _experiment_to_read(experiment, tracking_urls=tracking_urls)


# ---------------------------------------------------------------------------
# POST /experiments/{id}/pause
# ---------------------------------------------------------------------------


@router.post("/experiments/{experiment_id}/pause", response_model=ExperimentRead)
async def pause_experiment(
    experiment_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ExperimentRead:
    """Pause a running experiment."""
    experiment = await _experiment_service.pause_experiment(
        db=db,
        experiment_id=experiment_id,
        workspace_id=current_user.workspace_id,
    )
    return _experiment_to_read(experiment)


# ---------------------------------------------------------------------------
# POST /experiments/{id}/stop
# ---------------------------------------------------------------------------


@router.post("/experiments/{experiment_id}/stop", response_model=ExperimentRead)
async def stop_experiment(
    experiment_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ExperimentRead:
    """Stop an experiment."""
    experiment = await _experiment_service.stop_experiment(
        db=db,
        experiment_id=experiment_id,
        workspace_id=current_user.workspace_id,
    )
    return _experiment_to_read(experiment)


# ---------------------------------------------------------------------------
# GET /experiments/{id}/results
# ---------------------------------------------------------------------------


@router.get("/experiments/{experiment_id}/results", response_model=ExperimentResults)
async def get_experiment_results(
    experiment_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ExperimentResults:
    """Get experiment results with statistical analysis and winner recommendation."""
    results = await _experiment_service.get_results(
        db=db,
        experiment_id=experiment_id,
        workspace_id=current_user.workspace_id,
    )

    variant_results = [
        VariantResultRead(
            variant_id=uuid.UUID(vr["variant_id"]),
            variant_name=vr["variant_name"],
            is_control=vr["is_control"],
            visitor_count=vr["visitor_count"],
            impressions=vr.get("impressions", 0),
            clicks=vr.get("clicks", 0),
            conversions=vr.get("conversions", 0),
            conversion_rate=(
                vr["conversions"] / vr["visitor_count"]
                if vr["visitor_count"] > 0
                else 0.0
            ),
        )
        for vr in results["variant_results"]
    ]

    statistical_analyses = [
        StatisticalAnalysis(**sa) for sa in results["statistical_analyses"]
    ]

    winner_rec = results["winner_recommendation"]
    winner_recommendation = WinnerRecommendation(
        recommended_variant=winner_rec.get("recommended_variant"),
        confidence=winner_rec.get("confidence", 0.0),
        reason=winner_rec.get("reason", ""),
    )

    return ExperimentResults(
        experiment_id=uuid.UUID(results["experiment_id"]),
        experiment_name=results["experiment_name"],
        variant_results=variant_results,
        statistical_analyses=statistical_analyses,
        winner_recommendation=winner_recommendation,
    )


# ---------------------------------------------------------------------------
# POST /experiments/{id}/promote-winner
# ---------------------------------------------------------------------------


@router.post(
    "/experiments/{experiment_id}/promote-winner",
    response_model=PromoteWinnerResponse,
)
async def promote_winner(
    experiment_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> PromoteWinnerResponse:
    """Promote the winner variant and stop the experiment."""
    result = await _experiment_service.promote_winner(
        db=db,
        experiment_id=experiment_id,
        workspace_id=current_user.workspace_id,
    )
    return PromoteWinnerResponse(**result)


# ---------------------------------------------------------------------------
# POST /performance-events
# ---------------------------------------------------------------------------


@router.post(
    "/performance-events",
    status_code=status.HTTP_201_CREATED,
)
async def ingest_performance_event(
    data: PerformanceEventCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Ingest a single performance event for an experiment variant."""
    event = await _experiment_service.ingest_event(
        db=db,
        experiment_id=data.experiment_id,
        variant_id=data.variant_id,
        event_type=data.event_type,
        visitor_hash=data.visitor_hash,
        value=data.value,
        metadata=data.metadata,
    )
    return {"event_id": str(event.id), "status": "ingested"}


# ---------------------------------------------------------------------------
# POST /performance-events/batch
# ---------------------------------------------------------------------------


@router.post(
    "/performance-events/batch",
    status_code=status.HTTP_201_CREATED,
)
async def ingest_performance_events_batch(
    data: PerformanceEventBatchCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Ingest a batch of performance events."""
    events_data = [
        {
            "experiment_id": e.experiment_id,
            "variant_id": e.variant_id,
            "event_type": e.event_type,
            "visitor_hash": e.visitor_hash,
            "value": e.value,
            "metadata": e.metadata,
        }
        for e in data.events
    ]
    count = await _experiment_service.ingest_events_batch(db=db, events=events_data)
    return {"ingested": count}
