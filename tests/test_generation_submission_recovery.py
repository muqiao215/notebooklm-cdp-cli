from __future__ import annotations

from dataclasses import dataclass

import pytest

import notebooklm_cdp_cli.notebooklm_ops as ops
from notebooklm.types import GenerationStatus

from notebooklm_cdp_cli.config import Settings


NO_ARTIFACT_ID_ERROR = "Generation failed - no artifact_id returned"


@dataclass
class GenerateCase:
    wrapper_name: str
    method_name: str
    args: tuple


CASES = [
    GenerateCase("generate_report", "generate_report", ("briefing_doc", None)),
    GenerateCase("generate_audio", "generate_audio", (None,)),
    GenerateCase("generate_video", "generate_video", (None, None, None)),
    GenerateCase("generate_cinematic_video", "generate_cinematic_video", (None,)),
    GenerateCase("generate_slide_deck", "generate_slide_deck", (None, None, None)),
    GenerateCase("generate_infographic", "generate_infographic", (None, None, None, None)),
]


def _patch_backend(monkeypatch: pytest.MonkeyPatch, method_name: str, status: GenerationStatus):
    calls = {"wait": 0}

    class FakeAuthService:
        def __init__(self, settings: Settings):
            self.settings = settings

        async def notebooklm_auth(self):
            return object()

    class FakeArtifacts:
        def __init__(self):
            self.list_calls = 0

        def __getattr__(self, name: str):
            if name == method_name:
                async def generate(*args, **kwargs):
                    return status

                return generate
            if name == "list":
                async def list_artifacts(*args, **kwargs):
                    self.list_calls += 1
                    return []

                return list_artifacts
            if name == "wait_for_completion":
                async def wait_for_completion(*args, **kwargs):
                    calls["wait"] += 1
                    return status

                return wait_for_completion
            raise AttributeError(name)

    class FakeNotebookLMClient:
        def __init__(self, auth):
            self.auth = auth
            self.artifacts = FakeArtifacts()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(ops, "AuthService", FakeAuthService)
    monkeypatch.setattr(ops, "NotebookLMClient", FakeNotebookLMClient)
    return calls


@pytest.mark.anyio
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.wrapper_name)
async def test_generate_wrappers_recover_missing_artifact_id_submission(monkeypatch, case: GenerateCase):
    status = GenerationStatus(task_id="", status="failed", error=NO_ARTIFACT_ID_ERROR)
    _patch_backend(monkeypatch, case.method_name, status)

    wrapper = getattr(ops, case.wrapper_name)
    payload = await wrapper(Settings(), "nb-1", *case.args, wait=False)

    assert payload["status"] == "pending"
    assert payload["task_id"] is None
    assert payload["error"] is None
    assert payload["error_code"] is None
    assert payload["url"] is None
    assert payload["metadata"]["accepted_without_task_id"] is True
    assert payload["metadata"]["poll_supported"] is False
    assert payload["metadata"]["list_supported"] is True
    assert payload["metadata"]["upstream_status"] == "failed"
    assert payload["metadata"]["upstream_error"] == NO_ARTIFACT_ID_ERROR


@pytest.mark.anyio
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.wrapper_name)
async def test_generate_wrappers_skip_wait_without_task_id(monkeypatch, case: GenerateCase):
    status = GenerationStatus(task_id="", status="failed", error=NO_ARTIFACT_ID_ERROR)
    calls = _patch_backend(monkeypatch, case.method_name, status)

    wrapper = getattr(ops, case.wrapper_name)
    payload = await wrapper(Settings(), "nb-1", *case.args, wait=True)

    assert payload["status"] == "pending"
    assert payload["task_id"] is None
    assert calls["wait"] == 0


@pytest.mark.anyio
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.wrapper_name)
async def test_generate_wrappers_attach_new_visible_artifact_when_pending(monkeypatch, case: GenerateCase):
    status = GenerationStatus(task_id="", status="failed", error=NO_ARTIFACT_ID_ERROR)

    class FakeArtifact:
        def __init__(self, artifact_id: str, kind: str, title: str):
            self.id = artifact_id
            self.kind = kind
            self.title = title
            self.status = 1
            self.created_at = None
            self.url = None

    class FakeAuthService:
        def __init__(self, settings: Settings):
            self.settings = settings

        async def notebooklm_auth(self):
            return object()

    class FakeArtifacts:
        def __init__(self):
            self.list_calls = 0

        async def list(self, notebook_id, artifact_kind=None):
            self.list_calls += 1
            if self.list_calls == 1:
                return [FakeArtifact("existing-1", case.method_name.replace("generate_", ""), "Older")]
            return [
                FakeArtifact("existing-1", case.method_name.replace("generate_", ""), "Older"),
                FakeArtifact("new-1", case.method_name.replace("generate_", ""), "Fresh"),
            ]

        async def wait_for_completion(self, *args, **kwargs):
            raise AssertionError("wait_for_completion should not run without task_id")

        def __getattr__(self, name: str):
            if name == case.method_name:
                async def generate(*args, **kwargs):
                    return status

                return generate
            raise AttributeError(name)

    class FakeNotebookLMClient:
        def __init__(self, auth):
            self.auth = auth
            self.artifacts = FakeArtifacts()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(ops, "AuthService", FakeAuthService)
    monkeypatch.setattr(ops, "NotebookLMClient", FakeNotebookLMClient)
    monkeypatch.setattr(ops.asyncio, "sleep", lambda _: None)

    wrapper = getattr(ops, case.wrapper_name)
    payload = await wrapper(Settings(), "nb-1", *case.args, wait=False)

    assert payload["status"] == "pending"
    assert payload["visible_artifact"]["id"] == "new-1"
    assert payload["visible_artifact"]["title"] == "Fresh"
    assert payload["metadata"]["matched_artifact_id"] == "new-1"
    assert payload["metadata"]["new_artifact_count"] == 1
    assert payload["metadata"]["tracking_hint"] == "A newly visible artifact was detected; use its artifact_id for follow-up commands."
