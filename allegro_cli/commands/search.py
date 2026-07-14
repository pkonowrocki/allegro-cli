from __future__ import annotations

import dataclasses

from allegro_cli.api.client import AllegroClient
from allegro_cli.commands import _DEFAULT_COLUMNS
from allegro_cli.output import output_json, output_text, output_tsv


def _get_columns(args) -> list[str]:
    raw = getattr(args, "columns", None)
    if raw:
        return [c.strip() for c in raw.split(",") if c.strip()]
    return _DEFAULT_COLUMNS.split(",")


def _compact_offer(offer) -> dict:
    """Strip Offer down to the absolute essentials for LLM token efficiency."""
    return {
        "id": offer.id,
        "name": offer.name,
        "price": offer.sellingMode.price.amount,
        "seller": offer.seller.name,
        "url": offer.url,
        "smart": offer.delivery.availableForFree if offer.delivery else False,
    }


def handle_search(args, client: AllegroClient) -> int:
    result = client.scrape_search(
        phrase=args.phrase,
        page=args.page,
        category=args.category,
        sort=args.sort,
        price_min=args.price_min,
        price_max=args.price_max,
        seller=args.seller,
        condition=args.condition,
        smart=args.smart or args.free_shipping,
        delivery_time=args.delivery_time,
        location=args.location,
        pay=args.pay,
        filters=args.filter,
    )

    if args.format == "json":
        if getattr(args, "compact", False):
            data = {
                "offers": [_compact_offer(o) for o in result.offers],
                "page": result.page,
                "hasNextPage": result.hasNextPage,
            }
        else:
            data = {
                "offers": [dataclasses.asdict(o) for o in result.offers],
                "page": result.page,
                "hasNextPage": result.hasNextPage,
                "nextPageUrl": result.nextPageUrl,
            }
        output_json(data)
    else:
        rows = [dataclasses.asdict(o) for o in result.offers]
        columns = _get_columns(args)
        if args.format == "tsv":
            output_tsv(rows, columns=columns)
        else:
            output_text(rows, columns=columns)
    return 0


def handle_offer(args, client: AllegroClient) -> int:
    offer = client.scrape_offer(args.offer_id)

    if args.format == "json":
        if getattr(args, "compact", False):
            output_json({
                "id": offer.id,
                "name": offer.name,
                "price": offer.sellingMode.price.amount,
                "seller": offer.seller.name,
                "url": offer.url,
                "smart": offer.delivery.availableForFree if offer.delivery else False,
                "parameters": offer.parameters,
            })
        else:
            output_json(offer)
    else:
        rows = [dataclasses.asdict(offer)]
        columns = _get_columns(args)
        if args.format == "tsv":
            output_tsv(rows, columns=columns)
        else:
            output_text(rows, columns=columns)
    return 0
