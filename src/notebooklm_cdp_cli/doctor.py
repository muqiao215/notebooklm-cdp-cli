from __future__ import annotations

from .auth import AuthService
from .browser import BrowserInspector
from .config import Settings


async def run_doctor(settings: Settings) -> dict:
    browser = await BrowserInspector(settings).status()
    auth = await AuthService(settings).status()
    return {
        "browser": browser.to_dict(),
        "auth": auth.to_dict(),
    }

