from __future__ import annotations

import dataclasses

from allegro_cli.api.client import AllegroClient
from allegro_cli.api.models import (
    CannotReorderException,
    Order,
    OrderNotFoundException,
    OrderOffer,
)
from allegro_cli.output import make_error, output_error, output_json, output_text, output_tsv


def _parse_order(myorder: dict) -> Order:
    offers = [
        OrderOffer(
            id=o["id"],
            title=o.get("title", ""),
            unitPrice=o.get("unitPrice", ""),
            quantity=o.get("quantity", 1),
            imageUrl=o.get("imageUrl"),
            traits=o.get("traits", []),
        )
        for o in myorder.get("offers", [])
    ]
    waybills = myorder.get("delivery", {}).get("waybillsData", [])
    waybill = waybills[0]["waybillNumber"] if waybills else None
    status_primary = myorder.get("status", {}).get("primary", "UNKNOWN")
    total = myorder.get("totalCost", {})
    total_str = f"{total.get('amount', '0')} {total.get('currency', 'PLN')}"
    raw_offers = myorder.get("offers", [])
    order_date = raw_offers[0].get("orderDate", "") if raw_offers else ""
    can_reorder = any("CAN_BUY_AGAIN" in o.traits for o in offers)
    return_status = status_primary if status_primary in ("RETURNED", "RETURN_IN_PROGRESS") else None
    return Order(
        id=myorder["id"],
        seller=myorder.get("seller", {}).get("login", ""),
        sellerId=myorder.get("seller", {}).get("id", ""),
        offers=offers,
        status=status_primary,
        totalCost=total_str,
        waybill=waybill,
        orderDate=order_date,
        canReorder=can_reorder,
        returnStatus=return_status,
    )


def _compact_order(order: Order) -> dict:
    return {
        "id": order.id,
        "seller": order.seller,
        "status": order.status,
        "totalCost": order.totalCost,
        "canReorder": order.canReorder,
        "waybill": order.waybill,
        "returnStatus": order.returnStatus,
    }


def handle_orders_list(args, client: AllegroClient) -> int:
    offset = (args.page - 1) * args.limit
    raw = client.get_orders(offset=offset, limit=args.limit)
    orders = [
        _parse_order(myorder)
        for group in raw.get("orderGroups", [])
        for myorder in group.get("myorders", [])
    ]

    if args.search:
        term = args.search.lower()
        orders = [o for o in orders if any(term in of.title.lower() for of in o.offers)]
    if args.status:
        orders = [o for o in orders if o.status == args.status.upper()]

    if args.format == "json":
        if args.compact:
            output_json({"orders": [_compact_order(o) for o in orders]})
        else:
            output_json({
                "orders": [dataclasses.asdict(o) for o in orders],
                "total": raw.get("total", len(orders)),
            })
    elif args.format == "tsv":
        output_tsv(
            [dataclasses.asdict(o) for o in orders],
            columns=["id", "seller", "status", "totalCost", "waybill"],
        )
    else:
        output_text(
            [dataclasses.asdict(o) for o in orders],
            columns=["id", "seller", "status", "totalCost", "waybill"],
        )
    return 0


def handle_orders_reorder(args, client: AllegroClient) -> int:
    raw = client.get_orders(offset=0, limit=50)
    all_orders = [
        _parse_order(myorder)
        for group in raw.get("orderGroups", [])
        for myorder in group.get("myorders", [])
    ]
    order = next((o for o in all_orders if o.id == args.order_id), None)
    if not order:
        output_error([make_error(
            f"Order {args.order_id} not found in recent 50 orders",
            code="OrderNotFoundException",
            userMessage=f"Order {args.order_id} was not found in recent orders.",
        )])
        return 1

    reorderable = [o for o in order.offers if "CAN_BUY_AGAIN" in o.traits]
    if not reorderable:
        output_error([make_error(
            f"No reorderable items in order {args.order_id}",
            code="CannotReorderException",
            userMessage=f"None of the items in order {args.order_id} can be reordered.",
        )])
        return 1

    for offer in reorderable:
        client.change_cart_quantity(offer.id, delta=offer.quantity, seller_id=order.sellerId)

    output_json({"reordered": len(reorderable), "orderId": order.id})
    return 0


def handle_orders_returns(args, client: AllegroClient) -> int:
    args.status = "RETURNED"
    return handle_orders_list(args, client)
