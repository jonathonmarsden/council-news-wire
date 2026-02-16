"""Add logging tables

Revision ID: 2f3a0c8b2b9d
Revises: d99b9970035d
Create Date: 2026-02-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f3a0c8b2b9d'
down_revision: Union[str, Sequence[str], None] = 'd99b9970035d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'log_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.String(), nullable=True),
        sa.Column('state', sa.String(), nullable=True),
        sa.Column('council_id', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('event_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_log_events_council_id'), 'log_events', ['council_id'], unique=False)
    op.create_index(op.f('ix_log_events_run_id'), 'log_events', ['run_id'], unique=False)
    op.create_index(op.f('ix_log_events_state'), 'log_events', ['state'], unique=False)

    op.create_table(
        'run_summaries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('councils_scraped', sa.Integer(), nullable=False),
        sa.Column('articles_found', sa.Integer(), nullable=False),
        sa.Column('articles_posted', sa.Integer(), nullable=False),
        sa.Column('errors_count', sa.Integer(), nullable=False),
        sa.Column('warnings_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id')
    )
    op.create_index(op.f('ix_run_summaries_run_id'), 'run_summaries', ['run_id'], unique=True)
    op.create_index(op.f('ix_run_summaries_state'), 'run_summaries', ['state'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_run_summaries_state'), table_name='run_summaries')
    op.drop_index(op.f('ix_run_summaries_run_id'), table_name='run_summaries')
    op.drop_table('run_summaries')

    op.drop_index(op.f('ix_log_events_state'), table_name='log_events')
    op.drop_index(op.f('ix_log_events_run_id'), table_name='log_events')
    op.drop_index(op.f('ix_log_events_council_id'), table_name='log_events')
    op.drop_table('log_events')
