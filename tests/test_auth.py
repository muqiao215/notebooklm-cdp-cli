import pytest

from notebooklm_cdp_cli.auth import AuthService, TokenBundle
from notebooklm_cdp_cli.browser import BrowserStatus
from notebooklm_cdp_cli.config import Settings


@pytest.mark.anyio
async def test_auth_status_reports_live_tokens():
    service = AuthService(Settings())

    async def fake_browser_status():
        return BrowserStatus(
            connected=True,
            browser="Chrome/134.0.0.0",
            web_socket_url="ws://127.0.0.1:9222/devtools/browser/abc",
            notebooklm_targets=1,
            google_targets=2,
        )

    async def fake_cookies():
        return [
            {"name": "SID", "value": "sid", "domain": ".google.com"},
            {"name": "HSID", "value": "hsid", "domain": ".google.com"},
        ]

    async def fake_tokens(cookie_header):
        assert "SID=sid" in cookie_header
        return TokenBundle(csrf_token="csrf123", session_id="sess456")

    service.browser_status = fake_browser_status
    service.load_cookies = fake_cookies
    service.fetch_tokens = fake_tokens

    status = await service.status()

    assert status.browser_connected is True
    assert status.cookie_count == 2
    assert status.has_sid_cookie is True
    assert status.tokens.csrf_token == "csrf123"
    assert status.tokens.session_id == "sess456"
    assert status.ok is True


@pytest.mark.anyio
async def test_auth_status_handles_missing_browser_connection():
    service = AuthService(Settings())

    async def fake_browser_status():
        return BrowserStatus(
            connected=False,
            browser=None,
            web_socket_url=None,
            notebooklm_targets=0,
            google_targets=0,
            error="refused",
        )

    service.browser_status = fake_browser_status

    status = await service.status()

    assert status.ok is False
    assert status.error == "refused"
    assert status.cookie_count == 0

