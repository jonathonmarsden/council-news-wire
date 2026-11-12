"""The edge prune scans the whole table, so the sync asks for it once a day."""
from datetime import datetime

from scripts.cron.sync_edge import PRUNE_HOUR_UTC, prune_due


def test_prune_only_on_first_sync_of_the_prune_hour():
    assert prune_due(datetime(2026, 11, 12, PRUNE_HOUR_UTC, 8))
    assert not prune_due(datetime(2026, 11, 12, PRUNE_HOUR_UTC, 18))
    assert not prune_due(datetime(2026, 11, 12, (PRUNE_HOUR_UTC + 1) % 24, 8))
