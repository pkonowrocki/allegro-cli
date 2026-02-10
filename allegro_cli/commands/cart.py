from __future__ import annotations

from allegro_cli.api.client import AllegroClient
from allegro_cli.output import output_json, output_text, output_tsv

_CART_COLUMNS = ["selected", "offer_id", "name", "seller", "qty", "unit_price", "currency", "total"]


def _flatten_cart_items(cart: dict) -> list[dict]:
    """Flatten nested cart groups/items into flat rows for table display."""
    rows = []
    for group in cart.get("cart", {}).get("groups", []):
        seller = group.get("seller", {}).get("login", "")
        for item in group.get("items", []):
            offers = item.get("offers", [])
            offer = offers[0] if offers else {}
            unit_price = item.get("unitPrice", {})
            rows.append({
                "selected": "yes" if item.get("selected") else "no",
                "offer_id": offer.get("id", ""),
                "name": offer.get("name", ""),
                "seller": seller,
                "qty": str(item.get("quantity", {}).get("selected", "")),
                "unit_price": unit_price.get("amount", ""),
                "currency": unit_price.get("currency", "PLN"),
                "total": item.get("price", {}).get("amount", ""),
            })
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
    client.change_cart_quantity(
        item_id=args.offer_id,
        delta=args.quantity,
        seller_id=args.seller_id,
        nav_category_id=getattr(args, "category", None),
    )
    cart = client.get_cart()
    _output_cart(cart, args.format)
    return 0


def handle_cart_remove(args, client: AllegroClient) -> int:
    client.change_cart_quantity(
        item_id=args.offer_id,
        delta=-args.quantity,
        seller_id=args.seller_id,
    )
    cart = client.get_cart()
    _output_cart(cart, args.format)
    return 0
