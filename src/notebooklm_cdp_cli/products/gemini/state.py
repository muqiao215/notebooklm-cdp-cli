from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ...state import get_home_dir, load_context, save_context

_CHAT_SCHEMA_VERSION = 1
_CHAT_CONTEXT_KEY = "gemini_chat_session_id"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chat_home(create: bool = False) -> Path:
    path = get_home_dir(create=create) / "gemini-chat"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _sessions_dir(create: bool = False) -> Path:
    path = _chat_home(create=create) / "sessions"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _session_path(session_id: str) -> Path:
    return _sessions_dir(create=True) / f"{session_id}.json"


@dataclass(slots=True)
class ChatMessageRecord:
    role: str
    content: str
    created_at: str
    error: str | None = None


@dataclass(slots=True)
class ChatSessionRecord:
    id: str
    schema_version: int = _CHAT_SCHEMA_VERSION
    messages: list[ChatMessageRecord] = field(default_factory=list)
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)

    @property
    def message_count(self) -> int:
        return len(self.messages)


def save_chat_session(session: ChatSessionRecord) -> ChatSessionRecord:
    session.updated_at = _utcnow_iso()
    path = _session_path(session.id)
    path.write_text(json.dumps(asdict(session), indent=2, ensure_ascii=False), encoding="utf-8")
    return session


def load_chat_session(session_id: str) -> ChatSessionRecord | None:
    path = _sessions_dir() / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        messages = [ChatMessageRecord(**message) for message in payload.get("messages", [])]
        return ChatSessionRecord(
            id=payload["id"],
            schema_version=payload.get("schema_version", _CHAT_SCHEMA_VERSION),
            messages=messages,
            created_at=payload.get("created_at", _utcnow_iso()),
            updated_at=payload.get("updated_at", _utcnow_iso()),
        )
    except Exception:
        return None


def list_chat_sessions(limit: int = 100) -> list[ChatSessionRecord]:
    session_dir = _sessions_dir()
    if not session_dir.exists():
        return []

    sessions: list[ChatSessionRecord] = []
    for path in session_dir.glob("*.json"):
        loaded = load_chat_session(path.stem)
        if loaded is not None:
            sessions.append(loaded)

    sessions.sort(key=lambda session: session.updated_at, reverse=True)
    return sessions[:limit]


def set_current_chat_session_id(session_id: str | None) -> None:
    context = load_context()
    if session_id is None:
        context.pop(_CHAT_CONTEXT_KEY, None)
    else:
        context[_CHAT_CONTEXT_KEY] = session_id
    save_context(context)


def get_current_chat_session_id() -> str | None:
    return load_context().get(_CHAT_CONTEXT_KEY)


def session_summary(session: ChatSessionRecord) -> dict[str, int | str]:
    return {
        "id": session.id,
        "message_count": session.message_count,
    }
