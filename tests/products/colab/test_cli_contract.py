import json

import pytest
from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli


def _shared_target_payload() -> dict:
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


def test_colab_notebook_list_alias_uses_shared_target_layer(monkeypatch: pytest.MonkeyPatch):
    async def fake_list_targets(settings, product: str):
        assert product == "colab"
        return _shared_target_payload()

    monkeypatch.setattr("notebooklm_cdp_cli.core.targets_cli.list_targets_for_product", fake_list_targets)

    result = CliRunner().invoke(cli, ["colab", "notebook", "list", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "notebook_list"
    assert payload["product"] == "colab"
    assert payload["resolved"]["resolution_source"] == "explicit"


def test_colab_notebook_select_alias_uses_shared_target_layer(monkeypatch: pytest.MonkeyPatch):
    async def fake_select_target(settings, product: str, target_ref: str):
        assert product == "colab"
        assert target_ref == "colab-1"
        payload = _shared_target_payload()
        payload["count"] = None
        payload.pop("targets")
        return payload

    monkeypatch.setattr("notebooklm_cdp_cli.core.targets_cli.select_target_for_product", fake_select_target)

    result = CliRunner().invoke(cli, ["colab", "notebook", "select", "colab-1", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output)["command"] == "notebook_select"


def test_colab_notebook_current_alias_uses_shared_target_layer(monkeypatch: pytest.MonkeyPatch):
    async def fake_current_target(settings, product: str):
        assert product == "colab"
        payload = _shared_target_payload()
        payload["count"] = None
        payload.pop("targets")
        payload["selected"]["status"] = "stale"
        payload["resolved"]["resolution_source"] = "active"
        return payload

    monkeypatch.setattr("notebooklm_cdp_cli.core.targets_cli.current_target_for_product", fake_current_target)

    result = CliRunner().invoke(cli, ["colab", "notebook", "current", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "notebook_current"
    assert payload["selected"]["status"] == "stale"
    assert payload["resolved"]["resolution_source"] == "active"


def test_colab_notebook_open_alias_uses_shared_target_layer(monkeypatch: pytest.MonkeyPatch):
    async def fake_open_target(settings, product: str, target_ref: str | None):
        assert product == "colab"
        assert target_ref is None
        payload = _shared_target_payload()
        payload["count"] = None
        payload.pop("targets")
        payload["session"] = {"attached": True, "session_id": None}
        return payload

    monkeypatch.setattr("notebooklm_cdp_cli.core.targets_cli.open_target_for_product", fake_open_target)

    result = CliRunner().invoke(cli, ["colab", "notebook", "open", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "notebook_open"
    assert payload["session"] == {"attached": True, "session_id": None}


def test_colab_notebook_info_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_info(settings, target_id: str | None):
        assert target_id is None
        return {
            "product": "colab",
            "stability": "supported",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "explicit",
            },
            "session": {"attached": True, "session_id": None},
            "notebook": {
                "title": "Notebook",
                "url": "https://colab.research.google.com/drive/1",
                "total_cells": 12,
            },
            "runtime": {
                "state": "connected",
                "confidence": "high",
                "uncertainty": [],
            },
            "evidence": {"probe_sources": ["context", "runtime"]},
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.notebook_info", fake_info)

    result = CliRunner().invoke(cli, ["colab", "notebook", "info", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "notebook_info"
    assert payload["runtime"]["confidence"] == "high"


def test_colab_notebook_summary_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_summary(settings, target_id: str | None):
        return {
            "product": "colab",
            "stability": "supported",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "active",
            },
            "session": {"attached": True, "session_id": None},
            "title": "Notebook",
            "url": "https://colab.research.google.com/drive/1",
            "runtime_state": "connected",
            "runtime_confidence": "medium",
            "total_cells": 12,
            "current_cell": 3,
            "last_output_excerpt": "done",
            "last_error_excerpt": None,
            "evidence": {"probe_sources": ["summary"]},
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.notebook_summary", fake_summary)

    result = CliRunner().invoke(cli, ["colab", "notebook", "summary", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "notebook_summary"
    assert payload["runtime_confidence"] == "medium"


def test_colab_cell_count_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_cell_count(settings, target_id: str | None):
        return {
            "product": "colab",
            "stability": "supported",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "explicit",
            },
            "session": {"attached": True, "session_id": None},
            "cell_count": 12,
            "evidence": {"probe_sources": ["dom"]},
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.cell_count", fake_cell_count)

    result = CliRunner().invoke(cli, ["colab", "cell", "count", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.output)["command"] == "cell_count"


def test_colab_cell_run_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_run_code(settings, code: str, target_id: str | None, timeout: float):
        assert code == "print('hi')"
        assert timeout == 30.0
        return {
            "product": "colab",
            "stability": "supported",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "first",
            },
            "session": {"attached": True, "session_id": None},
            "state": "completed",
            "output": "hi",
            "execution_time": 0.3,
            "evidence": {"completion_strategy": "dom_probe"},
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.run_cell_code", fake_run_code)

    result = CliRunner().invoke(cli, ["colab", "cell", "run", "--code", "print('hi')", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "cell_run"
    assert payload["state"] == "completed"


def test_colab_cell_run_file_json_contract(monkeypatch: pytest.MonkeyPatch, tmp_path):
    code_file = tmp_path / "demo.py"
    code_file.write_text("print('file')", encoding="utf-8")

    async def fake_run_file(settings, file_path: str, target_id: str | None, timeout: float):
        assert file_path == str(code_file)
        assert timeout == 60.0
        return {
            "product": "colab",
            "stability": "supported",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "manual",
            },
            "session": {"attached": True, "session_id": None},
            "state": "completed",
            "output": "file",
            "execution_time": 0.4,
            "file": str(code_file),
            "evidence": {"completion_strategy": "dom_probe"},
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.run_cell_file", fake_run_file)

    result = CliRunner().invoke(cli, ["colab", "cell", "run-file", str(code_file), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "cell_run_file"
    assert payload["file"] == str(code_file)


def test_colab_runtime_status_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_runtime_status(settings, target_id: str | None):
        return {
            "product": "colab",
            "stability": "supported",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "active",
            },
            "session": {"attached": True, "session_id": None},
            "runtime": {
                "state": "connected",
                "attached": True,
                "interactive": True,
                "executor_hint": "google.colab.kernel",
                "confidence": "high",
                "uncertainty": [],
            },
            "evidence": {"probe_sources": ["colab_api", "dom"]},
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.runtime_status", fake_runtime_status)

    result = CliRunner().invoke(cli, ["colab", "runtime", "status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "runtime_status"
    assert payload["runtime"]["attached"] is True


def test_colab_help_lists_file_and_artifact_groups():
    runner = CliRunner()

    result = runner.invoke(cli, ["colab", "--help"])

    assert result.exit_code == 0
    assert "file" in result.output
    assert "artifact" in result.output


def test_colab_notebook_help_lists_export_command():
    runner = CliRunner()

    result = runner.invoke(cli, ["colab", "notebook", "--help"])

    assert result.exit_code == 0
    assert "export" in result.output


def test_colab_file_upload_json_contract(monkeypatch: pytest.MonkeyPatch, tmp_path):
    local_file = tmp_path / "data.csv"
    local_file.write_text("x,y\n1,2\n", encoding="utf-8")

    async def fake_upload_file(settings, file_path: str, target_id: str | None, timeout: float):
        assert file_path == str(local_file)
        assert timeout == 30.0
        return {
            "product": "colab",
            "stability": "best_effort",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "explicit",
            },
            "session": {"attached": True, "session_id": None},
            "file": {
                "name": "data.csv",
                "size": 8,
                "local_path": str(local_file),
            },
            "upload": {
                "state": "uploaded",
                "method": "google.colab.upload",
            },
            "evidence": {"timeout_seconds": 30.0},
            "uncertainty": ["browser_upload_heuristic"],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.upload_file", fake_upload_file)

    result = CliRunner().invoke(cli, ["colab", "file", "upload", str(local_file), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "file_upload"
    assert payload["stability"] == "best_effort"
    assert payload["upload"]["state"] == "uploaded"


def test_colab_file_upload_missing_file_returns_structured_error(tmp_path):
    missing = tmp_path / "missing.csv"

    result = CliRunner().invoke(cli, ["colab", "file", "upload", str(missing), "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["command"] == "file_upload"
    assert payload["stability"] == "best_effort"
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "local_file_not_found"


def test_colab_file_list_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_list_files(settings, target_id: str | None):
        return {
            "product": "colab",
            "stability": "best_effort",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "active",
            },
            "session": {"attached": True, "session_id": None},
            "count": 1,
            "files": [
                {
                    "name": "data.csv",
                    "size": 1024,
                    "type": "uploaded",
                    "download_url": "https://download.example/data.csv",
                }
            ],
            "evidence": {"probe_sources": ["colab_files_api", "dom_links"]},
            "uncertainty": ["dom_link_fallback"],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.list_files", fake_list_files)

    result = CliRunner().invoke(cli, ["colab", "file", "list", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "file_list"
    assert payload["count"] == 1
    assert payload["stability"] == "best_effort"


def test_colab_file_download_json_contract(monkeypatch: pytest.MonkeyPatch, tmp_path):
    output_path = tmp_path / "data.csv"

    async def fake_download_file(settings, file_name: str, output: str | None, target_id: str | None, timeout: float):
        assert file_name == "data.csv"
        assert output == str(output_path)
        assert timeout == 30.0
        return {
            "product": "colab",
            "stability": "best_effort",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "manual",
            },
            "session": {"attached": True, "session_id": None},
            "file": {
                "name": "data.csv",
                "download_url": "https://download.example/data.csv",
            },
            "download": {
                "state": "downloaded",
                "path": str(output_path),
                "bytes_written": 1024,
            },
            "evidence": {"timeout_seconds": 30.0},
            "uncertainty": ["browser_fetch_download"],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.download_file", fake_download_file)

    result = CliRunner().invoke(
        cli,
        ["colab", "file", "download", "data.csv", "--output", str(output_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "file_download"
    assert payload["download"]["state"] == "downloaded"


def test_colab_artifact_list_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_list_artifacts(settings, target_id: str | None):
        return {
            "product": "colab",
            "stability": "best_effort",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "active",
            },
            "session": {"attached": True, "session_id": None},
            "count": 2,
            "artifacts": [
                {
                    "artifact_id": "artifact-0",
                    "name": "output.csv",
                    "type": "file",
                    "url": "https://download.example/output.csv",
                },
                {
                    "artifact_id": "blob-1",
                    "name": "preview.png",
                    "type": "blob",
                    "url": "blob:https://colab.research.google.com/demo",
                },
            ],
            "evidence": {"probe_sources": ["colab_artifacts_api", "dom_links", "blob_outputs"]},
            "uncertainty": ["blob_artifacts_may_not_be_downloadable"],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.list_artifacts", fake_list_artifacts)

    result = CliRunner().invoke(cli, ["colab", "artifact", "list", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "artifact_list"
    assert payload["count"] == 2
    assert payload["stability"] == "best_effort"


def test_colab_artifact_latest_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_latest_artifact(settings, target_id: str | None):
        return {
            "product": "colab",
            "stability": "best_effort",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "active",
            },
            "session": {"attached": True, "session_id": None},
            "artifact": {
                "artifact_id": "artifact-1",
                "name": "latest.csv",
                "type": "file",
                "url": "https://download.example/latest.csv",
            },
            "evidence": {"selection_strategy": "last_detected"},
            "uncertainty": ["artifact_order_is_dom_inferred"],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.latest_artifact", fake_latest_artifact)

    result = CliRunner().invoke(cli, ["colab", "artifact", "latest", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "artifact_latest"
    assert payload["artifact"]["artifact_id"] == "artifact-1"


def test_colab_artifact_get_json_contract(monkeypatch: pytest.MonkeyPatch):
    async def fake_get_artifact(settings, artifact_id: str, target_id: str | None):
        assert artifact_id == "artifact-7"
        return {
            "product": "colab",
            "stability": "best_effort",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "explicit",
            },
            "session": {"attached": True, "session_id": None},
            "artifact": {
                "artifact_id": "artifact-7",
                "name": "weights.bin",
                "type": "file",
                "url": "https://download.example/weights.bin",
            },
            "evidence": {"lookup": "artifact_id"},
            "uncertainty": [],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.get_artifact", fake_get_artifact)

    result = CliRunner().invoke(cli, ["colab", "artifact", "get", "artifact-7", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "artifact_get"
    assert payload["artifact"]["name"] == "weights.bin"


def test_colab_artifact_download_json_contract(monkeypatch: pytest.MonkeyPatch, tmp_path):
    output_path = tmp_path / "weights.bin"

    async def fake_download_artifact(settings, artifact_id: str, output: str | None, target_id: str | None, timeout: float):
        assert artifact_id == "artifact-7"
        assert output == str(output_path)
        assert timeout == 30.0
        return {
            "product": "colab",
            "stability": "best_effort",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "manual",
            },
            "session": {"attached": True, "session_id": None},
            "artifact": {
                "artifact_id": "artifact-7",
                "name": "weights.bin",
                "type": "file",
                "url": "https://download.example/weights.bin",
            },
            "download": {
                "state": "downloaded",
                "path": str(output_path),
                "bytes_written": 2048,
            },
            "evidence": {"timeout_seconds": 30.0},
            "uncertainty": ["browser_fetch_download"],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.download_artifact", fake_download_artifact)

    result = CliRunner().invoke(
        cli,
        ["colab", "artifact", "download", "artifact-7", "--output", str(output_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "artifact_download"
    assert payload["download"]["state"] == "downloaded"


def test_colab_notebook_export_json_contract(monkeypatch: pytest.MonkeyPatch, tmp_path):
    output_path = tmp_path / "demo.ipynb"

    async def fake_export_notebook(
        settings,
        format: str,
        output: str,
        target_id: str | None,
        timeout: float,
    ):
        assert format == "ipynb"
        assert output == str(output_path)
        assert timeout == 45.0
        return {
            "product": "colab",
            "stability": "best_effort",
            "status": "ok",
            "error": None,
            "target": {
                "target_id": "colab-1",
                "url": "https://colab.research.google.com/drive/1",
                "resolution_source": "first",
            },
            "session": {"attached": True, "session_id": None},
            "export": {
                "state": "exported",
                "format": "ipynb",
                "path": str(output_path),
            },
            "evidence": {"serializer": "dom_reconstruction"},
            "uncertainty": ["notebook_export_fidelity_not_guaranteed"],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.products.colab.cli.export_notebook", fake_export_notebook)

    result = CliRunner().invoke(
        cli,
        ["colab", "notebook", "export", "--format", "ipynb", "--output", str(output_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["command"] == "notebook_export"
    assert payload["export"]["state"] == "exported"
