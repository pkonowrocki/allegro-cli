import pytest
from allegro_cli.api.client import AllegroClient
from allegro_cli.api.mock_client import MockAllegroClient
from allegro_cli.config import Config

def test_mock_client_packages():
    config = Config(cookies="mock_cookie")
    client = MockAllegroClient(config, fixtures_path="/tmp/allegro-cli-repo/tests/fixtures")
    
    # Test summary
    summary = client.get_packages_summary()
    assert summary["total"] == 2
    assert summary["parcelsForPickup"] == 1
    
    # Test list
    packages = client.get_packages_list()
    assert len(packages) == 1
    assert packages[0]["content"]["description"] == "Mock Item"
    assert packages[0]["delivery"]["waybill"] == "123"

def test_mock_client_404():
    config = Config(cookies="mock_cookie")
    client = MockAllegroClient(config, fixtures_path="/tmp/allegro-cli-repo/tests/fixtures")
    
    # Test non-existent fixture
    resp = client._request("GET", "/non-existent")
    assert resp.status_code == 404
