"""Remembered state for the monitors, so they report changes, not conditions.

A monitor describes what is wrong right now as findings: a dict from a stable
key (``disabled:dubbo``, ``thin:NSW``) to a small dict with at least ``msg``.
The key must not contain anything that changes from run to run, such as an
hour count, or every run looks like a new problem. Comparing this run's
findings with the last reported ones gives what opened and what cleared;
anything still open is not repeated.
"""
from datetime import datetime
from typing import Dict, Optional, Tuple

from core.models import MonitorState

Findings = Dict[str, Dict]


def load_state(db, key: str) -> Optional[Dict]:
    """The monitor's saved value, or None if it has never saved one."""
    with db.get_session() as s:
        row = s.get(MonitorState, key)
        return dict(row.value) if row is not None and row.value is not None else None


def save_state(db, key: str, value: Dict) -> None:
    with db.get_session() as s:
        row = s.get(MonitorState, key)
        if row is None:
            s.add(MonitorState(key=key, value=value, updated_at=datetime.utcnow()))
        else:
            row.value = value
            row.updated_at = datetime.utcnow()
        s.commit()


def diff_findings(previous: Findings, current: Findings) -> Tuple[Findings, Findings]:
    """(opened, cleared): keys new in ``current``, and keys gone from it."""
    opened = {k: v for k, v in current.items() if k not in previous}
    cleared = {k: v for k, v in previous.items() if k not in current}
    return opened, cleared
