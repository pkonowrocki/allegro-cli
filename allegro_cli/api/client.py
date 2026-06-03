from __future__ import annotations

import re
import time
from urllib.parse import urlencode

import httpx
from curl_cffi.requests import Session as CffiSession

from allegro_cli.api.models import (
    AllegroCliError,
    AuthenticationError,
    Offer,
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
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}


class AllegroClient:
    def __init__(self, config: Config, verbose: bool = False):
        self._config = config
        self._verbose = verbose

        # Edge client for cart/packages — only when cookies are present
        self._edge: httpx.Client | None = None
        self._web: CffiSession | None = None
        if config.cookies:
            self._edge = httpx.Client(
                base_url=config.edgeBaseUrl,
                headers={**_COMMON_HEADERS, "cookie": config.cookies},
                timeout=30.0,
            )
            # curl_cffi session — impersonates Chrome TLS fingerprint to pass Cloudflare
            self._web = CffiSession(impersonate="chrome")
            self._web.headers.update({"cookie": config.cookies})

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
        condition: str | None = None,
        free_shipping: bool = False,
    ) -> list[Offer]:
        if not self._config.cookies:
            raise AuthenticationError(
                "No cookies configured. Scrape requires browser cookies.\n"
                "Run: allegro login"
            )

        from allegro_cli.scraper import parse_search_results

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

        params: dict[str, str] = {"string": phrase}
        if page > 1:
            params["p"] = str(page)
        if sort:
            params["order"] = sort
        if price_min:
            params["price_from"] = price_min
        if price_max:
            params["price_to"] = price_max
        if condition:
            params["state"] = condition
        if free_shipping:
            params["delivery"] = "free"
        full_url = base_url + "?" + urlencode(params)

        html = self._fetch_page(full_url)
        return parse_search_results(html)

    def scrape_offer(self, offer_id: str) -> Offer:
        """Fetch and parse a single offer page by ID."""
        if not self._config.cookies:
            raise AuthenticationError(
                "No cookies configured. Scrape requires browser cookies.\n"
                "Run: allegro login"
            )

        from allegro_cli.scraper import (
            extract_lazy_contexts,
            parse_offer_page,
        )

        url = f"https://allegro.pl/oferta/-{offer_id}"
        html = self._fetch_page(url)
        offer = parse_offer_page(html, offer_id=offer_id)

        # If we only got a few params, try lazy loading the rest
        if len(offer.parameters) < 15:
            contexts = extract_lazy_contexts(html)
            if contexts:
                lazy_params = self._fetch_lazy_parameters(url, contexts)
                for k, v in lazy_params.items():
                    offer.parameters.setdefault(k, v)

        return offer

    def _fetch_lazy_parameters(
        self, offer_url: str, contexts: list[dict],
    ) -> dict[str, str]:
        """Fetch lazy-loaded parameter groups via the opbox API."""
        from allegro_cli.scraper import parse_opbox_parameters

        result: dict[str, str] = {}
        max_requests = 3
        for ctx in contexts[:max_requests]:
            lazy_url = f"{offer_url}?lazyContext={ctx['value']}"
            self._log(f"GET {lazy_url} (lazy params)")
            try:
                resp = self._web.get(
                    lazy_url,
                    headers={
                        "Accept": "application/vnd.opbox-web.subtree+json",
                    },
                    timeout=15,
                )
            except Exception:
                continue
            if resp.status_code != 200:
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

    def _fetch_page(self, url: str) -> str:
        # Try direct curl_cffi first
        if self._web:
            self._log(f"GET {url} (direct)")
            t0 = time.monotonic()
            resp = self._web.get(url, timeout=30)
            elapsed = time.monotonic() - t0
            self._log(f"Response: {resp.status_code} ({elapsed:.1f}s)")

            if resp.status_code == 200:
                return resp.text

            if resp.status_code == 401:
                raise AuthenticationError("Session expired (401). Run: allegro login")

            if resp.status_code == 403:
                raise AllegroCliError(
                    message="Forbidden (403) - DataDome challenge",
                    code="ForbiddenException",
                    userMessage="Access denied by Allegro's anti-bot system. Please refresh your cookies using 'allegro login'.",
                )

            raise AllegroCliError(
                message=f"Scrape returned {resp.status_code}: {resp.text[:300]}",
                code="ScrapeException",
                userMessage=f"Could not fetch search page ({resp.status_code}).",
            )
        
        raise AllegroCliError(
            message="Web client not initialized",
            code="ClientError",
            userMessage="Internal error: Web client is not available.",
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
            print(f"DEBUG: {method} {path} -> {resp.status_code}")
            print(f"DEBUG Response: {resp.text}")
        if resp.status_code == 401:
            raise AuthenticationError(
                "Session expired (401). Run: allegro login"
            )
        if resp.status_code == 403:
            raise AllegroCliError(
                message="Forbidden (403)",
                code="ForbiddenException",
                userMessage="Access denied. Your session cookies may have expired.",
            )
        if resp.status_code >= 400 and resp.status_code != 204:
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
