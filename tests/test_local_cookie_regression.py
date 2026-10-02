from unittest.mock import MagicMock, patch

from allegro_cli.api.client import AllegroClient
from allegro_cli.config import Config


def test_scrape_does_not_reuse_another_browsers_datadome_cookie():
    config = Config(cookies='QXLSESSID=test-session; datadome=test-browser-token')
    browser = MagicMock()
    client = AllegroClient(config)
    try:
        with patch('allegro_cli.api.client.launch', return_value=browser) as launch:
            client._ensure_browser()
        launch.assert_called_once_with(headless=True, locale='pl-PL')
        injected = browser.new_context.return_value.add_cookies.call_args.args[0]
        assert [cookie['name'] for cookie in injected] == ['QXLSESSID']
        assert client._edge.headers['cookie'] == config.cookies
        assert config.cookies == 'QXLSESSID=test-session; datadome=test-browser-token'
    finally:
        client.close()
