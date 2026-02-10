from __future__ import annotations

import dataclasses

from allegro_cli.config import load_config, save_config
from allegro_cli.output import output_json


def _mask_secret(value: str | None) -> str | None:
    if not value or len(value) <= 40:
        return value
    return value[:20] + "..." + value[-10:]


def handle_config_show(args) -> int:
    config = load_config()
    data = dataclasses.asdict(config)
    data["cookies"] = _mask_secret(data.get("cookies"))

    if args.format == "json":
        output_json(data)
    else:
        for key, val in data.items():
            print(f"{key}: {val}")
    return 0


def handle_config_set(args) -> int:
    config = load_config()
    if args.cookies is not None:
        config.cookies = args.cookies
    if args.edge_base_url is not None:
        config.edgeBaseUrl = args.edge_base_url
    if args.output_format is not None:
        config.outputFormat = args.output_format
    if getattr(args, "flaresolverr_url", None) is not None:
        config.flareSolverrUrl = args.flaresolverr_url
    save_config(config)
    output_json({"status": "ok", "message": "Configuration updated"})
    return 0
