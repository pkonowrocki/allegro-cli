"""End-to-end tests exercising the full CLI pipeline with fixture HTML."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from allegro_cli.main import main

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_config():
    return MagicMock(
        cookies="session=test",
        edgeBaseUrl="https://edge.allegro.pl",
        outputFormat="text",
        flareSolverrUrl=None,
    )


def _run_cli(argv: list[str], fixture: str | None = None, capsys=None):
    """Run main() with patched config and optional fixture HTML."""
    if fixture:
        html = (FIXTURES / fixture).read_text(encoding="utf-8")
        with (
            patch("allegro_cli.main.load_config", return_value=_mock_config()),
            patch("allegro_cli.main.ensure_dirs"),
            patch("sys.argv", ["allegro"] + argv),
            patch("allegro_cli.api.client.AllegroClient._fetch_page", return_value=html),
        ):
            return main()
    else:
        with (
            patch("allegro_cli.main.load_config", return_value=_mock_config()),
            patch("allegro_cli.main.ensure_dirs"),
            patch("sys.argv", ["allegro"] + argv),
        ):
            return main()


# --- Search tests ---


def test_e2e_search_text(capsys):
    result = _run_cli(
        ["search", "laptop", "--format", "text"],
        fixture="search_results.html",
    )
    assert result == 0
    out = capsys.readouterr().out
    assert "Laptop Lenovo ThinkPad" in out
    assert "Laptop Dell XPS 15" in out
    # Should have header separator line
    assert "---" in out


def test_e2e_search_json(capsys):
    result = _run_cli(
        ["search", "laptop", "--format", "json"],
        fixture="search_results.html",
    )
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["name"] == "Laptop Lenovo ThinkPad"
    assert data[1]["name"] == "Laptop Dell XPS 15"
    assert data[0]["sellingMode"]["price"]["amount"] == "3499.00"


def test_e2e_search_tsv(capsys):
    result = _run_cli(
        ["search", "laptop", "--format", "tsv"],
        fixture="search_results.html",
    )
    assert result == 0
    out = capsys.readouterr().out
    lines = out.strip().split("\n")
    # First line is header
    assert "id" in lines[0]
    assert "name" in lines[0]
    assert "\t" in lines[0]
    assert len(lines) == 3  # header + 2 data rows


def test_e2e_search_custom_columns(capsys):
    result = _run_cli(
        ["search", "laptop", "--format", "tsv", "--columns", "id,name"],
        fixture="search_results.html",
    )
    assert result == 0
    out = capsys.readouterr().out
    lines = out.strip().split("\n")
    header_cols = lines[0].split("\t")
    assert header_cols == ["id", "name"]
    assert "12345678" in lines[1]


def test_e2e_search_with_category(capsys):
    """URL should contain /kategoria/-{id} when --category is numeric."""
    fetched_urls = []

    def capture_fetch(self, url):
        fetched_urls.append(url)
        return (FIXTURES / "search_results.html").read_text(encoding="utf-8")

    with (
        patch("allegro_cli.main.load_config", return_value=_mock_config()),
        patch("allegro_cli.main.ensure_dirs"),
        patch("sys.argv", ["allegro", "search", "laptop", "--category", "491", "--format", "json"]),
        patch("allegro_cli.api.client.AllegroClient._fetch_page", capture_fetch),
    ):
        result = main()

    assert result == 0
    assert len(fetched_urls) == 1
    assert "/kategoria/-491" in fetched_urls[0]


def test_e2e_search_with_slug_category(capsys):
    """--category laptopy-491 extracts numeric ID."""
    fetched_urls = []

    def capture_fetch(self, url):
        fetched_urls.append(url)
        return (FIXTURES / "search_results.html").read_text(encoding="utf-8")

    with (
        patch("allegro_cli.main.load_config", return_value=_mock_config()),
        patch("allegro_cli.main.ensure_dirs"),
        patch("sys.argv", ["allegro", "search", "laptop", "--category", "laptopy-491", "--format", "json"]),
        patch("allegro_cli.api.client.AllegroClient._fetch_page", capture_fetch),
    ):
        result = main()

    assert result == 0
    assert len(fetched_urls) == 1
    assert "/kategoria/-491" in fetched_urls[0]


def test_e2e_search_with_sort(capsys):
    """URL should contain order= param when --sort is set."""
    fetched_urls = []

    def capture_fetch(self, url):
        fetched_urls.append(url)
        return (FIXTURES / "search_results.html").read_text(encoding="utf-8")

    with (
        patch("allegro_cli.main.load_config", return_value=_mock_config()),
        patch("allegro_cli.main.ensure_dirs"),
        patch("sys.argv", ["allegro", "search", "laptop", "--sort", "pd", "--format", "json"]),
        patch("allegro_cli.api.client.AllegroClient._fetch_page", capture_fetch),
    ):
        result = main()

    assert result == 0
    assert "order=pd" in fetched_urls[0]


def test_e2e_search_with_price_range(capsys):
    """URL should contain price_from and price_to params."""
    fetched_urls = []

    def capture_fetch(self, url):
        fetched_urls.append(url)
        return (FIXTURES / "search_results.html").read_text(encoding="utf-8")

    with (
        patch("allegro_cli.main.load_config", return_value=_mock_config()),
        patch("allegro_cli.main.ensure_dirs"),
        patch("sys.argv", [
            "allegro", "search", "laptop",
            "--price-min", "1000", "--price-max", "5000",
            "--format", "json",
        ]),
        patch("allegro_cli.api.client.AllegroClient._fetch_page", capture_fetch),
    ):
        result = main()

    assert result == 0
    assert "price_from=1000" in fetched_urls[0]
    assert "price_to=5000" in fetched_urls[0]


# --- Offer tests ---


def test_e2e_offer_json(capsys):
    result = _run_cli(
        ["offer", "12345678", "--format", "json"],
        fixture="offer_page.html",
    )
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    assert data["id"] == "12345678"
    assert data["name"] == "Laptop Lenovo ThinkPad X1 Carbon Gen 11"
    assert data["sellingMode"]["price"]["amount"] == "4599.00"
    assert data["seller"]["id"] == "99999"
    assert len(data["images"]) == 1
    assert "parameters" in data


def test_e2e_offer_parameters(capsys):
    result = _run_cli(
        ["offer", "12345678", "--format", "json"],
        fixture="offer_page.html",
    )
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    params = data["parameters"]
    assert params["Procesor"] == "Intel Core i7-1365U"
    assert params["Pamięć RAM"] == "16 GB"
    assert params["Dysk"] == "512 GB SSD"
    assert params["Ekran"] == "14 cali"


# --- Empty / error tests ---


def test_e2e_search_empty(capsys):
    result = _run_cli(
        ["search", "nonexistent", "--format", "json"],
        fixture="search_empty.html",
    )
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    assert data == []


def test_e2e_search_empty_text(capsys):
    result = _run_cli(
        ["search", "nonexistent", "--format", "text"],
        fixture="search_empty.html",
    )
    assert result == 0
    out = capsys.readouterr().out
    assert "(no results)" in out


def test_e2e_missing_cookies(capsys):
    no_cookies_config = MagicMock(
        cookies=None,
        edgeBaseUrl="https://edge.allegro.pl",
        outputFormat="text",
        flareSolverrUrl=None,
    )

    with (
        patch("allegro_cli.main.load_config", return_value=no_cookies_config),
        patch("allegro_cli.main.ensure_dirs"),
        patch("sys.argv", ["allegro", "search", "laptop"]),
    ):
        result = main()

    assert result == 2
    err = capsys.readouterr().err
    data = json.loads(err)
    assert data["errors"][0]["code"] == "AuthenticationException"
