from __future__ import annotations

from allegro_cli.api.client import AllegroClient
from allegro_cli.output import output_json, output_text, output_tsv

_CART_COLUMNS = [
    "selected",
    "offer_id",
    "name",
    "seller",
    "qty",
    "unit_price",
    "currency",
    "total",
]


def _flatten_cart_items(cart: dict) -> list[dict]:
    """Flatten nested cart groups/items into flat rows for table display."""
    rows = []
    for group in cart.get("cart", {}).get("groups", []):
        seller = group.get("seller", {}).get("login", "")
        for item in group.get("items", []):
            offers = item.get("offers", [])
            offer = offers[0] if offers else {}
            unit_price = item.get("unitPrice", {})
            qty_val = item.get("quantity")
            if isinstance(qty_val, dict):
                qty = str(qty_val.get("selected", ""))
            else:
                qty = str(qty_val) if qty_val is not None else ""
            rows.append(
                {
                    "selected": "yes" if item.get("selected") else "no",
                    "offer_id": offer.get("id", ""),
                    "name": offer.get("name", ""),
                    "seller": seller,
                    "qty": qty,
                    "unit_price": unit_price.get("amount", ""),
                    "currency": unit_price.get("currency", "PLN"),
                    "total": item.get("price", {}).get("amount", ""),
                }
            )
    return rows


def _output_cart(cart: dict, fmt: str) -> None:
    if fmt == "json":
        output_json(cart)
        return

    rows = _flatten_cart_items(cart)
    if fmt == "tsv":
        output_tsv(rows, _CART_COLUMNS)
    else:
        output_text(rows, _CART_COLUMNS)
        total = cart.get("cart", {}).get("prices", {}).get("total", {})
        if total:
            print(f"\nTotal: {total.get('amount', '?')} {total.get('currency', 'PLN')}")


def handle_cart_list(args, client: AllegroClient) -> int:
    cart = client.get_cart()
    _output_cart(cart, args.format)
    return 0


def handle_cart_add(args, client: AllegroClient) -> int:
    seller_id = args.seller_id
    category_id = getattr(args, "category", None)

    if not seller_id:
        # If seller_id is missing, fetch offer details to find it
        offer = client.scrape_offer(args.offer_id)
        seller_id = offer.seller.id
        if not category_id:
            category_id = offer.category.id

    client.change_cart_quantity(
        item_id=args.offer_id,
        delta=args.quantity,
        seller_id=seller_id,
        nav_category_id=category_id,
    )
    cart = client.get_cart()
    _output_cart(cart, args.format)
    return 0


def handle_cart_remove(args, client: AllegroClient) -> int:
    seller_id = args.seller_id
    if not seller_id:
        # Try to find seller_id in the cart
        cart = client.get_cart()
        for group in cart.get("cart", {}).get("groups", []):
            for item in group.get("items", []):
                for offer in item.get("offers", []):
                    if offer.get("id") == args.offer_id:
                        seller_id = group.get("seller", {}).get("id")
                        break
                if seller_id:
                    break
            if seller_id:
                break

        if not seller_id:
            # Fallback to scrape if not in cart (though remove implies it's in cart)
            offer = client.scrape_offer(args.offer_id)
            seller_id = offer.seller.id

    client.change_cart_quantity(
        item_id=args.offer_id,
        delta=-args.quantity,
        seller_id=seller_id,
    )
    cart = client.get_cart()
    _output_cart(cart, args.format)
    return 0
