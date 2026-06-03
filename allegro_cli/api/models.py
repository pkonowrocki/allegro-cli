from __future__ import annotations

from dataclasses import dataclass, field


# --- Data models (Allegro REST API conventions) ---

@dataclass
class Price:
    amount: str
    currency: str = "PLN"


@dataclass
class Seller:
    id: str
    name: str


@dataclass
class Category:
    id: str
    name: str | None = None


@dataclass
class Image:
    url: str


@dataclass
class SellingMode:
    format: str  # BUY_NOW, AUCTION, ADVERTISEMENT
    price: Price
    popularity: int | None = None


@dataclass
class DeliveryInfo:
    lowestPrice: Price | None = None
    availableForFree: bool = False


@dataclass
class Stock:
    unit: str = "UNIT"
    available: int = 0


@dataclass
class Offer:
    id: str
    name: str
    seller: Seller
    sellingMode: SellingMode
    category: Category
    images: list[Image] = field(default_factory=list)
    delivery: DeliveryInfo | None = None
    stock: Stock | None = None
    parameters: dict[str, str] = field(default_factory=dict)


# --- Exceptions ---

class AllegroCliError(Exception):
    def __init__(
        self,
        message: str,
        code: str,
        path: str | None = None,
        userMessage: str | None = None,
    ):
        self.message = message
        self.code = code
        self.path = path
        self.userMessage = userMessage or message
        super().__init__(message)


class AuthenticationError(AllegroCliError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AuthenticationException",
            userMessage="Authentication failed. Please refresh your session cookies using 'allegro login'.",
        )


class OfferNotFoundError(AllegroCliError):
    def __init__(self, offer_id: str):
        super().__init__(
            message=f"Offer {offer_id} not found",
            code="OfferNotFoundException",
            userMessage=f"The offer {offer_id} was not found. It might have been deleted or is no longer available.",
        )


class RateLimitError(AllegroCliError):
    def __init__(self, message: str = "Rate limit exceeded", userMessage: str | None = None):
        super().__init__(
            message=message,
            code="RateLimitException",
            userMessage=userMessage or "Allegro is temporarily blocking requests. Please wait a few minutes and try again.",
        )


class ScraperError(AllegroCliError):
    def __init__(self, message: str, path: str | None = None):
        super().__init__(
            message=message,
            code="ScraperException",
            path=path,
            userMessage="The website structure has changed, and the scraper can no longer find the required information.",
        )


class CartError(AllegroCliError):
    def __init__(self, message: str, code: str = "CartException"):
        super().__init__(
            message=message,
            code=code,
            userMessage=f"Shopping cart error: {message}",
        )


