import os
import threading
import uuid
from datetime import datetime
from typing import Dict, Optional

import requests

from core.database import Database

DISCORD_WEBHOOK_LOGS = os.environ.get("DISCORD_WEBHOOK_LOGS")
DISCORD_WEBHOOK_ALERTS = os.environ.get("DISCORD_WEBHOOK_ALERTS")


class RunTracker:
    """Tracks a single bot run and stores structured telemetry in Postgres."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._db = None
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.run_id = None
            self.state = None
            self.started_at = None
            self.councils_scraped = 0
            self.articles_found = 0
            self.articles_posted = 0
            self.errors_count = 0
            self.warnings_count = 0

    def _get_db(self) -> Optional[Database]:
        """
        Lazily create the DB handle so log_warning/log_error persist events
        even from scripts that never call start_run() — they used to be
        silently dropped.
        """
        if self._db is None:
            try:
                self._db = Database()
            except Exception:
                return None
        return self._db

    def start(self, state_code: str) -> str:
        if self._db is None:
            self._db = Database()
        with self._lock:
            self.run_id = uuid.uuid4().hex
            self.state = state_code.upper()
            self.started_at = datetime.utcnow()
            self.councils_scraped = 0
            self.articles_found = 0
            self.articles_posted = 0
            self.errors_count = 0
            self.warnings_count = 0
            return self.run_id

    def log_council_result(self, council_name: str, found: int) -> None:
        with self._lock:
            self.councils_scraped += 1
            self.articles_found += found

    def log_posted(self, count: int = 1) -> None:
        with self._lock:
            self.articles_posted += count

    def log_warning(
        self,
        council_id: Optional[str],
        message: str,
        event_type: str = "warning",
        event_metadata: Optional[Dict] = None,
    ) -> None:
        with self._lock:
            self.warnings_count += 1
            run_id = self.run_id
            state = self.state

        db = self._get_db()
        if not db:
            return
        db.add_log_event(
            event_type=event_type,
            severity="warning",
            message=message,
            run_id=run_id,
            state=state,
            council_id=council_id,
            event_metadata=event_metadata,
        )

    def log_error(
        self,
        council_id: Optional[str],
        message: str,
        event_type: str = "error",
        event_metadata: Optional[Dict] = None,
    ) -> None:
        with self._lock:
            self.errors_count += 1
            run_id = self.run_id
            state = self.state

        db = self._get_db()
        if not db:
            return
        db.add_log_event(
            event_type=event_type,
            severity="error",
            message=message,
            run_id=run_id,
            state=state,
            council_id=council_id,
            event_metadata=event_metadata,
        )

    def finish(self) -> None:
        with self._lock:
            if not self.run_id or not self.state or not self.started_at:
                return

            ended_at = datetime.utcnow()
            duration_ms = int((ended_at - self.started_at).total_seconds() * 1000)
            summary = {
                "run_id": self.run_id,
                "state": self.state,
                "started_at": self.started_at,
                "ended_at": ended_at,
                "duration_ms": duration_ms,
                "councils_scraped": self.councils_scraped,
                "articles_found": self.articles_found,
                "articles_posted": self.articles_posted,
                "errors_count": self.errors_count,
                "warnings_count": self.warnings_count,
            }

        if not self._db:
            return
        self._db.upsert_run_summary(summary)


current_run = RunTracker()


def start_run(state_code: str) -> str:
    """Initialize a new run tracker for the current process."""
    return current_run.start(state_code)


def finish_run() -> None:
    """Finalize and persist the current run summary."""
    current_run.finish()


def log_warning(council_id: Optional[str], message: str, event_type: str = "warning", event_metadata: Optional[Dict] = None) -> None:
    current_run.log_warning(council_id, message, event_type=event_type, event_metadata=event_metadata)


def log_error(council_id: Optional[str], message: str, event_type: str = "error", event_metadata: Optional[Dict] = None) -> None:
    current_run.log_error(council_id, message, event_type=event_type, event_metadata=event_metadata)


def log_generic_report(title: str, description: str, color: int = 3447003) -> None:
    """Send a one-off report embed to the logs channel."""
    embed = {
        "title": title,
        "description": description[:4000],
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
    }
    send_discord_embed(DISCORD_WEBHOOK_LOGS, embed)


def send_discord_embed(webhook_url: Optional[str], embed_dict: Dict, username: str = "Roundup News Bot") -> None:
    if not webhook_url:
        print("Discord webhook URL not configured; skipping log")
        return

    data = {
        "embeds": [embed_dict],
        "username": username,
    }

    _send_webhook(webhook_url, data)


def _send_webhook(url: str, data: Dict) -> None:
    max_attempts = 3
    backoff = 1

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(url, json=data, timeout=10)
        except Exception as e:
            print(f"Attempt {attempt}: Failed to send Discord webhook (exception): {e}")
            resp = None

        if resp is None:
            if attempt < max_attempts:
                _sleep(backoff)
                backoff *= 2
                continue
            print("Discord webhook failed after retries (network error)")
            return

        if resp.status_code in (200, 204):
            return

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            print(f"Attempt {attempt}: Discord webhook rate limited, Retry-After={retry_after}")
            if attempt < max_attempts:
                try:
                    wait = int(retry_after) if retry_after and retry_after.isdigit() else backoff
                except Exception:
                    wait = backoff
                backoff *= 2
                _sleep(wait)
                continue
            print("Discord webhook failed after retries (rate limited)")
            print("Response:", resp.status_code, resp.text[:1000])
            return

        print(f"Discord webhook returned HTTP {resp.status_code}: {resp.text[:1000]}")
        return


def _sleep(seconds: int) -> None:
    try:
        from time import sleep

        sleep(seconds)
    except Exception:
        pass
