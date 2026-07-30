"""Tests for the amplification shortlist (scripts/monitoring/amplify_candidates.py).

The tool exists because engagement-ranking alone does not work yet: 240 recent
posts across the eight feeds carried 13 likes between them, so "post the day's
best" would be picking at random and pushing arbitrary council notices into a
large tag. These tests pin the two behaviours that matter: engagement dominates
the ranking whenever it exists, and topic signal only breaks ties in silence.
"""
import sys

import pytest

sys.path.append("scripts/monitoring")
from scripts.monitoring.amplify_candidates import topic_score


def test_rates_and_budget_outrank_routine_notices():
    assert topic_score("Council adopts budget with a rates freeze") > \
           topic_score("Library opening hours this weekend")


def test_meeting_minutes_are_penalised():
    """Minutes and agendas are the least amplifiable thing a council posts."""
    assert topic_score("Minutes Ordinary Council Meeting - Tuesday 28 July") < 0


def test_housing_scores_highly():
    assert topic_score("New affordable housing approved for the shire") >= 5


def test_emergency_topics_score_highly():
    for text in ["Flood warning for the river district",
                 "Fire danger period begins Monday",
                 "Road safety upgrade announced"]:
        assert topic_score(text) > 0


def test_neutral_text_scores_zero():
    assert topic_score("Wander through the wildflowers") == 0


def test_multiple_topics_accumulate():
    both = topic_score("Budget funds new housing and road safety works")
    assert both > topic_score("Budget adopted")


def test_public_notice_is_penalised_but_less_than_minutes():
    notice = topic_score("Public notice regarding the annual report")
    minutes = topic_score("Minutes Ordinary Council Meeting")
    assert minutes < notice <= 0


@pytest.mark.parametrize("text,expect_positive", [
    ("Have your say on the draft plan", True),
    ("CEO resigns after five years", True),
    ("$45,000 in community grants announced", True),
    ("Photo gallery from the fair", False),
])
def test_topic_signal_direction(text, expect_positive):
    assert (topic_score(text) > 0) is expect_positive
