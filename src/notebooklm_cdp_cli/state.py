from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def get_home_dir(create: bool = False) -> Path:
    path = Path(os.getenv("NOTEBOOKLM_CDP_HOME", "~/.notebooklm-cdp")).expanduser()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_path() -> Path:
    return get_home_dir() / "config.json"


def get_context_path() -> Path:
    return get_home_dir() / "context.json"


def load_config() -> dict[str, Any]:
    path = get_config_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(data: dict[str, Any]) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_browser_config() -> dict[str, Any]:
    return load_config().get("browser", {})


def set_browser_config(browser: dict[str, Any]) -> None:
    config = load_config()
    config["browser"] = browser
    save_config(config)


def load_context() -> dict[str, Any]:
    path = get_context_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_context(data: dict[str, Any]) -> None:
    path = get_context_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def clear_context() -> None:
    save_context({})


def get_current_notebook() -> str | None:
    return load_context().get("notebook_id")


def set_current_notebook(notebook_id: str) -> None:
    context = load_context()
    context["notebook_id"] = notebook_id
    context.pop("conversation_id", None)
    save_context(context)


def get_current_conversation() -> str | None:
    return load_context().get("conversation_id")


def set_current_conversation(conversation_id: str | None) -> None:
    context = load_context()
    if conversation_id is None:
        context.pop("conversation_id", None)
    else:
        context["conversation_id"] = conversation_id
    save_context(context)
