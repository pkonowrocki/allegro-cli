from pathlib import Path

from allegro_cli.scraper import _extract_offer_id, parse_offer_page


def test_offer_price_comes_from_offer_bound_payload_not_finance_banner():
    fixture = Path(__file__).parent / 'fixtures/current-offer-price.html'
    offer = parse_offer_page(fixture.read_text(), offer_id='16949413245')
    assert offer.sellingMode.price.amount == '44.99'
    assert 'Jacobs' in offer.name


def test_canonical_product_url_does_not_lose_selected_offer_id():
    fixture = Path(__file__).parent / 'fixtures/current-offer-price.html'
    canonical = ('https://allegro.pl/produkt/kawa-rozpuszczalna-bezkofeinowa-jacobs-100-g-'
                 'e0cf3361-f9c8-4f2a-a078-f518841e984d')
    html = fixture.read_text().replace('<html>', f'<html><link rel="canonical" href="{canonical}">')
    offer = parse_offer_page(html, offer_id='16949413245')
    assert _extract_offer_id(offer.url) == '16949413245'
