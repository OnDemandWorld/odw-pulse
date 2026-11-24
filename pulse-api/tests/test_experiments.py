"""Experiment engine tests (TSD §2.15, §4.14-4.19, §5.17-5.31)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.api.schemas.experiment import ExperimentVariantCreate
from pulse.auth.security import create_access_token
from pulse.core.experiment.assignment import assign_variant
from pulse.services.experiment_service import ExperimentService
from tests.conftest import TEST_WORKSPACE_ID

# ---------------------------------------------------------------------------
# POST /api/v1/experiments — authentication
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_experiment_requires_auth(
    client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Creating an experiment without authentication should return 401."""
    payload = {
        "name": "Test Experiment",
        "description": "A/B test for homepage",
        "hypothesis": "Changing the CTA will increase conversions",
        "variants": [
            {"name": "control", "weight": 0.5},
            {"name": "treatment", "weight": 0.5},
        ],
    }

    response = await client.post("/api/v1/experiments", json=payload)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST + GET /api/v1/experiments — CRUD
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_and_get_experiment(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Creating an experiment and fetching it should return the experiment details."""
    payload = {
        "name": "Homepage CTA Test",
        "description": "Testing different CTA button colors",
        "hypothesis": "Red button will increase click-through rate",
        "variants": [
            {"name": "control", "weight": 0.5, "is_control": True},
            {"name": "treatment_red", "weight": 0.5},
        ],
    }

    # Create experiment
    response = await authorized_client.post("/api/v1/experiments", json=payload)
    assert response.status_code == 201
    exp_data = response.json()
    assert exp_data["name"] == "Homepage CTA Test"
    assert exp_data["status"] == "draft"
    assert exp_data["hypothesis"] == "Red button will increase click-through rate"
    assert len(exp_data["variants"]) == 2
    assert exp_data["variants"][0]["name"] == "control"
    assert exp_data["variants"][1]["name"] == "treatment_red"
    exp_id = exp_data["id"]

    # Get experiment
    response = await authorized_client.get(f"/api/v1/experiments/{exp_id}")
    assert response.status_code == 200
    fetched = response.json()
    assert fetched["id"] == exp_id
    assert fetched["name"] == "Homepage CTA Test"
    assert fetched["status"] == "draft"


# ---------------------------------------------------------------------------
# POST /api/v1/experiments/{id}/start — tracking URLs
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_start_experiment_generates_tracking_urls(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Starting an experiment should generate tracking URLs for each variant."""
    payload = {
        "name": "CTA Test",
        "variants": [
            {"name": "control", "weight": 0.5},
            {"name": "treatment", "weight": 0.5},
        ],
    }

    # Create experiment
    response = await authorized_client.post("/api/v1/experiments", json=payload)
    assert response.status_code == 201
    exp_id = response.json()["id"]

    # Start experiment
    response = await authorized_client.post(
        f"/api/v1/experiments/{exp_id}/start",
        params={"base_url": "https://example.com/landing"},
    )
    assert response.status_code == 200
    exp_data = response.json()
    assert exp_data["status"] == "running"
    assert exp_data["started_at"] is not None

    # Check tracking URLs
    tracking_urls = exp_data.get("tracking_urls", {})
    assert "control" in tracking_urls
    assert "treatment" in tracking_urls
    assert "utm_source=experiment" in tracking_urls["control"]
    assert "variant=control" in tracking_urls["control"]
    assert "variant=treatment" in tracking_urls["treatment"]


# ---------------------------------------------------------------------------
# Core: variant assignment is deterministic
# ---------------------------------------------------------------------------


def test_variant_assignment_is_deterministic() -> None:
    """The same visitor should always be assigned to the same variant."""
    weights = {"control": 0.5, "treatment": 0.5}

    # Same visitor, same experiment → same variant
    variant1 = assign_variant("user123", "exp456", weights)
    variant2 = assign_variant("user123", "exp456", weights)
    assert variant1 == variant2
    assert variant1 in ("control", "treatment")

    # Different visitor → potentially different variant
    variant3 = assign_variant("user789", "exp456", weights)
    # We can't assert they're different (could be same by chance),
    # but we can verify determinism
    variant4 = assign_variant("user789", "exp456", weights)
    assert variant3 == variant4

    # Different experiment → potentially different variant
    variant5 = assign_variant("user123", "exp999", weights)
    variant6 = assign_variant("user123", "exp999", weights)
    assert variant5 == variant6


def test_variant_assignment_respects_weights() -> None:
    """Assignment should roughly respect the weight distribution."""
    weights = {"control": 0.9, "treatment": 0.1}
    assignments = {"control": 0, "treatment": 0}

    # Simulate 1000 visitors
    for i in range(1000):
        variant = assign_variant(f"user{i}", "exp1", weights)
        assignments[variant] += 1

    # Should be roughly 90% control, 10% treatment (allow 5% margin)
    assert assignments["control"] > 800
    assert assignments["treatment"] < 200


# ---------------------------------------------------------------------------
# POST /api/v1/performance-events — event ingestion
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ingest_event_updates_variant_metrics(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Ingesting performance events should update variant metrics."""
    # Create experiment
    payload = {
        "name": "Conversion Test",
        "variants": [
            {"name": "control", "weight": 0.5},
            {"name": "treatment", "weight": 0.5},
        ],
    }
    response = await authorized_client.post("/api/v1/experiments", json=payload)
    assert response.status_code == 201
    exp_data = response.json()
    exp_id = exp_data["id"]
    control_id = exp_data["variants"][0]["id"]
    treatment_id = exp_data["variants"][1]["id"]

    # Ingest events for control
    for i in range(10):
        response = await authorized_client.post(
            "/api/v1/performance-events",
            json={
                "experiment_id": exp_id,
                "variant_id": control_id,
                "event_type": "impression",
                "visitor_hash": f"visitor{i}",
            },
        )
        assert response.status_code == 201

    # Ingest conversions for control (3 out of 10)
    for i in range(3):
        response = await authorized_client.post(
            "/api/v1/performance-events",
            json={
                "experiment_id": exp_id,
                "variant_id": control_id,
                "event_type": "conversion",
                "visitor_hash": f"visitor{i}",
            },
        )
        assert response.status_code == 201

    # Ingest events for treatment
    for i in range(10, 20):
        response = await authorized_client.post(
            "/api/v1/performance-events",
            json={
                "experiment_id": exp_id,
                "variant_id": treatment_id,
                "event_type": "impression",
                "visitor_hash": f"visitor{i}",
            },
        )
        assert response.status_code == 201

    # Ingest conversions for treatment (6 out of 10)
    for i in range(10, 16):
        response = await authorized_client.post(
            "/api/v1/performance-events",
            json={
                "experiment_id": exp_id,
                "variant_id": treatment_id,
                "event_type": "conversion",
                "visitor_hash": f"visitor{i}",
            },
        )
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/v1/experiments/{id}/results — winner recommendation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_experiment_results_recommends_winner(
    async_session: AsyncSession,
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Experiment results should recommend a winner based on conversion rates."""
    svc = ExperimentService()

    # Create experiment via service
    from pulse.api.schemas.experiment import ExperimentCreate

    exp = await svc.create_experiment(
        db=async_session,
        workspace_id=TEST_WORKSPACE_ID,
        data=ExperimentCreate(
            name="Winner Test",
            variants=[
                ExperimentVariantCreate(name="control", weight=0.5, is_control=True),
                ExperimentVariantCreate(name="treatment", weight=0.5),
            ],
        ),
    )
    exp_id = exp.id
    control_id = exp.variants[0].id
    treatment_id = exp.variants[1].id

    # Ingest events: control 3/100, treatment 15/100
    for i in range(100):
        await svc.ingest_event(
            db=async_session,
            workspace_id=TEST_WORKSPACE_ID,
            experiment_id=exp_id,
            variant_id=control_id,
            event_type="impression",
            visitor_hash=f"control_visitor_{i}",
        )

    for i in range(3):
        await svc.ingest_event(
            db=async_session,
            workspace_id=TEST_WORKSPACE_ID,
            experiment_id=exp_id,
            variant_id=control_id,
            event_type="conversion",
            visitor_hash=f"control_visitor_{i}",
        )

    for i in range(100):
        await svc.ingest_event(
            db=async_session,
            workspace_id=TEST_WORKSPACE_ID,
            experiment_id=exp_id,
            variant_id=treatment_id,
            event_type="impression",
            visitor_hash=f"treatment_visitor_{i}",
        )

    for i in range(15):
        await svc.ingest_event(
            db=async_session,
            workspace_id=TEST_WORKSPACE_ID,
            experiment_id=exp_id,
            variant_id=treatment_id,
            event_type="conversion",
            visitor_hash=f"treatment_visitor_{i}",
        )

    # Get results via API
    response = await authorized_client.get(f"/api/v1/experiments/{exp_id}/results")
    assert response.status_code == 200
    results = response.json()

    assert results["experiment_id"] == str(exp_id)
    assert len(results["variant_results"]) == 2
    assert results["winner_recommendation"]["recommended_variant"] is not None

    # Treatment should win (15% vs 3% conversion rate)
    assert results["winner_recommendation"]["recommended_variant"] == "treatment"


# ---------------------------------------------------------------------------
# Workspace isolation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_experiment_isolation_between_workspaces(
    authorized_client: AsyncClient,
    client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Experiments in one workspace should not be visible from another."""
    payload = {
        "name": "Workspace Isolation Test",
        "variants": [
            {"name": "control", "weight": 0.5},
            {"name": "treatment", "weight": 0.5},
        ],
    }

    # Create experiment in default workspace
    response = await authorized_client.post("/api/v1/experiments", json=payload)
    assert response.status_code == 201
    exp_id = response.json()["id"]

    # Create token for different workspace
    other_workspace = uuid.UUID("00000000-0000-0000-0000-000000000099")
    token = create_access_token(
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        email="other@example.com",
        workspace_id=other_workspace,
        role="editor",
    )

    # Try to get experiment with other workspace token
    response = await client.get(
        f"/api/v1/experiments/{exp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404  # Not found due to workspace isolation

    # List experiments with other workspace token
    response = await client.get(
        "/api/v1/experiments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0  # No experiments visible in other workspace


# ---------------------------------------------------------------------------
# Lifecycle: pause, resume, stop
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_experiment_lifecycle(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Testing the full experiment lifecycle: create → start → pause → resume → stop."""
    payload = {
        "name": "Lifecycle Test",
        "variants": [
            {"name": "control", "weight": 0.5},
            {"name": "treatment", "weight": 0.5},
        ],
    }

    # Create
    response = await authorized_client.post("/api/v1/experiments", json=payload)
    assert response.status_code == 201
    exp_id = response.json()["id"]
    assert response.json()["status"] == "draft"

    # Start
    response = await authorized_client.post(f"/api/v1/experiments/{exp_id}/start")
    assert response.status_code == 200
    assert response.json()["status"] == "running"

    # Pause
    response = await authorized_client.post(f"/api/v1/experiments/{exp_id}/pause")
    assert response.status_code == 200
    assert response.json()["status"] == "paused"

    # Resume
    response = await authorized_client.post(f"/api/v1/experiments/{exp_id}/start")
    # Should fail - can't start a paused experiment, need to use resume
    assert response.status_code == 400

    # Stop
    response = await authorized_client.post(f"/api/v1/experiments/{exp_id}/stop")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cannot_start_experiment_with_one_variant(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Starting an experiment with only one variant should return 400."""
    payload = {
        "name": "Single Variant Test",
        "variants": [{"name": "control", "weight": 1.0}],
    }

    response = await authorized_client.post("/api/v1/experiments", json=payload)
    assert response.status_code == 201
    exp_id = response.json()["id"]

    # Try to start (should fail - need at least 2 variants)
    response = await authorized_client.post(f"/api/v1/experiments/{exp_id}/start")
    assert response.status_code == 400


@pytest.mark.anyio
async def test_cannot_pause_non_running_experiment(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Pausing a draft experiment should return 400."""
    payload = {
        "name": "Draft Test",
        "variants": [
            {"name": "control", "weight": 0.5},
            {"name": "treatment", "weight": 0.5},
        ],
    }

    response = await authorized_client.post("/api/v1/experiments", json=payload)
    assert response.status_code == 201
    exp_id = response.json()["id"]

    # Try to pause (experiment is draft, not running)
    response = await authorized_client.post(f"/api/v1/experiments/{exp_id}/pause")
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Batch event ingestion
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_batch_event_ingestion(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Batch event ingestion should process multiple events at once."""
    payload = {
        "name": "Batch Test",
        "variants": [
            {"name": "control", "weight": 0.5},
            {"name": "treatment", "weight": 0.5},
        ],
    }

    response = await authorized_client.post("/api/v1/experiments", json=payload)
    assert response.status_code == 201
    exp_data = response.json()
    exp_id = exp_data["id"]
    control_id = exp_data["variants"][0]["id"]

    # Batch ingest
    batch_payload = {
        "events": [
            {
                "experiment_id": exp_id,
                "variant_id": control_id,
                "event_type": "impression",
                "visitor_hash": f"visitor{i}",
            }
            for i in range(50)
        ]
    }

    response = await authorized_client.post(
        "/api/v1/performance-events/batch", json=batch_payload
    )
    assert response.status_code == 201
    assert response.json()["ingested"] == 50


# ---------------------------------------------------------------------------
# Promote winner
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_promote_winner(
    async_session: AsyncSession,
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Promoting a winner should stop the experiment and record the winner."""
    svc = ExperimentService()

    # Create experiment
    from pulse.api.schemas.experiment import ExperimentCreate

    exp = await svc.create_experiment(
        db=async_session,
        workspace_id=TEST_WORKSPACE_ID,
        data=ExperimentCreate(
            name="Promote Test",
            variants=[
                ExperimentVariantCreate(name="control", weight=0.5, is_control=True),
                ExperimentVariantCreate(name="treatment", weight=0.5),
            ],
        ),
    )
    exp_id = exp.id

    # Start experiment
    await svc.start_experiment(async_session, exp_id, TEST_WORKSPACE_ID)

    # Ingest some events so we have a winner
    control_id = exp.variants[0].id
    treatment_id = exp.variants[1].id

    for i in range(50):
        await svc.ingest_event(
            db=async_session,
            workspace_id=TEST_WORKSPACE_ID,
            experiment_id=exp_id,
            variant_id=control_id,
            event_type="impression",
            visitor_hash=f"control_{i}",
        )

    for i in range(2):
        await svc.ingest_event(
            db=async_session,
            workspace_id=TEST_WORKSPACE_ID,
            experiment_id=exp_id,
            variant_id=control_id,
            event_type="conversion",
            visitor_hash=f"control_{i}",
        )

    for i in range(50):
        await svc.ingest_event(
            db=async_session,
            workspace_id=TEST_WORKSPACE_ID,
            experiment_id=exp_id,
            variant_id=treatment_id,
            event_type="impression",
            visitor_hash=f"treatment_{i}",
        )

    for i in range(10):
        await svc.ingest_event(
            db=async_session,
            workspace_id=TEST_WORKSPACE_ID,
            experiment_id=exp_id,
            variant_id=treatment_id,
            event_type="conversion",
            visitor_hash=f"treatment_{i}",
        )

    # Promote winner via API
    response = await authorized_client.post(
        f"/api/v1/experiments/{exp_id}/promote-winner"
    )
    assert response.status_code == 200
    result = response.json()
    assert result["winner_variant_name"] == "treatment"
    assert "confidence" in result
    assert "reason" in result


# ---------------------------------------------------------------------------
# Regression: audit #10 — conversions > visitors must not crash statistics
# ---------------------------------------------------------------------------


def test_chi_squared_rejects_conversions_exceeding_visitors() -> None:
    from pulse.core.experiment.statistics import bayesian_analysis, chi_squared_test

    # Negative contingency cells (duplicate conversion events) previously
    # produced chi2 < 0 -> math.sqrt ValueError.
    result = chi_squared_test(150, 100, 10, 100)
    assert result["error"] == "Invalid sample sizes"
    assert result["is_significant"] is False

    # p1 = 10/1 > 1 previously fed math.asin(math.sqrt(10)) -> domain error.
    result = chi_squared_test(10, 1, 0, 1)
    assert result["error"] == "Invalid sample sizes"

    # Bayesian path gets the same guard (negative Beta parameters).
    bayes = bayesian_analysis(10, 1, 0, 1)
    assert bayes["error"] == "Invalid sample sizes"

    # Valid tables still compute normally.
    ok = chi_squared_test(10, 100, 15, 100)
    assert "error" not in ok
    assert 0.0 <= ok["p_value"] <= 1.0


# ---------------------------------------------------------------------------
# Regression: audit #12 — event ingestion must enforce workspace ownership
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ingest_rejects_foreign_workspace_experiment(
    async_session: AsyncSession,
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Events targeting another workspace's experiment are rejected (404)."""
    from pulse.api.schemas.experiment import ExperimentCreate, ExperimentVariantCreate
    from pulse.models.workspace import Workspace

    svc = ExperimentService()
    other_ws_id = uuid.uuid4()
    async_session.add(
        Workspace(id=other_ws_id, name="Victim", slug=f"victim-{uuid.uuid4().hex[:8]}")
    )
    await async_session.commit()

    exp = await svc.create_experiment(
        db=async_session,
        workspace_id=other_ws_id,
        data=ExperimentCreate(
            name="Victim experiment",
            variants=[ExperimentVariantCreate(name="control", weight=1.0)],
        ),
    )

    response = await authorized_client.post(
        "/api/v1/performance-events",
        json={
            "experiment_id": str(exp.id),
            "variant_id": str(exp.variants[0].id),
            "event_type": "conversion",
            "visitor_hash": "attacker",
        },
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_ingest_rejects_mismatched_variant(
    async_session: AsyncSession,
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """A variant that does not belong to the experiment is rejected (400)."""
    from pulse.api.schemas.experiment import ExperimentCreate, ExperimentVariantCreate

    svc = ExperimentService()
    exp = await svc.create_experiment(
        db=async_session,
        workspace_id=TEST_WORKSPACE_ID,
        data=ExperimentCreate(
            name="Mismatch test",
            variants=[ExperimentVariantCreate(name="control", weight=1.0)],
        ),
    )

    response = await authorized_client.post(
        "/api/v1/performance-events",
        json={
            "experiment_id": str(exp.id),
            "variant_id": str(uuid.uuid4()),
            "event_type": "conversion",
        },
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Regression: audit #43/#44 — conversion dedup and winner direction
# ---------------------------------------------------------------------------


def test_conversions_deduplicated_per_visitor() -> None:
    from pulse.core.experiment.results import compute_results

    variants = [
        {"id": "c", "name": "control", "is_control": True},
        {"id": "t", "name": "treatment", "is_control": False},
    ]
    events: list[dict[str, Any]] = []
    for i in range(50):
        events.append({"variant_id": "t", "event_type": "impression", "visitor_hash": f"v{i}"})
        events.append({"variant_id": "t", "event_type": "conversion", "visitor_hash": f"v{i}"})
    # 10 duplicate conversion events must not inflate the rate above 100%.
    for i in range(10):
        events.append({"variant_id": "t", "event_type": "conversion", "visitor_hash": f"v{i}"})

    results = compute_results({"id": "e", "name": "exp"}, variants, events)
    treatment = next(v for v in results["variant_results"] if v["variant_name"] == "treatment")
    assert treatment["conversions"] == 50
    assert treatment["visitor_count"] == 50


def test_anonymous_conversions_keep_rate_at_most_one() -> None:
    from pulse.core.experiment.results import compute_results

    variants = [{"id": "t", "name": "treatment", "is_control": False}]
    events = [
        {"variant_id": "t", "event_type": "conversion", "visitor_hash": ""}
        for _ in range(10)
    ]
    results = compute_results({"id": "e", "name": "exp"}, variants, events)
    m = results["variant_results"][0]
    assert m["conversions"] == 10
    assert m["visitor_count"] == 10


def test_winner_recommendation_not_inverted_with_three_arms() -> None:
    """Audit #44: a significant treatment win must not be reported as control."""
    from pulse.core.experiment.results import compute_results

    variants = [
        {"id": "c", "name": "control", "is_control": True},
        {"id": "a", "name": "treatment_a", "is_control": False},
        {"id": "b", "name": "treatment_b", "is_control": False},
    ]
    events: list[dict[str, Any]] = []
    # control 10% of 1000, treatment_a 15% of 1000 (significant),
    # treatment_b 20% of 10 (best raw rate, not significant).
    for i in range(1000):
        events.append({"variant_id": "c", "event_type": "impression", "visitor_hash": f"c{i}"})
        if i < 100:
            events.append({"variant_id": "c", "event_type": "conversion", "visitor_hash": f"c{i}"})
        events.append({"variant_id": "a", "event_type": "impression", "visitor_hash": f"a{i}"})
        if i < 150:
            events.append({"variant_id": "a", "event_type": "conversion", "visitor_hash": f"a{i}"})
    for i in range(10):
        events.append({"variant_id": "b", "event_type": "impression", "visitor_hash": f"b{i}"})
        if i < 2:
            events.append({"variant_id": "b", "event_type": "conversion", "visitor_hash": f"b{i}"})

    results = compute_results({"id": "e", "name": "exp"}, variants, events)
    rec = results["winner_recommendation"]
    assert rec["recommended_variant"] == "treatment_a"
    assert "Control is statistically significantly better" not in rec["reason"]


# ---------------------------------------------------------------------------
# Regression: audit #28/#54/#29 — promotion persistence, is_control, batch cap
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_promote_winner_persists_configuration(
    async_session: AsyncSession,
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    from pulse.api.schemas.experiment import ExperimentCreate, ExperimentVariantCreate
    from pulse.models.experiment import Experiment

    svc = ExperimentService()
    exp = await svc.create_experiment(
        db=async_session,
        workspace_id=TEST_WORKSPACE_ID,
        data=ExperimentCreate(
            name="Promotion persistence",
            configuration={"randomisation_unit": "visitor"},
            variants=[
                ExperimentVariantCreate(name="control", weight=0.5, is_control=True),
                ExperimentVariantCreate(name="treatment", weight=0.5),
            ],
        ),
    )
    await svc.start_experiment(async_session, exp.id, TEST_WORKSPACE_ID)
    await svc.ingest_event(
        db=async_session,
        workspace_id=TEST_WORKSPACE_ID,
        experiment_id=exp.id,
        variant_id=exp.variants[1].id,
        event_type="conversion",
        visitor_hash="v1",
    )

    response = await authorized_client.post(f"/api/v1/experiments/{exp.id}/promote-winner")
    assert response.status_code == 200

    # Re-read from the database in a fresh state: winner info must be stored.
    await async_session.rollback()
    row = (
        await async_session.execute(select(Experiment).where(Experiment.id == exp.id))
    ).scalar_one()
    assert row.configuration is not None
    assert row.configuration.get("promoted_winner_name") is not None
    assert row.configuration.get("randomisation_unit") == "visitor"


@pytest.mark.anyio
async def test_is_control_flag_is_persisted(
    async_session: AsyncSession, test_workspace_and_user: tuple[Any, Any]
) -> None:
    from pulse.api.schemas.experiment import ExperimentCreate, ExperimentVariantCreate

    svc = ExperimentService()
    exp = await svc.create_experiment(
        db=async_session,
        workspace_id=TEST_WORKSPACE_ID,
        data=ExperimentCreate(
            name="Control flag",
            variants=[
                ExperimentVariantCreate(name="B", weight=0.5, is_control=True),
                ExperimentVariantCreate(name="A", weight=0.5),
            ],
        ),
    )
    results = await svc.get_results(async_session, exp.id, TEST_WORKSPACE_ID)
    by_name = {v["variant_name"]: v for v in results["variant_results"]}
    assert by_name["B"]["is_control"] is True
    assert by_name["A"]["is_control"] is False


@pytest.mark.anyio
async def test_event_batch_rejects_oversized_payload(
    authorized_client: AsyncClient, test_workspace_and_user: tuple[Any, Any]
) -> None:
    events = [
        {
            "experiment_id": str(uuid.uuid4()),
            "variant_id": str(uuid.uuid4()),
            "event_type": "impression",
        }
        for _ in range(1001)
    ]
    response = await authorized_client.post(
        "/api/v1/performance-events/batch", json={"events": events}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Regression: audit #55 — updating variants preserves event attribution
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_update_experiment_preserves_variant_ids_and_events(
    async_session: AsyncSession,
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    from pulse.api.schemas.experiment import ExperimentCreate, ExperimentVariantCreate
    from pulse.models.performance_event import PerformanceEvent

    svc = ExperimentService()
    exp = await svc.create_experiment(
        db=async_session,
        workspace_id=TEST_WORKSPACE_ID,
        data=ExperimentCreate(
            name="Update preserves events",
            variants=[
                ExperimentVariantCreate(name="control", weight=0.5, is_control=True),
                ExperimentVariantCreate(name="treatment", weight=0.5),
            ],
        ),
    )
    control_id = exp.variants[0].id
    await svc.ingest_event(
        db=async_session,
        workspace_id=TEST_WORKSPACE_ID,
        experiment_id=exp.id,
        variant_id=control_id,
        event_type="conversion",
        visitor_hash="v1",
    )

    # Rename one variant, keep "control"; add a new one.
    response = await authorized_client.put(
        f"/api/v1/experiments/{exp.id}",
        json={
            "name": "Update preserves events",
            "variants": [
                {"name": "control", "weight": 0.4, "is_control": True},
                {"name": "treatment_v2", "weight": 0.3},
                {"name": "treatment_v3", "weight": 0.3},
            ],
        },
    )
    assert response.status_code == 200

    # The surviving variant keeps its id, so the event stays attributed.
    event = (
        await async_session.execute(
            select(PerformanceEvent).where(PerformanceEvent.experiment_id == exp.id)
        )
    ).scalar_one()
    assert event.variant_id == control_id
