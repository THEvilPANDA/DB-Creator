"""initial

Revision ID: 795daa253739
Revises:
Create Date: 2026-06-24

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "795daa253739"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "servers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="5432"),
        sa.Column("engine", sa.String(50), nullable=False, server_default="postgresql"),
        sa.Column("environment", sa.String(50), nullable=False),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_connections", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("max_storage_gb", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("warning_threshold_pct", sa.Float(), nullable=False, server_default="75.0"),
        sa.Column("critical_threshold_pct", sa.Float(), nullable=False, server_default="90.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(255), nullable=True),
    )

    op.create_table(
        "naming_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("pattern", sa.String(500), nullable=False),
        sa.Column("prefix", sa.String(100), nullable=True),
        sa.Column("suffix", sa.String(100), nullable=True),
        sa.Column("separator", sa.String(10), nullable=False, server_default="_"),
        sa.Column("reserved_names", sa.JSON(), nullable=True),
        sa.Column("allow_collision", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(255), nullable=True),
    )

    op.create_table(
        "database_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("extensions", sa.JSON(), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(255), nullable=True),
    )

    op.create_table(
        "request_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("environment", sa.String(50), nullable=False),
        sa.Column("db_template_id", sa.Integer(), sa.ForeignKey("database_templates.id"), nullable=True),
        sa.Column("naming_profile_id", sa.Integer(), sa.ForeignKey("naming_profiles.id"), nullable=True),
        sa.Column("expiration_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("cost_center", sa.String(255), nullable=True),
        sa.Column("team", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(255), nullable=True),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("db_name", sa.String(255), nullable=False),
        sa.Column("environment", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id"), nullable=True),
        sa.Column("naming_profile_id", sa.Integer(), sa.ForeignKey("naming_profiles.id"), nullable=True),
        sa.Column("db_template_id", sa.Integer(), sa.ForeignKey("database_templates.id"), nullable=True),
        sa.Column("request_template_id", sa.Integer(), sa.ForeignKey("request_templates.id"), nullable=True),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("team", sa.String(255), nullable=True),
        sa.Column("cost_center", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(255), nullable=True),
    )

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("approver", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "creation_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id"), nullable=False),
        sa.Column("db_name", sa.String(255), nullable=False),
        sa.Column("db_user", sa.String(255), nullable=True),
        sa.Column("connection_uri", sa.Text(), nullable=True),
        sa.Column("iac_yaml", sa.Text(), nullable=True),
        sa.Column("iac_terraform", sa.Text(), nullable=True),
        sa.Column("provisioned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(255), nullable=True),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("creation_logs")
    op.drop_table("approval_requests")
    op.drop_table("jobs")
    op.drop_table("request_templates")
    op.drop_table("database_templates")
    op.drop_table("naming_profiles")
    op.drop_table("servers")
