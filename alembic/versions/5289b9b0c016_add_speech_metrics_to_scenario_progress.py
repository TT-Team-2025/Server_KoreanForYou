"""add speech_metrics to scenario_progress

Revision ID: 5289b9b0c016
Revises: 6a88f53650de
Create Date: 2025-11-11 05:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "5289b9b0c016"
down_revision = "6a88f53650de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('scenario_progress')]
    
    if 'speech_metrics' not in columns:
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

