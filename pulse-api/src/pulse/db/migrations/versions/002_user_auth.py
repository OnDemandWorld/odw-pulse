"""User authentication fields and enforceable RLS.

Revision ID: 002_user_auth
Revises: 001_initial_schema
Create Date: 2026-09-01

* Adds ``users.password_hash`` so login can be validated against real user
  records (the mock user store was removed).
* Makes ``users.email`` globally unique: login identifies a user without
  workspace context, so email cannot be scoped per workspace.
* Turns on ``FORCE ROW LEVEL SECURITY`` for every workspace-scoped table so
  the policies from migration 001 bind the table *owner* too, not just other
  roles.
* Grants DML on the schema to the dedicated ``pulse_api`` role when it
  exists.  The role itself is created by the deployment bootstrap
  (``docker/postgres-init.sql`` for compose, the ``postgres-init`` ConfigMap
  for k8s) — see PLAN.md, Phase 2.  The API connects as ``pulse_api``
  (RLS-scoped); login/registration use a privileged admin connection
  (``DATABASE_ADMIN_URL``); worker/scheduler stay on the trusted role.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_user_auth"
down_revision: str | None = "001_initial_schema"
branch_labels: str | None = None
depends_on: str | None = None

# Same set of workspace-scoped tables as migration 001.
_WORKSPACE_TABLES = [
    "users",
    "content_pieces",
    "content_versions",
    "review_annotations",
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


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Real user credentials.
    # ------------------------------------------------------------------
    op.add_column("users", sa.Column("password_hash", sa.Text, nullable=True))

    # Login looks users up by email alone (no workspace context yet), so
    # email must be globally unique.
    op.drop_constraint("uq_users_workspace_email", "users", type_="unique")
    op.create_unique_constraint("uq_users_email", "users", ["email"])

    # ------------------------------------------------------------------
    # 2. Bind the table owner to the RLS policies as well.  Enforcement
    #    becomes real once the API connects with the non-owner pulse_api
    #    role; superusers still bypass RLS (postgres behaviour).
    # ------------------------------------------------------------------
    for tbl in _WORKSPACE_TABLES:
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")

    # ------------------------------------------------------------------
    # 3. Grants for the dedicated API role, when the deployment created it.
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pulse_api') THEN
                GRANT USAGE ON SCHEMA public TO pulse_api;
                GRANT SELECT, INSERT, UPDATE, DELETE
                    ON ALL TABLES IN SCHEMA public TO pulse_api;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public
                    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pulse_api;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pulse_api') THEN
                REVOKE SELECT, INSERT, UPDATE, DELETE
                    ON ALL TABLES IN SCHEMA public FROM pulse_api;
                REVOKE USAGE ON SCHEMA public FROM pulse_api;
            END IF;
        END $$;
        """
    )

    for tbl in _WORKSPACE_TABLES:
        op.execute(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY")

    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.create_unique_constraint("uq_users_workspace_email", "users", ["workspace_id", "email"])
    op.drop_column("users", "password_hash")
