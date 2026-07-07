"""Add articles.attempt_count for post retry dead-lettering

Revision ID: b7c9d1e2f3a4
Revises: e4a1c3f7b8d2
Create Date: 2026-07-07

Transient BlueSky failures now leave articles queued for retry instead of
permanently rejecting them. attempt_count tracks failed attempts so a poison
article can be dead-lettered (status='failed') after repeated failures.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c9d1e2f3a4'
down_revision: Union[str, Sequence[str], None] = 'e4a1c3f7b8d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('articles', sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('articles', 'attempt_count')
