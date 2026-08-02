"""Tests for the promotion runner's safety properties.

The runner is invoked from cron, so it must survive being run twice on the same
day - by a retry, by a manual re-run, or by two containers overlapping. Posting
the same promo twice into someone else's hashtag is exactly the behaviour that
makes a bot unwelcome.
"""
import importlib
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def runner(tmp_path, monkeypatch):
    """A runner writing its ledger to a temp dir, with sending stubbed out."""
    monkeypatch.setenv("LGNEWS_DATA_DIR", str(tmp_path))
    module = importlib.import_module("scripts.cron.run_promotion")
    importlib.reload(module)

    sent = []

    def fake_send(channel, account, text, dry_run):
        sent.append((channel.key, account, text))
        return "posted: at://fake/{}".format(len(sent))

    monkeypatch.setattr(module, "send", fake_send)
    module.sent = sent
    return module


def _first_promo_day(module, key):
    from datetime import timedelta
    for n in range(400):
        day = module.EPOCH + timedelta(days=n)
        if any(c.key == key for c in module.due_channels(day, module.EPOCH)):
            return day
    raise AssertionError("no promo day found for " + key)


def test_running_twice_on_the_same_day_posts_once(runner):
    """The core guarantee: cron retries must not double-post."""
    day = _first_promo_day(runner, "nsw")
    runner.run(day, dry_run=False, verbose=False)
    first = len(runner.sent)
    runner.run(day, dry_run=False, verbose=False)
    assert len(runner.sent) == first, "second run posted again"


def test_a_quiet_day_posts_nothing(runner):
    from datetime import timedelta
    quiet = next(runner.EPOCH + timedelta(days=n) for n in range(60)
                 if not runner.due_channels(runner.EPOCH + timedelta(days=n),
                                            runner.EPOCH))
    runner.run(quiet, dry_run=False, verbose=False)
    assert runner.sent == []


def test_dry_run_sends_nothing_and_records_nothing(runner, tmp_path):
    day = _first_promo_day(runner, "nsw")
    runner.run(day, dry_run=True, verbose=False)
    ledger = runner._load(runner.LEDGER)
    assert ledger == {}, "a dry run must not consume the occurrence"


def test_the_national_channel_is_never_sent_unattended(runner):
    """It posts from a person's account, so cron only ever drafts it."""
    day = _first_promo_day(runner, "national")
    runner.run(day, dry_run=False, verbose=False)
    assert all(key != "national" for key, _, _ in runner.sent)
    drafts = runner._load(runner.DRAFTS)
    assert "national" in drafts


def test_approving_a_draft_sends_it_once(runner):
    day = _first_promo_day(runner, "national")
    runner.run(day, dry_run=False, verbose=False)

    runner.approve("national", dry_run=False)
    assert [k for k, _, _ in runner.sent].count("national") == 1

    # A second approval of the same occurrence must not resend.
    runner.approve("national", dry_run=False)
    assert [k for k, _, _ in runner.sent].count("national") == 1


def test_approving_with_no_draft_is_not_an_error_that_posts(runner):
    assert runner.approve("national", dry_run=False) == 1
    assert runner.sent == []


def test_a_failed_send_does_not_consume_the_occurrence(runner, monkeypatch):
    """A network failure should leave the promo to be retried, not lose it."""
    monkeypatch.setattr(runner, "send",
                        lambda channel, account, text, dry_run: "failed: authentication")
    day = _first_promo_day(runner, "nsw")
    runner.run(day, dry_run=False, verbose=False)
    assert runner._load(runner.LEDGER) == {}


def test_the_window_holds_a_channel_until_its_local_morning(runner):
    """Cron ticks hourly across 21:00-01:00 UTC; each feed waits for its own
    local 07:30-09:00, which is why Perth does not post at 5am."""
    from datetime import timedelta
    day = _first_promo_day(runner, "nsw")
    channel = next(c for c in runner.due_channels(day, runner.EPOCH)
                   if c.key == "nsw")
    when = runner.post_time_utc(channel, day, 0)

    runner.run(day, dry_run=False, verbose=False,
               now=when - timedelta(minutes=30), respect_window=True)
    assert runner.sent == [], "posted before the window opened"

    runner.run(day, dry_run=False, verbose=False,
               now=when + timedelta(minutes=1), respect_window=True)
    assert [k for k, _, _ in runner.sent] == ["nsw"]


def test_hourly_ticks_across_the_window_still_post_once(runner):
    """The cron line fires five times a night; the ledger is what makes that
    safe."""
    from datetime import timedelta
    day = _first_promo_day(runner, "nsw")
    channel = next(c for c in runner.due_channels(day, runner.EPOCH)
                   if c.key == "nsw")
    when = runner.post_time_utc(channel, day, 0)
    for hour in range(-2, 4):
        runner.run(day, dry_run=False, verbose=False,
                   now=when + timedelta(hours=hour), respect_window=True)
    assert [k for k, _, _ in runner.sent].count("nsw") == 1


def test_an_unwritable_ledger_stops_the_run(runner, tmp_path, monkeypatch):
    """Without a writable ledger nothing prevents a repeat post, and the cron
    line ticks five times a night - so refuse to start."""
    blocked = tmp_path / "readonly"
    blocked.mkdir()
    blocked.chmod(0o500)
    monkeypatch.setattr(runner, "LEDGER", blocked / "sub" / "ledger.json")
    try:
        assert runner.check_ledger_is_writable() is False
    finally:
        blocked.chmod(0o700)


def test_a_writable_ledger_passes_the_check(runner):
    assert runner.check_ledger_is_writable() is True


def test_the_ledger_records_what_was_actually_posted(runner):
    day = _first_promo_day(runner, "nsw")
    runner.run(day, dry_run=False, verbose=False)
    ledger = runner._load(runner.LEDGER)
    assert len(ledger) == 1
    entry = next(iter(ledger.values()))
    assert "#NSWpol" == entry["tag"]
    assert "posted_at" in entry and entry["text"]
