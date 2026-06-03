from __future__ import annotations

from allegro_cli.api.client import AllegroClient
from allegro_cli.output import output_json, output_tsv


def handle_packages_summary(args, client: AllegroClient) -> int:
    summary = client.get_packages_summary()
    packages = client.get_packages_list()

    if args.format == "json":
        return output_json({"summary": summary, "packages": packages})
    elif args.format == "tsv":
        # Summary as first row
        rows = [{"total": str(summary.get("total", 0)),
                 "parcelsForPickup": str(summary.get("parcelsForPickup", 0))}]
        # Detailed packages
        for p in packages:
            rows.append({
                "total": "---",
                "parcelsForPickup": f"{p['delivery']['waybill']} | {p['delivery']['status']}"
            })
        columns = ["total", "parcelsForPickup"]
        output_tsv(rows, columns)
    else:
        total = summary.get("total", 0)
        pickup = summary.get("parcelsForPickup", 0)
        print(f"Total packages:    {total}")
        print(f"Ready for pickup:  {pickup}")
        if summary.get("message"):
            print(f"Message:           {summary.get('message')}")
        
        if not packages:
            return 0
        
        print("\nDetailed Packages:")
        print("-" * 60)
        for p in packages:
            item = p.get("content", {}).get("description", "Unknown Item")
            carrier = p.get("delivery", {}).get("carrierId", "Unknown")
            waybill = p.get("delivery", {}).get("waybill", "N/A")
            status = p.get("delivery", {}).get("status", "Unknown")
            desc = p.get("delivery", {}).get("description", {})
            title = desc.get("title", "No status")
            subtitle = desc.get("subtitle", "")
            
            print(f"📦 {item}")
            print(f"   Carrier: {carrier} | Waybill: {waybill} | Status: {status}")
            print(f"   {title}")
            if subtitle:
                print(f"   {subtitle}")
            print("-" * 60)
    return 0
