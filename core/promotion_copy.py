"""Copy for the scheduled promotional posts.

A promo earns its place in someone else's hashtag by being useful there, so
these say what the service is, what it covers and what it costs, and then stop.
No hard sell, no urgency, no emoji.

Variants rotate with the occurrence number so a tag that sees the feed once a
week is not reading the same sentence every week.
"""
from __future__ import annotations

from typing import Dict, List

from core.promotion import Channel

# Council counts come from the repo's own config (states/*/councils.json,
# enabled only) and are stated in the copy, so they must be kept true. Total is
# 538 configured; 536 post (Hay and Pormpuraaw publish nothing scrapeable).
# `name` is the place ("in Victoria"); `adj` qualifies the councils themselves
# ("79 Victorian councils"). Keeping both avoids "18 the Northern Territory
# councils", which is what a single field produces.
STATE_FACTS: Dict[str, Dict[str, str]] = {
    "NSW": {"name": "New South Wales", "adj": "NSW", "councils": "127",
            "handle": "roundupnewsbotnsw.bsky.social"},
    "VIC": {"name": "Victoria", "adj": "Victorian", "councils": "79",
            "handle": "roundupnewsbotvic.bsky.social"},
    "QLD": {"name": "Queensland", "adj": "Queensland", "councils": "76",
            "handle": "roundupnewsbotqld.bsky.social"},
    "WA": {"name": "Western Australia", "adj": "WA", "councils": "138",
           "handle": "roundupnewsbotwa.bsky.social"},
    "SA": {"name": "South Australia", "adj": "South Australian", "councils": "68",
           "handle": "roundupnewsbotsa.bsky.social"},
    "TAS": {"name": "Tasmania", "adj": "Tasmanian", "councils": "29",
            "handle": "roundupnewsbottas.bsky.social"},
    "NT": {"name": "the Northern Territory", "adj": "NT", "councils": "18",
           "handle": "roundupnewsbotnt.bsky.social"},
    "ACT": {"name": "the ACT", "adj": "ACT", "councils": "3",
            "handle": "roundupnewsbotact.bsky.social"},
}

SITE = "https://lgnews.jonathonmarsden.com/"


def _state_variants(f: Dict[str, str]) -> List[str]:
    return [
        "Every news item from all {councils} {adj} councils, posted automatically "
        "and unedited. Free to follow, no ads, no tracking.".format(**f),

        "This feed carries council news from all {councils} {adj} councils - "
        "every item, unedited, usually within a day of publication.".format(**f),

        "Following local government in {name}? This feed posts every news item "
        "from all {councils} councils, automatically and in full.".format(**f),

        "All {councils} {adj} councils, one feed. Automated, unedited and free - "
        "the stories as councils published them.".format(**f),
    ]


NATIONAL_VARIANTS = [
    "I run eight Bluesky feeds carrying council news from all 538 Australian "
    "councils - one per state and territory. Automated, unedited, free to follow.",

    "Local government makes decisions that rarely reach the news. I run a feed "
    "for each state and territory carrying every item from all 538 councils.",

    "Eight feeds, 538 councils, every news item published automatically and "
    "unedited. One for each state and territory, free to follow.",

    "Council news is public but hard to find. These eight feeds carry every item "
    "from all 538 Australian councils, unedited and free.",
]

LOCALGOV_VARIANTS = [
    "Every news item from all 538 Australian councils, split into eight "
    "state and territory feeds. Automated, unedited, free to follow.",

    "Tracking local government? Eight feeds carry every item published by all "
    "538 Australian councils - one per state and territory.",

    "All 538 Australian councils, eight feeds, every story unedited. "
    "Automated and free.",
]


def body_for(channel: Channel, account: str, occurrence: int) -> str:
    """The promo text for one occurrence, before the link and hashtags."""
    if channel.key == "national":
        return NATIONAL_VARIANTS[occurrence % len(NATIONAL_VARIANTS)]
    if channel.key == "localgov":
        return LOCALGOV_VARIANTS[occurrence % len(LOCALGOV_VARIANTS)]
    facts = STATE_FACTS[account]
    variants = _state_variants(facts)
    return variants[occurrence % len(variants)]


def compose(channel: Channel, account: str, occurrence: int) -> str:
    """Full post text: body, link, then the tags.

    The community tag is what makes this post visible to the people it is meant
    for; the brand tag ties it to the rest of the network. Tags go last so the
    facet builder can bound them to the tail of the post.
    """
    body = body_for(channel, account, occurrence)
    link = SITE
    if channel.key not in ("national", "localgov"):
        link = "https://bsky.app/profile/" + STATE_FACTS[account]["handle"]
    return "{}\n\n{}\n\n{} #LGNewsRoundup".format(body, link, channel.tag)
