"""
Shared fixtures for the regression suite.

These fixtures are deliberately hermetic: no network, no external database,
no credentials. Every test using them runs offline in milliseconds, so the
suite can run on any contributor's machine and in a fork's CI.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import Database  # noqa: E402
from core.models import Base  # noqa: E402


@pytest.fixture
def db():
    """An isolated in-memory database with the real schema."""
    database = Database(db_url="sqlite:///:memory:", create_tables=True)
    yield database
    Base.metadata.drop_all(database.engine)


def make_article(url="https://example.gov.au/news/1", council_id="testville",
                 title="Test article", date=None, excerpt="An excerpt"):
    """Build an article dict in the shape process_articles produces."""
    return {
        "url": url,
        "council_id": council_id,
        "title": title,
        "date": date if date is not None else datetime.now(),
        "excerpt": excerpt,
    }


@pytest.fixture
def article_factory():
    return make_article


class FakeResponse:
    """Minimal stand-in for an ATProto post response."""

    def __init__(self, uri="at://did:plc:test/app.bsky.feed.post/abc"):
        self.uri = uri


class FakeHTTPError(Exception):
    """Exception carrying an HTTP status, mimicking an API error."""

    def __init__(self, status_code, message="api error"):
        super().__init__(message)
        self.response = type("R", (), {"status_code": status_code})()


class FakeClient:
    """
    Stand-in for the ATProto client.

    Records every post attempt so tests can assert exactly-once behaviour,
    and can be told to fail in specific ways to exercise error handling.
    """

    def __init__(self, fail_with=None, fail_times=0):
        self.posts = []
        self.login_calls = 0
        self.fail_with = fail_with
        self.fail_times = fail_times

    def login(self, handle, password):
        self.login_calls += 1
        return True

    def send_post(self, text, facets=None):
        if self.fail_with is not None and self.fail_times != 0:
            if self.fail_times > 0:
                self.fail_times -= 1
            raise self.fail_with
        self.posts.append({"text": text, "facets": facets})
        return FakeResponse()


@pytest.fixture
def fake_client():
    return FakeClient


@pytest.fixture
def poster(fake_client):
    """A BlueSkyPoster wired to a fake client — never touches the network."""
    from core.poster import BlueSkyPoster

    def _make(fail_with=None, fail_times=0, state_code="VIC", auth_fails=False):
        p = BlueSkyPoster("roundupnewsbotvic.bsky.social", "app-password",
                          state_code=state_code)
        client = fake_client(fail_with=fail_with, fail_times=fail_times)
        p.client = client
        p._authenticated = not auth_fails

        # authenticate() would construct a real network client; keep the fake.
        def _authenticate():
            if auth_fails:
                return False
            p.client = client
            p._authenticated = True
            return True

        p.authenticate = _authenticate
        return p

    return _make


@pytest.fixture
def days_ago():
    return lambda n: datetime.now() - timedelta(days=n)
