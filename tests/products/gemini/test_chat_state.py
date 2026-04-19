import json

from notebooklm_cdp_cli.products.gemini.state import (
    ChatMessageRecord,
    ChatSessionRecord,
    get_current_chat_session_id,
    list_chat_sessions,
    load_chat_session,
    save_chat_session,
    set_current_chat_session_id,
)


def test_chat_session_roundtrip_uses_typed_records(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))

    session = ChatSessionRecord(
        id="chat-1",
        messages=[
            ChatMessageRecord(role="user", content="hello", created_at="2026-04-19T12:00:00+00:00"),
            ChatMessageRecord(role="assistant", content="world", created_at="2026-04-19T12:00:01+00:00"),
        ],
    )

    save_chat_session(session)

    loaded = load_chat_session("chat-1")
    assert loaded is not None
    assert loaded.id == "chat-1"
    assert [type(message).__name__ for message in loaded.messages] == ["ChatMessageRecord", "ChatMessageRecord"]
    assert loaded.messages[0].content == "hello"
    assert loaded.messages[1].role == "assistant"

    payload = json.loads((tmp_path / "gemini-chat" / "sessions" / "chat-1.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["messages"] == [
        {
            "content": "hello",
            "created_at": "2026-04-19T12:00:00+00:00",
            "error": None,
            "role": "user",
        },
        {
            "content": "world",
            "created_at": "2026-04-19T12:00:01+00:00",
            "error": None,
            "role": "assistant",
        },
    ]


def test_chat_session_listing_and_current_pointer(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))

    save_chat_session(ChatSessionRecord(id="chat-1"))
    save_chat_session(
        ChatSessionRecord(
            id="chat-2",
            updated_at="2026-04-19T13:00:00+00:00",
        )
    )
    set_current_chat_session_id("chat-2")

    sessions = list_chat_sessions()
    assert [session.id for session in sessions] == ["chat-2", "chat-1"]
    assert get_current_chat_session_id() == "chat-2"
