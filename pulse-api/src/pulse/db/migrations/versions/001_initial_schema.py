"""Initial schema — create all Pulse tables, partitions, RLS policies.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-06-24

This is the comprehensive initial migration.  It creates every table
declared in ``pulse.models``, attaches hash- and range-based
partitions for the high-volume tables, adds supporting indexes, and
enables Row-Level Security (RLS) on all workspace-scoped tables.

The migration is fully reversible — ``downgrade()`` drops every
object created by ``upgrade()`` in the correct dependency order.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Custom enum types (PostgreSQL-only).  SQLite ignores these.
    # ------------------------------------------------------------------
    user_role = sa.Enum(
        "owner", "admin", "editor", "viewer", name="user_role", create_constraint=True
    )
    content_status = sa.Enum(
        "draft",
        "review",
        "approved",
        "rejected",
        "archived",
        name="content_status",
        create_constraint=True,
    )
    bulk_job_status = sa.Enum(
        "pending",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        name="bulk_job_status",
        create_constraint=True,
    )
    experiment_status = sa.Enum(
        "draft",
        "running",
        "paused",
        "completed",
        "archived",
        name="experiment_status",
        create_constraint=True,
    )
    exposure_channel = sa.Enum(
        "web",
        "email",
        "mobile",
        "api",
        "other",
        name="exposure_channel",
        create_constraint=True,
    )
    performance_metric_type = sa.Enum(
        "impression",
        "click",
        "conversion",
        "revenue",
        "custom",
        name="performance_metric_type",
        create_constraint=True,
    )
    prompt_status = sa.Enum(
        "draft",
        "active",
        "archived",
        name="prompt_status",
        create_constraint=True,
    )

    user_role.create(op.get_bind(), checkfirst=True)
    content_status.create(op.get_bind(), checkfirst=True)
    bulk_job_status.create(op.get_bind(), checkfirst=True)
    experiment_status.create(op.get_bind(), checkfirst=True)
    exposure_channel.create(op.get_bind(), checkfirst=True)
    performance_metric_type.create(op.get_bind(), checkfirst=True)
    prompt_status.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # 2. Non-partitioned base tables
    # ------------------------------------------------------------------

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("settings", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),
        comment="Top-level tenant boundary.",
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid, nullable=False),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "owner",
                "admin",
                "editor",
                "viewer",
                name="user_role",
                create_constraint=True,
            ),
            server_default="viewer",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "email", name="uq_users_workspace_email"),
        comment="Workspace-scoped user identity.",
    )
    op.create_index("ix_users_workspace_id", "users", ["workspace_id"])

    op.create_table(
        "market_profiles",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "code",
            sa.Text,
            nullable=False,
            comment="ISO 639-1 language code optionally suffixed with a region, e.g. 'en-US'.",
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("cultural_dimensions", sa.JSON, nullable=True),
        sa.Column(
            "fallback_code",
            sa.Text,
            nullable=True,
            comment="Market code to fall back to when generation for this market fails.",
        ),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_market_profiles_code"),
        comment="Language / region profile for content localisation.",
    )

    op.create_table(
        "generation_cache",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "hash",
            sa.Text,
            nullable=False,
            comment="Hex-encoded SHA-256 of the normalised prompt.",
        ),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("response", sa.Text, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("provider", sa.Text, nullable=True),
        sa.Column("model", sa.Text, nullable=True),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="TTL-based expiration; rows are reaped by a background job.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="Deterministic LLM prompt/response cache.",
    )
    op.create_index("ix_generation_cache_hash", "generation_cache", ["hash"])
    op.create_index("ix_generation_cache_expires_at", "generation_cache", ["expires_at"])

    # ------------------------------------------------------------------
    # 3. Partitioned parent tables (DDL only — partitions follow later)
    # ------------------------------------------------------------------

    # content_pieces — HASH(workspace_id), 16 partitions
    op.create_table(
        "content_pieces",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid, nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "review",
                "approved",
                "rejected",
                "archived",
                name="content_status",
                create_constraint=True,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("market_code", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_content_pieces_workspace_slug"),
        comment="Content pieces — partitioned by HASH(workspace_id) into 16 partitions.",
        postgresql_partition_by="HASH(workspace_id)",
    )

    op.create_index(
        "ix_content_pieces_workspace_status",
        "content_pieces",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_content_pieces_workspace_market",
        "content_pieces",
        ["workspace_id", "market_code"],
    )

    op.create_table(
        "content_versions",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("content_piece_id", sa.Uuid, nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "review",
                "approved",
                "rejected",
                "archived",
                name="content_status",
                create_constraint=False,
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("change_note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["content_piece_id"], ["content_pieces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "content_piece_id",
            "version_number",
            name="uq_content_versions_piece_version",
        ),
        comment="Immutable content versions.",
    )
    op.create_index(
        "ix_content_versions_content_piece_id",
        "content_versions",
        ["content_piece_id"],
    )

    op.create_table(
        "brand_voices",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tone_profile", sa.JSON, nullable=True),
        sa.Column("guidelines", sa.JSON, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        comment="Brand voice / tone configuration per workspace.",
    )
    op.create_index("ix_brand_voices_workspace_id", "brand_voices", ["workspace_id"])

    op.create_table(
        "glossaries",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "name", name="uq_glossaries_workspace_name"),
        comment="Workspace-owned terminology glossaries.",
    )
    op.create_index("ix_glossaries_workspace_id", "glossaries", ["workspace_id"])

    op.create_table(
        "glossary_terms",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("glossary_id", sa.Uuid, nullable=False),
        sa.Column("term", sa.Text, nullable=False),
        sa.Column("definition", sa.Text, nullable=True),
        sa.Column("translations", sa.JSON, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["glossary_id"], ["glossaries.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("glossary_id", "term", name="uq_glossary_terms_glossary_term"),
        comment="Terminology entries within a glossary.",
    )
    op.create_index("ix_glossary_terms_glossary_id", "glossary_terms", ["glossary_id"])

    op.create_table(
        "bulk_jobs",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="bulk_job_status",
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("total", sa.Integer, server_default="0", nullable=False),
        sa.Column("progress", sa.Integer, server_default="0", nullable=False),
        sa.Column("input_file", sa.Text, nullable=True),
        sa.Column("output_file", sa.Text, nullable=True),
        sa.Column("errors", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        comment="Asynchronous batch content-generation jobs.",
    )
    op.create_index("ix_bulk_jobs_workspace_id", "bulk_jobs", ["workspace_id"])

    # audit_logs — RANGE(created_at) monthly
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid, nullable=False),
        sa.Column(
            "action",
            sa.Text,
            nullable=False,
            comment="Dot-namespaced action, e.g. 'content_piece.created'.",
        ),
        sa.Column(
            "actor_id",
            sa.Uuid,
            nullable=True,
            comment="User or API key that performed the action.",
        ),
        sa.Column(
            "resource",
            sa.Text,
            nullable=True,
            comment="Resource identifier, e.g. 'content_piece:1234'.",
        ),
        sa.Column(
            "details",
            sa.JSON,
            nullable=True,
            comment="Free-form structured payload describing the action.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        comment="Immutable audit trail — partitioned by RANGE(created_at) monthly.",
        postgresql_partition_by="RANGE(created_at)",
    )
    op.create_index(
        "ix_audit_logs_workspace_created",
        "audit_logs",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_audit_logs_workspace_action",
        "audit_logs",
        ["workspace_id", "action"],
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column(
            "key_hash",
            sa.Text,
            nullable=False,
            comment="SHA-256 hex digest of the API key.",
        ),
        sa.Column(
            "scopes",
            sa.ARRAY(sa.Text),
            nullable=True,
            comment="Authorised scope tokens, e.g. ['content:read','content:write'].",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="NULL means the key never expires.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
        comment="Workspace-scoped API access keys.",
    )
    op.create_index("ix_api_keys_workspace_id", "api_keys", ["workspace_id"])

    op.create_table(
        "webhook_configs",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column(
            "events",
            sa.ARRAY(sa.Text),
            nullable=False,
            comment="Event types this webhook is subscribed to.",
        ),
        sa.Column(
            "signing_secret",
            sa.Text,
            nullable=False,
            comment="Shared secret used to HMAC-sign outgoing payloads.",
        ),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        comment="Outbound webhook subscriptions.",
    )
    op.create_index("ix_webhook_configs_workspace_id", "webhook_configs", ["workspace_id"])

    op.create_table(
        "experiments",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "running",
                "paused",
                "completed",
                "archived",
                name="experiment_status",
                create_constraint=True,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("hypothesis", sa.Text, nullable=True),
        sa.Column("configuration", sa.JSON, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        comment="Experiment definitions (TSD §4.14).",
    )
    op.create_index("ix_experiments_workspace_id", "experiments", ["workspace_id"])

    op.create_table(
        "experiment_variants",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("experiment_id", sa.Uuid, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column(
            "weight",
            sa.Float,
            server_default="1.0",
            nullable=False,
            comment="Relative traffic weight (normalised at assignment time).",
        ),
        sa.Column("configuration", sa.JSON, nullable=True),
        sa.Column(
            "position",
            sa.Integer,
            server_default="0",
            nullable=False,
            comment="Display ordering index.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("experiment_id", "name", name="uq_experiment_variants_experiment_name"),
        comment="Experiment variants / treatment arms (TSD §4.14).",
    )
    op.create_index(
        "ix_experiment_variants_experiment_id",
        "experiment_variants",
        ["experiment_id"],
    )

    # ------------------------------------------------------------------
    # 4. Experimentation / performance partitioned tables
    # ------------------------------------------------------------------

    op.create_table(
        "experiment_assignments",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("experiment_id", sa.Uuid, nullable=False),
        sa.Column("variant_id", sa.Uuid, nullable=False),
        sa.Column(
            "subject_id",
            sa.Text,
            nullable=False,
            comment="Opaque subject identifier (user id, session id, …).",
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["experiment_variants.id"], ondelete="CASCADE"),
        comment="Experiment subject → variant assignments — partitioned by RANGE(assigned_at) monthly.",
        postgresql_partition_by="RANGE(assigned_at)",
    )
    op.create_index(
        "ix_experiment_assignments_experiment_subject",
        "experiment_assignments",
        ["experiment_id", "subject_id"],
    )
    op.create_index(
        "ix_experiment_assignments_assigned_at",
        "experiment_assignments",
        ["assigned_at"],
    )

    op.create_table(
        "experiment_exposures",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("experiment_id", sa.Uuid, nullable=False),
        sa.Column("variant_id", sa.Uuid, nullable=False),
        sa.Column("subject_id", sa.Text, nullable=False),
        sa.Column(
            "channel",
            sa.Enum(
                "web",
                "email",
                "mobile",
                "api",
                "other",
                name="exposure_channel",
                create_constraint=True,
            ),
            server_default="web",
            nullable=False,
        ),
        sa.Column(
            "exposed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["experiment_variants.id"], ondelete="CASCADE"),
        comment="Variant exposure events — partitioned by RANGE(exposed_at) weekly.",
        postgresql_partition_by="RANGE(exposed_at)",
    )
    op.create_index(
        "ix_experiment_exposures_experiment_subject",
        "experiment_exposures",
        ["experiment_id", "subject_id"],
    )
    op.create_index(
        "ix_experiment_exposures_exposed_at",
        "experiment_exposures",
        ["exposed_at"],
    )

    op.create_table(
        "performance_events",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("content_piece_id", sa.Uuid, nullable=True),
        sa.Column("experiment_id", sa.Uuid, nullable=True),
        sa.Column("variant_id", sa.Uuid, nullable=True),
        sa.Column("subject_id", sa.Text, nullable=True),
        sa.Column(
            "metric_type",
            sa.Enum(
                "impression",
                "click",
                "conversion",
                "revenue",
                "custom",
                name="performance_metric_type",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "value",
            sa.Float,
            server_default="1.0",
            nullable=False,
            comment="Numeric value of the metric (count, revenue, …).",
        ),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["content_piece_id"], ["content_pieces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["variant_id"], ["experiment_variants.id"], ondelete="SET NULL"),
        comment="Business-metric signals — partitioned by RANGE(received_at) weekly.",
        postgresql_partition_by="RANGE(received_at)",
    )
    op.create_index(
        "ix_performance_events_content_piece",
        "performance_events",
        ["content_piece_id"],
    )
    op.create_index(
        "ix_performance_events_experiment",
        "performance_events",
        ["experiment_id"],
    )
    op.create_index(
        "ix_performance_events_received_at",
        "performance_events",
        ["received_at"],
    )
    op.create_index(
        "ix_performance_events_metric_type",
        "performance_events",
        ["metric_type"],
    )

    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Uuid, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid, nullable=False),
        sa.Column(
            "name",
            sa.Text,
            nullable=False,
            comment="Stable identifier shared across versions, e.g. 'blog_outline_v1'.",
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column(
            "template",
            sa.Text,
            nullable=False,
            comment="The prompt body with {{variable}} placeholders.",
        ),
        sa.Column(
            "variables",
            sa.JSON,
            nullable=True,
            comment="Schema describing expected template variables.",
        ),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "active",
                "archived",
                name="prompt_status",
                create_constraint=True,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "workspace_id",
            "name",
            "version_number",
            name="uq_prompt_versions_name_version",
        ),
        comment="Append-only prompt version history (TSD §4.18-4.19).",
    )
    op.create_index("ix_prompt_versions_workspace_id", "prompt_versions", ["workspace_id"])

    # ------------------------------------------------------------------
    # 5. Partitions
    # ------------------------------------------------------------------

    # content_pieces: 16 hash partitions
    for i in range(16):
        op.execute(
            f"CREATE TABLE IF NOT EXISTS content_pieces_p{i} "
            f"PARTITION OF content_pieces FOR VALUES WITH (MODULUS 16, REMAINDER {i})"
        )

    # audit_logs: 24 monthly range partitions starting Jan 2026
    _create_monthly_partitions(
        op,
        "audit_logs",
        "created_at",
        start=date(2026, 1, 1),
        count=24,
    )

    # experiment_assignments: 24 monthly range partitions
    _create_monthly_partitions(
        op,
        "experiment_assignments",
        "assigned_at",
        start=date(2026, 1, 1),
        count=24,
    )

    # experiment_exposures: 52 weekly range partitions
    _create_weekly_partitions(
        op,
        "experiment_exposures",
        "exposed_at",
        start=date(2026, 1, 5),
        count=52,
    )

    # performance_events: 52 weekly range partitions
    _create_weekly_partitions(
        op,
        "performance_events",
        "received_at",
        start=date(2026, 1, 5),
        count=52,
    )

    # ------------------------------------------------------------------
    # 6. Row-Level Security
    # ------------------------------------------------------------------

    workspace_scoped_tables = [
        "users",
        "content_pieces",
        "content_versions",
        "brand_voices",
        "glossaries",
        "glossary_terms",
        "bulk_jobs",
        "audit_logs",
        "api_keys",
        "webhook_configs",
        "experiments",
        "experiment_variants",
        "experiment_assignments",
        "experiment_exposures",
        "prompt_versions",
    ]

    for tbl in workspace_scoped_tables:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")

    # Simple per-table policies.  In production these should reference
    # ``current_setting('app.current_workspace_id')`` (or the JWT claim
    # helper) so that each session is scoped to exactly one workspace.
    # The policies below are placeholders — they enable RLS enforcement
    # without blocking application bootstrapping.
    _policy_ddl = [
        # users
        "CREATE POLICY users_workspace_isolation ON users FOR ALL USING (true) WITH CHECK (true)",
        # content_pieces
        "CREATE POLICY content_pieces_workspace_isolation ON content_pieces "
        "FOR ALL USING (true) WITH CHECK (true)",
        # content_versions — inherit via FK to content_pieces
        "CREATE POLICY content_versions_workspace_isolation ON content_versions "
        "FOR ALL USING (true) WITH CHECK (true)",
        # brand_voices
        "CREATE POLICY brand_voices_workspace_isolation ON brand_voices "
        "FOR ALL USING (true) WITH CHECK (true)",
        # glossaries
        "CREATE POLICY glossaries_workspace_isolation ON glossaries "
        "FOR ALL USING (true) WITH CHECK (true)",
        # glossary_terms — inherit via FK to glossaries
        "CREATE POLICY glossary_terms_workspace_isolation ON glossary_terms "
        "FOR ALL USING (true) WITH CHECK (true)",
        # bulk_jobs
        "CREATE POLICY bulk_jobs_workspace_isolation ON bulk_jobs "
        "FOR ALL USING (true) WITH CHECK (true)",
        # audit_logs
        "CREATE POLICY audit_logs_workspace_isolation ON audit_logs "
        "FOR ALL USING (true) WITH CHECK (true)",
        # api_keys
        "CREATE POLICY api_keys_workspace_isolation ON api_keys "
        "FOR ALL USING (true) WITH CHECK (true)",
        # webhook_configs
        "CREATE POLICY webhook_configs_workspace_isolation ON webhook_configs "
        "FOR ALL USING (true) WITH CHECK (true)",
        # experiments
        "CREATE POLICY experiments_workspace_isolation ON experiments "
        "FOR ALL USING (true) WITH CHECK (true)",
        # experiment_variants — inherit via FK to experiments
        "CREATE POLICY experiment_variants_workspace_isolation ON experiment_variants "
        "FOR ALL USING (true) WITH CHECK (true)",
        # experiment_assignments — inherit via FK to experiments
        "CREATE POLICY experiment_assignments_workspace_isolation "
        "ON experiment_assignments FOR ALL USING (true) WITH CHECK (true)",
        # experiment_exposures — inherit via FK to experiments
        "CREATE POLICY experiment_exposures_workspace_isolation "
        "ON experiment_exposures FOR ALL USING (true) WITH CHECK (true)",
        # prompt_versions
        "CREATE POLICY prompt_versions_workspace_isolation ON prompt_versions "
        "FOR ALL USING (true) WITH CHECK (true)",
    ]
    for ddl in _policy_ddl:
        op.execute(ddl)


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    # 1. Drop RLS policies (order matches upgrade).
    _policy_names = [
        "users_workspace_isolation",
        "content_pieces_workspace_isolation",
        "content_versions_workspace_isolation",
        "brand_voices_workspace_isolation",
        "glossaries_workspace_isolation",
        "glossary_terms_workspace_isolation",
        "bulk_jobs_workspace_isolation",
        "audit_logs_workspace_isolation",
        "api_keys_workspace_isolation",
        "webhook_configs_workspace_isolation",
        "experiments_workspace_isolation",
        "experiment_variants_workspace_isolation",
        "experiment_assignments_workspace_isolation",
        "experiment_exposures_workspace_isolation",
        "prompt_versions_workspace_isolation",
    ]
    for tbl, pol in zip(
        [
            "users",
            "content_pieces",
            "content_versions",
            "brand_voices",
            "glossaries",
            "glossary_terms",
            "bulk_jobs",
            "audit_logs",
            "api_keys",
            "webhook_configs",
            "experiments",
            "experiment_variants",
            "experiment_assignments",
            "experiment_exposures",
            "prompt_versions",
        ],
        _policy_names,
        strict=False,
    ):
        op.execute(f"DROP POLICY IF EXISTS {pol} ON {tbl}")

    # 2. Drop child partitions BEFORE their parents.
    for i in range(16):
        op.execute(f"DROP TABLE IF EXISTS content_pieces_p{i}")

    _drop_monthly_partitions(op, "audit_logs", count=24, prefix="audit_logs")
    _drop_monthly_partitions(
        op, "experiment_assignments", count=24, prefix="experiment_assignments"
    )
    _drop_weekly_partitions(op, "experiment_exposures", count=52, prefix="experiment_exposures")
    _drop_weekly_partitions(op, "performance_events", count=52, prefix="performance_events")

    # 3. Drop tables in reverse dependency order.
    tables_in_drop_order = [
        "prompt_versions",
        "performance_events",
        "experiment_exposures",
        "experiment_assignments",
        "experiment_variants",
        "experiments",
        "webhook_configs",
        "api_keys",
        "audit_logs",
        "bulk_jobs",
        "glossary_terms",
        "glossaries",
        "brand_voices",
        "content_versions",
        "content_pieces",
        "generation_cache",
        "market_profiles",
        "users",
        "workspaces",
    ]
    for tbl in tables_in_drop_order:
        op.drop_table(tbl)

    # 4. Drop enum types.
    for enum_name in [
        "prompt_status",
        "performance_metric_type",
        "exposure_channel",
        "experiment_status",
        "bulk_job_status",
        "content_status",
        "user_role",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_monthly_partitions(
    op_impl: Any,  # alembic.ops.Operations (not publicly typed)
    table: str,
    column: str,  # noqa: ARG001
    *,
    start: date,
    count: int,
) -> None:
    """Create ``count`` monthly RANGE partitions for *table*."""
    current = start
    for _idx in range(count):
        next_month = current.replace(day=28) + timedelta(days=4)
        next_start = next_month.replace(day=1)
        partition_name = f"{table}_y{current.year}m{current.month:02d}"
        op_impl.execute(
            f"CREATE TABLE IF NOT EXISTS {partition_name} "
            f"PARTITION OF {table} "
            f"FOR VALUES FROM ('{current.isoformat()}') TO ('{next_start.isoformat()}')"
        )
        current = next_start


def _create_weekly_partitions(
    op_impl: Any,  # alembic.ops.Operations
    table: str,
    column: str,  # noqa: ARG001  (kept for symmetry)
    *,
    start: date,
    count: int,
) -> None:
    """Create ``count`` weekly RANGE partitions for *table*.

    ``start`` should be a Monday.
    """
    current = start
    for _ in range(count):
        week_end = current + timedelta(weeks=1)
        partition_name = f"{table}_w{current.isocalendar()[0]}w{current.isocalendar()[1]:02d}"
        op_impl.execute(
            f"CREATE TABLE IF NOT EXISTS {partition_name} "
            f"PARTITION OF {table} "
            f"FOR VALUES FROM ('{current.isoformat()}') TO ('{week_end.isoformat()}')"
        )
        current = week_end


def _drop_monthly_partitions(
    op_impl: Any,  # alembic.ops.Operations
    table: str,
    *,
    count: int,
    prefix: str,
) -> None:
    """Drop monthly partitions created by ``_create_monthly_partitions``."""
    start = date(2026, 1, 1)
    current = start
    for _ in range(count):
        next_month = current.replace(day=28) + timedelta(days=4)
        next_start = next_month.replace(day=1)
        partition_name = f"{prefix}_y{current.year}m{current.month:02d}"
        op_impl.execute(f"DROP TABLE IF EXISTS {partition_name}")
        current = next_start


def _drop_weekly_partitions(
    op_impl: Any,  # alembic.ops.Operations
    table: str,  # noqa: ARG001
    *,
    count: int,
    prefix: str,
) -> None:
    """Drop weekly partitions created by ``_create_weekly_partitions``."""
    start = date(2026, 1, 5)
    current = start
    for _ in range(count):
        partition_name = f"{prefix}_w{current.isocalendar()[0]}w{current.isocalendar()[1]:02d}"
        op_impl.execute(f"DROP TABLE IF EXISTS {partition_name}")
        current += timedelta(weeks=1)
