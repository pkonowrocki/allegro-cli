from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from dataclasses import dataclass

from allegro_cli.api.client import AllegroClient
from allegro_cli.config import Config

@dataclass
class MockResponse:
    status_code: int
    text: str
    json_data: Any = None

    def json(self) -> Any:
        return self.json_data or json.loads(self.text)

class MockAllegroClient(AllegroClient):
    """
    A version of AllegroClient that reads responses from local JSON fixtures
    instead of making real network requests.
    """
    def __init__(self, config: Config, fixtures_path: str = "tests/fixtures"):
        super().__init__(config)
        self.fixtures_path = Path(fixtures_path)

    def _request(
        self,
        method: str,
        path: str,
        accept: str = "application/vnd.allegro.internal.v1+json",
        content_type: str | None = None,
        **kwargs,
    ) -> MockResponse:
        # Normalize path for lookup (remove query params)
        clean_path = path.split("?")[0]
        # Replace / with _ and remove leading / for filename
        filename = f"{method.lower()}_{clean_path.strip('/').replace('/', '_')}.json"
        fixture_file = self.fixtures_path / filename

        if not fixture_file.exists():
            # Fallback: return 404
            return MockResponse(status_code=404, text="Not Found")

        with open(fixture_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return MockResponse(
            status_code=data.get("status_code", 200),
            text=json.dumps(data.get("body", {}), ensure_ascii=False),
            json_data=data.get("body")
        )

    def _fetch_page(self, url: str) -> str:
        # Mimic the behavior of _request but for the web client
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path
        
        # We use the same fixture logic as _request
        resp = self._request("GET", path)
        return resp.text
