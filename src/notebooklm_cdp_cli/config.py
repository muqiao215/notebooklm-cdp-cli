from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .state import get_browser_config


@dataclass(slots=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 9222
    timeout: float = 5.0
    user_data_dir: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        saved = get_browser_config()
        return cls(
            host=os.getenv("NOTEBOOKLM_CDP_HOST", saved.get("host", defaults.host)),
            port=int(os.getenv("NOTEBOOKLM_CDP_PORT", str(saved.get("port", defaults.port)))),
            timeout=float(os.getenv("NOTEBOOKLM_CDP_TIMEOUT", str(defaults.timeout))),
            user_data_dir=os.getenv(
                "NOTEBOOKLM_CDP_USER_DATA_DIR",
                saved.get("user_data_dir"),
            ),
        )

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


def default_user_data_dir_candidates() -> list[str]:
    candidates = []
    env_path = os.getenv("NOTEBOOKLM_CDP_USER_DATA_DIR")
    if env_path:
        candidates.append(env_path)
    candidates.extend(
        [
            "/root/.browser-login/google-chrome-user-data",
            str(Path.home() / ".config" / "google-chrome"),
            str(Path.home() / ".config" / "chromium"),
        ]
    )
    seen = set()
    unique = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique
