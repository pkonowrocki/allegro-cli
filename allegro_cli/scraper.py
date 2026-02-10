from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup, Tag

from allegro_cli.api.models import (
    Category,
    Image,
    Offer,
    Price,
    Seller,
    SellingMode,
)


def _extract_offer_id(url: str) -> str | None:
    if not url:
        return None
    # Standard: /oferta/slug-12345678
    match = re.search(r"-(\d{6,})$", url.split("?")[0])
    if match:
        return match.group(1)
    # Fallback: /oferta/i12345678.html or offerID in query
    match = re.search(r"[/-]i?(\d{8,})", url)
    return match.group(1) if match else None


def _clean_price(raw: str) -> str:
    """Normalise '1\xa0299,56\xa0zł' or '1 299.56 zł' → '1299.56'."""
    cleaned = raw.replace("zł", "").replace("\xa0", "").replace(" ", "").strip()
    cleaned = cleaned.replace(",", ".")
    # Reject if not a valid number
    if re.fullmatch(r"\d+(\.\d+)?", cleaned):
        return cleaned
    return ""


def _extract_price(article: Tag) -> str:
    # 1) aria-label like "1894,00 zł aktualna cena"
    price_el = article.find(
        attrs={"aria-label": lambda x: x and "cena" in x.lower() and "zł" in x},
    )
    if price_el:
        label = price_el.get("aria-label", "")
        # Extract the price portion before "zł"
        match = re.search(r"([\d\s\xa0.,]+)\s*zł", label)
        if match:
            result = _clean_price(match.group(1) + "zł")
            if result:
                return result

    # 2) Any aria-label with zł (fallback)
    price_el2 = article.find(attrs={"aria-label": lambda x: x and "zł" in x})
    if price_el2:
        result = _clean_price(price_el2.get("aria-label", ""))
        if result:
            return result

    # 3) Text node containing 'zł'
    price_node = article.find(string=lambda t: t and "zł" in t)
    if price_node:
        result = _clean_price(price_node.parent.get_text(strip=True))
        if result:
            return result

    # 4) data-price attribute
    price_data = article.find(attrs={"data-price": True})
    if price_data:
        return price_data["data-price"]

    return ""


def _extract_image(article: Tag) -> str:
    """Find the real product image, skipping icons and placeholders."""
    for img in article.find_all("img"):
        # Skip tiny icons (e.g. 16x16 badge icons)
        w = img.get("width")
        h = img.get("height")
        if w and h:
            try:
                if int(w) <= 48 or int(h) <= 48:
                    continue
            except ValueError:
                pass

        src = img.get("data-src") or img.get("src") or ""
        if not src:
            continue
        # Skip SVG placeholders and tracking pixels
        if "placeholder" in src or src.endswith(".svg") or "1x1" in src:
            continue
        # Skip Allegro's generic info/badge icons
        if "action-common-information" in src or "brand-subb" in src:
            continue
        return src
    return ""


def _is_real_offer(article: Tag, offer_id: str | None, title: str) -> bool:
    """Filter out non-offer articles (category links, banners, etc.)."""
    if title == "Unknown Title":
        return False
    # Must have a valid offer ID (8+ digits)
    if not offer_id or len(offer_id) < 8:
        return False
    # Must have a link to /oferta/ or similar product page
    link = article.find("a", href=True)
    if link:
        href = link["href"]
        if "/oferta/" in href or "/listing/" in href:
            return True
        # Links with long numeric IDs are likely offers
        if offer_id and len(offer_id) >= 8:
            return True
    return False


def _try_extract_json_offers(html: str) -> list[Offer] | None:
    """Try to extract offers from embedded JSON (e.g. __NEXT_DATA__)."""
    match = re.search(
        r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return None

    # Navigate the Next.js data structure to find offer items
    props = data.get("props", {}).get("pageProps", {})
    items = props.get("items") or props.get("searchResult", {}).get("items")
    if not items:
        # Try deeper paths
        state = props.get("initialState", {})
        items = state.get("listing", {}).get("items")
    if not items or not isinstance(items, list):
        return None

    offers: list[Offer] = []
    for item in items:
        try:
            offer_id = str(item.get("id", ""))
            name = item.get("name") or item.get("title", "")
            if not name:
                continue

            # Price
            price_data = item.get("price", {})
            if isinstance(price_data, dict):
                amount = str(price_data.get("normal", {}).get("amount", ""))
                if not amount:
                    amount = str(price_data.get("amount", ""))
            else:
                amount = str(price_data) if price_data else ""

            # Image
            images_raw = item.get("images", []) or item.get("photos", [])
            images = []
            for img in images_raw:
                url = img.get("url", "") if isinstance(img, dict) else str(img)
                if url:
                    images.append(Image(url=url))

            # Seller
            seller_data = item.get("seller", {})
            seller_name = ""
            seller_id = ""
            if isinstance(seller_data, dict):
                seller_id = str(seller_data.get("id", ""))
                seller_name = seller_data.get("login", seller_data.get("name", ""))

            offers.append(
                Offer(
                    id=offer_id,
                    name=name,
                    seller=Seller(id=seller_id, name=seller_name),
                    sellingMode=SellingMode(
                        format="BUY_NOW",
                        price=Price(amount=amount, currency="PLN"),
                    ),
                    category=Category(id=""),
                    images=images,
                )
            )
        except Exception:
            continue

    return offers if offers else None


def parse_search_results(html: str) -> list[Offer]:
    # Try structured JSON first (more reliable when available)
    json_offers = _try_extract_json_offers(html)
    if json_offers:
        return json_offers

    # Fall back to HTML parsing
    soup = BeautifulSoup(html, "lxml")
    offers: list[Offer] = []

    for article in soup.find_all("article"):
        try:
            title_tag = article.find("h2")
            title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

            link_tag = article.find("a", href=True)
            url = link_tag["href"] if link_tag else ""
            offer_id = _extract_offer_id(url)

            if not _is_real_offer(article, offer_id, title):
                continue

            price_amount = _extract_price(article)
            image_url = _extract_image(article)

            offers.append(
                Offer(
                    id=offer_id or "",
                    name=title,
                    seller=Seller(id="", name=""),
                    sellingMode=SellingMode(
                        format="BUY_NOW",
                        price=Price(amount=price_amount, currency="PLN"),
                    ),
                    category=Category(id=""),
                    images=[Image(url=image_url)] if image_url else [],
                )
            )
        except Exception:
            continue

    return offers


def _extract_parameters_from_json(html: str) -> dict[str, str]:
    """Extract product parameters from __NEXT_DATA__ JSON."""
    match = re.search(
        r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return {}

    try:
        data = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return {}

    props = data.get("props", {}).get("pageProps", {})

    # Try several known paths for parameters
    params_list = (
        props.get("parameters")
        or props.get("offer", {}).get("parameters")
        or props.get("product", {}).get("parameters")
    )
    if not params_list or not isinstance(params_list, list):
        return {}

    result: dict[str, str] = {}
    for item in params_list:
        name = item.get("name", "")
        value = item.get("value") or item.get("values", "")
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        if name:
            result[name] = str(value)
    return result


def _extract_parameters_from_html(soup: BeautifulSoup) -> dict[str, str]:
    """Fallback: extract parameters from HTML tables or definition lists."""
    # Find heading containing "parametr" or "specyfik" (case-insensitive)
    heading = soup.find(
        re.compile(r"^h[1-6]$"),
        string=re.compile(r"parametr|specyfik", re.IGNORECASE),
    )
    if not heading:
        return {}

    result: dict[str, str] = {}

    # Look for a <table> after the heading
    table = heading.find_next("table")
    if table:
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                val = cells[1].get_text(strip=True)
                if key:
                    result[key] = val
        if result:
            return result

    # Look for a <dl> after the heading
    dl = heading.find_next("dl")
    if dl:
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            key = dt.get_text(strip=True)
            val = dd.get_text(strip=True)
            if key:
                result[key] = val

    return result


def parse_offer_page(html: str, offer_id: str = "") -> Offer:
    """Parse a single offer page into an Offer."""
    soup = BeautifulSoup(html, "lxml")

    # Title from <h1>
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else "Unknown Title"

    # ID — from canonical URL or passed-in ID
    if not offer_id:
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            offer_id = _extract_offer_id(canonical["href"]) or ""

    # Price — meta tag is most reliable on offer pages
    price_amount = ""
    meta_price = soup.find("meta", property="product:price:amount")
    if meta_price and meta_price.get("content"):
        price_amount = meta_price["content"]
    else:
        # Fallback: aria-label with "cena"
        price_el = soup.find(
            attrs={"aria-label": lambda x: x and "cena" in x.lower() and "zł" in x},
        )
        if price_el:
            label = price_el.get("aria-label", "")
            match = re.search(r"([\d\s\xa0.,]+)\s*zł", label)
            if match:
                price_amount = _clean_price(match.group(1) + "zł")
        # Last resort: text node with zł
        if not price_amount:
            price_node = soup.find(string=lambda t: t and "zł" in t)
            if price_node:
                price_amount = _clean_price(price_node.parent.get_text(strip=True))

    # Image — og:image or first product image
    image_url = ""
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        image_url = og_image["content"]

    # Seller ID from embedded JSON
    seller_id = ""
    seller_name = ""
    seller_match = re.search(r'"sellerId":"(\d+)"', html)
    if seller_match:
        seller_id = seller_match.group(1)
    if not seller_id:
        seller_match2 = re.search(r'"seller":\{"id":"(\d+)"', html)
        if seller_match2:
            seller_id = seller_match2.group(1)

    # Parameters — try JSON first, HTML fallback
    parameters = _extract_parameters_from_json(html)
    if not parameters:
        parameters = _extract_parameters_from_html(soup)

    return Offer(
        id=offer_id,
        name=title,
        seller=Seller(id=seller_id, name=seller_name),
        sellingMode=SellingMode(
            format="BUY_NOW",
            price=Price(amount=price_amount, currency="PLN"),
        ),
        category=Category(id=""),
        images=[Image(url=image_url)] if image_url else [],
        parameters=parameters,
    )


def parse_next_page_url(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    next_link = soup.find("a", attrs={"rel": "next"})
    if next_link and next_link.get("href"):
        return next_link["href"]
    return None
