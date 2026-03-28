from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

import httpx
from notebooklm.auth import AuthTokens as NotebookLMAuthTokens

from .browser import BrowserInspector, BrowserStatus
from .config import Settings

TOKEN_PATTERNS = {
    "csrf_token": re.compile(r'"SNlM0e":"([^"]+)"'),
    "session_id": re.compile(r'"FdrFJe":"([^"]+)"'),
}

ALLOWED_COOKIE_DOMAINS = (
    ".google.com",
    "notebooklm.google.com",
    ".googleusercontent.com",
)


@dataclass(slots=True)
class TokenBundle:
    csrf_token: str
    session_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AuthStatus:
    ok: bool
    browser_connected: bool
    cookie_count: int
    has_sid_cookie: bool
    tokens: TokenBundle | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.tokens is None:
            data["tokens"] = None
        return data


class AuthService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.inspector = BrowserInspector(settings)

    async def browser_status(self) -> BrowserStatus:
        return await self.inspector.status()

    async def load_cookies(self) -> list[dict[str, Any]]:
        cookies = await self.inspector.get_cookies()
        return [cookie for cookie in cookies if self._is_allowed_cookie(cookie.get("domain", ""))]

    async def fetch_tokens(self, cookie_header: str) -> TokenBundle:
        headers = {"Cookie": cookie_header}
        async with httpx.AsyncClient(timeout=self.settings.timeout, follow_redirects=True) as client:
            response = await client.get("https://notebooklm.google.com/", headers=headers)
        response.raise_for_status()

        csrf_match = TOKEN_PATTERNS["csrf_token"].search(response.text)
        sid_match = TOKEN_PATTERNS["session_id"].search(response.text)
        if not csrf_match or not sid_match:
            raise RuntimeError("NotebookLM tokens were not found in the homepage response")

        return TokenBundle(
            csrf_token=csrf_match.group(1),
            session_id=sid_match.group(1),
        )

    async def status(self) -> AuthStatus:
        browser = await self.browser_status()
        if not browser.connected:
            return AuthStatus(
                ok=False,
                browser_connected=False,
                cookie_count=0,
                has_sid_cookie=False,
                tokens=None,
                error=browser.error,
            )

        try:
            cookies = await self.load_cookies()
            cookie_header = self._build_cookie_header(cookies)
            tokens = await self.fetch_tokens(cookie_header)
        except Exception as exc:
            cookies = locals().get("cookies", [])
            return AuthStatus(
                ok=False,
                browser_connected=True,
                cookie_count=len(cookies),
                has_sid_cookie=self._has_sid_cookie(cookies),
                tokens=None,
                error=str(exc),
            )

        return AuthStatus(
            ok=True,
            browser_connected=True,
            cookie_count=len(cookies),
            has_sid_cookie=self._has_sid_cookie(cookies),
            tokens=tokens,
        )

    async def notebooklm_auth(self) -> NotebookLMAuthTokens:
        cookies = await self.load_cookies()
        cookie_map = {
            cookie["name"]: cookie["value"]
            for cookie in cookies
            if "name" in cookie and "value" in cookie
        }
        tokens = await self.fetch_tokens(self._build_cookie_header(cookies))
        return NotebookLMAuthTokens(
            cookies=cookie_map,
            csrf_token=tokens.csrf_token,
            session_id=tokens.session_id,
        )

    @staticmethod
    def _has_sid_cookie(cookies: list[dict[str, Any]]) -> bool:
        return any(cookie.get("name") == "SID" for cookie in cookies)

    @staticmethod
    def _build_cookie_header(cookies: list[dict[str, Any]]) -> str:
        return "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in cookies if "name" in cookie and "value" in cookie)

    @staticmethod
    def _is_allowed_cookie(domain: str) -> bool:
        return domain in ALLOWED_COOKIE_DOMAINS
