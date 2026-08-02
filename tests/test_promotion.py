"""Tests for the scheduled hashtag promotion.

The failure this design exists to prevent is the one that actually happened: in
July 2026 community tags were added to routine story posts and the feeds became
49% of #LocalGov, 16% of #NSWpol and 14% of #WApol within hours. So the tests
below care most about footprint - how often we post, how much of a tag that is,
and whether anything can post twice.
"""
from datetime import date, timedelta

import pytest

from core.promotion import (
    CHANNELS, EXCLUDED, MAX_CHANNELS_PER_DAY, ROTATION_STEP_DAYS, account_for,
    deferred_channels, due_channels, interval_for, occurrence_index,
    post_time_utc,
)
from core.promotion_copy import STATE_FACTS, compose

EPOCH = date(2026, 8, 3)


def _channel(key):
    return next(c for c in CHANNELS if c.key == key)


# --- footprint: the whole point of the exercise -------------------------------

def test_no_tag_carries_more_than_a_tenth_of_its_traffic_from_us():
    """A promo should be a participant in a tag, not a fixture of it.

    Shares are summed PER TAG, not per channel: #Auspol carries both the human
    account weekly and a rotating bot slot fortnightly, and it is the total
    footprint in someone else's tag that matters, not any one channel's.
    """
    from collections import defaultdict
    per_tag = defaultdict(float)
    volume = {}
    for channel in CHANNELS:
        per_tag[channel.tag] += 7.0 / interval_for(channel)
        volume[channel.tag] = channel.weekly_volume
    for tag, posts_per_week in per_tag.items():
        share = 100.0 * posts_per_week / volume[tag]
        assert share < 10.0, (
            "{} would carry {:.1f}% of its traffic from us".format(tag, share))


def test_act_is_excluded_entirely():
    """#ACTpol carries ~2 posts a week; any cadence would dominate it."""
    assert "act" in EXCLUDED
    assert not any(c.key == "act" for c in CHANNELS)
    assert not any("actpol" in c.tag.lower() for c in CHANNELS)


def test_smaller_tags_get_longer_intervals():
    """Cadence has to track tag volume, or a uniform schedule floods the quiet
    tags while being invisible in the busy ones."""
    state_channels = [c for c in CHANNELS if c.key in
                      ("nsw", "vic", "qld", "wa", "sa", "tas", "nt")]
    ordered = sorted(state_channels, key=lambda c: c.weekly_volume)
    intervals = [interval_for(c) for c in ordered]
    assert intervals == sorted(intervals, reverse=True), (
        "quieter tags must not be posted to more often than busy ones")


def test_only_one_account_posts_to_the_national_tag_per_occurrence():
    """Eight feeds each posting fortnightly would be eight times the footprint,
    and eight near-identical accounts in one tag reads as a swarm."""
    channel = _channel("national_bots")
    assert channel.rotating_account
    accounts = {account_for(channel, occ) for occ in range(len(channel.accounts))}
    assert len(accounts) == len(channel.accounts), "should cycle through feeds"


# --- rotation -----------------------------------------------------------------

def test_posting_day_visits_every_weekday():
    """A fixed weekday only ever reaches people who read on that day."""
    channel = _channel("nsw")
    weekdays = set()
    day, seen = EPOCH, 0
    while seen < 7 and day < EPOCH + timedelta(days=200):
        if occurrence_index(channel, day, EPOCH) is not None:
            weekdays.add(day.weekday())
            seen += 1
        day += timedelta(days=1)
    assert weekdays == set(range(7)), "rotation should cover all seven weekdays"


def test_interval_between_posts_is_never_shorter_than_the_cadence():
    """The rotation must add days, never subtract them."""
    for channel in CHANNELS:
        days = [EPOCH + timedelta(days=n)
                for n in range(400)
                if occurrence_index(channel, EPOCH + timedelta(days=n), EPOCH) is not None]
        gaps = {(b - a).days for a, b in zip(days, days[1:])}
        assert gaps, "{} never fires".format(channel.key)
        assert min(gaps) >= interval_for(channel), (
            "{} fires {}d apart, faster than its {}d cadence".format(
                channel.key, min(gaps), interval_for(channel)))


def test_channels_do_not_all_fire_on_the_same_day():
    """Nine near-identical accounts posting promos at once is the coordinated
    pattern the whole design is meant to avoid.

    Checked over ~3 years because cadences of 7, 14 and 28 days drift into
    alignment rarely - the first triple collision is 38 days out, the next is
    ten months later.
    """
    busiest = max(len(due_channels(EPOCH + timedelta(days=n), EPOCH))
                  for n in range(1000))
    assert busiest <= MAX_CHANNELS_PER_DAY, \
        "{} channels fall due on one day".format(busiest)


def test_the_daily_cap_defers_the_busiest_tags_first():
    """When the cap bites, the quiet tags keep their slot.

    A monthly channel waits four weeks for its turn, so deferring it costs far
    more than deferring a weekly one.
    """
    collision = next(
        EPOCH + timedelta(days=n) for n in range(1000)
        if len(due_channels(EPOCH + timedelta(days=n), EPOCH, enforce_cap=False))
        > MAX_CHANNELS_PER_DAY)
    kept = due_channels(collision, EPOCH)
    dropped = deferred_channels(collision, EPOCH)
    assert len(kept) == MAX_CHANNELS_PER_DAY
    assert dropped, "a collision must actually defer something"
    assert max(c.weekly_volume for c in kept) <= min(c.weekly_volume for c in dropped)


def test_deferral_is_rare():
    """If the cap fired often it would be silently rewriting the cadence."""
    deferred_days = sum(1 for n in range(1000)
                        if deferred_channels(EPOCH + timedelta(days=n), EPOCH))
    assert deferred_days <= 10, \
        "{} deferrals in 1000 days - phases need rebalancing".format(deferred_days)


def test_occurrence_numbers_increase_by_one():
    channel = _channel("vic")
    seen = [occurrence_index(channel, EPOCH + timedelta(days=n), EPOCH)
            for n in range(200)]
    seen = [s for s in seen if s is not None]
    assert seen == list(range(len(seen)))


def test_nothing_fires_before_its_phase():
    for channel in CHANNELS:
        for n in range(channel.phase):
            assert occurrence_index(channel, EPOCH + timedelta(days=n), EPOCH) is None


# --- timing -------------------------------------------------------------------

def test_posts_land_in_the_local_morning_window():
    """Perth runs 2-3 hours behind the eastern states, so a single UTC time
    would put the WA post at 5am local."""
    from zoneinfo import ZoneInfo
    for channel in CHANNELS:
        for occ in range(6):
            day = EPOCH + timedelta(days=channel.phase + occ * 9)
            local = post_time_utc(channel, day, occ).astimezone(
                ZoneInfo(channel.timezone))
            minutes = local.hour * 60 + local.minute
            assert 7 * 60 + 30 <= minutes <= 9 * 60, (
                "{} occurrence {} lands at {} local".format(
                    channel.key, occ, local.strftime("%H:%M")))


def test_post_time_is_stable_for_a_given_occurrence():
    """A dry run must predict what the real run will do."""
    channel = _channel("qld")
    day = EPOCH + timedelta(days=channel.phase)
    assert post_time_utc(channel, day, 0) == post_time_utc(channel, day, 0)


def test_post_time_varies_between_occurrences():
    channel = _channel("nsw")
    times = {post_time_utc(channel, EPOCH + timedelta(days=occ * 9), occ).strftime("%H:%M")
             for occ in range(5)}
    assert len(times) > 1, "a fixed minute every time reads as machine-generated"


# --- copy ---------------------------------------------------------------------

def test_every_post_fits_bluesky_and_carries_both_tags():
    for channel in CHANNELS:
        for occ in range(4):
            text = compose(channel, account_for(channel, occ), occ)
            assert len(text) <= 300, "{} occurrence {} is {} chars".format(
                channel.key, occ, len(text))
            assert channel.tag.lower() in text.lower()
            assert "#LGNewsRoundup" in text


def test_copy_carries_no_emoji():
    """No emoji anywhere in this project."""
    for channel in CHANNELS:
        for occ in range(4):
            text = compose(channel, account_for(channel, occ), occ)
            assert all(ord(ch) < 0x2190 for ch in text), \
                "{} occurrence {} contains a non-text glyph".format(channel.key, occ)


def test_copy_varies_between_occurrences():
    """A tag that sees the feed weekly should not read the same sentence weekly."""
    for channel in CHANNELS:
        texts = {compose(channel, account_for(channel, occ), occ) for occ in range(4)}
        assert len(texts) > 1, "{} repeats identical copy".format(channel.key)


def test_council_counts_match_the_repo():
    """The copy states council numbers, so they have to be true."""
    import json
    import pathlib
    for state, facts in STATE_FACTS.items():
        path = pathlib.Path("states") / state.lower() / "councils.json"
        if not path.exists():
            continue
        raw = json.loads(path.read_text())
        councils = raw["councils"] if isinstance(raw, dict) else raw
        enabled = [c for c in councils if c.get("enabled", True)]
        assert int(facts["councils"]) == len(enabled), (
            "{}: copy claims {} councils, repo has {}".format(
                state, facts["councils"], len(enabled)))


def test_state_copy_reads_grammatically():
    """"18 the Northern Territory councils" is what one name field produces."""
    for channel in CHANNELS:
        if channel.key in ("national", "localgov"):
            continue
        for occ in range(4):
            text = compose(channel, account_for(channel, occ), occ)
            assert "the Northern Territory councils" not in text
            assert " the ACT councils" not in text


# --- the national channel -----------------------------------------------------

def test_national_channel_is_gated_on_approval():
    """It posts from a person's account, so it is never sent unattended."""
    national = _channel("national")
    assert national.requires_approval
    assert national.account == "ADMIN"


def test_the_national_tag_is_never_hit_by_eight_accounts_at_once():
    """One rotating feed at a time, plus the human account - never a swarm."""
    auspol = [c for c in CHANNELS if "auspol" in c.tag.lower()]
    assert auspol, "the national tag should be in use"
    for channel in auspol:
        assert channel.account == "ADMIN" or channel.rotating_account, (
            "{} would put a fixed bot account in the national tag".format(
                channel.key))


def test_we_do_not_promote_into_a_foreign_tag():
    """#LocalGov is British Columbia municipal politics, not Australian: its
    companions are #bclocalgov, #bcmuni, #cariboord and #cdnmuni, and we were
    already its fourth-largest poster. Measured 2026-08-02."""
    for channel in CHANNELS:
        assert "localgov" not in channel.tag.lower(), (
            "{} targets a Canadian tag".format(channel.key))


def test_the_two_national_channels_speak_differently():
    """One is a person, one is a feed. Identical copy from both would make the
    human slot look like just another bot."""
    human = _channel("national")
    bots = _channel("national_bots")
    human_copy = {compose(human, "ADMIN", occ) for occ in range(4)}
    bot_copy = {compose(bots, account_for(bots, occ), occ) for occ in range(4)}
    assert not (human_copy & bot_copy), "the two national voices overlap"
