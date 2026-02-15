#!/usr/bin/env python3
"""
Deprecated: SQLite database merge is no longer supported.

The project now uses PostgreSQL exclusively. Use pg_dump/pg_restore or SQL-based
data migration instead.
"""

import sys

def main() -> None:
    print("SQLite merge is deprecated. Use pg_dump/pg_restore for PostgreSQL.")
    sys.exit(1)

if __name__ == "__main__":
    main()
