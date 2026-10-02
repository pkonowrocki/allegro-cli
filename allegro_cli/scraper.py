from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup, Tag

from allegro_cli.api.models import (
    Category,
    DeliveryInfo,
    Image,
    Offer,
    Price,
    ScraperError,
    Seller,
    SellingMode,
    Stock,
)


def _extract_offer_id(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    # Current product cards carry offerId; sponsored cards wrap the URL.
    if parsed.path == "/events/clicks":
        target = query.get("redirect", [""])[0]
        target_parts = urlparse(target)
        if target_parts.hostname != "allegro.pl":
            return None
        url = target
        parsed = target_parts
        query = parse_qs(parsed.query)
    offer_id = query.get("offerId", [""])[0]
    if re.fullmatch(r"\d{8,}", offer_id):
        return offer_id
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
    except json.JSONDecodeError:
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

            # URL
            url = item.get("url", "")

            # Image
            images_raw = item.get("images", []) or item.get("photos", [])
            images = []
            for img in images_raw:
                img_url = img.get("url", "") if isinstance(img, dict) else str(img)
                if img_url:
                    images.append(Image(url=img_url))

            # Seller
            seller_data = item.get("seller", {})
            seller_name = ""
            seller_id = ""
            if isinstance(seller_data, dict):
                seller_id = str(seller_data.get("id", ""))
                seller_name = seller_data.get("login", seller_data.get("name", ""))

            # Selling mode
            selling_format = item.get("sellingMode", {}).get("format", "BUY_NOW") if isinstance(item.get("sellingMode"), dict) else "BUY_NOW"
            popularity = item.get("popularity")
            if popularity is not None:
                popularity = int(popularity)

            # Delivery
            delivery = None
            delivery_data = item.get("delivery")
            if isinstance(delivery_data, dict):
                lp = delivery_data.get("lowestPrice", {})
                delivery = DeliveryInfo(
                    lowestPrice=Price(amount=str(lp.get("amount", "")), currency=lp.get("currency", "PLN")) if isinstance(lp, dict) and lp.get("amount") else None,
                    availableForFree=delivery_data.get("availableForFree", False),
                )

            # Stock
            stock = None
            stock_data = item.get("stock")
            if isinstance(stock_data, dict):
                stock = Stock(
                    unit=stock_data.get("unit", "UNIT"),
                    available=int(stock_data.get("available", 0)),
                )

            offers.append(
                Offer(
                    id=offer_id,
                    name=name,
                    url=url,
                    seller=Seller(id=seller_id, name=seller_name),
                    sellingMode=SellingMode(
                        format=selling_format,
                        price=Price(amount=amount, currency="PLN"),
                        popularity=popularity,
                    ),
                    category=Category(id=""),
                    images=images,
                    delivery=delivery,
                    stock=stock,
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
            if offer_id and ("/events/clicks?" in url or "offerId=" in url):
                url = f"https://allegro.pl/oferta/{offer_id}"

            if not _is_real_offer(article, offer_id, title):
                continue

            price_amount = _extract_price(article)
            image_url = _extract_image(article)

            # Seller from DOM (best-effort)
            seller_id = ""
            seller_name = ""
            seller_link = article.find("a", href=re.compile(r"/uzytkownik/"))
            if seller_link:
                seller_name = seller_link.get_text(strip=True)
            # ponytail: HTML seller extraction is best-effort, blank if not found

            offers.append(
                Offer(
                    id=offer_id or "",
                    name=title,
                    url=url,
                    seller=Seller(id=seller_id, name=seller_name),
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


def _extract_parameters_from_serialized_json(soup: BeautifulSoup) -> dict[str, str]:
    """Extract parameters from <script data-serialize-box-id> JSON blocks.

    Allegro embeds offer parameters in JSON inside <script> tags that contain
    a ``groups`` list with ``singleValueParams`` and ``multiValueParams``.
    """
    result: dict[str, str] = {}
    for script in soup.find_all("script", attrs={"data-serialize-box-id": True}):
        text = script.string
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        groups = data.get("groups")
        if not groups or not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for param in group.get("singleValueParams", []):
                name = param.get("name", "")
                value = param.get("value", {})
                if isinstance(value, dict):
                    value = value.get("name", "")
                if name and value:
                    result.setdefault(name, str(value))
            for param in group.get("multiValueParams", []):
                name = param.get("name", "")
                values = param.get("values", [])
                if isinstance(values, list):
                    parts = []
                    for v in values:
                        if isinstance(v, dict):
                            parts.append(v.get("name", ""))
                        else:
                            parts.append(str(v))
                    value = ", ".join(p for p in parts if p)
                else:
                    value = str(values)
                if name and value:
                    result.setdefault(name, value)
    return result


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
    except json.JSONDecodeError:
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
        if not isinstance(item, dict):
            continue
        name = item.get("name", "")
        value = item.get("value") or item.get("values", "")
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        if name:
            result[name] = str(value)
    return result


def _extract_param_value(cell: Tag) -> str:
    """Extract a clean parameter value from a table cell.

    Allegro value cells contain ``<a>`` with the value and optionally a sibling
    ``<div>`` with a long description (e.g. for "Stan").  We want just the
    concise value, not the description.
    """
    # Check for <a> or <span> inside a wrapper <div>
    wrapper = cell.find("div")
    target = wrapper if wrapper else cell

    # Prefer the first <a> link text (the concise value)
    link = target.find("a")
    if link:
        return link.get_text(strip=True)

    # If no link, take the first direct text node or first child text,
    # skipping nested description divs.
    for child in target.children:
        if isinstance(child, str):
            text = child.strip()
            if text:
                return text
        elif hasattr(child, "name") and child.name not in ("div",):
            text = child.get_text(strip=True)
            if text:
                return text

    # Final fallback: full text
    return cell.get_text(strip=True)


def _extract_params_from_table(table: Tag) -> dict[str, str]:
    """Extract key-value parameters from a 2-column table."""
    result: dict[str, str] = {}
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            key = cells[0].get_text(strip=True)
            val = _extract_param_value(cells[1])
            if key and val:
                result.setdefault(key, val)
    return result


def _extract_parameters_from_html(soup: BeautifulSoup) -> dict[str, str]:
    """Fallback: extract parameters from HTML tables or definition lists.

    Allegro renders parameters in tables that follow headings containing
    "Parametry" or "Specyfikacja".  The page may have multiple such tables
    (a compact sidebar one and a full expanded one).  We pick the table with
    the most parameters.
    """
    best: dict[str, str] = {}

    # Scan ALL parameter-related headings and their subsequent tables
    for heading in soup.find_all(
        re.compile(r"^h[1-6]$"),
        string=re.compile(r"parametr|specyfik", re.IGNORECASE),
    ):
        table = heading.find_next("table")
        if table:
            params = _extract_params_from_table(table)
            if len(params) > len(best):
                best = params

    if best:
        return best

    # Fallback: look for a <dl> after any parameter heading
    heading = soup.find(
        re.compile(r"^h[1-6]$"),
        string=re.compile(r"parametr|specyfik", re.IGNORECASE),
    )
    if heading:
        dl = heading.find_next("dl")
        if dl:
            result: dict[str, str] = {}
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt, dd in zip(dts, dds):
                key = dt.get_text(strip=True)
                val = dd.get_text(strip=True)
                if key:
                    result[key] = val
            return result

    return {}


def _walk_for_params(data, result: dict[str, str]) -> None:
    """Recursively walk a JSON structure looking for parameter groups."""
    if isinstance(data, dict):
        groups = data.get("groups")
        if isinstance(groups, list):
            for group in groups:
                if not isinstance(group, dict):
                    continue
                for param in group.get("singleValueParams", []):
                    name = param.get("name", "")
                    value = param.get("value", {})
                    if isinstance(value, dict):
                        value = value.get("name", "")
                    if name and value:
                        result.setdefault(name, str(value))
                for param in group.get("multiValueParams", []):
                    name = param.get("name", "")
                    values = param.get("values", [])
                    if isinstance(values, list):
                        parts = []
                        for v in values:
                            if isinstance(v, dict):
                                parts.append(v.get("name", ""))
                            else:
                                parts.append(str(v))
                        value = ", ".join(p for p in parts if p)
                    else:
                        value = str(values)
                    if name and value:
                        result.setdefault(name, value)
        for v in data.values():
            _walk_for_params(v, result)
    elif isinstance(data, list):
        for item in data:
            _walk_for_params(item, result)


def extract_lazy_contexts(html: str) -> list[dict]:
    """Extract lazy-load context entries from the initial HTML.

    Allegro embeds ``<script data-serialize-box-id>`` tags whose JSON payload
    may contain ``contextUrlParamName: "lazyContext"`` with an encoded value
    used to fetch additional page sections via the opbox API.
    """
    contexts: list[dict] = []
    for m in re.finditer(
        r'<script[^>]+data-serialize-box-id="([^"]*)"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    ):
        box_id = m.group(1)
        try:
            data = json.loads(m.group(2))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        if (
            data.get("contextUrlParamName") == "lazyContext"
            and data.get("contextUrlParamValue")
        ):
            contexts.append({
                "box_id": box_id,
                "value": data["contextUrlParamValue"],
                "cardinal": data.get("cardinal", 0),
                "corellationId": data.get("corellationId", ""),
            })
    # Sort: "tab content" first (where params live), then by cardinal
    contexts.sort(
        key=lambda c: (c["corellationId"] != "tab content", c["cardinal"]),
    )
    return contexts


def parse_opbox_parameters(data) -> dict[str, str]:
    """Extract parameters from an opbox subtree JSON response."""
    result: dict[str, str] = {}
    _walk_for_params(data, result)
    return result


def parse_offer_page(html: str, offer_id: str = "") -> Offer:
    """Parse a single offer page into an Offer."""
    soup = BeautifulSoup(html, "lxml")

    # Title from <h1>
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else "Unknown Title"
    if title == "Unknown Title":
        raise ScraperError("Could not find offer title (h1 tag)", path="h1")

    # ID — from canonical URL or passed-in ID
    if not offer_id:
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            offer_id = _extract_offer_id(canonical["href"]) or ""

    # URL — from canonical link or construct from offer_id
    canonical = soup.find("link", rel="canonical")
    offer_url = canonical["href"] if canonical and canonical.get("href") else ""
    if offer_id and _extract_offer_id(offer_url) != offer_id:
        offer_url = f"https://allegro.pl/oferta/-{offer_id}"

    # Price — meta tag is most reliable on offer pages
    price_amount = ""
    meta_price = soup.find("meta", property="product:price:amount")
    if meta_price and meta_price.get("content"):
        price_amount = meta_price["content"]
    else:
        # Current offer pages serialize the selected offer's own price.
        # Bind it to the requested ID so recommendations cannot win.
        for script in soup.find_all("script", attrs={"data-serialize-box-id": True}):
            try:
                data = json.loads(script.get_text())
            except (ValueError, TypeError):
                continue
            if not isinstance(data, dict) or str(data.get("offerId", "")) != offer_id:
                continue
            price_data = data.get("price")
            if isinstance(price_data, dict) and isinstance(price_data.get("priceString"), str):
                price_amount = _clean_price(price_data["priceString"])
                if price_amount:
                    break
    if not price_amount:
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
    
    if not price_amount:
        raise ScraperError("Could not find offer price", path="price")

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

    # Parameters — try serialized JSON (most reliable), then __NEXT_DATA__, then HTML
    parameters = _extract_parameters_from_serialized_json(soup)
    if not parameters:
        parameters = _extract_parameters_from_json(html)
    if not parameters:
        parameters = _extract_parameters_from_html(soup)

    return Offer(
        id=offer_id,
        name=title,
        url=offer_url,
        seller=Seller(id=seller_id, name=seller_name),
        sellingMode=SellingMode(
            format="BUY_NOW",
            price=Price(amount=price_amount, currency="PLN"),
        ),
        category=Category(id=""),
        images=[Image(url=image_url)] if image_url else [],
        parameters=parameters,
    )


def parse_other_offers_panel(html: str) -> dict | None:
    """Read only the serialized 'Other Offers' box, never recommendations."""
    soup = BeautifulSoup(html, "lxml")
    box = soup.find(attrs={"data-box-name": "Other Offers"})
    if not box:
        return None
    script = soup.find("script", attrs={"data-serialize-box-id": box.get("data-box-id")})
    if not script:
        raise ScraperError("Other Offers panel payload missing", path="otherOffers")
    try:
        data = json.loads(script.get_text())
    except ValueError as exc:
        raise ScraperError("Invalid Other Offers panel payload", path="otherOffers") from exc
    if not isinstance(data, dict) or not isinstance(data.get("offerCount"), int):
        raise ScraperError("Invalid Other Offers panel count", path="otherOffers")
    result = {
        "title": data.get("title"),
        "offerCount": data["offerCount"],
        "isProductSet": data.get("isProductSet"),
        "cheapest": None,
        "fastest": None,
    }
    for group in data.get("links", []):
        for link in group.get("links", []):
            kind = link.get("analyticsAttributes", {}).get("data-analytics-click-label")
            if kind not in ("cheapest", "fastest"):
                continue
            raw = link.get("rawPrice") or {}
            amount = raw.get("amount")
            if not isinstance(amount, str) or not re.fullmatch(r"\d+(?:\.\d+)?", amount):
                raise ScraperError("Other Offers panel price missing", path="otherOffers.price")
            url = link.get("url") or ""
            offer_id = _extract_offer_id(url)
            result[kind] = {
                "price": {"amount": amount, "currency": raw.get("currency")},
                "subtitle": link.get("subtitle"),
                "smartEligible": bool(link.get("freeboxIcon") and
                                      link["freeboxIcon"].get("alt") == "Smart!"),
                "offerId": offer_id,
                "url": url if offer_id else None,
                "queryParameters": {p["name"]: p["value"]
                                    for p in link.get("queryParameters", [])},
            }
    return result


def parse_other_offers_listing(html: str) -> list[dict]:
    """Parse only actual cards inside the comparison listing."""
    soup = BeautifulSoup(html, "lxml")
    box = soup.find(attrs={"data-box-name": "ProductListingContent"})
    if not box:
        raise ScraperError("Other Offers listing missing", path="otherOffers.listing")
    result = []
    seen = set()
    for article in box.find_all("article"):
        heading = article.find(["h2", "h3"])
        link = heading.find("a", href=True) if heading else None
        if not link:
            continue
        url = link["href"]
        parts = urlparse(url)
        if parts.hostname not in (None, "allegro.pl"):
            continue
        offer_id = _extract_offer_id(url)
        if not offer_id or offer_id in seen:
            continue
        price_el = article.find(attrs={"aria-label": lambda v: v and "aktualna cena" in v})
        price_match = re.search(r"([\d\s\xa0.,]+)\s*zł", price_el["aria-label"]) if price_el else None
        amount = _clean_price(price_match.group(1) + "zł") if price_match else ""
        if not amount:
            raise ScraperError(f"Missing comparison price for {offer_id}", path="otherOffers.price")
        text = article.get_text(" ", strip=True)
        seller = re.search(r"\|\s*(.+?)\s+Poleca sprzedającego:", text)
        total = re.search(r"(\d[\d\s\xa0]*,\d{2})\s*zł\s+z dostawą", text)
        condition = None
        for dt in article.find_all("dt"):
            if dt.get_text(strip=True) == "Stan":
                dd = dt.find_next_sibling("dd")
                condition = dd.get_text(strip=True) if dd else None
                break
        product = re.search(r"([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})$", parts.path)
        result.append({
            "offerId": offer_id,
            "name": heading.get_text(" ", strip=True),
            "url": url if parts.hostname else "https://allegro.pl" + url,
            "productId": product.group(1) if product else None,
            "price": {"amount": amount, "currency": "PLN"},
            "seller": seller.group(1).strip() if seller else None,
            "condition": condition,
            "smartEligible": article.find("img", alt="Smart!") is not None,
            "displayedTotalWithDelivery": {"amount": _clean_price(total.group(1) + "zł"),
                                           "currency": "PLN"} if total else None,
        })
        seen.add(offer_id)
    return result


def parse_next_page_url(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    next_link = soup.find("a", attrs={"rel": "next"})
    if next_link and next_link.get("href"):
        return next_link["href"]
    return None
