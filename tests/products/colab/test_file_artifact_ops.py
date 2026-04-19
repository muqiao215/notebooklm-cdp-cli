import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from notebooklm_cdp_cli.config import Settings
from notebooklm_cdp_cli.products.colab import ops


class _FakeSession:
    def __init__(self):
        self.target = SimpleNamespace(
            target_id="colab-1",
            title="Notebook",
            url="https://colab.research.google.com/drive/1",
        )
        self.session_id = "session-1"
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _patch_open_page(monkeypatch: pytest.MonkeyPatch, page):
    session = _FakeSession()
    resolution = SimpleNamespace(resolution_source="active")

    async def fake_open_page(settings: Settings, target_id: str | None = None):
        assert isinstance(settings, Settings)
        return session, resolution, page

    monkeypatch.setattr(ops, "_open_page", fake_open_page)
    return session


def test_list_files_returns_best_effort_payload(monkeypatch: pytest.MonkeyPatch):
    class FakePage:
        async def list_files(self):
            return {
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

    session = _patch_open_page(monkeypatch, FakePage())

    payload = asyncio.run(ops.list_files(Settings()))

    assert payload["stability"] == "best_effort"
    assert payload["count"] == 1
    assert payload["files"][0]["name"] == "data.csv"
    assert payload["uncertainty"] == ["dom_link_fallback"]
    assert session.closed is True


def test_upload_file_missing_local_file_raises_best_effort_error(tmp_path):
    missing = tmp_path / "missing.csv"

    with pytest.raises(ops.ColabOperationError) as excinfo:
        asyncio.run(ops.upload_file(Settings(), str(missing)))

    assert excinfo.value.code == "local_file_not_found"
    assert excinfo.value.stability == "best_effort"


def test_download_file_rejects_unsupported_download_url(monkeypatch: pytest.MonkeyPatch):
    class FakePage:
        async def list_files(self):
            return {
                "files": [
                    {
                        "name": "data.csv",
                        "size": 10,
                        "type": "uploaded",
                        "download_url": "blob:https://colab.research.google.com/demo",
                    }
                ],
                "evidence": {"probe_sources": ["dom_links"]},
                "uncertainty": [],
            }

    _patch_open_page(monkeypatch, FakePage())

    with pytest.raises(ops.ColabOperationError) as excinfo:
        asyncio.run(ops.download_file(Settings(), "data.csv"))

    assert excinfo.value.code == "file_download_unsupported"
    assert excinfo.value.stability == "best_effort"


def test_get_artifact_missing_raises_best_effort_error(monkeypatch: pytest.MonkeyPatch):
    class FakePage:
        async def list_artifacts(self):
            return {
                "artifacts": [],
                "evidence": {"probe_sources": ["dom_links"]},
                "uncertainty": ["artifact_collection_empty"],
            }

    _patch_open_page(monkeypatch, FakePage())

    with pytest.raises(ops.ColabOperationError) as excinfo:
        asyncio.run(ops.get_artifact(Settings(), "artifact-7"))

    assert excinfo.value.code == "artifact_not_found"
    assert excinfo.value.stability == "best_effort"


def test_download_artifact_rejects_blob_url(monkeypatch: pytest.MonkeyPatch):
    class FakePage:
        async def list_artifacts(self):
            return {
                "artifacts": [
                    {
                        "artifact_id": "blob-1",
                        "name": "preview.png",
                        "type": "blob",
                        "url": "blob:https://colab.research.google.com/demo",
                    }
                ],
                "evidence": {"probe_sources": ["blob_outputs"]},
                "uncertainty": ["blob_artifacts_may_not_be_downloadable"],
            }

    _patch_open_page(monkeypatch, FakePage())

    with pytest.raises(ops.ColabOperationError) as excinfo:
        asyncio.run(ops.download_artifact(Settings(), "blob-1"))

    assert excinfo.value.code == "artifact_download_unsupported"
    assert excinfo.value.stability == "best_effort"


def test_download_file_propagates_timeout_as_best_effort_error(monkeypatch: pytest.MonkeyPatch, tmp_path):
    output_path = tmp_path / "data.csv"

    class FakePage:
        async def list_files(self):
            return {
                "files": [
                    {
                        "name": "data.csv",
                        "size": 10,
                        "type": "uploaded",
                        "download_url": "https://download.example/data.csv",
                    }
                ],
                "evidence": {"probe_sources": ["colab_files_api"]},
                "uncertainty": [],
            }

        async def download_url_to_path(self, url: str, destination_path: str, timeout: float):
            raise ops.ColabOperationError(
                code="download_timeout",
                message="Timed out while fetching file content from Colab.",
                evidence={"timeout_seconds": timeout},
                stability="best_effort",
            )

    _patch_open_page(monkeypatch, FakePage())

    with pytest.raises(ops.ColabOperationError) as excinfo:
        asyncio.run(ops.download_file(Settings(), "data.csv", output=str(output_path), timeout=9.0))

    assert excinfo.value.code == "download_timeout"
    assert excinfo.value.stability == "best_effort"


def test_export_notebook_returns_best_effort_payload(monkeypatch: pytest.MonkeyPatch, tmp_path):
    output_path = tmp_path / "demo.ipynb"

    class FakePage:
        async def export_notebook(self, format: str, output: str, timeout: float):
            Path(output).write_text("{\"cells\": []}\n", encoding="utf-8")
            return {
                "export": {
                    "state": "exported",
                    "format": format,
                    "path": output,
                    "bytes_written": 14,
                },
                "evidence": {"serializer": "dom_reconstruction"},
                "uncertainty": ["notebook_export_fidelity_not_guaranteed"],
            }

    session = _patch_open_page(monkeypatch, FakePage())

    payload = asyncio.run(ops.export_notebook(Settings(), "ipynb", str(output_path)))

    assert payload["stability"] == "best_effort"
    assert payload["export"]["state"] == "exported"
    assert payload["uncertainty"] == ["notebook_export_fidelity_not_guaranteed"]
    assert session.closed is True
