from __future__ import annotations

from allegro_cli.api.client import AllegroClient
from allegro_cli.output import output_json, output_tsv


def handle_packages_summary(args, client: AllegroClient) -> int:
    summary = client.get_packages_summary()

    if args.format == "json":
        output_json(summary)
    elif args.format == "tsv":
        columns = ["total", "parcelsForPickup"]
        rows = [{"total": str(summary.get("total", 0)),
                 "parcelsForPickup": str(summary.get("parcelsForPickup", 0))}]
        output_tsv(rows, columns)
    else:
        total = summary.get("total", 0)
        pickup = summary.get("parcelsForPickup", 0)
        msg = summary.get("message")
        print(f"Total packages:    {total}")
        print(f"Ready for pickup:  {pickup}")
        if msg:
            print(f"Message:           {msg}")
    return 0
