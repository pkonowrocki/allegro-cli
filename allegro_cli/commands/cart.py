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
    if not isinstance(cart, dict):
        return []
    
    rows = []
    cart_data = cart.get("cart", {})
    if not isinstance(cart_data, dict):
        return []
        
    groups = cart_data.get("groups", [])
    if not isinstance(groups, list):
        return []

    for group in groups:
        if not isinstance(group, dict):
            continue
        seller = group.get("seller", "")
        if isinstance(seller, dict):
            seller = seller.get("login", "")
        else:
            seller = str(seller) if seller else ""
        
        items = group.get("items", [])
        if not isinstance(items, list):
            continue
            
        for item in items:
            if not isinstance(item, dict):
                continue
            offers = item.get("offers", [])
            if not isinstance(offers, list) or not offers:
                continue
            offer = offers[0]
            if not isinstance(offer, dict):
                offer = {}
                
            unit_price_val = item.get("unitPrice")
            if isinstance(unit_price_val, dict):
                unit_price_amount = unit_price_val.get("amount", "")
                unit_price_currency = unit_price_val.get("currency", "PLN")
            else:
                unit_price_amount = str(unit_price_val) if unit_price_val else ""
                unit_price_currency = "PLN"
                
            qty_val = item.get("quantity")
            if isinstance(qty_val, dict):
                qty = str(qty_val.get("selected", ""))
            else:
                qty = str(qty_val) if qty_val is not None else ""
                
            price_val = item.get("price")
            if isinstance(price_val, dict):
                total_amount = price_val.get("amount", "")
            else:
                total_amount = str(price_val) if price_val else ""
                
            selected_val = item.get("selected")
            if isinstance(selected_val, bool):
                selected = "yes" if selected_val else "no"
            else:
                selected = str(selected_val) if selected_val else "no"
                
            rows.append(
                {
                    "selected": selected,
                    "offer_id": offer.get("id", "") if isinstance(offer, dict) else "",
                    "name": offer.get("name", "") if isinstance(offer, dict) else "",
                    "seller": seller,
                    "qty": qty,
                    "unit_price": unit_price_amount,
                    "currency": unit_price_currency,
                    "total": total_amount,
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
        total = cart.get("cart", {}).get("prices", {})
        if isinstance(total, dict):
            total_amount = total.get("amount", "?")
            total_currency = total.get("currency", "PLN")
        else:
            total_amount = str(total) if total else "?"
            total_currency = "PLN"
        if total_amount and total_amount != "?":
            print(f"\nTotal: {total_amount} {total_currency}")


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
def handle_cart_remove(args, client: AllegroClient) -> int:
    # 1. Find the unique item_id (UUID) for the given offer_id in the cart
    item_id_to_remove = None
    
    try:
        cart = client.get_cart()
    except Exception:
        print("Error: Could not fetch cart.")
        return 1

    if not isinstance(cart, dict):
        print(f"Error: Expected dict from get_cart, got {type(cart)}")
        return 1

    cart_data = cart.get("cart")
    if not isinstance(cart_data, dict):
        print("Error: Cart data missing or invalid.")
        return 1
        
    groups = cart_data.get("groups", [])
    if not isinstance(groups, list):
        print("Error: Cart groups missing or invalid.")
        return 1
    
    for group in groups:
        if not isinstance(group, dict):
            continue
        items = group.get("items", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            offers = item.get("offers", [])
            if not isinstance(offers, list):
                continue
            for offer in offers:
                if isinstance(offer, dict) and offer.get("id") == args.offer_id:
                    item_id_to_remove = item.get("id")
                    break
            if item_id_to_remove:
                break
        if item_id_to_remove:
            break

    if not item_id_to_remove:
        print(f"Error: Offer {args.offer_id} not found in cart.")
        return 1

    # 2. Use the new DELETE endpoint
    try:
        client.remove_cart_item(item_id_to_remove)
    except Exception as e:
        print(f"Error removing item: {e}")
        return 1
    
    cart = client.get_cart()
    _output_cart(cart, args.format)
    return 0
