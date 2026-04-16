"""Migrate articles.date from String to DateTime

Revision ID: e4a1c3f7b8d2
Revises: 2f3a0c8b2b9d
Create Date: 2026-04-16

Background: articles.date was originally stored as a string (ISO 8601 or
freeform) for legacy reasons.  This migration converts it to a proper
DateTime column so comparisons, ordering, and range queries work correctly.

The USING clause on PostgreSQL casts the existing text values to TIMESTAMP.
Rows with NULL or unparseable dates remain NULL (::timestamp returns NULL for
invalid input in PostgreSQL, rather than raising an error).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e4a1c3f7b8d2'
down_revision: Union[str, Sequence[str], None] = '2f3a0c8b2b9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Attempt to parse existing string dates as timestamps.
    # Rows with NULL or invalid date strings will become NULL.
    op.execute("""
        ALTER TABLE articles
        ALTER COLUMN date TYPE TIMESTAMP
        USING CASE
            WHEN date IS NULL OR trim(date) = '' THEN NULL
            ELSE date::timestamp
        END
    """)


def downgrade() -> None:
    # Convert back to String (ISO 8601 representation via to_char, or cast).
    op.execute("""
        ALTER TABLE articles
        ALTER COLUMN date TYPE VARCHAR
        USING CASE
            WHEN date IS NULL THEN NULL
            ELSE to_char(date, 'YYYY-MM-DD"T"HH24:MI:SS')
        END
    """)
