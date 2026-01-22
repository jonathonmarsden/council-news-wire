#!/usr/bin/env python3
"""
Merge the old database (pre-Dec-5) into the new database (post-Dec-5).
This fixes the 'Stale' status for councils that haven't posted news since the migration.

Usage:
    python3 scripts/maintenance/merge_databases.py --old ./bot.db --new ./data/bot.db
"""

import sqlite3
import argparse
import sys
from pathlib import Path

def merge_databases(old_db_path, new_db_path, dry_run=False):
    print(f"Merging {old_db_path} -> {new_db_path}")
    
    if not Path(old_db_path).exists():
        print(f"Error: Old DB {old_db_path} not found.")
        return
    if not Path(new_db_path).exists():
        print(f"Error: New DB {new_db_path} not found.")
        return

    # Connect to both
    conn_old = sqlite3.connect(old_db_path)
    conn_new = sqlite3.connect(new_db_path)
    
    conn_old.row_factory = sqlite3.Row
    
    cursor_old = conn_old.cursor()
    cursor_new = conn_new.cursor()
    
    # helper to check schema
    def get_columns(cursor, table):
        cursor.execute(f"PRAGMA table_info({table})")
        return {r[1] for r in cursor.fetchall()}

    # Check tables
    cursor_old.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables_old = {r['name'] for r in cursor_old.fetchall()}
    
    print(f"Tables in old DB: {tables_old}")
    
    if 'articles' not in tables_old:
        print("Error: 'articles' table not found in old DB.")
        return

    # Get articles from old
    cursor_old.execute("SELECT * FROM articles")
    articles = cursor_old.fetchall()
    print(f"Found {len(articles)} articles in old DB.")
    
    merged_count = 0
    skipped_count = 0
    error_count = 0
    
    print(f"{'DRY RUN ' if dry_run else ''}Starting merge...")
    
    try:
        # Get columns of target table to match dynamic schema if needed
        # Assuming schema is identical for now, or at least compatible
        # We'll construct the INSERT dynamically based on keys provided
        
        for article in articles:
            # article is a Row object
            data = dict(article)
            
            # Check if exists
            # We assume 'url' or 'council_id'+'title' is unique? 
            # The schema usually has a unique constraint on url or similar.
            
            # Let's try to insert and catch IntegrityError (Duplicate)
            keys = list(data.keys())
            placeholders = ', '.join(['?'] * len(keys))
            columns = ', '.join(keys)
            values = list(data.values())
            
            sql = f"INSERT INTO articles ({columns}) VALUES ({placeholders})"
            
            try:
                if not dry_run:
                    cursor_new.execute(sql, values)
                merged_count += 1
            except sqlite3.IntegrityError:
                # Duplicate
                skipped_count += 1
            except Exception as e:
                print(f"Error inserting article {data.get('url', 'unknown')}: {e}")
                error_count += 1
                
        if not dry_run:
            conn_new.commit()
            print("Changes committed.")
        else:
            print("Dry run - no changes committed.")
            
    except Exception as e:
        print(f"Fatal error during merge: {e}")
    finally:
        conn_old.close()
        conn_new.close()

    print(f"\nSummary:")
    print(f"  Attempted: {len(articles)}")
    print(f"  Merged:    {merged_count}")
    print(f"  Skipped:   {skipped_count} (Duplicates)")
    print(f"  Errors:    {error_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Merge SQLite databases.')
    parser.add_argument('--old', required=True, help='Path to source DB')
    parser.add_argument('--new', required=True, help='Path to destination DB')
    parser.add_argument('--dry-run', action='store_true', help='Do not commit changes')
    
    args = parser.parse_args()
    
    merge_databases(args.old, args.new, args.dry_run)
