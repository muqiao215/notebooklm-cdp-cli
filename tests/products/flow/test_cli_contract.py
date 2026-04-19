import json

import pytest
from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli
from notebooklm_cdp_cli.products.flow.ops import FlowCommandResult


def _load_json(output: str) -> dict:
    return json.loads(output)


def _result(*, command: str, path: str | None = None) -> FlowCommandResult:
    return FlowCommandResult(
        command=command,
        title="Google Flow",
        url="https://labs.google/fx/tools/flow?sia=true",
        path=path,
        evidence={"opened_via": "created_target"},
        target={
            "resolution_source": "created",
            "target_id": "flow-target-1",
            "url": "https://labs.google/fx/tools/flow?sia=true",
        },
        session={"attached": True, "session_id": "flow-session-1"},
    )


def test_flow_open_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_open_flow(settings):
        return _result(command="open")

    monkeypatch.setattr("notebooklm_cdp_cli.products.flow.cli.open_flow", fake_open_flow)

    result = CliRunner().invoke(cli, ["flow", "open", "--json"])

    assert result.exit_code == 0
    assert _load_json(result.output) == {
        "command": "open",
        "error": None,
        "evidence": {"opened_via": "created_target"},
        "path": None,
        "product": "flow",
        "session": {"attached": True, "session_id": "flow-session-1"},
        "stability": "experimental",
        "status": "ok",
        "target": {
            "resolution_source": "created",
            "target_id": "flow-target-1",
            "url": "https://labs.google/fx/tools/flow?sia=true",
        },
        "title": "Google Flow",
        "url": "https://labs.google/fx/tools/flow?sia=true",
    }


def test_flow_text_to_video_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_text_to_video(settings, prompt: str, output_dir: str, timeout: float):
        assert prompt == "crashing waves"
        assert output_dir == "out"
        assert timeout == 180.0
        return _result(command="text_to_video", path="out/flow_video.mp4")

    monkeypatch.setattr("notebooklm_cdp_cli.products.flow.cli.text_to_video", fake_text_to_video)

    result = CliRunner().invoke(
        cli,
        ["flow", "text-to-video", "crashing waves", "--output", "out", "--timeout", "180", "--json"],
    )

    assert result.exit_code == 0
    payload = _load_json(result.output)
    assert payload["command"] == "text_to_video"
    assert payload["product"] == "flow"
    assert payload["stability"] == "experimental"
    assert payload["status"] == "ok"
    assert payload["path"] == "out/flow_video.mp4"


def test_flow_image_to_video_json_contract(monkeypatch: pytest.MonkeyPatch, tmp_path):
    image = tmp_path / "input.png"
    image.write_bytes(b"png")

    async def fake_image_to_video(settings, image_path: str, prompt: str | None, output_dir: str, timeout: float):
        assert image_path == str(image)
        assert prompt == "add wind"
        assert output_dir == "out"
        assert timeout == 180.0
        return _result(command="image_to_video", path="out/flow_video.mp4")

    monkeypatch.setattr("notebooklm_cdp_cli.products.flow.cli.image_to_video", fake_image_to_video)

    result = CliRunner().invoke(
        cli,
        [
            "flow",
            "image-to-video",
            str(image),
            "--prompt",
            "add wind",
            "--output",
            "out",
            "--timeout",
            "180",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = _load_json(result.output)
    assert payload["command"] == "image_to_video"
    assert payload["stability"] == "experimental"
    assert payload["path"] == "out/flow_video.mp4"


def test_flow_screenshot_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_take_screenshot(settings, path: str):
        assert path == "snap.png"
        return _result(command="screenshot", path="snap.png")

    monkeypatch.setattr("notebooklm_cdp_cli.products.flow.cli.take_screenshot", fake_take_screenshot)

    result = CliRunner().invoke(cli, ["flow", "screenshot", "snap.png", "--json"])

    assert result.exit_code == 0
    payload = _load_json(result.output)
    assert payload["command"] == "screenshot"
    assert payload["stability"] == "experimental"
    assert payload["path"] == "snap.png"


def test_flow_help_mentions_experimental():
    result = CliRunner().invoke(cli, ["flow", "text-to-video", "--help"])

    assert result.exit_code == 0
    assert "experimental" in result.output.lower()
