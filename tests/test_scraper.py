from allegro_cli.scraper import parse_next_page_url, parse_offer_page, parse_search_results

SAMPLE_HTML = """\
<html>
<body>
  <article>
    <a href="https://allegro.pl/oferta/laptop-dell-15-i7-16gb-512gb-12345678">
      <img src="https://img.allegro.pl/photos/abc123.jpg" />
    </a>
    <h2>Laptop Dell 15 i7 16GB 512GB</h2>
    <span>1\xa0299,00\xa0zł</span>
  </article>
  <article>
    <a href="https://allegro.pl/oferta/laptop-lenovo-14-87654321">
      <img src="https://img.allegro.pl/photos/def456.jpg" />
    </a>
    <h2>Laptop Lenovo 14</h2>
    <span>899,99\xa0zł</span>
  </article>
  <article>
    <a href="https://allegro.pl/oferta/no-price-item-11111111">
    </a>
    <h2>Item Without Price</h2>
  </article>
  <a rel="next" href="https://allegro.pl/listing?string=laptop&p=2">next</a>
</body>
</html>
"""

SAMPLE_HTML_NO_NEXT = """\
<html>
<body>
  <article>
    <a href="https://allegro.pl/oferta/single-item-99999999">
      <img src="https://img.allegro.pl/photos/single.jpg" />
    </a>
    <h2>Single Item</h2>
    <span>50,00 zł</span>
  </article>
</body>
</html>
"""

# Junk articles that should be filtered out
SAMPLE_HTML_WITH_JUNK = """\
<html>
<body>
  <article>
    <a href="https://allegro.pl/oferta/real-laptop-offer-12345678">
      <img src="https://img.allegro.pl/photos/real.jpg" />
    </a>
    <h2>Real Laptop Offer</h2>
    <span>2499,00 zł</span>
  </article>
  <article>
    <a href="https://allegro.pl/kategoria/laptopy-34385">
      <img src="https://assets.allegrostatic.com/metrum/metrum-placeholder/placeholder-405f0677c6.svg" />
    </a>
    <h2>Unknown Title</h2>
  </article>
  <article>
    <a href="https://allegro.pl/kategoria/tablety-121727">
    </a>
  </article>
</body>
</html>
"""

# Test data-src image extraction
SAMPLE_HTML_DATA_SRC = """\
<html>
<body>
  <article>
    <a href="https://allegro.pl/oferta/laptop-hp-15-98765432">
      <img src="https://a.allegroimg.com/original/34a646/action-common-information-33306995c6"
           data-src="https://a.allegroimg.com/original/real-product-image.jpg" />
    </a>
    <h2>Laptop HP 15</h2>
    <span>3107,00 zł</span>
  </article>
</body>
</html>
"""


def test_parse_search_results_extracts_offers():
    offers = parse_search_results(SAMPLE_HTML)
    assert len(offers) == 3

    assert offers[0].id == "12345678"
    assert offers[0].name == "Laptop Dell 15 i7 16GB 512GB"
    assert offers[0].sellingMode.price.amount == "1299.00"
    assert offers[0].sellingMode.price.currency == "PLN"
    assert len(offers[0].images) == 1
    assert "abc123" in offers[0].images[0].url

    assert offers[1].id == "87654321"
    assert offers[1].name == "Laptop Lenovo 14"
    assert offers[1].sellingMode.price.amount == "899.99"

    assert offers[2].id == "11111111"
    assert offers[2].name == "Item Without Price"
    assert offers[2].sellingMode.price.amount == ""
    assert offers[2].images == []


def test_parse_search_results_empty_html():
    offers = parse_search_results("<html><body></body></html>")
    assert offers == []


def test_parse_search_results_filters_junk():
    offers = parse_search_results(SAMPLE_HTML_WITH_JUNK)
    assert len(offers) == 1
    assert offers[0].id == "12345678"
    assert offers[0].name == "Real Laptop Offer"


def test_parse_search_results_prefers_data_src():
    offers = parse_search_results(SAMPLE_HTML_DATA_SRC)
    assert len(offers) == 1
    assert "real-product-image" in offers[0].images[0].url
    assert "action-common-information" not in offers[0].images[0].url


def test_parse_search_results_filters_ads_without_id():
    html = """\
<html><body>
  <article>
    <a href="https://allegro.pl/oferta/real-item-12345678">
      <img src="https://img.allegro.pl/photos/real.jpg" />
    </a>
    <h2>Real Item</h2>
    <span>100,00 zł</span>
  </article>
  <article>
    <a href="https://allegro.pl/some-ad-link">
      <img src="https://img.allegro.pl/photos/ad.jpg" />
    </a>
    <h2>Macbook Pro 14'' 2021 32G 1T</h2>
    <span>4000,00 zł</span>
  </article>
</body></html>
"""
    offers = parse_search_results(html)
    assert len(offers) == 1
    assert offers[0].name == "Real Item"


def test_parse_offer_page_meta_price():
    html = """\
<html><head>
  <meta property="product:price:amount" content="2499.00" />
  <meta property="og:image" content="https://img.allegro.pl/photos/offer.jpg" />
  <link rel="canonical" href="https://allegro.pl/oferta/laptop-dell-15-12345678" />
</head><body>
  <h1>Laptop Dell 15 i7 16GB</h1>
  <script>{"sellerId":"98765"}</script>
</body></html>
"""
    offer = parse_offer_page(html)
    assert offer.id == "12345678"
    assert offer.name == "Laptop Dell 15 i7 16GB"
    assert offer.sellingMode.price.amount == "2499.00"
    assert offer.seller.id == "98765"
    assert len(offer.images) == 1
    assert "offer.jpg" in offer.images[0].url
    assert offer.parameters == {}


def test_parse_offer_page_with_explicit_id():
    html = """\
<html><head></head><body>
  <h1>Some Offer</h1>
  <p aria-label="1 299,00 zł aktualna cena">1 299,00 zł</p>
</body></html>
"""
    offer = parse_offer_page(html, offer_id="99999999")
    assert offer.id == "99999999"
    assert offer.name == "Some Offer"
    assert offer.sellingMode.price.amount == "1299.00"
    assert offer.parameters == {}


def test_parse_offer_page_extracts_parameters_json():
    html = """\
<html><head></head><body>
  <h1>Laptop Test</h1>
  <meta property="product:price:amount" content="1999.00" />
  <script id="__NEXT_DATA__" type="application/json">
  {
    "props": {
      "pageProps": {
        "parameters": [
          {"name": "Procesor", "value": "i7"},
          {"name": "RAM", "value": "16 GB"}
        ]
      }
    }
  }
  </script>
</body></html>
"""
    offer = parse_offer_page(html, offer_id="11111111")
    assert offer.parameters == {"Procesor": "i7", "RAM": "16 GB"}


def test_parse_offer_page_extracts_parameters_html():
    html = """\
<html><head></head><body>
  <h1>Laptop Test</h1>
  <meta property="product:price:amount" content="1999.00" />
  <h3>Parametry</h3>
  <table>
    <tr><td>Procesor</td><td>i5</td></tr>
    <tr><td>RAM</td><td>8 GB</td></tr>
  </table>
</body></html>
"""
    offer = parse_offer_page(html, offer_id="22222222")
    assert offer.parameters == {"Procesor": "i5", "RAM": "8 GB"}


def test_parse_offer_page_no_parameters():
    html = """\
<html><head></head><body>
  <h1>Simple Offer</h1>
  <meta property="product:price:amount" content="99.00" />
</body></html>
"""
    offer = parse_offer_page(html, offer_id="33333333")
    assert offer.parameters == {}


def test_parse_next_page_url():
    url = parse_next_page_url(SAMPLE_HTML)
    assert url == "https://allegro.pl/listing?string=laptop&p=2"


def test_parse_next_page_url_none():
    url = parse_next_page_url(SAMPLE_HTML_NO_NEXT)
    assert url is None
