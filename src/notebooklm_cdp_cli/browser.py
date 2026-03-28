from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
import websockets

from .config import Settings, default_user_data_dir_candidates
from .state import set_browser_config


@dataclass(slots=True)
class BrowserStatus:
    connected: bool
    browser: str | None
    web_socket_url: str | None
    notebooklm_targets: int
    google_targets: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BrowserInspector:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def _get_json(self, path: str) -> Any:
        async with httpx.AsyncClient(base_url=self.settings.base_url, timeout=self.settings.timeout) as client:
            response = await client.get(path)
            response.raise_for_status()
            return response.json()

    async def status(self) -> BrowserStatus:
        try:
            version = await self._get_json("/json/version")
            targets = await self._get_json("/json/list")
        except Exception as exc:
            return BrowserStatus(
                connected=False,
                browser=None,
                web_socket_url=None,
                notebooklm_targets=0,
                google_targets=0,
                error=str(exc),
            )

        notebooklm_targets = 0
        google_targets = 0
        for target in targets:
            url = str(target.get("url", ""))
            if "google.com" in url:
                google_targets += 1
            if "notebooklm.google.com" in url:
                notebooklm_targets += 1

        return BrowserStatus(
            connected=True,
            browser=version.get("Browser"),
            web_socket_url=version.get("webSocketDebuggerUrl"),
            notebooklm_targets=notebooklm_targets,
            google_targets=google_targets,
        )

    async def get_cookies(self) -> list[dict[str, Any]]:
        status = await self.status()
        if not status.connected or not status.web_socket_url:
            raise RuntimeError(status.error or "CDP browser is not connected")

        payload = {"id": 1, "method": "Storage.getCookies"}
        async with websockets.connect(status.web_socket_url) as websocket:
            await websocket.send(json.dumps(payload))
            raw_response = await websocket.recv()

        response = json.loads(raw_response)
        cookies = response.get("result", {}).get("cookies")
        if cookies is None:
            raise RuntimeError("CDP did not return cookies")
        return cookies


def read_devtools_active_port(user_data_dir: str) -> tuple[int, str | None]:
    path = Path(user_data_dir) / "DevToolsActivePort"
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise RuntimeError(f"DevToolsActivePort is empty: {path}")
    port = int(lines[0].strip())
    ws_path = lines[1].strip() if len(lines) > 1 else None
    return port, ws_path


def detect_browser_profile() -> dict[str, Any]:
    errors = []
    for user_data_dir in default_user_data_dir_candidates():
        path = Path(user_data_dir)
        if not path.exists():
            continue
        try:
            port, ws_path = read_devtools_active_port(user_data_dir)
            return {
                "host": "127.0.0.1",
                "port": port,
                "user_data_dir": user_data_dir,
                "web_socket_path": ws_path,
                "source": "DevToolsActivePort",
            }
        except Exception as exc:
            errors.append(f"{user_data_dir}: {exc}")

    raise RuntimeError("No Chrome DevToolsActivePort file was found in known profiles" if not errors else "; ".join(errors))


def attach_browser(
    user_data_dir: str | None,
    host: str | None,
    port: int | None,
) -> dict[str, Any]:
    if user_data_dir:
        detected_port, ws_path = read_devtools_active_port(user_data_dir)
        browser = {
            "host": host or "127.0.0.1",
            "port": port or detected_port,
            "user_data_dir": user_data_dir,
            "web_socket_path": ws_path,
            "source": "DevToolsActivePort",
        }
    elif port is not None:
        browser = {
            "host": host or "127.0.0.1",
            "port": port,
            "user_data_dir": None,
            "web_socket_path": None,
            "source": "manual",
        }
    else:
        browser = detect_browser_profile()
        if host:
            browser["host"] = host

    set_browser_config(browser)
    return browser
