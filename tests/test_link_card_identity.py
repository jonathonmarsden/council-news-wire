"""Link-card fetches follow the council's setting: a council configured with
the declared crawler name is never fetched as a browser at posting time."""
from unittest.mock import MagicMock, patch

from core import link_card

UA = "LGNewsRoundupBot/1.0 (+https://lgnews.jonathonmarsden.com/bot.html)"
PAGE = '<html><head><meta property="og:title" content="A council story"></head></html>'


def _resp():
    r = MagicMock()
    r.status_code = 200
    r.headers = {}
    r.text = PAGE
    r.content = PAGE.encode()
    return r


def test_declared_council_is_fetched_by_name_not_as_a_browser():
    with patch.object(link_card, "_public_http_url", return_value=True), \
         patch.object(link_card._plain_requests, "get", return_value=_resp()) as plain, \
         patch.object(link_card._requests, "get", side_effect=AssertionError("impersonated")):
        data = link_card.fetch_card_data("https://www.example.gov.au/news/a", UA)
    assert data["title"] == "A council story"
    assert plain.call_args.kwargs["headers"]["User-Agent"] == UA


def test_other_councils_are_unchanged():
    with patch.object(link_card, "_public_http_url", return_value=True), \
         patch.object(link_card._plain_requests, "get", side_effect=AssertionError("plain")), \
         patch.object(link_card._requests, "get", return_value=_resp()) as browser:
        assert link_card.fetch_card_data("https://www.example.gov.au/news/a")
    assert browser.called
