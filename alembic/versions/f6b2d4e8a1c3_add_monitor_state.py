"""Add monitor_state: what each monitor last reported

Revision ID: f6b2d4e8a1c3
Revises: c5d8e9f01a2b
Create Date: 2026-11-05

The alert monitors used to report every open condition on every run, so the
same notice arrived four times a day for weeks. They now remember what they
last reported and speak only when a problem opens or clears.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6b2d4e8a1c3'
down_revision: Union[str, Sequence[str], None] = 'c5d8e9f01a2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'monitor_state',
        sa.Column('key', sa.String(), primary_key=True),
        sa.Column('value', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('monitor_state')
