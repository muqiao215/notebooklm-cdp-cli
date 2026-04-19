import json

import pytest
from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli
from notebooklm_cdp_cli.products.gemini.ops import (
    GeminiOperationError,
    ImageGenerationResult,
    SessionEvidence,
    TargetEvidence,
    TextGenerationResult,
)


def _load_json(output: str) -> dict:
    return json.loads(output)


def _target() -> TargetEvidence:
    return TargetEvidence(
        target_id="target-1",
        url="https://gemini.google.com/app",
        resolution_source="active",
    )


def _session() -> SessionEvidence:
    return SessionEvidence(attached=True, session_id="session-1")


def test_gemini_generate_text_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_text(settings, prompt: str, timeout: float):
        assert settings.host == "127.0.0.1"
        assert prompt == "write a haiku"
        assert timeout == 60.0
        return TextGenerationResult(
            text="moon over chrome",
            images=[],
            thinking=None,
            target=_target(),
            session=_session(),
        )

    monkeypatch.setattr(
        "notebooklm_cdp_cli.products.gemini.cli.generate_text",
        fake_generate_text,
    )

    result = CliRunner().invoke(
        cli,
        ["gemini", "generate", "text", "write a haiku", "--timeout", "60", "--json"],
    )

    assert result.exit_code == 0
    assert _load_json(result.output) == {
        "command": "generate_text",
        "error": None,
        "images": [],
        "product": "gemini",
        "session": {"attached": True, "session_id": "session-1"},
        "stability": "supported",
        "status": "ok",
        "target": {
            "resolution_source": "active",
            "target_id": "target-1",
            "url": "https://gemini.google.com/app",
        },
        "text": "moon over chrome",
        "thinking": None,
    }


def test_gemini_ask_json_is_supported_text_alias(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_text(settings, prompt: str, timeout: float):
        assert prompt == "what is NotebookLM?"
        assert timeout == 30.0
        return TextGenerationResult(
            text="A research assistant.",
            images=[],
            thinking="short trace",
            target=_target(),
            session=_session(),
        )

    monkeypatch.setattr(
        "notebooklm_cdp_cli.products.gemini.cli.generate_text",
        fake_generate_text,
    )

    result = CliRunner().invoke(
        cli,
        ["gemini", "ask", "what is NotebookLM?", "--timeout", "30", "--json"],
    )

    assert result.exit_code == 0
    payload = _load_json(result.output)
    assert payload["command"] == "ask"
    assert payload["product"] == "gemini"
    assert payload["status"] == "ok"
    assert payload["stability"] == "supported"
    assert payload["error"] is None
    assert payload["text"] == "A research assistant."
    assert payload["target"]["target_id"] == "target-1"
    assert payload["session"]["session_id"] == "session-1"


def test_gemini_generate_image_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_image(settings, prompt: str, output_dir: str, timeout: float):
        assert prompt == "poster"
        assert output_dir == "out"
        assert timeout == 120.0
        return ImageGenerationResult(
            paths=["out/poster.png"],
            error_code=None,
            state_path=["prompt_filled", "submitted", "images_saved"],
            evidence={"downloaded": 1},
            target=_target(),
            session=_session(),
        )

    monkeypatch.setattr(
        "notebooklm_cdp_cli.products.gemini.cli.generate_image",
        fake_generate_image,
    )

    result = CliRunner().invoke(
        cli,
        ["gemini", "generate", "image", "poster", "--output", "out", "--timeout", "120", "--json"],
    )

    assert result.exit_code == 0
    assert _load_json(result.output) == {
        "command": "generate_image",
        "error": None,
        "error_code": None,
        "evidence": {"downloaded": 1},
        "paths": ["out/poster.png"],
        "product": "gemini",
        "session": {"attached": True, "session_id": "session-1"},
        "stability": "supported",
        "state_path": ["prompt_filled", "submitted", "images_saved"],
        "status": "ok",
        "target": {
            "resolution_source": "active",
            "target_id": "target-1",
            "url": "https://gemini.google.com/app",
        },
    }


def test_gemini_generate_vision_json_contract(monkeypatch: pytest.MonkeyPatch, tmp_path):
    image = tmp_path / "input.png"
    image.write_bytes(b"png")

    async def fake_generate_vision(settings, prompt: str, image_path: str, timeout: float):
        assert prompt == "describe it"
        assert image_path == str(image)
        assert timeout == 90.0
        return TextGenerationResult(
            text="A small image.",
            images=[],
            thinking=None,
            target=_target(),
            session=_session(),
        )

    monkeypatch.setattr(
        "notebooklm_cdp_cli.products.gemini.cli.generate_vision",
        fake_generate_vision,
    )

    result = CliRunner().invoke(
        cli,
        [
            "gemini",
            "generate",
            "vision",
            "describe it",
            "--image",
            str(image),
            "--timeout",
            "90",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = _load_json(result.output)
    assert payload["command"] == "generate_vision"
    assert payload["product"] == "gemini"
    assert payload["status"] == "ok"
    assert payload["error"] is None
    assert payload["image"] == str(image)
    assert payload["text"] == "A small image."
    assert payload["target"]["resolution_source"] == "active"
    assert payload["session"]["attached"] is True


@pytest.mark.parametrize(
    ("args", "patch_name"),
    [
        (["gemini", "generate", "text", "hello", "--json"], "generate_text"),
        (["gemini", "generate", "image", "poster", "--json"], "generate_image"),
        (["gemini", "generate", "vision", "describe", "--image", "{image}", "--json"], "generate_vision"),
    ],
)
def test_gemini_json_error_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    args: list[str],
    patch_name: str,
):
    image = tmp_path / "input.png"
    image.write_bytes(b"png")
    resolved_args = [str(image) if arg == "{image}" else arg for arg in args]

    async def fake_operation(*args, **kwargs):
        raise GeminiOperationError(
            code="target_not_found",
            message="No Gemini tab is available",
            target=TargetEvidence(
                target_id=None,
                url=None,
                resolution_source="none",
            ),
        )

    monkeypatch.setattr(f"notebooklm_cdp_cli.products.gemini.cli.{patch_name}", fake_operation)

    result = CliRunner().invoke(cli, resolved_args)

    assert result.exit_code == 1
    payload = _load_json(result.output)
    assert payload["product"] == "gemini"
    assert payload["status"] == "error"
    assert payload["stability"] == "supported"
    assert payload["error"] == {
        "code": "target_not_found",
        "message": "No Gemini tab is available",
    }
    assert payload["target"] == {
        "resolution_source": "none",
        "target_id": None,
        "url": None,
    }
