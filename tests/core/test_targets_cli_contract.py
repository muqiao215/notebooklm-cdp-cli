import json

import pytest
from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli


def _payload_base() -> dict:
    return {
        "product": "colab",
        "stability": "supported",
        "status": "ok",
        "error": None,
        "count": 1,
        "targets": [
            {
                "target_id": "colab-1",
                "title": "Notebook",
                "url": "https://colab.research.google.com/drive/1",
                "attached": True,
                "selected": True,
            }
        ],
        "selected": {
            "target_id": "colab-1",
            "title": "Notebook",
            "url": "https://colab.research.google.com/drive/1",
            "status": "selected",
        },
        "resolved": {
            "target_id": "colab-1",
            "title": "Notebook",
            "url": "https://colab.research.google.com/drive/1",
            "attached": True,
            "resolution_source": "explicit",
        },
        "evidence": {
            "candidate_count": 1,
            "resolution_source": "explicit",
        },
    }


def test_targets_list_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_list_targets(settings, product: str):
        assert product == "colab"
        return _payload_base()

    monkeypatch.setattr("notebooklm_cdp_cli.core.targets_cli.list_targets_for_product", fake_list_targets)

    result = CliRunner().invoke(cli, ["targets", "list", "--product", "colab", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        **_payload_base(),
        "command": "targets_list",
    }


def test_targets_select_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_select_target(settings, product: str, target_ref: str):
        assert product == "colab"
        assert target_ref == "colab-1"
        payload = _payload_base()
        payload["count"] = None
        payload.pop("targets")
        return payload

    monkeypatch.setattr("notebooklm_cdp_cli.core.targets_cli.select_target_for_product", fake_select_target)

    result = CliRunner().invoke(cli, ["targets", "select", "--product", "colab", "colab-1", "--json"])

    assert result.exit_code == 0
    expected = _payload_base()
    expected["count"] = None
    expected.pop("targets")
    expected["command"] = "targets_select"
    assert json.loads(result.output) == expected


def test_targets_current_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_current_target(settings, product: str):
        assert product == "colab"
        payload = _payload_base()
        payload["count"] = None
        payload.pop("targets")
        return payload

    monkeypatch.setattr("notebooklm_cdp_cli.core.targets_cli.current_target_for_product", fake_current_target)

    result = CliRunner().invoke(cli, ["targets", "current", "--product", "colab", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output)["command"] == "targets_current"


def test_targets_open_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_open_target(settings, product: str, target_ref: str | None):
        assert product == "colab"
        assert target_ref is None
        payload = _payload_base()
        payload["count"] = None
        payload.pop("targets")
        payload["session"] = {"attached": True, "session_id": None}
        return payload

    monkeypatch.setattr("notebooklm_cdp_cli.core.targets_cli.open_target_for_product", fake_open_target)

    result = CliRunner().invoke(cli, ["targets", "open", "--product", "colab", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "targets_open"
    assert payload["product"] == "colab"
    assert payload["session"] == {"attached": True, "session_id": None}
