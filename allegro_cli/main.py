from __future__ import annotations

import argparse
import sys

from allegro_cli.api.models import AllegroCliError, AuthenticationError
from allegro_cli.config import ensure_dirs, load_config
from allegro_cli.output import make_error, output_error

_DEFAULT_COLUMNS = "id,name,sellingMode.price.amount,seller.name"


def create_parser() -> argparse.ArgumentParser:
    from allegro_cli import __version__

    # Shared flags that every subcommand inherits
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--format",
        choices=["text", "json", "tsv"],
        default=None,
        help="Output format (default: text)",
    )
    common.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Show progress and debug info on stderr",
    )

    parser = argparse.ArgumentParser(
        prog="allegro",
        description="Allegro CLI - search, browse, and manage cart (LLM-agent friendly)",
        parents=[common],
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- search (scrape-based, cookie auth) ---
    sp_search = sub.add_parser(
        "search", parents=[common],
        help="Search offers (cookie auth, scrape)",
    )
    sp_search.add_argument("phrase", help="Search phrase")
    sp_search.add_argument("--page", type=int, default=1, help="Page number (default: 1)")
    sp_search.add_argument(
        "--category", default=None,
        help="Category ID or slug (e.g. 491, laptopy-491)",
    )
    sp_search.add_argument(
        "--sort", default=None,
        help="Sort: p (price asc), pd (price desc), m (relevance), n (newest)",
    )
    sp_search.add_argument(
        "--price-min", dest="price_min", default=None,
        help="Minimum price in PLN",
    )
    sp_search.add_argument(
        "--price-max", dest="price_max", default=None,
        help="Maximum price in PLN",
    )
    sp_search.add_argument(
        "--seller", default=None,
        help="Seller login (searches on seller's page, e.g. Muvepl)",
    )
    sp_search.add_argument(
        "--columns", default=None,
        help=f"Comma-separated columns (default: {_DEFAULT_COLUMNS})",
    )

    # --- offer ---
    sp_offer = sub.add_parser(
        "offer", parents=[common],
        help="Get offer details by ID",
    )
    sp_offer.add_argument("offer_id", help="Offer ID")
    sp_offer.add_argument(
        "--columns", default=None,
        help=f"Comma-separated columns (default: {_DEFAULT_COLUMNS})",
    )

    # --- cart ---
    sp_cart = sub.add_parser("cart", parents=[common], help="Manage shopping cart")
    cart_sub = sp_cart.add_subparsers(dest="cart_action", required=True)

    cart_sub.add_parser("list", parents=[common], help="List cart contents")

    sp_add = cart_sub.add_parser("add", parents=[common], help="Add item to cart (increase quantity)")
    sp_add.add_argument("offer_id", help="Offer ID")
    sp_add.add_argument("seller_id", nargs="?", default=None, help="Seller ID (optional, fetched if missing)")
    sp_add.add_argument("--quantity", type=int, default=1, help="Quantity to add")
    sp_add.add_argument("--category", help="Navigation category ID")

    sp_remove = cart_sub.add_parser("remove", parents=[common], help="Remove item from cart (decrease quantity)")
    sp_remove.add_argument("offer_id", help="Offer ID")
    sp_remove.add_argument("seller_id", nargs="?", default=None, help="Seller ID (optional, fetched if missing)")
    sp_remove.add_argument("--quantity", type=int, default=1, help="Quantity to remove")

    # --- packages ---
    sub.add_parser("packages", parents=[common], help="Show packages/delivery summary")

    # --- login ---
    sub.add_parser("login", parents=[common], help="Import browser cookies (paste from Chrome DevTools)")

    # --- config ---
    sp_config = sub.add_parser("config", parents=[common], help="Manage configuration")
    config_sub = sp_config.add_subparsers(dest="config_action", required=True)

    config_sub.add_parser("show", parents=[common], help="Show current configuration")

    sp_set = config_sub.add_parser("set", parents=[common], help="Update configuration")
    sp_set.add_argument("--cookies", help="Browser cookie string from Chrome DevTools")
    sp_set.add_argument("--edge-base-url", dest="edge_base_url")
    sp_set.add_argument("--output-format", dest="output_format", choices=["text", "json", "tsv"])
    sp_set.add_argument(
        "--flaresolverr-url", dest="flaresolverr_url",
        help="FlareSolverr URL (e.g. http://localhost:8191/v1)",
    )

    return parser


def main() -> int:
    ensure_dirs()
    parser = create_parser()
    args = parser.parse_args()

    config = load_config()
    args.format = args.format or config.outputFormat or "text"

    try:
        if args.command == "login":
            from allegro_cli.commands.login import handle_login
            return handle_login(args)

        if args.command == "config":
            from allegro_cli.commands.config_cmd import (
                handle_config_set,
                handle_config_show,
            )
            match args.config_action:
                case "show":
                    return handle_config_show(args)
                case "set":
                    return handle_config_set(args)

        # Commands that need the API client
        from allegro_cli.api.client import AllegroClient
        client = AllegroClient(config, verbose=args.verbose)

        match args.command:
            case "search":
                from allegro_cli.commands.search import handle_search
                return handle_search(args, client)
            case "offer":
                from allegro_cli.commands.search import handle_offer
                return handle_offer(args, client)
            case "cart":
                from allegro_cli.commands.cart import (
                    handle_cart_list,
                    handle_cart_add,
                    handle_cart_remove,
                )
                match args.cart_action:
                    case "list":
                        return handle_cart_list(args, client)
                    case "add":
                        return handle_cart_add(args, client)
                    case "remove":
                        return handle_cart_remove(args, client)
            case "packages":
                from allegro_cli.commands.packages import handle_packages_summary
                return handle_packages_summary(args, client)

    except AuthenticationError as exc:
        output_error([make_error(
            message=exc.message,
            code=exc.code,
            userMessage=exc.userMessage,
        )])
        return 2

    except AllegroCliError as exc:
        output_error([make_error(
            message=exc.message,
            code=exc.code,
            path=exc.path,
            userMessage=exc.userMessage,
        )])
        return 1

    except Exception as exc:
        output_error([make_error(
            message=str(exc),
            code=type(exc).__name__,
            userMessage="An unexpected error occurred.",
        )])
        return 1

    return 0


def cli() -> None:
    sys.exit(main())


if __name__ == "__main__":
    cli()
