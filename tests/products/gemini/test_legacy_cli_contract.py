import json

import pytest
from click.testing import CliRunner

from notebooklm_cdp_cli.products.gemini.legacy_cli import gemini_web_cli
from notebooklm_cdp_cli.products.gemini.ops import ImageGenerationResult, SessionEvidence, TargetEvidence, TextGenerationResult


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


def test_gemini_web_generate_text_preserves_original_command(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_text(settings, prompt: str, timeout: float):
        assert settings.host == "127.0.0.1"
        assert prompt == "Hello, Gemini!"
        assert timeout == 60.0
        return TextGenerationResult(
            text="Hello from Gemini Web.",
            images=[],
            thinking=None,
            target=_target(),
            session=_session(),
        )

    monkeypatch.setattr("notebooklm_cdp_cli.products.gemini.cli.generate_text", fake_generate_text)

    result = CliRunner().invoke(gemini_web_cli, ["generate", "text", "Hello, Gemini!", "--json"])

    assert result.exit_code == 0
    payload = _load_json(result.output)
    assert payload["command"] == "generate_text"
    assert payload["product"] == "gemini"
    assert payload["status"] == "ok"
    assert payload["text"] == "Hello from Gemini Web."


def test_gemini_web_ask_preserves_original_shortcut(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_text(settings, prompt: str, timeout: float):
        assert prompt == "What is the capital of France?"
        assert timeout == 30.0
        return TextGenerationResult(
            text="Paris.",
            images=[],
            thinking=None,
            target=_target(),
            session=_session(),
        )

    monkeypatch.setattr("notebooklm_cdp_cli.products.gemini.cli.generate_text", fake_generate_text)

    result = CliRunner().invoke(gemini_web_cli, ["ask", "What is the capital of France?", "--json"])

    assert result.exit_code == 0
    payload = _load_json(result.output)
    assert payload["command"] == "ask"
    assert payload["text"] == "Paris."


def test_gemini_web_generate_image_preserves_original_command(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_image(settings, prompt: str, output_dir: str, timeout: float):
        assert prompt == "A cat playing piano"
        assert output_dir == "out"
        assert timeout == 120.0
        return ImageGenerationResult(
            paths=["out/cat.png"],
            error_code=None,
            state_path=["prompt_filled", "submitted", "images_saved"],
            evidence={"downloaded": 1},
            target=_target(),
            session=_session(),
        )

    monkeypatch.setattr("notebooklm_cdp_cli.products.gemini.cli.generate_image", fake_generate_image)

    result = CliRunner().invoke(
        gemini_web_cli,
        ["generate", "image", "A cat playing piano", "--output", "out", "--json"],
    )

    assert result.exit_code == 0
    payload = _load_json(result.output)
    assert payload["command"] == "generate_image"
    assert payload["paths"] == ["out/cat.png"]


def test_gemini_web_generate_vision_preserves_original_command(monkeypatch: pytest.MonkeyPatch, tmp_path):
    image = tmp_path / "photo.png"
    image.write_bytes(b"png")

    async def fake_generate_vision(settings, prompt: str, image_path: str, timeout: float):
        assert prompt == "What is in this image?"
        assert image_path == str(image)
        assert timeout == 90.0
        return TextGenerationResult(
            text="A photo.",
            images=[],
            thinking=None,
            target=_target(),
            session=_session(),
        )

    monkeypatch.setattr("notebooklm_cdp_cli.products.gemini.cli.generate_vision", fake_generate_vision)

    result = CliRunner().invoke(
        gemini_web_cli,
        ["generate", "vision", "-i", str(image), "What is in this image?", "--json"],
    )

    assert result.exit_code == 0
    payload = _load_json(result.output)
    assert payload["command"] == "generate_vision"
    assert payload["image"] == str(image)
    assert payload["text"] == "A photo."


def test_gemini_web_help_preserves_original_groups():
    result = CliRunner().invoke(gemini_web_cli, ["--help"])

    assert result.exit_code == 0
    assert "generate" in result.output
    assert "ask" in result.output
    assert "flow" in result.output
