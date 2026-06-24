"""Experiment management service (TSD §2.15, §4.14-4.19)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.api.schemas.experiment import ExperimentCreate
from pulse.core.experiment.results import compute_results
from pulse.core.experiment.tracking import generate_tracking_urls
from pulse.models.experiment import Experiment, ExperimentStatus, ExperimentVariant
from pulse.models.performance_event import PerformanceEvent, PerformanceMetricType


class ExperimentService:
    """Service for managing experiments, variants, events, and results."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _load_experiment_with_variants(
        self,
        db: AsyncSession,
        experiment_id: uuid.UUID,
    ) -> Experiment:
        """Load an experiment with its variants explicitly populated."""
        # Query variants separately
        variant_result = await db.execute(
            select(ExperimentVariant)
            .where(ExperimentVariant.experiment_id == experiment_id)
            .order_by(ExperimentVariant.position)
        )
        variants = list(variant_result.scalars().all())

        # Query experiment
        exp_result = await db.execute(
            select(Experiment).where(Experiment.id == experiment_id)
        )
        experiment = exp_result.scalar_one()

        # Manually populate variants (bypass noload strategy)
        experiment.variants = variants

        return experiment

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_experiment(
        self,
        db: AsyncSession,
        workspace_id: uuid.UUID,
        data: ExperimentCreate,
        created_by: uuid.UUID | None = None,
    ) -> Experiment:
        """Create a new experiment with optional initial variants."""
        experiment = Experiment(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            name=data.name,
            description=data.description,
            hypothesis=data.hypothesis,
            configuration=data.configuration,
            status=ExperimentStatus.DRAFT,
            created_by=created_by,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(experiment)

        # Create variants
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

        await db.commit()

        # Load with variants explicitly
        return await self._load_experiment_with_variants(db, experiment.id)

    async def get_experiment(
        self,
        db: AsyncSession,
        experiment_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Experiment:
        """Get an experiment by ID, scoped to workspace."""
        result = await db.execute(
            select(Experiment).where(
                Experiment.id == experiment_id,
                Experiment.workspace_id == workspace_id,
            )
        )
        experiment = result.scalar_one_or_none()
        if experiment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found",
            )
        # Load variants explicitly (bypass noload strategy)
        return await self._load_experiment_with_variants(db, experiment_id)

    async def list_experiments(
        self,
        db: AsyncSession,
        workspace_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Experiment], int]:
        """List experiments with pagination, scoped to workspace."""
        # Total count
        count_query = (
            select(func.count())
            .select_from(Experiment)
            .where(Experiment.workspace_id == workspace_id)
        )
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Paginated items
        query = (
            select(Experiment)
            .where(Experiment.workspace_id == workspace_id)
            .order_by(Experiment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(query)
        items = list(result.scalars().all())

        # Load variants for each experiment
        for item in items:
            variants_result = await db.execute(
                select(ExperimentVariant)
                .where(ExperimentVariant.experiment_id == item.id)
                .order_by(ExperimentVariant.position)
            )
            item.variants = list(variants_result.scalars().all())

        return items, total

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start_experiment(
        self,
        db: AsyncSession,
        experiment_id: uuid.UUID,
        workspace_id: uuid.UUID,
        base_url: str | None = None,
    ) -> Experiment:
        """Start an experiment (DRAFT → RUNNING)."""
        experiment = await self.get_experiment(db, experiment_id, workspace_id)

        if experiment.status != ExperimentStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot start experiment in '{experiment.status.value}' status",
            )

        # Verify at least 2 variants
        result = await db.execute(
            select(func.count())
            .select_from(ExperimentVariant)
            .where(ExperimentVariant.experiment_id == experiment_id)
        )
        variant_count = result.scalar() or 0

        if variant_count < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Experiment must have at least 2 variants to start",
            )

        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.now(UTC)
        experiment.updated_at = datetime.now(UTC)
        await db.commit()

        # Reload with variants
        return await self._load_experiment_with_variants(db, experiment_id)

    async def pause_experiment(
        self,
        db: AsyncSession,
        experiment_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Experiment:
        """Pause a running experiment (RUNNING → PAUSED)."""
        experiment = await self.get_experiment(db, experiment_id, workspace_id)

        if experiment.status != ExperimentStatus.RUNNING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot pause experiment in '{experiment.status.value}' status",
            )

        experiment.status = ExperimentStatus.PAUSED
        experiment.updated_at = datetime.now(UTC)
        await db.commit()
        return await self._load_experiment_with_variants(db, experiment_id)

    async def resume_experiment(
        self,
        db: AsyncSession,
        experiment_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Experiment:
        """Resume a paused experiment (PAUSED → RUNNING)."""
        experiment = await self.get_experiment(db, experiment_id, workspace_id)

        if experiment.status != ExperimentStatus.PAUSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resume experiment in '{experiment.status.value}' status",
            )

        experiment.status = ExperimentStatus.RUNNING
        experiment.updated_at = datetime.now(UTC)
        await db.commit()
        return await self._load_experiment_with_variants(db, experiment_id)

    async def stop_experiment(
        self,
        db: AsyncSession,
        experiment_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> Experiment:
        """Stop an experiment (RUNNING/PAUSED → COMPLETED)."""
        experiment = await self.get_experiment(db, experiment_id, workspace_id)

        if experiment.status not in (
            ExperimentStatus.RUNNING,
            ExperimentStatus.PAUSED,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot stop experiment in '{experiment.status.value}' status",
            )

        experiment.status = ExperimentStatus.COMPLETED
        experiment.ended_at = datetime.now(UTC)
        experiment.updated_at = datetime.now(UTC)
        await db.commit()
        return await self._load_experiment_with_variants(db, experiment_id)

    # ------------------------------------------------------------------
    # Event ingestion
    # ------------------------------------------------------------------

    async def ingest_event(
        self,
        db: AsyncSession,
        experiment_id: uuid.UUID,
        variant_id: uuid.UUID,
        event_type: str,
        visitor_hash: str | None = None,
        value: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> PerformanceEvent:
        """Ingest a performance event for an experiment variant."""
        try:
            metric_type = PerformanceMetricType(event_type)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event type: {event_type}",
            ) from err

        event = PerformanceEvent(
            id=uuid.uuid4(),
            experiment_id=experiment_id,
            variant_id=variant_id,
            subject_id=visitor_hash,
            metric_type=metric_type,
            value=value,
            metadata_=metadata or {},
            received_at=datetime.now(UTC),
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    async def ingest_events_batch(
        self,
        db: AsyncSession,
        events: list[dict[str, Any]],
    ) -> int:
        """Ingest a batch of performance events. Returns count inserted."""
        count = 0
        for event_data in events:
            try:
                metric_type = PerformanceMetricType(event_data["event_type"])
            except (ValueError, KeyError):
                continue

            event = PerformanceEvent(
                id=uuid.uuid4(),
                experiment_id=event_data["experiment_id"],
                variant_id=event_data["variant_id"],
                subject_id=event_data.get("visitor_hash"),
                metric_type=metric_type,
                value=event_data.get("value", 1.0),
                metadata_=event_data.get("metadata", {}),
                received_at=datetime.now(UTC),
            )
            db.add(event)
            count += 1

        await db.commit()
        return count

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    async def get_results(
        self,
        db: AsyncSession,
        experiment_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Compute and return experiment results."""
        experiment = await self.get_experiment(db, experiment_id, workspace_id)

        # Load variants
        variant_result = await db.execute(
            select(ExperimentVariant).where(
                ExperimentVariant.experiment_id == experiment_id
            )
        )
        variants = list(variant_result.scalars().all())

        # Load events
        event_result = await db.execute(
            select(PerformanceEvent).where(
                PerformanceEvent.experiment_id == experiment_id
            )
        )
        events = list(event_result.scalars().all())

        # Prepare data for compute_results
        experiment_dict = {
            "id": str(experiment.id),
            "name": experiment.name,
            "hypothesis": experiment.hypothesis,
        }

        # Determine control variant (first variant or one with is_control flag in config)
        variant_dicts = []
        for i, v in enumerate(variants):
            config = v.configuration or {}
            variant_dicts.append({
                "id": str(v.id),
                "name": v.name,
                "is_control": config.get("is_control", i == 0),
            })

        event_dicts = [
            {
                "variant_id": str(e.variant_id),
                "event_type": e.metric_type.value,
                "visitor_hash": e.subject_id or "",
            }
            for e in events
        ]

        return compute_results(experiment_dict, variant_dicts, event_dicts)

    async def promote_winner(
        self,
        db: AsyncSession,
        experiment_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Promote the winner variant and stop the experiment.

        Returns a dict with the promoted variant info.
        """
        results = await self.get_results(db, experiment_id, workspace_id)

        winner = results.get("winner_recommendation", {})
        winner_name = winner.get("recommended_variant")

        if not winner_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No winner could be recommended",
            )

        # Find the variant
        result = await db.execute(
            select(ExperimentVariant).where(
                ExperimentVariant.experiment_id == experiment_id,
                ExperimentVariant.name == winner_name,
            )
        )
        winner_variant = result.scalar_one_or_none()

        if winner_variant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Winner variant not found",
            )

        # Stop the experiment
        experiment = await self.get_experiment(db, experiment_id, workspace_id)
        if experiment.status in (ExperimentStatus.RUNNING, ExperimentStatus.PAUSED):
            experiment.status = ExperimentStatus.COMPLETED
            experiment.ended_at = datetime.now(UTC)
            experiment.updated_at = datetime.now(UTC)

            # Store winner info in configuration
            config = experiment.configuration or {}
            winner_variant_id = str(winner_variant.id)
            config["promoted_winner_id"] = winner_variant_id
            config["promoted_winner_name"] = winner_name
            experiment.configuration = config

            await db.commit()

        else:
            winner_variant_id = str(winner_variant.id)

        return {
            "experiment_id": str(experiment_id),
            "winner_variant_id": winner_variant_id,
            "winner_variant_name": winner_name,
            "confidence": winner.get("confidence", 0.0),
            "reason": winner.get("reason", ""),
        }

    # ------------------------------------------------------------------
    # Tracking URLs
    # ------------------------------------------------------------------

    async def generate_tracking_urls(
        self,
        db: AsyncSession,
        experiment_id: uuid.UUID,
        workspace_id: uuid.UUID,
        base_url: str,
    ) -> dict[str, str]:
        """Generate tracking URLs for all variants in an experiment."""
        # Verify experiment exists and belongs to workspace
        await self.get_experiment(db, experiment_id, workspace_id)

        result = await db.execute(
            select(ExperimentVariant).where(
                ExperimentVariant.experiment_id == experiment_id
            )
        )
        variants = list(result.scalars().all())

        variant_names = [v.name for v in variants]

        return generate_tracking_urls(
            base_url=base_url,
            experiment_id=str(experiment_id),
            variants=variant_names,
        )

    # ------------------------------------------------------------------
    # Delete (cleanup)
    # ------------------------------------------------------------------

    async def delete_experiment(
        self,
        db: AsyncSession,
        experiment_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> None:
        """Delete an experiment and all its variants/events (only DRAFT)."""
        experiment = await self.get_experiment(db, experiment_id, workspace_id)

        if experiment.status != ExperimentStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft experiments can be deleted",
            )

        # Delete associated events
        await db.execute(
            delete(PerformanceEvent).where(
                PerformanceEvent.experiment_id == experiment_id
            )
        )

        # Delete experiment (variants cascade)
        await db.delete(experiment)
        await db.commit()
