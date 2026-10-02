import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from allegro_cli.api.client import AllegroClient
from allegro_cli.config import Config

from allegro_cli import scraper

FIXTURES = Path(__file__).parent / 'fixtures'


def test_same_price_new_condition_stale_cards_require_a_new_document():
    page = MagicMock()
    page.url = 'https://allegro.pl/oferta/kawa-16949413245?order=p&buyNew=1&offerTypeBuyNow=1'
    fresh = (FIXTURES / 'other-offers-listing.html').read_text()
    stale = fresh.replace('18913049995', '88888888888')
    state = {'reads': 0, 'reloaded': False}

    def content():
        state['reads'] += 1
        if state['reads'] == 1:
            return panel_html()
        return fresh if state['reloaded'] else stale

    def reload(**kwargs):
        state['reloaded'] = True
        return MagicMock(status=200)

    page.content.side_effect = content
    page.reload.side_effect = reload
    client = AllegroClient(Config())
    try:
        with patch.object(client, 'scrape_offer'), patch.object(client, '_ensure_browser', return_value=page):
            result = client.compare_offer('16949413245')
        assert result['cheapest']['offerId'] == '18913049995'
        assert result['complete'] is True
        page.reload.assert_called_once_with(wait_until='domcontentloaded', timeout=30000)
        page.goto.assert_not_called()
    finally:
        client.close()


def panel_html():
    data = (FIXTURES / 'other-offers-panel.json').read_text()
    return ('<div data-box-name="Other Offers" data-box-id="panel"></div>'
            f'<script data-serialize-box-id="panel">{data}</script>')


def test_reads_actual_product_set_panel_without_fabricating_offer_id():
    result = scraper.parse_other_offers_panel(panel_html())
    assert result['offerCount'] == 4
    assert result['isProductSet'] is True
    assert result['cheapest']['price'] == {'amount': '43.90', 'currency': 'PLN'}
    assert result['fastest']['price']['amount'] == '44.99'
    assert result['cheapest']['smartEligible'] is True
    assert result['cheapest']['offerId'] is None
    assert result['cheapest']['url'] is None  # anchor is not an offer URL
    assert result['cheapest']['queryParameters']['order'] == 'p'


def test_other_offers_listing_is_scoped_and_keeps_displayed_delivery_total():
    html = (FIXTURES / 'other-offers-listing.html').read_text()
    # Unrelated recommendations outside the actual comparison must be ignored.
    result = scraper.parse_other_offers_listing('<article><h2>noise</h2></article>' + html)
    assert len(result) == 4
    assert [r['price']['amount'] for r in result] == ['43.90', '44.99', '54.99', '89.90']
    cheapest = result[0]
    assert cheapest['offerId'] == '18913049995'
    assert cheapest['seller'] == 'Niemieckie_Prom'
    assert cheapest['displayedTotalWithDelivery']['amount'] == '54.39'
    assert cheapest['smartEligible'] is True
    assert cheapest['condition'] == 'Nowy'
    assert cheapest['offerId'] in cheapest['url']
    assert cheapest['productId'] == 'e0cf3361-f9c8-4f2a-a078-f518841e984d'


def test_client_opens_only_cheapest_panel_and_resolves_matching_offer():
    from unittest.mock import MagicMock, patch
    from allegro_cli.api.client import AllegroClient
    from allegro_cli.config import Config
    client = AllegroClient(Config())
    page = MagicMock()
    page.url = 'https://allegro.pl/oferta/kawa-16949413245?order=p&buyNew=1&offerTypeBuyNow=1#inne-oferty-produktu'
    page.reload.return_value.status = 200
    page.content.side_effect = [panel_html()] + [(FIXTURES / 'other-offers-listing.html').read_text()] * 2
    try:
        with patch.object(client, 'scrape_offer'), patch.object(client, '_ensure_browser', return_value=page):
            result = client.compare_offer('16949413245')
        assert result['sourceOfferId'] == '16949413245'
        assert result['returnedOfferCount'] == 4
        assert result['complete'] is True
        assert result['cheapest']['offerId'] == '18913049995'
        assert result['fastest']['offerId'] is None
        page.locator.assert_called_once_with('.other-offers-link-cheapest')
        page.locator.return_value.first.click.assert_called_once()
    finally:
        client.close()


def test_compare_command_routes_to_client_and_emits_json(capsys):
    import sys
    from unittest.mock import MagicMock, patch
    from allegro_cli.main import main
    client = MagicMock()
    client.compare_offer.return_value = {'sourceOfferId': '16949413245', 'offerCount': 4}
    with patch.object(sys, 'argv', ['allegro', 'compare', '16949413245', '--format', 'json']), \
         patch('allegro_cli.api.client.AllegroClient', return_value=client):
        assert main() == 0
    assert json.loads(capsys.readouterr().out)['offerCount'] == 4
    client.compare_offer.assert_called_once_with('16949413245')
    client.close.assert_called_once()


def test_partial_comparison_does_not_claim_all_offers_loaded():
    from unittest.mock import MagicMock, patch
    from allegro_cli.api.client import AllegroClient
    from allegro_cli.config import Config
    data = json.loads((FIXTURES / 'other-offers-panel.json').read_text())
    data['offerCount'] = 157
    html = ('<div data-box-name="Other Offers" data-box-id="panel"></div>'
            f'<script data-serialize-box-id="panel">{json.dumps(data)}</script>')
    page = MagicMock()
    page.url = 'https://allegro.pl/oferta/kawa-16949413245?order=p&buyNew=1&offerTypeBuyNow=1'
    page.reload.return_value.status = 200
    page.content.side_effect = [html] + [(FIXTURES / 'other-offers-listing.html').read_text()] * 2
    client = AllegroClient(Config())
    try:
        with patch.object(client, 'scrape_offer'), patch.object(client, '_ensure_browser', return_value=page):
            result = client.compare_offer('16949413245')
        assert result['complete'] is False
        assert result['offerCount'] == 157
        assert result['returnedOfferCount'] == 4
    finally:
        client.close()


def test_absent_panel_is_not_zero_competing_offers():
    assert scraper.parse_other_offers_panel('<html><h1>Product</h1></html>') is None


def test_missing_listing_price_fails_instead_of_reading_banner_price():
    import pytest
    from allegro_cli.api.models import ScraperError
    html = (FIXTURES / 'other-offers-listing.html').read_text()
    html = html.replace('aktualna cena', 'unknown')
    with pytest.raises(ScraperError, match='Missing comparison price'):
        scraper.parse_other_offers_listing(html)


def test_client_waits_for_refreshed_new_condition_listing():
    from unittest.mock import MagicMock, patch
    from allegro_cli.api.client import AllegroClient
    from allegro_cli.config import Config
    page = MagicMock()
    page.url = 'https://allegro.pl/oferta/kawa-16949413245?order=p&buyNew=1&offerTypeBuyNow=1'
    fresh = (FIXTURES / 'other-offers-listing.html').read_text()
    stale = fresh.replace('>Nowy</dd>', '>Używany</dd>')
    assert stale != fresh
    page.reload.return_value.status = 200
    page.content.side_effect = [panel_html(), stale, stale, fresh]
    client = AllegroClient(Config())
    try:
        with patch.object(client, 'scrape_offer'), patch.object(client, '_ensure_browser', return_value=page):
            result = client.compare_offer('16949413245')
        assert all(o['condition'] == 'Nowy' for o in result['offers'])
        assert page.content.call_count == 4
    finally:
        client.close()


def test_existing_cheapest_offer_id_is_not_overwritten_on_price_tie():
    from unittest.mock import MagicMock, patch
    from allegro_cli.api.client import AllegroClient
    from allegro_cli.config import Config
    data = json.loads((FIXTURES / 'other-offers-panel.json').read_text())
    data['links'][0]['links'][0]['url'] = 'https://allegro.pl/oferta/-16949413245'
    html = ('<div data-box-name="Other Offers" data-box-id="panel"></div>'
            f'<script data-serialize-box-id="panel">{json.dumps(data)}</script>')
    listing = (FIXTURES / 'other-offers-listing.html').read_text().replace('44,99', '43,90')
    page = MagicMock()
    page.url = 'https://allegro.pl/oferta/kawa-16949413245?order=p&buyNew=1&offerTypeBuyNow=1'
    page.reload.return_value.status = 200
    page.content.side_effect = [html, listing, listing]
    client = AllegroClient(Config())
    try:
        with patch.object(client, 'scrape_offer'), patch.object(client, '_ensure_browser', return_value=page):
            result = client.compare_offer('16949413245')
        assert result['cheapest']['offerId'] == '16949413245'
    finally:
        client.close()


def test_partial_tsv_includes_completeness_metadata(capsys):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from allegro_cli.commands.search import handle_compare
    client = MagicMock()
    client.compare_offer.return_value = {
        'offers': [{'offerId': '18913049995', 'price': {'amount': '43.90'}}],
        'sourceOfferId': '16949413245', 'offerCount': 157,
        'returnedOfferCount': 1, 'complete': False,
        'deliveryPriceScope': 'displayed_listing_not_checkout',
    }
    assert handle_compare(SimpleNamespace(offer_id='16949413245', format='tsv'), client) == 0
    text = capsys.readouterr().out
    assert 'complete' in text
    assert 'False' in text
    assert '157' in text
    assert 'displayed_listing_not_checkout' in text
