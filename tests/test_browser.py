import pytest

from notebooklm_cdp_cli.browser import BrowserInspector
from notebooklm_cdp_cli.config import Settings


@pytest.mark.anyio
async def test_browser_inspector_reports_notebooklm_targets():
    settings = Settings()
    inspector = BrowserInspector(settings)

    async def fake_get_json(path):
        if path == "/json/version":
            return {
                "Browser": "Chrome/134.0.0.0",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/abc",
            }
        if path == "/json/list":
            return [
                {"id": "1", "url": "https://notebooklm.google.com/notebook/abc"},
                {"id": "2", "url": "https://gemini.google.com/app"},
                {"id": "3", "url": "https://accounts.google.com/RotateCookiesPage"},
            ]
        raise AssertionError(path)

    inspector._get_json = fake_get_json

    status = await inspector.status()

    assert status.connected is True
    assert status.browser == "Chrome/134.0.0.0"
    assert status.web_socket_url == "ws://127.0.0.1:9222/devtools/browser/abc"
    assert status.notebooklm_targets == 1
    assert status.google_targets == 3


@pytest.mark.anyio
async def test_browser_inspector_handles_unreachable_cdp():
    settings = Settings()
    inspector = BrowserInspector(settings)

    async def fake_get_json(path):
        raise RuntimeError("connection refused")

    inspector._get_json = fake_get_json

    status = await inspector.status()

    assert status.connected is False
    assert "connection refused" in status.error

