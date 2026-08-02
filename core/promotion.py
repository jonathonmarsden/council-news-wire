"""Scheduled promotion of the feeds into community hashtags.

The routine story posts deliberately carry only tags this project owns
(#LGNewsRoundup and the council's own tag). That rule exists because the feeds
publish thousands of posts a month: in July 2026 a change briefly added
community tags and within hours the feeds were 49% of #LocalGov, 16% of #NSWpol
and 14% of #WApol. A firehose cannot politely wear a community tag.

A single deliberate promotional post is a different act from 8,000 stories
wearing a tag, so this module lets the feeds introduce themselves in the tags
where their audience actually is - at a rate set by how much traffic each tag
carries.

Two rules do the work:

1. **Frequency is per tag, not per feed.** Measured 2026-08-02, #auspol carries
   ~3,200 posts a week and #actpol carries ~2. The same weekly cadence is 0.03%
   of one and 52% of the other. Each tag therefore gets its own interval, and
   #actpol gets no automated promotion at all.

2. **The day rotates.** Posting every 9 days walks the post through all seven
   weekdays, so it reaches people who read on Sundays as well as people who read
   on Tuesdays, and never settles into a machine-like weekly pattern.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

# Rotating the posting day by 9 days walks through every weekday (9 and 7 are
# coprime) without the fixed-weekday look of a 7-day cycle. A 14-day channel
# steps by 16, a 28-day channel by 30, for the same reason.
ROTATION_STEP_DAYS = 2

# Local-time window for a promotional post. Australian political Bluesky is
# busiest over the morning commute and news cycle; posting at 3am would be
# unpredictable in the sense of reaching nobody.
WINDOW_START = time(7, 30)
WINDOW_END = time(9, 0)


@dataclass(frozen=True)
class Channel:
    """One account posting into one hashtag at one cadence.

    `interval_days` is chosen so a single post stays a small share of the tag's
    traffic. `share_pct` records the measured share at that interval, so a
    future reader can see the reasoning rather than a bare magic number.

    `phase` offsets this channel's first post from the shared epoch. Without it
    every channel would fall due on the same day and stay locked together
    forever - nine near-identical accounts posting promos within the same hour
    is the coordinated-behaviour pattern this whole design exists to avoid.
    """
    key: str
    account: str                # env suffix: VIC, NSW, ... or ADMIN
    tag: str
    interval_days: int
    weekly_volume: int          # posts/week in the tag, measured 2026-08-02
    share_pct: float            # our share at this interval
    phase: int = 0              # days after the epoch that this channel starts
    timezone: str = "Australia/Sydney"
    requires_approval: bool = False
    rotating_account: bool = False   # account varies per occurrence
    accounts: tuple = ()


# Measured on 2026-08-02 by sampling the most recent 100 posts in each tag.
# Small tags are noisy at that sample size, so treat the volumes as indicative
# and re-measure before tightening any interval.
CHANNELS: List[Channel] = [
    Channel("nsw", "NSW", "#NSWpol", 7, 112, 0.89, phase=0),
    Channel("vic", "VIC", "#SpringSt", 7, 140, 0.72, phase=2,
            timezone="Australia/Melbourne"),
    Channel("qld", "QLD", "#QldPol", 7, 172, 0.58, phase=4,
            timezone="Australia/Brisbane"),
    Channel("wa", "WA", "#WApol", 14, 19, 5.40, phase=6,
            timezone="Australia/Perth"),
    Channel("sa", "SA", "#SAparli", 28, 14, 7.36, phase=8,
            timezone="Australia/Adelaide"),
    Channel("tas", "TAS", "#TasPol", 28, 11, 9.03, phase=10,
            timezone="Australia/Hobart"),
    Channel("nt", "NT", "#NTpol", 28, 7, 15.13, phase=12,
            timezone="Australia/Darwin"),

    # One feed at a time reaches the national tag, rotating through the states.
    # Eight feeds each posting fortnightly would be eight times the footprint,
    # and eight near-identical accounts in one tag reads as coordinated
    # behaviour whatever the intent.
    #
    # This slot used to be #LocalGov. A co-occurrence sample on 2026-08-02
    # showed that tag is not Australian: its companions are #bclocalgov,
    # #bcmuni, #cariboord, #cdnmuni and #williamslake - British Columbia
    # municipal politics, with a UK cluster second and average engagement of
    # 0.4. We were already its fourth-largest poster. #Auspol is where
    # Australian readers of council news actually are.
    Channel("national_bots", "VIC", "#Auspol", 14, 3200, 0.02, phase=3,
            rotating_account=True,
            accounts=("VIC", "NSW", "QLD", "WA", "SA", "TAS", "NT")),

    # National promotion also comes from the human account. A person describing
    # feeds they run is legitimate in #auspol in a way a broadcasting bot is
    # not - which is why this one is drafted for review rather than published
    # unattended, and why it carries different copy from the bot slot above.
    Channel("national", "ADMIN", "#Auspol", 7, 3200, 0.03, phase=5,
            requires_approval=True),
]

# ACT is deliberately absent. #ACTpol carries ~2 posts a week, so any automated
# participation would dominate the tag outright. The ACT feed has to grow
# through the starter pack and direct outreach instead.
EXCLUDED = {"act": "#ACTpol carries ~2 posts/week; any cadence would dominate it"}

CHANNELS_BY_KEY: Dict[str, Channel] = {c.key: c for c in CHANNELS}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def interval_for(channel: Channel) -> int:
    """Channel cadence in days, overridable per channel via the environment.

    The measured volumes behind these intervals are a snapshot, so
    LGNEWS_PROMO_INTERVAL_NSW=14 can correct one without a code change.
    """
    return _env_int(f"LGNEWS_PROMO_INTERVAL_{channel.key.upper()}",
                    channel.interval_days)


def occurrence_index(channel: Channel, today: date, epoch: date) -> Optional[int]:
    """Which occurrence falls on `today`, or None if today is not a promo day.

    Occurrence N lands on epoch + phase + N * (interval + ROTATION_STEP_DAYS).
    The extra step is what rotates the weekday: with a 7-day interval the gap
    becomes 9 days, so the post moves forward two weekdays each time and visits
    all seven before returning to the start. The phase keeps channels from
    falling due on the same day as each other.
    """
    start = epoch + timedelta(days=channel.phase)
    if today < start:
        return None
    stride = interval_for(channel) + ROTATION_STEP_DAYS
    delta = (today - start).days
    if delta % stride != 0:
        return None
    return delta // stride


# Most days carry one channel, some carry two. Three or more accounts promoting
# on the same day is the coordinated-swarm look, so it is capped rather than
# left to chance.
MAX_CHANNELS_PER_DAY = 2


def due_channels(today: date, epoch: date, enforce_cap: bool = True) -> List[Channel]:
    """Channels whose promo day is `today`.

    Phases keep the channels apart, but cadences of 7, 14 and 28 days
    occasionally drift into alignment anyway - about five days in a thousand
    land three channels together. On those days the lowest-volume tags go first
    (they have the longest waits between posts, so deferring them costs most)
    and the rest stand down until their next occurrence.

    `enforce_cap=False` exposes the raw schedule, which is what the deferral
    bookkeeping and the tests need.
    """
    due = [c for c in CHANNELS if occurrence_index(c, today, epoch) is not None]
    if not enforce_cap or len(due) <= MAX_CHANNELS_PER_DAY:
        return due
    return sorted(due, key=lambda c: c.weekly_volume)[:MAX_CHANNELS_PER_DAY]


def deferred_channels(today: date, epoch: date) -> List[Channel]:
    """Channels due today that the daily cap pushed off."""
    kept = {c.key for c in due_channels(today, epoch)}
    return [c for c in due_channels(today, epoch, enforce_cap=False)
            if c.key not in kept]


def account_for(channel: Channel, occurrence: int) -> str:
    """Env suffix of the account that posts this occurrence.

    #LocalGov rotates through the state feeds so the tag sees a different voice
    each time and no single feed accumulates a footprint there.
    """
    if channel.rotating_account and channel.accounts:
        return channel.accounts[occurrence % len(channel.accounts)]
    return channel.account


def post_time_utc(channel: Channel, day: date, occurrence: int) -> datetime:
    """A varying minute inside the local morning window, as UTC.

    Derived from the occurrence rather than randomised, so a dry run and the
    real run agree and the schedule can be inspected ahead of time. Perth is two
    to three hours behind the eastern states, so using each channel's own
    timezone is what stops the WA post landing at 5am local.
    """
    span = (WINDOW_END.hour * 60 + WINDOW_END.minute) - \
           (WINDOW_START.hour * 60 + WINDOW_START.minute)
    # 37 is coprime with the 90-minute span, so successive occurrences land on
    # well-spread minutes instead of cycling through a handful.
    offset = (occurrence * 37) % span
    start = WINDOW_START.hour * 60 + WINDOW_START.minute + offset
    local = datetime.combine(day, time(start // 60, start % 60),
                             tzinfo=ZoneInfo(channel.timezone))
    return local.astimezone(ZoneInfo("UTC"))
