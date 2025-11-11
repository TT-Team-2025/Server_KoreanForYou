"""add speech_metrics to scenario_progress

Revision ID: 7b95c3c9a471
Revises: 6a88f53650de
Create Date: 2025-11-11 04:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "7b95c3c9a471"
down_revision = "6a88f53650de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scenario_progress",
        sa.Column(
            "speech_metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.execute(
        "UPDATE scenario_progress SET speech_metrics = '[]'::jsonb WHERE speech_metrics IS NULL"
    )
    op.alter_column("scenario_progress", "speech_metrics", server_default=None)


def downgrade() -> None:
    op.drop_column("scenario_progress", "speech_metrics")

