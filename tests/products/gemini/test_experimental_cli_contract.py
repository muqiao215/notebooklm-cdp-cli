import json

import pytest
from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli
from notebooklm_cdp_cli.products.gemini.ops import (
    DeepResearchResult,
    GeminiOperationError,
    SessionEvidence,
    TargetEvidence,
    VideoGenerationResult,
)


def _load_json(output: str) -> dict:
    return json.loads(output)


def _target() -> TargetEvidence:
    return TargetEvidence(
        target_id="target-1",
        url="https://gemini.google.com/app",
        resolution_source="created",
    )


def _session() -> SessionEvidence:
    return SessionEvidence(attached=True, session_id="session-1")


def test_gemini_deep_research_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_deep_research(settings, query: str, timeout: float, output_path: str | None = None):
        assert query == "agent memory"
        assert timeout == 300.0
        assert output_path is None
        return DeepResearchResult(
            query=query,
            report="Structured report",
            sources=["https://example.com/report"],
            evidence={"completion_strategy": "body_text_probe"},
            target=_target(),
            session=_session(),
        )

    monkeypatch.setattr(
        "notebooklm_cdp_cli.products.gemini.cli.deep_research",
        fake_deep_research,
    )

    result = CliRunner().invoke(
        cli,
        ["gemini", "deep-research", "agent memory", "--timeout", "300", "--json"],
    )

    assert result.exit_code == 0
    assert _load_json(result.output) == {
        "command": "deep_research",
        "error": None,
        "evidence": {"completion_strategy": "body_text_probe"},
        "product": "gemini",
        "query": "agent memory",
        "report": "Structured report",
        "session": {"attached": True, "session_id": "session-1"},
        "sources": ["https://example.com/report"],
        "stability": "experimental",
        "status": "ok",
        "target": {
            "resolution_source": "created",
            "target_id": "target-1",
            "url": "https://gemini.google.com/app",
        },
    }


def test_gemini_generate_video_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_video(settings, prompt: str, output_dir: str, timeout: float):
        assert prompt == "cinematic sunrise"
        assert output_dir == "out"
        assert timeout == 180.0
        return VideoGenerationResult(
            path="out/gemini_video.mp4",
            evidence={"source_type": "video"},
            target=_target(),
            session=_session(),
        )

    monkeypatch.setattr(
        "notebooklm_cdp_cli.products.gemini.cli.generate_video",
        fake_generate_video,
    )

    result = CliRunner().invoke(
        cli,
        ["gemini", "generate", "video", "cinematic sunrise", "--output", "out", "--timeout", "180", "--json"],
    )

    assert result.exit_code == 0
    assert _load_json(result.output) == {
        "command": "generate_video",
        "error": None,
        "evidence": {"source_type": "video"},
        "path": "out/gemini_video.mp4",
        "product": "gemini",
        "session": {"attached": True, "session_id": "session-1"},
        "stability": "experimental",
        "status": "ok",
        "target": {
            "resolution_source": "created",
            "target_id": "target-1",
            "url": "https://gemini.google.com/app",
        },
    }


def test_gemini_chat_commands_use_typed_session_store(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))

    start_result = CliRunner().invoke(
        cli,
        ["gemini", "chat", "start", "--session-id", "chat-1", "--json"],
    )
    assert start_result.exit_code == 0
    assert _load_json(start_result.output) == {
        "chat_session": {
            "id": "chat-1",
            "message_count": 0,
        },
        "command": "chat_start",
        "error": None,
        "product": "gemini",
        "stability": "experimental",
        "status": "ok",
    }

    list_result = CliRunner().invoke(
        cli,
        ["gemini", "chat", "list", "--json"],
    )
    assert list_result.exit_code == 0
    assert _load_json(list_result.output) == {
        "chat_sessions": [
            {
                "id": "chat-1",
                "message_count": 0,
            }
        ],
        "command": "chat_list",
        "error": None,
        "product": "gemini",
        "stability": "experimental",
        "status": "ok",
    }

    use_result = CliRunner().invoke(
        cli,
        ["gemini", "chat", "use", "chat-1", "--json"],
    )
    assert use_result.exit_code == 0
    assert _load_json(use_result.output) == {
        "chat_session": {
            "id": "chat-1",
            "message_count": 0,
        },
        "command": "chat_use",
        "error": None,
        "product": "gemini",
        "stability": "experimental",
        "status": "ok",
    }


def test_gemini_chat_send_json_contract(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    runner = CliRunner()
    start_result = runner.invoke(cli, ["gemini", "chat", "start", "--session-id", "chat-1", "--json"])
    assert start_result.exit_code == 0

    async def fake_send_chat_message(settings, session_id: str, message: str, timeout: float):
        assert session_id == "chat-1"
        assert message == "hello there"
        assert timeout == 60.0
        return {
            "chat_session": {"id": "chat-1", "message_count": 2},
            "reply": "General Kenobi.",
            "session": {"attached": True, "session_id": "session-1"},
            "target": {
                "resolution_source": "created",
                "target_id": "target-1",
                "url": "https://gemini.google.com/app",
            },
        }

    monkeypatch.setattr(
        "notebooklm_cdp_cli.products.gemini.cli.send_chat_message",
        fake_send_chat_message,
    )

    send_result = runner.invoke(
        cli,
        ["gemini", "chat", "send", "--session", "chat-1", "hello there", "--json"],
    )

    assert send_result.exit_code == 0
    assert _load_json(send_result.output) == {
        "chat_session": {"id": "chat-1", "message_count": 2},
        "command": "chat_send",
        "error": None,
        "product": "gemini",
        "reply": "General Kenobi.",
        "session": {"attached": True, "session_id": "session-1"},
        "stability": "experimental",
        "status": "ok",
        "target": {
            "resolution_source": "created",
            "target_id": "target-1",
            "url": "https://gemini.google.com/app",
        },
    }


@pytest.mark.parametrize(
    ("args", "patch_name"),
    [
        (["gemini", "deep-research", "topic", "--json"], "deep_research"),
        (["gemini", "generate", "video", "topic", "--json"], "generate_video"),
    ],
)
def test_gemini_experimental_error_contract(
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
    patch_name: str,
):
    async def fake_operation(*args, **kwargs):
        raise GeminiOperationError(
            code="target_not_found",
            message="No Gemini tab is available",
            target=TargetEvidence(target_id=None, url=None, resolution_source="none"),
        )

    monkeypatch.setattr(f"notebooklm_cdp_cli.products.gemini.cli.{patch_name}", fake_operation)

    result = CliRunner().invoke(cli, args)

    assert result.exit_code == 1
    payload = _load_json(result.output)
    assert payload["product"] == "gemini"
    assert payload["status"] == "error"
    assert payload["stability"] == "experimental"
    assert payload["error"] == {
        "code": "target_not_found",
        "message": "No Gemini tab is available",
    }


def test_gemini_experimental_help_mentions_experimental():
    result = CliRunner().invoke(cli, ["gemini", "deep-research", "--help"])

    assert result.exit_code == 0
    assert "experimental" in result.output.lower()
