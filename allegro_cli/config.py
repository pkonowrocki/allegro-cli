from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

CONFIG_DIR = Path.home() / ".allegro-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    cookies: str | None = None
    edgeBaseUrl: str = "https://edge.allegro.pl"
    outputFormat: str = "text"
    flareSolverrUrl: str | None = None


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config(path: Path | None = None) -> Config:
    path = path or CONFIG_FILE
    if not path.exists():
        return Config()
    data = json.loads(path.read_text(encoding="utf-8"))
    return Config(
        cookies=data.get("cookies"),
        edgeBaseUrl=data.get("edgeBaseUrl", Config.edgeBaseUrl),
        outputFormat=data.get("outputFormat", Config.outputFormat),
        flareSolverrUrl=data.get("flareSolverrUrl"),
    )


def save_config(config: Config, path: Path | None = None) -> None:
    path = path or CONFIG_FILE
    ensure_dirs()
    path.write_text(
        json.dumps(asdict(config), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
