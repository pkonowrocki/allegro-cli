from pathlib import Path

from allegro_cli.scraper import parse_search_results


def test_current_listing_sponsored_and_product_links():
    html = (Path(__file__).parent / 'fixtures/current-listing-articles.html').read_text()
    offers = parse_search_results(html)
    assert [o.id for o in offers] == [
        '16949413245', '16902296850', '16949435021', '17329936598',
    ]
    assert [o.sellingMode.price.amount for o in offers] == [
        '44.99', '43.98', '68.97', '24.99',
    ]
    assert all(o.url == f'https://allegro.pl/oferta/{o.id}' for o in offers)
