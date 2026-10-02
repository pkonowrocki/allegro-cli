from pathlib import Path
from unittest.mock import MagicMock, patch

from allegro_cli.api.client import AllegroClient
from allegro_cli.api.models import RateLimitError
from allegro_cli.config import Config


FIXTURES = Path(__file__).parent / 'fixtures'


def test_offer_recovers_403_by_following_exact_listing_link_headlessly():
    url = 'https://allegro.pl/oferta/laptop-lenovo-thinkpad-x1-12345678'
    listing_html = f'<article><h2><a href="{url}">Laptop Lenovo ThinkPad</a></h2></article>'
    blocked_browser = MagicMock()
    blocked_page = MagicMock(url=url)
    fresh_browser = MagicMock()
    page = fresh_browser.new_context.return_value.new_page.return_value
    page.url = url
    page.content.return_value = (FIXTURES / 'offer_page.html').read_text()
    page.expect_navigation.return_value.__enter__.return_value.value.status = 200
    client = AllegroClient(Config(cookies='QXLSESSID=test-session'))
    client._browser = blocked_browser
    client._page = blocked_page
    try:
        with (
            patch.object(client, '_fetch_page', side_effect=[RateLimitError(), listing_html]) as fetch,
            patch('allegro_cli.api.client.launch', return_value=fresh_browser) as launch,
        ):
            offer = client.scrape_offer('12345678')
        assert offer.id == '12345678'
        assert offer.sellingMode.price.amount == '4599.00'
        blocked_browser.close.assert_called_once()
        launch.assert_called_once_with(headless=True, locale='pl-PL')
        assert fetch.call_args_list[1].args[0] == (
            'https://allegro.pl/listing?string=laptop+lenovo+thinkpad+x1'
        )
        page.locator.return_value.first.click.assert_called_once()
    finally:
        client.close()


def test_offer_waits_for_challenge_redirect_to_successful_product_response():
    url = 'https://allegro.pl/oferta/laptop-lenovo-thinkpad-x1-12345678'
    listing_html = f'<article><h2><a href="{url}">Laptop Lenovo ThinkPad</a></h2></article>'
    browser = MagicMock()
    page = browser.new_context.return_value.new_page.return_value
    page.url = url
    page.content.return_value = (FIXTURES / 'offer_page.html').read_text()
    page.expect_navigation.return_value.__enter__.return_value.value.status = 403
    final_response = MagicMock(status=200)
    final_response.request.frame = page.main_frame
    final_response.request.is_navigation_request.return_value = True

    def render_product(*args, **kwargs):
        callback = page.on.call_args.args[1]
        callback(final_response)

    page.wait_for_selector.side_effect = render_product
    client = AllegroClient(Config(cookies='QXLSESSID=test-session'))
    try:
        with (
            patch.object(client, '_fetch_page', return_value=listing_html),
            patch('allegro_cli.api.client.launch', return_value=browser),
        ):
            html = client._fetch_offer_via_listing('12345678', url)
        assert html == (FIXTURES / 'offer_page.html').read_text()
    finally:
        client.close()
