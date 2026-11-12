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
# enabled only) and are stated in the copy, so they must be kept true.
# Australia has 538 councils (ALGA); 536 are collected. Not collected:
# Pormpuraaw and Yarrabah (nothing scrapeable). WA's count includes the two
# Indian Ocean Territories shires, Christmas Island and Cocos (Keeling) Islands. The ACT
# has no councils; its "councils" are three ACT Government news sources.
# `name` is the place ("in Victoria"); `adj` qualifies the councils themselves
# ("79 Victorian councils"). Keeping both avoids "18 the Northern Territory
# councils", which is what a single field produces.
STATE_FACTS: Dict[str, Dict[str, str]] = {
    "NSW": {"name": "New South Wales", "adj": "NSW", "councils": "128",
            "handle": "roundupnewsbotnsw.bsky.social"},
    "VIC": {"name": "Victoria", "adj": "Victorian", "councils": "79",
            "handle": "roundupnewsbotvic.bsky.social"},
    "QLD": {"name": "Queensland", "adj": "Queensland", "councils": "75",
            "handle": "roundupnewsbotqld.bsky.social"},
    "WA": {"name": "Western Australia", "adj": "WA", "councils": "139",
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

SITE = "https://councilnewswire.au/"

# Councils across the states and the NT; the ACT Government is named separately.
NATIONAL_COUNCILS = sum(int(f["councils"]) for k, f in STATE_FACTS.items() if k != "ACT")


ACT_VARIANTS = [
    "Every news item from the ACT Government - ministers' and department "
    "releases and Our Canberra - posted automatically and unedited. Free to "
    "follow, no ads, no tracking.",

    "Canberra has no local council: the ACT Government does that job. This "
    "feed carries its news releases, every item, unedited.",

    "Following Canberra? This feed posts every ACT Government news release and "
    "Our Canberra story, automatically and in full.",

    "ACT Government news, one feed. Automated, unedited and free - the "
    "releases as they were published.",
]


def _state_variants(f: Dict[str, str]) -> List[str]:
    return [
        "Every news item from {councils} {adj} councils, posted automatically "
        "and unedited. Free to follow, no ads, no tracking.".format(**f),

        "This feed carries council news from {councils} {adj} councils - "
        "every item, unedited, usually within a day of publication.".format(**f),

        "Following local government in {name}? This feed posts every news item "
        "from {councils} councils, automatically and in full.".format(**f),

        "{councils} {adj} councils, one feed. Automated, unedited and free - "
        "the stories as councils published them.".format(**f),
    ]


NATIONAL_VARIANTS = [
    "I run eight Bluesky feeds carrying council news from {n} Australian "
    "councils and the ACT Government - one per state and territory. Automated, unedited, free to follow.",

    "Local government makes decisions that rarely reach the news. I run a feed "
    "for each state and territory carrying every item from {n} councils and the ACT Government.",

    "Eight feeds, {n} councils plus the ACT Government, every news item published automatically and "
    "unedited. One for each state and territory, free to follow.",

    "Council news is public but hard to find. These eight feeds carry every item "
    "from {n} Australian councils and the ACT Government, unedited and free.",
]

# Posted by a state feed into the national tag, so it speaks as a feed rather
# than as a person - the national/ADMIN copy above is written in first person
# and the two must not sound like the same voice.
NATIONAL_BOT_VARIANTS = [
    "Every news item from {n} Australian councils and the ACT Government, split into eight "
    "state and territory feeds. Automated, unedited, free to follow.",

    "Tracking local government? Eight feeds carry every item published by "
    "{n} Australian councils and the ACT Government - one per state and territory.",

    "{n} Australian councils plus the ACT Government, eight feeds, every story unedited. "
    "Automated and free.",

    "Council decisions rarely reach the news. These eight feeds carry every "
    "item published by {n} Australian councils and the ACT Government, unedited.",
]


def body_for(channel: Channel, account: str, occurrence: int) -> str:
    """The promo text for one occurrence, before the link and hashtags."""
    if channel.key == "national":
        return NATIONAL_VARIANTS[occurrence % len(NATIONAL_VARIANTS)].format(n=NATIONAL_COUNCILS)
    if channel.key == "national_bots":
        return NATIONAL_BOT_VARIANTS[occurrence % len(NATIONAL_BOT_VARIANTS)].format(n=NATIONAL_COUNCILS)
    facts = STATE_FACTS[account]
    variants = ACT_VARIANTS if account == "ACT" else _state_variants(facts)
    return variants[occurrence % len(variants)]


def compose(channel: Channel, account: str, occurrence: int) -> str:
    """Full post text: body, link, then the tags.

    The community tag is what makes this post visible to the people it is meant
    for; the brand tag ties it to the rest of the network. Tags go last so the
    facet builder can bound them to the tail of the post.
    """
    body = body_for(channel, account, occurrence)
    link = SITE
    if channel.key not in ("national", "national_bots"):
        link = "https://bsky.app/profile/" + STATE_FACTS[account]["handle"]
    return "{}\n\n{}\n\n{} #LGNewsRoundup".format(body, link, channel.tag)
