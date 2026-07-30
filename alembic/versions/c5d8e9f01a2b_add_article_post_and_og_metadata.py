"""Add BlueSky post identifiers and OpenGraph metadata to articles

Revision ID: c5d8e9f01a2b
Revises: b7c9d1e2f3a4
Create Date: 2026-07-30

Two gaps this closes.

1. We recorded that an article was posted (posted_at, posted_to_handle) but not
   WHERE. Finding a story's own post again meant scraping the public feed and
   matching on title, which is how a duplicate slipped through during a card
   backfill. bluesky_uri/bluesky_cid make dedup, correction and engagement
   lookups direct.

2. Link cards fetch a page's OpenGraph title/description/image at post time and
   then discarded them. Keeping og_image_url/og_description means cards can be
   rebuilt or audited without re-fetching a council's site, and image_status
   makes the per-council image gap measurable - the input to deciding where a
   generated fallback card is needed.

All columns are nullable with no backfill: existing rows keep NULL, which reads
correctly as "we did not record this at the time".
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5d8e9f01a2b'
down_revision: Union[str, Sequence[str], None] = 'b7c9d1e2f3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('articles', sa.Column('bluesky_uri', sa.String(), nullable=True))
    op.add_column('articles', sa.Column('bluesky_cid', sa.String(), nullable=True))
    op.add_column('articles', sa.Column('og_image_url', sa.Text(), nullable=True))
    op.add_column('articles', sa.Column('og_description', sa.Text(), nullable=True))
    op.add_column('articles', sa.Column('image_status', sa.String(), nullable=True))
    op.create_index('ix_articles_bluesky_uri', 'articles', ['bluesky_uri'])
    op.create_index('ix_articles_image_status', 'articles', ['image_status'])


def downgrade() -> None:
    op.drop_index('ix_articles_image_status', table_name='articles')
    op.drop_index('ix_articles_bluesky_uri', table_name='articles')
    op.drop_column('articles', 'image_status')
    op.drop_column('articles', 'og_description')
    op.drop_column('articles', 'og_image_url')
    op.drop_column('articles', 'bluesky_cid')
    op.drop_column('articles', 'bluesky_uri')
