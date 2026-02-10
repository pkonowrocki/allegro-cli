from __future__ import annotations

import dataclasses

from allegro_cli.api.client import AllegroClient
from allegro_cli.main import _DEFAULT_COLUMNS
from allegro_cli.output import output_json, output_text, output_tsv


def _get_columns(args) -> list[str]:
    raw = getattr(args, "columns", None)
    if raw:
        return [c.strip() for c in raw.split(",") if c.strip()]
    return _DEFAULT_COLUMNS.split(",")


def handle_search(args, client: AllegroClient) -> int:
    offers = client.scrape_search(
        phrase=args.phrase,
        page=getattr(args, "page", 1),
        category=getattr(args, "category", None),
        sort=getattr(args, "sort", None),
        price_min=getattr(args, "price_min", None),
        price_max=getattr(args, "price_max", None),
    )

    if args.format == "json":
        output_json([dataclasses.asdict(o) for o in offers])
    else:
        rows = [dataclasses.asdict(o) for o in offers]
        columns = _get_columns(args)
        if args.format == "tsv":
            output_tsv(rows, columns=columns)
        else:
            output_text(rows, columns=columns)
    return 0


def handle_offer(args, client: AllegroClient) -> int:
    offer = client.scrape_offer(args.offer_id)

    if args.format == "json":
        output_json(offer)
    else:
        rows = [dataclasses.asdict(offer)]
        columns = _get_columns(args)
        if args.format == "tsv":
            output_tsv(rows, columns=columns)
        else:
            output_text(rows, columns=columns)
    return 0
