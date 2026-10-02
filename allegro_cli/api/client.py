from __future__ import annotations

import json
import re
import time
from urllib.parse import unquote, urlencode, urlparse

import httpx
from cloakbrowser import launch

from allegro_cli.api.models import (
    AllegroCliError,
    AuthenticationError,
    OfferNotFoundError,
    RateLimitError,
    ScraperError,
    CartError,
    Offer,
    SearchResult,
)
from allegro_cli.config import Config

_COMMON_HEADERS = {
    "origin": "https://allegro.pl",
    "referer": "https://allegro.pl/",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "accept-language": "pl-PL",
}


class AllegroClient:
    def __init__(self, config: Config, verbose: bool = False):
        self._config = config
        self._verbose = verbose

        # Edge client for cart/packages — only when cookies are present
        self._edge: httpx.Client | None = None
        self._browser = None  # ponytail: single browser per invocation, closed on last use
        self._page = None
        if config.cookies:
            self._edge = httpx.Client(
                base_url=config.edgeBaseUrl,
                headers={**_COMMON_HEADERS, "cookie": config.cookies},
                timeout=30.0,
            )

    def _ensure_browser(self):
        if self._page:
            return self._page
        if not self._config.cookies:
            raise AuthenticationError(
                "No cookies configured. Scrape requires browser cookies.\n"
                "Run: allegro login"
            )
        kwargs: dict = {"headless": True, "locale": "pl-PL"}
        if self._config.cloakLicenseKey:
            kwargs["license_key"] = self._config.cloakLicenseKey
        self._browser = launch(**kwargs)
        context = self._browser.new_context(locale="pl-PL")
        # Inject cookies into the browser context
        cookies = []
        for pair in self._config.cookies.split(";"):
            pair = pair.strip()
            if "=" not in pair:
                continue
            name, _, value = pair.partition("=")
            # Let CloakBrowser establish its own DataDome cookie. Reusing a
            # token from a different browser caused 403 on valid sessions.
            if name.strip().lower() == "datadome":
                continue
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".allegro.pl",
                "path": "/",
            })
        context.add_cookies(cookies)
        self._page = context.new_page()
        return self._page

    # --- Scrape (allegro.pl, cookie auth) ---

    def scrape_search(
        self,
        phrase: str,
        page: int = 1,
        category: str | None = None,
        sort: str | None = None,
        price_min: str | None = None,
        price_max: str | None = None,
        seller: str | None = None,
        condition: list[str] | None = None,
        smart: bool = False,
        delivery_time: str | None = None,
        location: str | None = None,
        pay: bool = False,
        filters: list[str] | None = None,
    ) -> SearchResult:
        from allegro_cli.scraper import parse_next_page_url, parse_search_results

        if seller:
            base_url = f"https://allegro.pl/uzytkownik/{seller}"
        elif category:
            cat_match = re.search(r"(\d+)$", category)
            if cat_match:
                base_url = f"https://allegro.pl/kategoria/-{cat_match.group(1)}"
            else:
                base_url = f"https://allegro.pl/kategoria/{category}"
        else:
            base_url = "https://allegro.pl/listing"

        # Use a list of tuples to support multiple values for the same key (e.g. stan=nowe&stan=used)
        params: list[tuple[str, str]] = [("string", phrase)]
        if page > 1:
            params.append(("p", str(page)))
        if sort:
            params.append(("order", sort))
        if price_min:
            params.append(("price_from", price_min))
        if price_max:
            params.append(("price_to", price_max))
        if condition:
            for c in condition:
                params.append(("stan", c))
        if smart:
            params.append(("allegro-smart-standard", "1"))
        if delivery_time:
            params.append(("delivery_time", delivery_time))
        if location:
            params.append(("miejsce-wysylki", location))
        if pay:
            params.append(("allegro-pay", "1"))
        if filters:
            for f in filters:
                if "=" in f:
                    k, v = f.split("=", 1)
                    params.append((k, v))

        full_url = base_url + "?" + urlencode(params)

        html = self._fetch_page(full_url)
        offers = parse_search_results(html)
        next_page_url = parse_next_page_url(html)
        return SearchResult(
            offers=offers,
            page=page,
            hasNextPage=next_page_url is not None,
            nextPageUrl=next_page_url,
        )

    def scrape_offer(self, offer_id: str) -> Offer:
        """Fetch and parse a single offer page by ID."""
        from allegro_cli.scraper import (
            extract_lazy_contexts,
            parse_offer_page,
        )
        url = f"https://allegro.pl/oferta/-{offer_id}"
        try:
            html = self._fetch_page(url)
        except RateLimitError:
            # Direct offer navigation is blocked even when following its
            # actual link from a listing works in the same headless backend.
            resolved_url = self._page.url if self._page else url
            html = self._fetch_offer_via_listing(offer_id, resolved_url)
        except AllegroCliError as e:
            if e.code == "NotFoundException":
                raise OfferNotFoundError(offer_id)
            raise e

        offer = parse_offer_page(html, offer_id=offer_id)
        if not offer:
            raise OfferNotFoundError(offer_id)

        # If we only got a few params, try lazy loading the rest
        if len(offer.parameters) < 15:
            contexts = extract_lazy_contexts(html)
            if contexts:
                lazy_params = self._fetch_lazy_parameters(url, contexts)
                for k, v in lazy_params.items():
                    offer.parameters.setdefault(k, v)

        return offer

    def _fetch_offer_via_listing(self, offer_id: str, resolved_url: str) -> str:
        from bs4 import BeautifulSoup
        from allegro_cli.scraper import _extract_offer_id

        resolved = urlparse(resolved_url)
        match = re.fullmatch(
            r"/oferta/(.+)-" + re.escape(offer_id), unquote(resolved.path),
        )
        if resolved.hostname != "allegro.pl" or not match:
            raise RateLimitError("Offer blocked; no resolved product title for listing navigation")
        phrase = match.group(1).replace("-", " ")
        listing_url = "https://allegro.pl/listing?" + urlencode({"string": phrase})

        # A denied navigation leaves a browser-bound challenge cookie behind.
        # Keep saved account cookies and the edge client untouched.
        self.close()
        listing_html = self._fetch_page(listing_url)
        page = self._ensure_browser()
        soup = BeautifulSoup(listing_html, "lxml")
        href = None
        for article in soup.find_all("article"):
            for link in article.find_all("a", href=True):
                candidate = link["href"]
                if urlparse(candidate).hostname not in (None, "allegro.pl"):
                    continue
                if _extract_offer_id(candidate) == offer_id:
                    href = candidate
                    break
            if href:
                break
        if not href:
            raise ScraperError(f"Offer {offer_id} not present in fallback listing")

        self._log(f"Following exact offer {offer_id} from listing (headless)")
        selector = "article a[href=" + json.dumps(href) + "]"
        navigation_statuses = []

        def record_navigation(response):
            if response.request.is_navigation_request() and response.request.frame == page.main_frame:
                navigation_statuses.append(response.status)

        page.on("response", record_navigation)
        try:
            with page.expect_navigation(wait_until="domcontentloaded", timeout=30000) as navigation:
                page.locator(selector).first.click(timeout=15000)
            response = navigation.value
            # DataDome can return an initial 403 that its own JS resolves via
            # redirects. Wait for product content, then require a final 200.
            page.wait_for_selector("h1", state="attached", timeout=20000)
            final_status = navigation_statuses[-1] if navigation_statuses else (
                response.status if response else 0
            )
            if final_status != 200:
                raise RateLimitError("Offer remains blocked after listing navigation")
            if urlparse(page.url).hostname != "allegro.pl" or _extract_offer_id(page.url) != offer_id:
                raise ScraperError("Listing navigation did not reach the requested offer")
            return page.content()
        finally:
            page.remove_listener("response", record_navigation)

    def compare_offer(self, offer_id: str) -> dict:
        """Read Allegro's comparison panel and its first cheapest-sorted page."""
        from decimal import Decimal
        from urllib.parse import parse_qs
        from allegro_cli.scraper import parse_other_offers_panel, parse_other_offers_listing

        self.scrape_offer(offer_id)
        page = self._ensure_browser()
        summary = parse_other_offers_panel(page.content())
        if summary is None:
            raise ScraperError("This offer has no Other Offers panel", path="otherOffers")
        result = {"sourceOfferId": offer_id, **summary, "offers": [],
                  "returnedOfferCount": 0, "complete": False, "page": 1,
                  "sort": "price", "deliveryPriceScope": "displayed_listing_not_checkout"}
        if not summary["cheapest"]:
            return result
        page.locator(".other-offers-link-cheapest").first.click(timeout=15000)
        page.wait_for_selector('[data-box-name="ProductListingContent"] article h2',
                               state="attached", timeout=20000)
        params = parse_qs(urlparse(page.url).query)
        for key, value in summary["cheapest"]["queryParameters"].items():
            if params.get(key) != [value]:
                raise ScraperError("Comparison filters not applied", path="otherOffers.filters")
        # Matching price/condition cannot distinguish stale cards with equal
        # prices. A full reload provides a new document for the selected URL,
        # independent of the sidebar's asynchronous update generation.
        self._fetch_page(page.url, reload=True)
        page.wait_for_selector('[data-box-name="ProductListingContent"] article h2',
                               state="attached", timeout=20000)
        params = parse_qs(urlparse(page.url).query)
        for key, value in summary["cheapest"]["queryParameters"].items():
            if params.get(key) != [value]:
                raise ScraperError("Comparison filters lost after reload", path="otherOffers.filters")
        # A new document alone is insufficient if its cards are hydrated later.
        # Keep price/condition checks as additional validation of fresh results.
        deadline = time.monotonic() + 20
        while True:
            try:
                offers = parse_other_offers_listing(page.content())
            except ScraperError:
                offers = []
            offers.sort(key=lambda o: Decimal(o["price"]["amount"]))
            new_only = params.get("buyNew") == ["1"]
            ready = (offers and offers[0]["price"] == summary["cheapest"]["price"] and
                     (not new_only or all(o["condition"] == "Nowy" for o in offers)))
            if ready:
                break
            if time.monotonic() >= deadline:
                raise ScraperError("Comparison listing did not match panel price/condition after refresh",
                                   path="otherOffers.listing")
            page.wait_for_timeout(200)
        result["offers"] = offers
        result["returnedOfferCount"] = len(offers)
        # Conservative: panel count can include conditions hidden by filters.
        result["complete"] = len(offers) == summary["offerCount"]
        selected_id = summary["cheapest"]["offerId"]
        candidate = (next((o for o in offers if o["offerId"] == selected_id), None)
                     if selected_id else offers[0])
        if candidate and candidate["price"] == summary["cheapest"]["price"]:
            result["cheapest"] = {**summary["cheapest"], **candidate}
        return result

    def _fetch_lazy_parameters(
        self, offer_url: str, contexts: list[dict],
    ) -> dict[str, str]:
        """Fetch lazy-loaded parameter groups via the opbox API."""
        from allegro_cli.scraper import parse_opbox_parameters

        result: dict[str, str] = {}
        max_requests = 3
        page = self._ensure_browser()
        for ctx in contexts[:max_requests]:
            lazy_url = f"{offer_url}?lazyContext={ctx['value']}"
            self._log(f"GET {lazy_url} (lazy params)")
            try:
                resp = page.request.get(
                    lazy_url,
                    headers={
                        "Accept": "application/vnd.opbox-web.subtree+json",
                    },
                )
            except Exception:
                continue
            if resp.status != 200:
                continue
            try:
                data = resp.json()
            except (ValueError, Exception):
                continue
            params = parse_opbox_parameters(data)
            for k, v in params.items():
                result.setdefault(k, v)
            if len(result) > 15:
                break
        return result

    def _fetch_page(self, url: str, *, reload: bool = False) -> str:
        from urllib.parse import parse_qs
        from playwright.sync_api import Error as PlaywrightError
        from allegro_cli.scraper import _extract_offer_id

        page = self._ensure_browser()
        self._log(f"GET {url} (CloakBrowser)")
        responses = []

        def record_navigation(response):
            if response.request.is_navigation_request() and response.request.frame == page.main_frame:
                responses.append(response)

        # Register before goto: challenge JS can redirect before it returns.
        page.on("response", record_navigation)
        try:
            t0 = time.monotonic()
            resp = (page.reload(wait_until="domcontentloaded", timeout=30000) if reload else
                    page.goto(url, wait_until="domcontentloaded", timeout=30000))
            status = resp.status if resp else 0
            self._log(f"Response: {status} ({time.monotonic() - t0:.1f}s)")
            if status == 403:
                requested = urlparse(url)
                requested_id = _extract_offer_id(url) if requested.path.startswith(("/oferta/", "/produkt/")) else None
                selector = "h1" if requested_id else "body"
                deadline = time.monotonic() + 20
                restored_query = False
                while True:
                    latest = responses[-1] if responses else resp
                    current = urlparse(page.url)
                    same_target = (current.scheme == "https" and current.hostname == requested.hostname and
                                   (_extract_offer_id(page.url) == requested_id if requested_id else
                                    current.path == requested.path and all(
                                        parse_qs(current.query).get(k) == v
                                        for k, v in parse_qs(requested.query).items())))
                    if (latest and latest.status == 200 and not same_target and not requested_id and
                        not restored_query and current.scheme == "https" and
                        current.hostname == requested.hostname and current.path == requested.path):
                        # Challenge redirects can turn query spaces into literal '+'.
                        # With the established session, restore the exact request once.
                        restored_query = True
                        restored = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        if restored:
                            responses.append(restored)
                        continue
                    if latest and latest.status == 200 and same_target:
                        try:
                            ready = (page.evaluate("document.readyState") in ("interactive", "complete") and
                                     page.title().strip().lower() not in ("", "allegro.pl") and
                                     page.locator(selector).count() > 0)
                            if ready:
                                self._log("Challenge resolved by site JavaScript: final 200")
                                return page.content()
                        except PlaywrightError:
                            # Execution context can disappear during redirects.
                            pass
                    elif latest and latest.status in (401, 404) and same_target:
                        status = latest.status
                        break
                    if time.monotonic() >= deadline:
                        break
                    page.wait_for_timeout(250)
        finally:
            page.remove_listener("response", record_navigation)

        if status == 200:
            return page.content()

        if status == 401:
            raise AuthenticationError("Session expired (401). Run: allegro login")

        if status == 403:
            raise RateLimitError(
                message="Forbidden (403) - challenge did not resolve within 20 seconds",
                userMessage="Allegro did not allow this request after waiting for the page challenge.",
            )

        if status == 404:
            raise AllegroCliError(
                message=f"Page not found (404): {url}",
                code="NotFoundException",
                userMessage="The requested page was not found.",
            )

        raise AllegroCliError(
            message=f"Scrape returned {status}: {url}",
            code="ScrapeException",
            userMessage=f"Could not fetch page ({status}).",
        )

    # --- Cart (edge.allegro.pl, cookie auth) ---

    def _require_edge(self) -> httpx.Client:
        if not self._edge:
            raise AuthenticationError(
                "No cookies configured. Cart/packages require browser cookies.\n"
                "Run: allegro login"
            )
        return self._edge

    def get_cart(self) -> dict:
        resp = self._request(
            "GET", "/carts",
            accept="application/vnd.allegro.internal.v6+json",
        )
        return resp.json()

    def change_cart_quantity(
        self,
        item_id: str,
        delta: int,
        seller_id: str,
        nav_category_id: str | None = None,
    ) -> None:
        body = {
            "items": [
                {
                    "itemId": item_id,
                    "delta": delta,
                    "sellerId": seller_id,
                    **({"navCategoryId": nav_category_id} if nav_category_id else {}),
                    "navTree": "navigation-pl",
                }
            ]
        }
        self._request(
            "POST",
            "/carts/changeQuantityCommand",
            json=body,
            accept="application/vnd.allegro.public.v5+json",
            content_type="application/vnd.allegro.public.v5+json",
        )

    def remove_cart_item(self, item_id: str) -> None:
        """Completely remove an item from the cart using its unique item ID."""
        self._request(
            "DELETE",
            f"/cart/items?ids={item_id}",
            accept="application/vnd.allegro.internal.v1+json",
        )


    # --- Packages / delivery ---

    def get_packages_summary(self) -> dict:
        resp = self._request(
            "GET", "/packages/summary",
            accept="application/vnd.allegro.internal.v1+json",
        )
        return resp.json()

    def get_packages_list(self) -> list[dict]:
        """Fetch the detailed list of current packages."""
        resp = self._request(
            "GET", "/packages",
            accept="application/vnd.allegro.internal.v1+json",
        )
        data = resp.json()
        return data.get("packages", [])

    def get_orders(self, offset: int = 0, limit: int = 15) -> dict:
        """Fetch paginated order history from edge.allegro.pl/myorders."""
        resp = self._request(
            "GET", f"/myorders?offset={offset}&limit={limit}",
            accept="application/vnd.allegro.internal.v1+json",
        )
        return resp.json()

    # --- HTTP layer (edge API, cookie auth) ---

    def _request(
        self,
        method: str,
        path: str,
        accept: str = "application/vnd.allegro.internal.v1+json",
        content_type: str | None = None,
        **kwargs,
    ) -> httpx.Response:
        edge = self._require_edge()
        headers = {"accept": accept}
        if content_type:
            headers["content-type"] = content_type

        resp = edge.request(method, path, headers=headers, **kwargs)
        if self._verbose:
            self._log(f"DEBUG: {method} {path} -> {resp.status_code}")
            self._log(f"DEBUG Response: {resp.text}")
        if resp.status_code == 401:
            raise AuthenticationError("Session expired (401). Run: allegro login")
        if resp.status_code == 403:
            raise RateLimitError(
                message="Forbidden (403)",
                userMessage="Access denied. Your session cookies may have expired.",
            )
        if resp.status_code >= 400:
            # Check if it's a cart-related endpoint
            if "/cart" in path or "/carts" in path:
                raise CartError(
                    message=f"API returned {resp.status_code}: {resp.text[:300]}",
                    code="CartApiException",
                )
            raise AllegroCliError(
                message=f"API returned {resp.status_code}: {resp.text[:300]}",
                code="ApiException",
                userMessage=f"Allegro API error ({resp.status_code}).",
            )
        return resp

    def _log(self, msg: str) -> None:
        if self._verbose:
            import sys
            print(msg, file=sys.stderr, flush=True)

    def close(self):
        if self._browser:
            self._browser.close()
            self._browser = None
            self._page = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
