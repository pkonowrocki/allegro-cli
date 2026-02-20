import json
from unittest.mock import patch, MagicMock

from allegro_cli.main import create_parser, main
from allegro_cli.api.models import (
    Offer, Seller, SellingMode, Price, Category,
)


def _make_offer(id="abc-123", name="Test Offer", amount="99.00"):
    return Offer(
        id=id,
        name=name,
        seller=Seller(id="seller-1", name="testshop"),
        sellingMode=SellingMode(format="BUY_NOW", price=Price(amount=amount)),
        category=Category(id="cat-1"),
    )


def test_parser_search():
    parser = create_parser()
    args = parser.parse_args(["search", "laptop"])
    assert args.command == "search"
    assert args.phrase == "laptop"
    assert args.page == 1


def test_parser_search_with_page():
    parser = create_parser()
    args = parser.parse_args(["search", "laptop", "--page", "3"])
    assert args.command == "search"
    assert args.phrase == "laptop"
    assert args.page == 3


def test_parser_search_with_flags_after():
    """Flags like --format work after the subcommand."""
    parser = create_parser()
    args = parser.parse_args(["search", "laptop", "--format", "tsv", "--page", "2"])
    assert args.command == "search"
    assert args.phrase == "laptop"
    assert args.format == "tsv"
    assert args.page == 2


def test_parser_search_custom_columns():
    parser = create_parser()
    args = parser.parse_args(["search", "laptop", "--columns", "id,name,sellingMode.price.amount"])
    assert args.columns == "id,name,sellingMode.price.amount"


def test_parser_search_with_category():
    parser = create_parser()
    args = parser.parse_args(["search", "laptop", "--category", "491"])
    assert args.category == "491"


def test_parser_search_with_sort():
    parser = create_parser()
    args = parser.parse_args(["search", "laptop", "--sort", "pd"])
    assert args.sort == "pd"


def test_parser_search_with_price_range():
    parser = create_parser()
    args = parser.parse_args(["search", "laptop", "--price-min", "1000", "--price-max", "5000"])
    assert args.price_min == "1000"
    assert args.price_max == "5000"


def test_parser_search_all_filters():
    parser = create_parser()
    args = parser.parse_args([
        "search", "laptop",
        "--category", "laptopy-491",
        "--sort", "p",
        "--price-min", "500",
        "--price-max", "3000",
        "--page", "2",
    ])
    assert args.category == "laptopy-491"
    assert args.sort == "p"
    assert args.price_min == "500"
    assert args.price_max == "3000"
    assert args.page == 2


def test_parser_search_with_seller():
    parser = create_parser()
    args = parser.parse_args(["search", "minecraft", "--seller", "Muvepl"])
    assert args.seller == "Muvepl"


def test_parser_search_all_filters_with_seller():
    parser = create_parser()
    args = parser.parse_args([
        "search", "laptop",
        "--seller", "Muvepl",
        "--sort", "p",
        "--price-min", "500",
        "--price-max", "3000",
        "--page", "2",
    ])
    assert args.seller == "Muvepl"
    assert args.sort == "p"
    assert args.price_min == "500"
    assert args.price_max == "3000"
    assert args.page == 2


def test_parser_offer():
    parser = create_parser()
    args = parser.parse_args(["offer", "some-id"])
    assert args.command == "offer"
    assert args.offer_id == "some-id"


def test_parser_offer_with_format():
    parser = create_parser()
    args = parser.parse_args(["offer", "12345", "--format", "json"])
    assert args.command == "offer"
    assert args.format == "json"


def test_parser_login():
    parser = create_parser()
    args = parser.parse_args(["login"])
    assert args.command == "login"


def test_parser_config_show():
    parser = create_parser()
    args = parser.parse_args(["config", "show"])
    assert args.command == "config"
    assert args.config_action == "show"


def test_parser_config_set_cookies():
    parser = create_parser()
    args = parser.parse_args(["config", "set", "--cookies", "session=abc"])
    assert args.command == "config"
    assert args.config_action == "set"
    assert args.cookies == "session=abc"


def test_parser_cart_list():
    parser = create_parser()
    args = parser.parse_args(["cart", "list"])
    assert args.command == "cart"
    assert args.cart_action == "list"


def test_parser_cart_add():
    parser = create_parser()
    args = parser.parse_args(["cart", "add", "offer123", "seller456", "--quantity", "2"])
    assert args.offer_id == "offer123"
    assert args.seller_id == "seller456"
    assert args.quantity == 2


def test_parser_packages():
    parser = create_parser()
    args = parser.parse_args(["packages"])
    assert args.command == "packages"


def test_search_command_outputs_json(capsys):
    mock_client = MagicMock()
    mock_client.scrape_search.return_value = [_make_offer()]

    with (
        patch("allegro_cli.main.load_config") as mock_load,
        patch("allegro_cli.main.ensure_dirs"),
        patch("allegro_cli.api.client.AllegroClient", return_value=mock_client),
        patch("sys.argv", ["allegro", "search", "laptop", "--format", "json"]),
    ):
        mock_load.return_value = MagicMock(
            cookies="session=x",
            edgeBaseUrl="https://edge.allegro.pl",
            outputFormat="text",
            flareSolverrUrl=None,
        )
        result = main()

    assert result == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "Test Offer"


def test_config_show_masks_cookies(capsys):
    from allegro_cli.config import Config

    long_cookie = "a" * 50

    with (
        patch("allegro_cli.main.load_config") as mock_load,
        patch("allegro_cli.commands.config_cmd.load_config") as mock_cmd_load,
        patch("allegro_cli.main.ensure_dirs"),
        patch("sys.argv", ["allegro", "config", "show", "--format", "json"]),
    ):
        cfg = Config(cookies=long_cookie)
        mock_load.return_value = cfg
        mock_cmd_load.return_value = cfg
        result = main()

    assert result == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    # Cookie should be masked
    assert data["cookies"] != long_cookie
    assert "..." in data["cookies"]


def test_missing_cookies_returns_auth_error_for_cart(capsys):
    from allegro_cli.config import Config

    with (
        patch("allegro_cli.main.load_config") as mock_load,
        patch("allegro_cli.main.ensure_dirs"),
        patch("sys.argv", ["allegro", "cart", "list"]),
    ):
        mock_load.return_value = Config(cookies=None)
        result = main()

    assert result == 2
    captured = capsys.readouterr()
    data = json.loads(captured.err)
    assert data["errors"][0]["code"] == "AuthenticationException"


def test_missing_cookies_returns_auth_error_for_search(capsys):
    from allegro_cli.config import Config

    with (
        patch("allegro_cli.main.load_config") as mock_load,
        patch("allegro_cli.main.ensure_dirs"),
        patch("sys.argv", ["allegro", "search", "laptop"]),
    ):
        mock_load.return_value = Config(cookies=None)
        result = main()

    assert result == 2
    captured = capsys.readouterr()
    data = json.loads(captured.err)
    assert data["errors"][0]["code"] == "AuthenticationException"
