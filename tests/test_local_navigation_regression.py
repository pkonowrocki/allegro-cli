from unittest.mock import MagicMock, patch

import pytest

from allegro_cli.api.client import AllegroClient
from allegro_cli.api.models import RateLimitError
from allegro_cli.config import Config


@pytest.mark.parametrize('requested,final,selector', [
    ('https://allegro.pl/listing?string=Jacobs%20bezkofeinowa',
     'https://allegro.pl/listing?string=Jacobs+bezkofeinowa', 'body'),
    ('https://allegro.pl/oferta/-16949413245',
     'https://allegro.pl/oferta/kawa-16949413245', 'h1'),
])
def test_fetch_page_waits_for_site_redirect_instead_of_failing_on_initial_403(requested, final, selector):
    client = AllegroClient(Config())
    page = MagicMock()
    page.goto.return_value.status = 403
    page.url = requested
    page.content.return_value = '<html>actual product content</html>'
    page.locator.return_value.count.return_value = 1
    page.title.return_value = 'Actual product - Allegro'
    page.evaluate.return_value = 'complete'

    def resolve(*args, **kwargs):
        response = MagicMock(status=200, url=final)
        response.request.is_navigation_request.return_value = True
        response.request.frame = page.main_frame
        page.url = final
        page.on.call_args.args[1](response)

    page.wait_for_timeout.side_effect = resolve
    try:
        with patch.object(client, '_ensure_browser', return_value=page):
            result = client._fetch_page(requested)
        assert result == '<html>actual product content</html>'
        page.goto.assert_called_once()
        page.locator.assert_called_with(selector)
        page.remove_listener.assert_called_once()
    finally:
        client.close()


def test_permanent_403_has_bounded_wait_and_never_returns_challenge_html():
    client = AllegroClient(Config())
    page = MagicMock()
    page.goto.return_value.status = 403
    page.url = 'https://allegro.pl/oferta/-16949413245'
    try:
        with patch.object(client, '_ensure_browser', return_value=page), \
             patch('allegro_cli.api.client.time.monotonic', side_effect=[0, 0, 0, 21]):
            with pytest.raises(RateLimitError):
                client._fetch_page(page.url)
        page.content.assert_not_called()
        page.remove_listener.assert_called_once()
    finally:
        client.close()


@pytest.mark.parametrize('final,title,subframe', [
    ('https://allegro.pl/oferta/kawa-16902296850', 'Another product - Allegro', False),
    ('https://example.com/oferta/kawa-16949413245', 'Foreign site', False),
    ('https://allegro.pl/oferta/kawa-16949413245', 'allegro.pl', False),
    ('https://allegro.pl/oferta/kawa-16949413245', 'Actual product - Allegro', True),
])
def test_challenge_cannot_succeed_on_wrong_target_interstitial_or_subframe(final, title, subframe):
    client = AllegroClient(Config())
    page = MagicMock()
    requested = 'https://allegro.pl/oferta/-16949413245'
    page.goto.return_value.status = 403
    page.url = requested
    page.title.return_value = title
    page.evaluate.return_value = 'complete'
    page.locator.return_value.count.return_value = 1

    def redirect(*args):
        response = MagicMock(status=200, url=final)
        response.request.is_navigation_request.return_value = True
        response.request.frame = MagicMock() if subframe else page.main_frame
        page.url = final
        page.on.call_args.args[1](response)

    page.wait_for_timeout.side_effect = redirect
    try:
        with patch.object(client, '_ensure_browser', return_value=page), \
             patch('allegro_cli.api.client.time.monotonic', side_effect=[0, 0, 0, 0, 21]):
            with pytest.raises(RateLimitError):
                client._fetch_page(requested)
        page.content.assert_not_called()
    finally:
        client.close()


def test_query_reencoded_by_challenge_is_restored_once_not_silently_changed():
    client = AllegroClient(Config())
    page = MagicMock()
    requested = 'https://allegro.pl/listing?string=Jacobs+bezkofeinowa'
    altered = 'https://allegro.pl/listing?string=Jacobs%2Bbezkofeinowa'
    page.url = requested
    page.title.return_value = 'Jacobs - Allegro'
    page.evaluate.return_value = 'complete'
    page.locator.return_value.count.return_value = 1
    page.content.return_value = '<html>correct search results</html>'
    first = MagicMock(status=403, url=requested)
    restored = MagicMock(status=200, url=requested)

    def goto(*args, **kwargs):
        if page.goto.call_count == 1:
            return first
        page.url = requested
        return restored

    def redirect(*args):
        response = MagicMock(status=200, url=altered)
        response.request.is_navigation_request.return_value = True
        response.request.frame = page.main_frame
        page.url = altered
        page.on.call_args.args[1](response)

    page.goto.side_effect = goto
    page.wait_for_timeout.side_effect = redirect
    try:
        with patch.object(client, '_ensure_browser', return_value=page), \
             patch('allegro_cli.api.client.time.monotonic', side_effect=[0, 0, 0, 0, 21]):
            assert client._fetch_page(requested) == '<html>correct search results</html>'
        assert page.goto.call_count == 2
        assert page.url == requested
    finally:
        client.close()
