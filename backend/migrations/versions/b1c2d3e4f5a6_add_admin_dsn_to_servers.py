"""add admin_dsn to servers

Revision ID: b1c2d3e4f5a6
Revises: 795daa253739
Create Date: 2026-06-24

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "795daa253739"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("servers", sa.Column("admin_dsn", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("servers", "admin_dsn")
