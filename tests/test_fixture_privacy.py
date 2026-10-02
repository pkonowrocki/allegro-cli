from html import unescape
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit


FIXTURES = Path(__file__).parent / 'fixtures'
PUBLIC_FIXTURES = [
    'current-listing-articles.html',
    'current-offer-price.html',
    'other-offers-listing.html',
    'other-offers-panel.json',
]
TRACKING_KEYS = {'emission_id', 'emission_unit_id', 'ts', 'sig', 'bi_c', 'ocoi'}


def check_tracking(url):
    params = parse_qs(urlsplit(url).query)
    for key in TRACKING_KEYS & params.keys():
        for value in params[key]:
            assert value.startswith('synthetic-') or (key == 'ts' and value == '0'), key
    for redirect in params.get('redirect', []):
        check_tracking(redirect)


def test_public_regression_fixtures_do_not_include_private_history_or_tracking():
    for name in PUBLIC_FIXTURES:
        text = (FIXTURES / name).read_text()
        assert 'Twój zakup' not in text, name
        assert '/moje-allegro/' not in text, name
        assert 'Cookie:' not in text, name
        assert 'Authorization:' not in text, name
        for url in re.findall(r'(?:href|src)="([^"]+)"', text):
            check_tracking(unescape(url))


def test_unrelated_financing_price_is_explicitly_synthetic():
    text = (FIXTURES / 'current-offer-price.html').read_text()
    assert 'Synthetic financing banner' in text
    assert 'not captured account data' in text
