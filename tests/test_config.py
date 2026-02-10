import json
from pathlib import Path

from allegro_cli.config import Config, load_config, save_config


def test_load_default_config(tmp_path: Path):
    config = load_config(tmp_path / "nonexistent.json")
    assert config.cookies is None
    assert config.edgeBaseUrl == "https://edge.allegro.pl"
    assert config.outputFormat == "text"
    assert config.flareSolverrUrl is None


def test_save_and_load_config(tmp_path: Path):
    path = tmp_path / "config.json"
    config = Config(cookies="session=abc123")
    save_config(config, path)

    loaded = load_config(path)
    assert loaded.cookies == "session=abc123"
    assert loaded.edgeBaseUrl == "https://edge.allegro.pl"


def test_config_json_uses_camel_case(tmp_path: Path):
    path = tmp_path / "config.json"
    save_config(Config(cookies="x"), path)
    raw = json.loads(path.read_text())
    assert "edgeBaseUrl" in raw
    assert "edge_base_url" not in raw
    assert "outputFormat" in raw
    assert "flareSolverrUrl" in raw
