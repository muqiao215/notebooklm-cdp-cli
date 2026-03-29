from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any
from urllib.parse import urlparse

import httpx
from notebooklm.client import NotebookLMClient
from notebooklm.cli.language import SUPPORTED_LANGUAGES
from notebooklm.rpc import (
    AudioFormat,
    AudioLength,
    ChatGoal,
    ChatResponseLength,
    ExportType,
    InfographicDetail,
    InfographicOrientation,
    InfographicStyle,
    QuizDifficulty,
    QuizQuantity,
    SlideDeckFormat,
    SlideDeckLength,
    VideoFormat,
    VideoStyle,
)
from notebooklm.rpc.types import ReportFormat, SharePermission, ShareViewLevel
from notebooklm.types import ArtifactType
from notebooklm.types import ChatMode

from .auth import AuthService
from .config import Settings

_MISSING_ARTIFACT_ID_HINT = "no artifact_id returned"
_PENDING_VISIBILITY_TIMEOUT = 2.0
_PENDING_VISIBILITY_INTERVAL = 1.0
_DOWNLOAD_HINTS = {
    "audio": "download audio ./audio.mp3 --artifact-id {artifact_id}",
    "video": "download video ./video.mp4 --artifact-id {artifact_id}",
    "report": "download report ./report.md --artifact-id {artifact_id}",
    "infographic": "download infographic ./infographic.png --artifact-id {artifact_id}",
    "slide_deck": "download slide-deck ./deck.pdf --artifact-id {artifact_id}",
}


def _notebook_to_dict(notebook) -> dict[str, Any]:
    created_at = notebook.created_at.isoformat() if notebook.created_at else None
    return {
        "id": notebook.id,
        "title": notebook.title,
        "created_at": created_at,
        "is_owner": notebook.is_owner,
    }


def _topic_to_dict(topic) -> dict[str, Any]:
    return {
        "question": topic.question,
        "prompt": topic.prompt,
    }


def _source_to_dict(source) -> dict[str, Any]:
    created_at = source.created_at.isoformat() if source.created_at else None
    kind = getattr(source.kind, "value", str(source.kind))
    return {
        "id": source.id,
        "title": source.title,
        "url": source.url,
        "kind": kind,
        "created_at": created_at,
        "status": source.status,
    }


def _artifact_to_dict(artifact) -> dict[str, Any]:
    created_at = artifact.created_at.isoformat() if artifact.created_at else None
    kind = getattr(artifact.kind, "value", str(artifact.kind))
    return {
        "id": artifact.id,
        "title": artifact.title,
        "kind": kind,
        "status": artifact.status,
        "created_at": created_at,
        "url": artifact.url,
    }


def _note_to_dict(note) -> dict[str, Any]:
    created_at = note.created_at.isoformat() if note.created_at else None
    return {
        "id": note.id,
        "notebook_id": note.notebook_id,
        "title": note.title,
        "content": note.content,
        "created_at": created_at,
    }


def _shared_user_to_dict(user) -> dict[str, Any]:
    return {
        "email": user.email,
        "permission": user.permission.name.lower(),
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
    }


def _share_status_to_dict(status) -> dict[str, Any]:
    return {
        "notebook_id": status.notebook_id,
        "is_public": status.is_public,
        "access": status.access.name.lower(),
        "view_level": status.view_level.name.lower(),
        "share_url": status.share_url,
        "shared_users": [_shared_user_to_dict(user) for user in status.shared_users],
    }


def _status_to_dict(status) -> dict[str, Any]:
    return {
        "task_id": status.task_id,
        "status": status.status,
        "url": status.url,
        "error": status.error,
        "error_code": status.error_code,
        "metadata": status.metadata,
    }


def _normalize_generation_status(status) -> dict[str, Any]:
    error = status.error or ""
    if (
        not status.task_id
        and status.status == "failed"
        and _MISSING_ARTIFACT_ID_HINT in error.lower()
    ):
        metadata = dict(status.metadata or {})
        metadata.update(
            {
                "accepted_without_task_id": True,
                "poll_supported": False,
                "list_supported": True,
                "tracking_hint": "Use artifact list to find the generated artifact once it appears.",
                "upstream_status": status.status,
                "upstream_error": status.error,
                "upstream_error_code": status.error_code,
            }
        )
        return {
            "task_id": None,
            "status": "pending",
            "url": status.url,
            "error": None,
            "error_code": None,
            "metadata": metadata,
        }
    return _status_to_dict(status)


async def _list_artifacts_with_client(
    client: NotebookLMClient,
    notebook_id: str,
    artifact_kind: str | None,
) -> list[dict[str, Any]]:
    kind = ArtifactType(artifact_kind) if artifact_kind else None
    artifacts = await client.artifacts.list(notebook_id, kind)
    return [_artifact_to_dict(artifact) for artifact in artifacts]


def _next_steps_for_pending(
    artifact_kind: str | None,
    task_id: str | None,
    visible_artifact: dict[str, Any] | None,
) -> list[str]:
    steps: list[str] = []
    if task_id:
        steps.append(f"artifact wait {task_id}")
    if visible_artifact:
        artifact_id = visible_artifact["id"]
        steps.append(f"artifact get {artifact_id}")
        template = _DOWNLOAD_HINTS.get(artifact_kind or "")
        if template:
            steps.append(template.format(artifact_id=artifact_id))
        return steps
    if artifact_kind:
        steps.append(f"artifact list --kind {artifact_kind}")
    else:
        steps.append("artifact list")
    return steps


def _merge_pending_follow_up(payload: dict[str, Any], follow_up: dict[str, Any]) -> dict[str, Any]:
    merged = dict(payload)
    merged["pending_follow_up"] = follow_up
    visible_artifacts = list(follow_up.get("visible_artifacts", []))
    visible_artifact = follow_up.get("visible_artifact")
    metadata = dict(merged.get("metadata") or {})
    metadata["new_artifact_count"] = len(visible_artifacts)

    if visible_artifact:
        merged["artifact_id"] = visible_artifact["id"]
        merged["visible_artifact"] = visible_artifact
        merged["visible_artifacts"] = visible_artifacts
        metadata["matched_artifact_id"] = visible_artifact["id"]
        metadata["tracking_hint"] = (
            "A newly visible artifact was detected; use its artifact_id for follow-up commands."
        )
    else:
        metadata["tracking_hint"] = (
            "Submission was accepted, but no new artifact is visible yet; re-run artifact list or wait if a task_id becomes available."
        )

    merged["metadata"] = metadata
    return merged


async def _inspect_pending_artifacts_with_client(
    client: NotebookLMClient,
    notebook_id: str,
    artifact_kind: str | None,
    baseline_artifact_ids: list[str],
    timeout: float,
    interval: float,
    task_id: str | None,
) -> dict[str, Any]:
    baseline_ids = set(baseline_artifact_ids)
    elapsed = 0.0
    attempts = 0
    latest: list[dict[str, Any]] = []

    while True:
        attempts += 1
        latest = await _list_artifacts_with_client(client, notebook_id, artifact_kind)
        new_artifacts = [artifact for artifact in latest if artifact["id"] not in baseline_ids]
        if new_artifacts or elapsed >= timeout:
            visible_artifact = new_artifacts[0] if len(new_artifacts) == 1 else None
            return {
                "checked": True,
                "artifact_kind": artifact_kind,
                "artifact_visible": bool(new_artifacts),
                "visible_artifact": visible_artifact,
                "visible_artifacts": new_artifacts,
                "attempts": attempts,
                "next_steps": _next_steps_for_pending(artifact_kind, task_id, visible_artifact),
            }
        await asyncio.sleep(interval)
        elapsed += interval


def _enum_member(enum_cls, value: str | None):
    if value is None:
        return None
    return enum_cls[value.replace("-", "_").upper()]


def list_languages() -> list[dict[str, str]]:
    return [{"code": code, "name": name} for code, name in SUPPORTED_LANGUAGES.items()]


def get_language_name(language: str | None) -> str | None:
    if language is None:
        return None
    return SUPPORTED_LANGUAGES.get(language)


async def list_notebooks(settings: Settings) -> list[dict[str, Any]]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        notebooks = await client.notebooks.list()
    return [_notebook_to_dict(notebook) for notebook in notebooks]


async def get_notebook(settings: Settings, notebook_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        notebook = await client.notebooks.get(notebook_id)
    return _notebook_to_dict(notebook)


async def create_notebook(settings: Settings, title: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        notebook = await client.notebooks.create(title)
    return _notebook_to_dict(notebook)


async def rename_notebook(settings: Settings, notebook_id: str, title: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        notebook = await client.notebooks.rename(notebook_id, title)
    return _notebook_to_dict(notebook)


async def delete_notebook(settings: Settings, notebook_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        deleted = await client.notebooks.delete(notebook_id)
    return {"deleted": bool(deleted), "notebook_id": notebook_id}


async def get_notebook_summary(settings: Settings, notebook_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        summary = await client.notebooks.get_summary(notebook_id)
    return {"notebook_id": notebook_id, "summary": summary}


async def describe_notebook(settings: Settings, notebook_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        description = await client.notebooks.get_description(notebook_id)
    return {
        "notebook_id": notebook_id,
        "summary": description.summary,
        "suggested_topics": [_topic_to_dict(topic) for topic in description.suggested_topics],
    }


async def get_notebook_metadata(settings: Settings, notebook_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        metadata = await client.notebooks.get_metadata(notebook_id)
    return metadata.to_dict()


async def remove_notebook_from_recent(settings: Settings, notebook_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        await client.notebooks.remove_from_recent(notebook_id)
    return {"notebook_id": notebook_id, "removed_from_recent": True}


async def list_sources(settings: Settings, notebook_id: str) -> list[dict[str, Any]]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        sources = await client.sources.list(notebook_id)
    return [_source_to_dict(source) for source in sources]


async def add_source_url(settings: Settings, notebook_id: str, url: str, wait: bool, timeout: float = 30.0) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        source = await client.sources.add_url(notebook_id, url, wait=wait)
    return _source_to_dict(source)


# Known paywall / non-article domains — pre-check will skip these by default.
KNOWN_PAYWALL_DOMAINS = frozenset([
    "nytimes.com",
    "ft.com",
    "wsj.com",
    "economist.com",
    "theinformation.com",
    "fastcompany.com",
    "businessinsider.com",
    "bloomberg.com",
    "medium.com",          # paywalled articles common
    "substack.com",         # paywalled posts common
    "wired.com",
    "arstechnica.com",
])


def _classify_error(url: str, exc: Exception) -> tuple[str, str]:
    """Classify an add-source error into a category and user-facing message."""
    cause = exc
    while cause.__cause__:
        cause = cause.__cause__

    msg = str(cause).lower()

    # Timeout
    if "timeout" in msg or isinstance(cause, asyncio.TimeoutError):
        return "timeout", f"Request timed out (server slow or unreachable)"
    # Rate limit
    if "429" in msg or "rate limit" in msg:
        return "rate_limit", f"Rate limited by NotebookLM"
    # Duplicate / already exists (null result from server)
    if "null result" in msg:
        return "duplicate", f"URL already in notebook (or server rejected)"
    # Content / parse error
    if "parse" in msg or "empty" in msg:
        return "content", f"Server could not parse content"
    # Network
    if "network" in msg or "connection" in msg or "refused" in msg:
        return "unreachable", f"Could not reach URL"
    return "unknown", str(cause)


def _is_paywall_host(host: str) -> bool:
    """Check if host matches a paywall domain exactly or as a subdomain."""
    return any(host == d or host.endswith("." + d) for d in KNOWN_PAYWALL_DOMAINS)


async def _precheck_url(
    client: httpx.AsyncClient,
    url: str,
    skip_paywall: bool = True,
    skip_feed: bool = True,
) -> tuple[bool, str, str]:
    """Check a URL is reachable and likely an article (not RSS/paywall redirect).

    Returns:
        (should_skip, reason, final_url)
        should_skip=False means URL looks good.
        should_skip=True means reason explains why.
    """
    host = url.split("/")[2] if "://" in url else url

    # Skip known non-article feeds — controlled by skip_feed flag
    if skip_feed and any(x in url for x in ["/feeds/", "feedburner", "/rss", "atom.xml", "/comments/default"]):
        return True, "feed", url
    # Skip known paywall domains — controlled by skip_paywall flag
    if skip_paywall and _is_paywall_host(host):
        return True, "paywall", url

    try:
        response = await client.head(url, timeout=httpx.Timeout(5.0), follow_redirects=True)
        content_type = response.headers.get("content-type", "").lower()
        # Skip non-HTML
        if content_type and "text/html" not in content_type and "application/xhtml" not in content_type:
            return True, f"not_article ({content_type})", url
        # Skip non-200
        if response.status_code >= 400:
            return True, f"http_{response.status_code}", url
        return False, "", url
    except httpx.TimeoutException:
        # HEAD timeout — still try the full add (NotebookLM might have better access)
        return False, "", url
    except httpx.HTTPError as e:
        return True, f"unreachable ({e})", url


async def add_source_url_batch(
    settings: Settings,
    notebook_id: str,
    urls: list[str],
    wait: bool,
    max_concurrency: int = 5,
    skip_paywall: bool = True,
    skip_feed: bool = True,
    retry_count: int = 2,
    retry_timeouts: tuple[float, ...] = (10.0, 25.0),
) -> list[dict[str, Any]]:
    """Add multiple URLs with pre-check, smart retries, and error classification.

    Args:
        settings: Connection settings.
        notebook_id: Target notebook.
        urls: List of URLs to add.
        wait: Wait for each source to finish processing.
        max_concurrency: Max simultaneous requests.
        skip_paywall: Skip known paywall domains (default True).
        skip_feed: Skip RSS/Atom feed URLs (default True).
        retry_count: Max retries per URL on timeout (default 2).
        retry_timeouts: Timeout per retry attempt (default 10s, 25s).

    Returns:
        List of result dicts. Each dict always contains 'url' and 'status'.
        'status' is 'success', 'skipped', or 'error'.
        Skipped entries include 'reason'. Error entries include 'category' and 'message'.
    """
    http = httpx.AsyncClient(timeout=httpx.Timeout(5.0), follow_redirects=True)
    try:
        # --- Pre-check phase ---
        prechecked: list[tuple[str, bool, str]] = []
        for url in urls:
            skip, reason, _ = await _precheck_url(http, url, skip_paywall, skip_feed)
            prechecked.append((url, skip, reason))
    finally:
        await http.aclose()

    # Filter
    to_add = [(url, reason) for url, skip, reason in prechecked if not skip]
    skipped = [(url, reason) for url, skip, reason in prechecked if skip]

    # --- Add phase with bounded concurrency ---
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _add_one_with_retry(url: str) -> dict[str, Any]:
        async with semaphore:
            for attempt in range(retry_count + 1):
                timeout = retry_timeouts[attempt] if attempt < len(retry_timeouts) else retry_timeouts[-1]
                try:
                    result = await add_source_url(settings, notebook_id, url, wait=wait, timeout=timeout)
                    return {"url": url, "status": "success", **result}
                except Exception as exc:
                    if attempt == retry_count:
                        category, message = _classify_error(url, exc)
                        return {"url": url, "status": "error", "category": category, "message": message}
                    await asyncio.sleep(0.5 * (attempt + 1))  # brief back-off

    import_results = await asyncio.gather(*[_add_one_with_retry(url) for url, _ in to_add])

    # --- Assemble final results ---
    results: list[dict[str, Any]] = []
    for url, reason in skipped:
        results.append({"url": url, "status": "skipped", "reason": reason})
    results.extend(import_results)
    return results


async def add_source_file(
    settings: Settings,
    notebook_id: str,
    file_path: str,
    wait: bool,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        source = await client.sources.add_file(notebook_id, file_path, wait=wait)
    return _source_to_dict(source)


async def get_source(settings: Settings, notebook_id: str, source_id: str) -> dict[str, Any] | None:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        source = await client.sources.get(notebook_id, source_id)
    if source is None:
        return None
    return _source_to_dict(source)


async def wait_for_source(
    settings: Settings,
    notebook_id: str,
    source_id: str,
    initial_interval: float,
    max_interval: float,
    timeout: float,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        source = await client.sources.wait_until_ready(
            notebook_id,
            source_id,
            timeout=timeout,
            initial_interval=initial_interval,
            max_interval=max_interval,
        )
    return _source_to_dict(source)


async def add_source_text(
    settings: Settings,
    notebook_id: str,
    title: str,
    content: str,
    wait: bool,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        source = await client.sources.add_text(notebook_id, title, content, wait=wait)
    return _source_to_dict(source)


async def add_source_drive(
    settings: Settings,
    notebook_id: str,
    file_id: str,
    title: str,
    mime_type: str,
    wait: bool,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        source = await client.sources.add_drive(
            notebook_id,
            file_id,
            title,
            mime_type=mime_type,
            wait=wait,
        )
    return _source_to_dict(source)


async def rename_source(
    settings: Settings,
    notebook_id: str,
    source_id: str,
    title: str,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        source = await client.sources.rename(notebook_id, source_id, title)
    return _source_to_dict(source)


async def delete_source(settings: Settings, notebook_id: str, source_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        deleted = await client.sources.delete(notebook_id, source_id)
    return {"deleted": bool(deleted), "source_id": source_id}


async def refresh_source(settings: Settings, notebook_id: str, source_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        refreshed = await client.sources.refresh(notebook_id, source_id)
    return {"source_id": source_id, "refreshed": bool(refreshed)}


async def check_source_freshness(
    settings: Settings,
    notebook_id: str,
    source_id: str,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        is_fresh = await client.sources.check_freshness(notebook_id, source_id)
    return {"source_id": source_id, "is_fresh": bool(is_fresh), "is_stale": not bool(is_fresh)}


async def get_source_guide(settings: Settings, notebook_id: str, source_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        guide = await client.sources.get_guide(notebook_id, source_id)
    return {"source_id": source_id, **guide}


async def get_source_fulltext(settings: Settings, notebook_id: str, source_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        fulltext = await client.sources.get_fulltext(notebook_id, source_id)
    return {
        "source_id": fulltext.source_id,
        "title": fulltext.title,
        "kind": getattr(fulltext.kind, "value", str(fulltext.kind)),
        "content": fulltext.content,
        "char_count": fulltext.char_count,
        "url": fulltext.url,
    }


async def wait_for_sources(
    settings: Settings,
    notebook_id: str,
    source_ids: list[str],
    initial_interval: float,
    max_interval: float,
    timeout: float,
) -> list[dict[str, Any]]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        sources = await client.sources.wait_for_sources(
            notebook_id,
            source_ids,
            timeout=timeout,
            initial_interval=initial_interval,
            max_interval=max_interval,
        )
    return [_source_to_dict(source) for source in sources]


async def ask_question(
    settings: Settings,
    notebook_id: str,
    question: str,
    conversation_id: str | None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        result = await client.chat.ask(
            notebook_id,
            question,
            source_ids=source_ids,
            conversation_id=conversation_id,
        )
    return {
        "answer": result.answer,
        "conversation_id": result.conversation_id,
        "turn_number": result.turn_number,
        "is_follow_up": result.is_follow_up,
        "references": [asdict(reference) for reference in result.references],
    }


async def get_chat_history(
    settings: Settings,
    notebook_id: str,
    limit: int,
    conversation_id: str | None,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        resolved_conversation = conversation_id or await client.chat.get_conversation_id(notebook_id)
        history = await client.chat.get_history(
            notebook_id,
            limit=limit,
            conversation_id=resolved_conversation,
        )
    return {
        "notebook_id": notebook_id,
        "conversation_id": resolved_conversation,
        "count": len(history),
        "qa_pairs": [
            {"turn": index, "question": question, "answer": answer}
            for index, (question, answer) in enumerate(history, start=1)
        ],
    }


async def configure_chat(
    settings: Settings,
    notebook_id: str,
    mode: str | None,
    persona: str | None,
    response_length: str | None,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        if mode is not None:
            mode_map = {
                "default": ChatMode.DEFAULT,
                "learning-guide": ChatMode.LEARNING_GUIDE,
                "concise": ChatMode.CONCISE,
                "detailed": ChatMode.DETAILED,
            }
            await client.chat.set_mode(notebook_id, mode_map[mode])
        else:
            response_length_map = {
                "default": ChatResponseLength.DEFAULT,
                "longer": ChatResponseLength.LONGER,
                "shorter": ChatResponseLength.SHORTER,
            }
            goal = ChatGoal.CUSTOM if persona else None
            await client.chat.configure(
                notebook_id,
                goal=goal,
                response_length=response_length_map.get(response_length),
                custom_prompt=persona,
            )
    return {
        "notebook_id": notebook_id,
        "mode": mode,
        "persona": persona,
        "response_length": response_length,
    }


async def get_share_status(settings: Settings, notebook_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        status = await client.sharing.get_status(notebook_id)
    return _share_status_to_dict(status)


async def set_share_public(settings: Settings, notebook_id: str, public: bool) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        status = await client.sharing.set_public(notebook_id, public)
    return _share_status_to_dict(status)


async def set_share_view_level(settings: Settings, notebook_id: str, level: str) -> dict[str, Any]:
    level_map = {
        "full_notebook": ShareViewLevel.FULL_NOTEBOOK,
        "chat_only": ShareViewLevel.CHAT_ONLY,
    }
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        status = await client.sharing.set_view_level(notebook_id, level_map[level])
    return _share_status_to_dict(status)


async def add_share_user(
    settings: Settings,
    notebook_id: str,
    email: str,
    permission: str,
    notify: bool,
    message: str,
) -> dict[str, Any]:
    permission_map = {
        "viewer": SharePermission.VIEWER,
        "editor": SharePermission.EDITOR,
    }
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        await client.sharing.add_user(
            notebook_id,
            email,
            permission=permission_map[permission],
            notify=notify,
            welcome_message=message,
        )
    return {
        "notebook_id": notebook_id,
        "added_user": email,
        "permission": permission,
        "notified": notify,
    }


async def update_share_user(
    settings: Settings,
    notebook_id: str,
    email: str,
    permission: str,
) -> dict[str, Any]:
    permission_map = {
        "viewer": SharePermission.VIEWER,
        "editor": SharePermission.EDITOR,
    }
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        await client.sharing.update_user(notebook_id, email, permission_map[permission])
    return {
        "notebook_id": notebook_id,
        "updated_user": email,
        "permission": permission,
    }


async def remove_share_user(settings: Settings, notebook_id: str, email: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        await client.sharing.remove_user(notebook_id, email)
    return {
        "notebook_id": notebook_id,
        "removed_user": email,
    }


async def start_research(
    settings: Settings,
    notebook_id: str,
    query: str,
    search_source: str,
    mode: str,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        result = await client.research.start(notebook_id, query, search_source, mode)
    if result is None:
        return {
            "notebook_id": notebook_id,
            "query": query,
            "source": search_source,
            "mode": mode,
            "status": "failed",
        }
    return {
        **result,
        "source": search_source,
        "status": "started",
    }


async def get_research_status(settings: Settings, notebook_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        status = await client.research.poll(notebook_id)
    return {"notebook_id": notebook_id, **status}


async def wait_for_research(
    settings: Settings,
    notebook_id: str,
    timeout: int,
    interval: int,
    import_all: bool,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        elapsed = 0
        status = await client.research.poll(notebook_id)
        while status.get("status") == "in_progress" and elapsed < timeout:
            await asyncio.sleep(interval)
            elapsed += interval
            status = await client.research.poll(notebook_id)

        payload = {"notebook_id": notebook_id, **status}
        if status.get("status") != "completed":
            if status.get("status") == "no_research":
                payload["error"] = "No research running"
            elif status.get("status") == "in_progress":
                payload["status"] = "timeout"
                payload["error"] = f"Timed out after {timeout}s"
            return payload

        if import_all and status.get("task_id") and status.get("sources"):
            imported = await client.research.import_sources(
                notebook_id,
                status["task_id"],
                status["sources"],
            )
            payload["imported"] = len(imported)
            payload["imported_sources"] = imported
        return payload


async def add_research_source(
    settings: Settings,
    notebook_id: str,
    query: str,
    search_source: str,
    mode: str,
    wait: bool,
    import_all: bool,
) -> dict[str, Any]:
    started = await start_research(settings, notebook_id, query, search_source, mode)
    if not wait:
        return started
    return await wait_for_research(settings, notebook_id, timeout=300, interval=5, import_all=import_all)


async def list_artifacts(
    settings: Settings,
    notebook_id: str,
    kind: str | None,
) -> list[dict[str, Any]]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        return await _list_artifacts_with_client(client, notebook_id, kind)


async def inspect_pending_artifacts(
    settings: Settings,
    notebook_id: str,
    artifact_kind: str | None,
    baseline_artifact_ids: list[str] | None,
    timeout: float = _PENDING_VISIBILITY_TIMEOUT,
    interval: float = _PENDING_VISIBILITY_INTERVAL,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        return await _inspect_pending_artifacts_with_client(
            client=client,
            notebook_id=notebook_id,
            artifact_kind=artifact_kind,
            baseline_artifact_ids=list(baseline_artifact_ids or []),
            timeout=max(timeout, 0.0),
            interval=max(interval, 0.1),
            task_id=None,
        )


async def get_artifact(settings: Settings, notebook_id: str, artifact_id: str) -> dict[str, Any] | None:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        artifact = await client.artifacts.get(notebook_id, artifact_id)
    if artifact is None:
        return None
    return _artifact_to_dict(artifact)


async def rename_artifact(
    settings: Settings,
    notebook_id: str,
    artifact_id: str,
    title: str,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        await client.artifacts.rename(notebook_id, artifact_id, title)
        artifact = await client.artifacts.get(notebook_id, artifact_id)
    if artifact is None:
        return {"id": artifact_id, "title": title}
    return _artifact_to_dict(artifact)


async def delete_artifact(settings: Settings, notebook_id: str, artifact_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        deleted = await client.artifacts.delete(notebook_id, artifact_id)
    return {"deleted": bool(deleted), "artifact_id": artifact_id}


async def export_artifact(
    settings: Settings,
    notebook_id: str,
    artifact_id: str,
    export_type: str,
    title: str,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        result = await client.artifacts.export(
            notebook_id,
            artifact_id=artifact_id,
            title=title,
            export_type=ExportType[export_type.upper()],
        )
    payload = result if isinstance(result, dict) else {"result": result}
    payload["artifact_id"] = artifact_id
    payload["export_type"] = export_type
    return payload


async def generate_report(
    settings: Settings,
    notebook_id: str,
    report_format: str,
    custom_prompt: str | None,
    wait: bool = False,
    extra_instructions: str | None = None,
    language: str | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        baseline_artifacts = await _list_artifacts_with_client(client, notebook_id, "report")
        status = await client.artifacts.generate_report(
            notebook_id,
            report_format=ReportFormat(report_format),
            source_ids=source_ids,
            language=language or "en",
            custom_prompt=custom_prompt,
            extra_instructions=extra_instructions,
        )
        if wait and status.task_id:
            status = await client.artifacts.wait_for_completion(notebook_id, status.task_id)
        payload = _normalize_generation_status(status)
        if payload.get("status") == "pending" and payload.get("metadata", {}).get("accepted_without_task_id"):
            follow_up = await _inspect_pending_artifacts_with_client(
                client,
                notebook_id,
                "report",
                [artifact["id"] for artifact in baseline_artifacts],
                timeout=_PENDING_VISIBILITY_TIMEOUT,
                interval=_PENDING_VISIBILITY_INTERVAL,
                task_id=payload.get("task_id"),
            )
            payload = _merge_pending_follow_up(payload, follow_up)
    return payload


async def generate_audio(
    settings: Settings,
    notebook_id: str,
    instructions: str | None,
    wait: bool = False,
    language: str | None = None,
    source_ids: list[str] | None = None,
    audio_format: str | None = None,
    audio_length: str | None = None,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        baseline_artifacts = await _list_artifacts_with_client(client, notebook_id, "audio")
        status = await client.artifacts.generate_audio(
            notebook_id,
            source_ids=source_ids,
            language=language or "en",
            instructions=instructions,
            audio_format=_enum_member(AudioFormat, audio_format),
            audio_length=_enum_member(AudioLength, audio_length),
        )
        if wait and status.task_id:
            status = await client.artifacts.wait_for_completion(notebook_id, status.task_id)
        payload = _normalize_generation_status(status)
        if payload.get("status") == "pending" and payload.get("metadata", {}).get("accepted_without_task_id"):
            follow_up = await _inspect_pending_artifacts_with_client(
                client,
                notebook_id,
                "audio",
                [artifact["id"] for artifact in baseline_artifacts],
                timeout=_PENDING_VISIBILITY_TIMEOUT,
                interval=_PENDING_VISIBILITY_INTERVAL,
                task_id=payload.get("task_id"),
            )
            payload = _merge_pending_follow_up(payload, follow_up)
    return payload


async def poll_artifact(settings: Settings, notebook_id: str, task_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        status = await client.artifacts.poll_status(notebook_id, task_id)
    return _status_to_dict(status)


async def wait_for_artifact(
    settings: Settings,
    notebook_id: str,
    task_id: str,
    initial_interval: float,
    max_interval: float,
    timeout: float,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        status = await client.artifacts.wait_for_completion(
            notebook_id,
            task_id,
            initial_interval=initial_interval,
            max_interval=max_interval,
            timeout=timeout,
        )
    return _status_to_dict(status)


async def suggest_report_formats(settings: Settings, notebook_id: str) -> list[dict[str, Any]]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        suggestions = await client.artifacts.suggest_reports(notebook_id)
    return [asdict(suggestion) for suggestion in suggestions]


async def generate_video(
    settings: Settings,
    notebook_id: str,
    instructions: str | None,
    video_format: str | None,
    style: str | None,
    wait: bool = False,
    language: str | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        baseline_artifacts = await _list_artifacts_with_client(client, notebook_id, "video")
        status = await client.artifacts.generate_video(
            notebook_id,
            source_ids=source_ids,
            language=language or "en",
            instructions=instructions,
            video_format=_enum_member(VideoFormat, video_format),
            video_style=_enum_member(VideoStyle, style),
        )
        if wait and status.task_id:
            status = await client.artifacts.wait_for_completion(notebook_id, status.task_id)
        payload = _normalize_generation_status(status)
        if payload.get("status") == "pending" and payload.get("metadata", {}).get("accepted_without_task_id"):
            follow_up = await _inspect_pending_artifacts_with_client(
                client,
                notebook_id,
                "video",
                [artifact["id"] for artifact in baseline_artifacts],
                timeout=_PENDING_VISIBILITY_TIMEOUT,
                interval=_PENDING_VISIBILITY_INTERVAL,
                task_id=payload.get("task_id"),
            )
            payload = _merge_pending_follow_up(payload, follow_up)
    return payload


async def generate_cinematic_video(
    settings: Settings,
    notebook_id: str,
    instructions: str | None,
    wait: bool = False,
    language: str | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        baseline_artifacts = await _list_artifacts_with_client(client, notebook_id, "video")
        status = await client.artifacts.generate_cinematic_video(
            notebook_id,
            source_ids=source_ids,
            language=language or "en",
            instructions=instructions,
        )
        if wait and status.task_id:
            status = await client.artifacts.wait_for_completion(notebook_id, status.task_id)
        payload = _normalize_generation_status(status)
        if payload.get("status") == "pending" and payload.get("metadata", {}).get("accepted_without_task_id"):
            follow_up = await _inspect_pending_artifacts_with_client(
                client,
                notebook_id,
                "video",
                [artifact["id"] for artifact in baseline_artifacts],
                timeout=_PENDING_VISIBILITY_TIMEOUT,
                interval=_PENDING_VISIBILITY_INTERVAL,
                task_id=payload.get("task_id"),
            )
            payload = _merge_pending_follow_up(payload, follow_up)
    return payload


async def generate_slide_deck(
    settings: Settings,
    notebook_id: str,
    instructions: str | None,
    slide_format: str | None,
    length: str | None,
    wait: bool = False,
    language: str | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        baseline_artifacts = await _list_artifacts_with_client(client, notebook_id, "slide_deck")
        status = await client.artifacts.generate_slide_deck(
            notebook_id,
            source_ids=source_ids,
            language=language or "en",
            instructions=instructions,
            slide_format=_enum_member(SlideDeckFormat, slide_format),
            slide_length=_enum_member(SlideDeckLength, length),
        )
        if wait and status.task_id:
            status = await client.artifacts.wait_for_completion(notebook_id, status.task_id)
        payload = _normalize_generation_status(status)
        if payload.get("status") == "pending" and payload.get("metadata", {}).get("accepted_without_task_id"):
            follow_up = await _inspect_pending_artifacts_with_client(
                client,
                notebook_id,
                "slide_deck",
                [artifact["id"] for artifact in baseline_artifacts],
                timeout=_PENDING_VISIBILITY_TIMEOUT,
                interval=_PENDING_VISIBILITY_INTERVAL,
                task_id=payload.get("task_id"),
            )
            payload = _merge_pending_follow_up(payload, follow_up)
    return payload


async def revise_slide(
    settings: Settings,
    notebook_id: str,
    artifact_id: str,
    slide_index: int,
    prompt: str,
    wait: bool,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        status = await client.artifacts.revise_slide(
            notebook_id,
            artifact_id=artifact_id,
            slide_index=slide_index,
            prompt=prompt,
        )
        if wait and status.task_id:
            status = await client.artifacts.wait_for_completion(notebook_id, status.task_id)
    return _normalize_generation_status(status)


async def generate_infographic(
    settings: Settings,
    notebook_id: str,
    instructions: str | None,
    orientation: str | None,
    detail: str | None,
    style: str | None,
    wait: bool = False,
    language: str | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        baseline_artifacts = await _list_artifacts_with_client(client, notebook_id, "infographic")
        status = await client.artifacts.generate_infographic(
            notebook_id,
            source_ids=source_ids,
            language=language or "en",
            instructions=instructions,
            orientation=_enum_member(InfographicOrientation, orientation),
            detail_level=_enum_member(InfographicDetail, detail),
            style=_enum_member(InfographicStyle, style),
        )
        if wait and status.task_id:
            status = await client.artifacts.wait_for_completion(notebook_id, status.task_id)
        payload = _normalize_generation_status(status)
        if payload.get("status") == "pending" and payload.get("metadata", {}).get("accepted_without_task_id"):
            follow_up = await _inspect_pending_artifacts_with_client(
                client,
                notebook_id,
                "infographic",
                [artifact["id"] for artifact in baseline_artifacts],
                timeout=_PENDING_VISIBILITY_TIMEOUT,
                interval=_PENDING_VISIBILITY_INTERVAL,
                task_id=payload.get("task_id"),
            )
            payload = _merge_pending_follow_up(payload, follow_up)
    return payload


async def generate_quiz(
    settings: Settings,
    notebook_id: str,
    instructions: str | None,
    quantity: str | None,
    difficulty: str | None,
    wait: bool,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        status = await client.artifacts.generate_quiz(
            notebook_id,
            instructions=instructions,
            quantity=_enum_member(QuizQuantity, quantity),
            difficulty=_enum_member(QuizDifficulty, difficulty),
        )
        if wait and status.task_id:
            status = await client.artifacts.wait_for_completion(notebook_id, status.task_id)
    return _normalize_generation_status(status)


async def generate_flashcards(
    settings: Settings,
    notebook_id: str,
    instructions: str | None,
    quantity: str | None,
    difficulty: str | None,
    wait: bool,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        status = await client.artifacts.generate_flashcards(
            notebook_id,
            instructions=instructions,
            quantity=_enum_member(QuizQuantity, quantity),
            difficulty=_enum_member(QuizDifficulty, difficulty),
        )
        if wait and status.task_id:
            status = await client.artifacts.wait_for_completion(notebook_id, status.task_id)
    return _normalize_generation_status(status)


async def generate_data_table(
    settings: Settings,
    notebook_id: str,
    instructions: str | None,
    wait: bool,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        status = await client.artifacts.generate_data_table(
            notebook_id,
            instructions=instructions,
        )
        if wait and status.task_id:
            status = await client.artifacts.wait_for_completion(notebook_id, status.task_id)
    return _normalize_generation_status(status)


async def generate_mind_map(settings: Settings, notebook_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        payload = await client.artifacts.generate_mind_map(notebook_id)
    return {
        "kind": "mind_map",
        "note_id": payload.get("note_id"),
        "mind_map": payload.get("mind_map"),
    }


async def download_report(
    settings: Settings,
    notebook_id: str,
    output_path: str,
    artifact_id: str | None,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        path = await client.artifacts.download_report(notebook_id, output_path, artifact_id=artifact_id)
    return {"output_path": path}


async def _extract_audio_url(
    client: NotebookLMClient,
    notebook_id: str,
    artifact_id: str | None,
) -> tuple[str, str]:
    """Extract signed audio URL from notebook artifact.

    Returns:
        Tuple of (artifact_id, signed_url).
    """
    from notebooklm.rpc import ArtifactStatus, ArtifactTypeCode

    artifacts_data = await client.artifacts._list_raw(notebook_id)
    audio_candidates = [
        a
        for a in artifacts_data
        if isinstance(a, list)
        and len(a) > 4
        and a[2] == ArtifactTypeCode.AUDIO.value
        and a[4] == ArtifactStatus.COMPLETED.value
    ]

    if artifact_id:
        audio_art = next((a for a in audio_candidates if a[0] == artifact_id), None)
        if not audio_art:
            raise ValueError(f"Audio artifact {artifact_id} not found or not ready")
    else:
        audio_art = audio_candidates[0] if audio_candidates else None

    if not audio_art:
        raise ValueError("No completed audio artifacts found")

    # Extract URL from metadata[6][5]
    if len(audio_art) <= 6:
        raise ValueError("Invalid audio artifact structure")
    metadata = audio_art[6]
    if not isinstance(metadata, list) or len(metadata) <= 5:
        raise ValueError("Invalid audio metadata structure")

    media_list = metadata[5]
    if not isinstance(media_list, list) or len(media_list) == 0:
        raise ValueError("No media URLs found in audio artifact")

    # Prefer audio/mp4, fall back to first URL
    url = None
    for item in media_list:
        if isinstance(item, list) and len(item) > 2 and item[2] == "audio/mp4":
            url = item[0]
            break

    if not url and isinstance(media_list[0], list):
        url = media_list[0][0]

    if not url:
        raise ValueError("Could not extract audio download URL")
    return audio_art[0], url


async def _extract_infographic_url(
    client: NotebookLMClient,
    notebook_id: str,
    artifact_id: str | None,
) -> tuple[str, str]:
    """Extract signed infographic URL from notebook artifact.

    Returns:
        Tuple of (artifact_id, signed_url).
    """
    from notebooklm.rpc import ArtifactStatus, ArtifactTypeCode

    artifacts_data = await client.artifacts._list_raw(notebook_id)
    info_candidates = [
        a
        for a in artifacts_data
        if isinstance(a, list)
        and len(a) > 4
        and a[2] == ArtifactTypeCode.INFOGRAPHIC.value
        and a[4] == ArtifactStatus.COMPLETED.value
    ]

    if artifact_id:
        info_art = next((i for i in info_candidates if i[0] == artifact_id), None)
        if not info_art:
            raise ValueError(f"Infographic artifact {artifact_id} not found or not ready")
    else:
        info_art = info_candidates[0] if info_candidates else None

    if not info_art:
        raise ValueError("No completed infographic artifacts found")

    # Extract URL from the nested metadata structure
    url = None
    for item in reversed(info_art):
        if isinstance(item, list) and len(item) > 0 and isinstance(item[0], list):
            if len(item) > 2 and isinstance(item[2], list) and len(item[2]) > 0:
                content_list = item[2]
                if isinstance(content_list[0], list) and len(content_list[0]) > 1:
                    img_data = content_list[0][1]
                    if (
                        isinstance(img_data, list)
                        and len(img_data) > 0
                        and isinstance(img_data[0], str)
                        and img_data[0].startswith("http")
                    ):
                        url = img_data[0]
                        break

    if not url:
        raise ValueError("Could not extract infographic download URL")
    return info_art[0], url


async def _extract_slide_deck_url(
    client: NotebookLMClient,
    notebook_id: str,
    artifact_id: str | None,
    output_format: str,
) -> tuple[str, str]:
    """Extract signed slide deck URL from notebook artifact.

    Returns:
        Tuple of (artifact_id, signed_url).
    """
    from notebooklm.rpc import ArtifactStatus, ArtifactTypeCode

    artifacts_data = await client.artifacts._list_raw(notebook_id)
    slide_candidates = [
        a
        for a in artifacts_data
        if isinstance(a, list)
        and len(a) > 4
        and a[2] == ArtifactTypeCode.SLIDE_DECK.value
        and a[4] == ArtifactStatus.COMPLETED.value
    ]

    if artifact_id:
        slide_art = next((s for s in slide_candidates if s[0] == artifact_id), None)
        if not slide_art:
            raise ValueError(f"Slide deck artifact {artifact_id} not found or not ready")
    else:
        slide_art = slide_candidates[0] if slide_candidates else None

    if not slide_art:
        raise ValueError("No completed slide deck artifacts found")

    # Extract URL from metadata[16]: [config, title, slides_list, pdf_url, pptx_url]
    if len(slide_art) <= 16:
        raise ValueError("Invalid slide deck artifact structure")
    metadata = slide_art[16]
    if not isinstance(metadata, list):
        raise ValueError("Invalid slide deck metadata structure")

    if output_format == "pptx":
        if len(metadata) < 5:
            raise ValueError("PPTX URL not available in artifact data")
        url = metadata[4]
    else:
        if len(metadata) < 4:
            raise ValueError("PDF URL not available in artifact data")
        url = metadata[3]

    if not isinstance(url, str) or not url.startswith("http"):
        raise ValueError(f"Could not find {output_format.upper()} download URL")
    return slide_art[0], url


async def _build_cookie_jar(settings: Settings) -> httpx.Cookies:
    """Build httpx.Cookies from CDP browser cookies."""
    raw_cookies = await AuthService(settings).load_cookies()
    cookie_jar = httpx.Cookies()
    for cookie in raw_cookies:
        domain = cookie.get("domain", "")
        name = cookie.get("name", "")
        value = cookie.get("value", "")
        if name and value:
            cookie_jar.set(name, value, domain=domain if domain else None)
    return cookie_jar


async def download_audio(
    settings: Settings,
    notebook_id: str,
    output_path: str,
    artifact_id: str | None,
) -> dict[str, Any]:
    auth_tokens = await AuthService(settings).notebooklm_auth()
    cookie_jar = await _build_cookie_jar(settings)

    async with NotebookLMClient(auth_tokens) as client:
        resolved_artifact_id, signed_url = await _extract_audio_url(client, notebook_id, artifact_id)

    downloaded = await _stream_download(signed_url, output_path, cookie_jar)
    return {"output_path": downloaded}


async def _extract_video_url(
    client: NotebookLMClient,
    notebook_id: str,
    artifact_id: str | None,
) -> tuple[str, str]:
    """Extract signed video URL from notebook artifact using NotebookLMClient API.

    Returns:
        Tuple of (artifact_id, signed_url).
    Raises:
        ArtifactNotReadyError: If video not found or not ready.
    """
    from notebooklm.rpc import ArtifactStatus, ArtifactTypeCode

    artifacts_data = await client.artifacts._list_raw(notebook_id)
    video_candidates = [
        a
        for a in artifacts_data
        if isinstance(a, list)
        and len(a) > 4
        and a[2] == ArtifactTypeCode.VIDEO.value
        and a[4] == ArtifactStatus.COMPLETED.value
    ]

    if artifact_id:
        video_art = next((v for v in video_candidates if v[0] == artifact_id), None)
        if not video_art:
            raise ValueError(f"Video artifact {artifact_id} not found or not ready")
    else:
        video_art = video_candidates[0] if video_candidates else None

    if not video_art:
        raise ValueError("No completed video artifacts found")

    # Extract URL from metadata[8]
    if len(video_art) <= 8:
        raise ValueError("Invalid video artifact structure")
    metadata = video_art[8]
    if not isinstance(metadata, list):
        raise ValueError("Invalid video metadata structure")

    media_list = None
    for item in metadata:
        if (
            isinstance(item, list)
            and len(item) > 0
            and isinstance(item[0], list)
            and len(item[0]) > 0
            and isinstance(item[0][0], str)
            and item[0][0].startswith("http")
        ):
            media_list = item
            break

    if not media_list:
        raise ValueError("No media URLs found in video artifact")

    return video_art[0], media_list[0][0]


async def _stream_download(url: str, output_path: str, cookies: httpx.Cookies, timeout: float = 300.0) -> str:
    """Stream-download a file using httpx with explicit cookie jar.

    This replaces notebooklm_py's _download_url which requires storage_state.json.
    """
    import logging
    from pathlib import Path

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Download URL must use HTTPS: {url[:80]}")
    trusted = (".google.com", ".googleusercontent.com", ".googleapis.com")
    if not any(parsed.netloc == d.lstrip(".") or parsed.netloc.endswith(d) for d in trusted):
        raise ValueError(f"Untrusted download domain: {parsed.netloc}")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(
        cookies=cookies,
        timeout=httpx.Timeout(timeout, connect=10.0),
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        },
    ) as http:
        async with http.stream("GET", url) as response:
            response.raise_for_status()
            with open(output_file, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    f.write(chunk)

    return str(output_file)


async def download_video(
    settings: Settings,
    notebook_id: str,
    output_path: str,
    artifact_id: str | None,
) -> dict[str, Any]:
    auth_tokens = await AuthService(settings).notebooklm_auth()
    cookie_jar = await _build_cookie_jar(settings)

    async with NotebookLMClient(auth_tokens) as client:
        resolved_artifact_id, signed_url = await _extract_video_url(client, notebook_id, artifact_id)

    downloaded = await _stream_download(signed_url, output_path, cookie_jar)
    return {"output_path": downloaded}


async def download_slide_deck(
    settings: Settings,
    notebook_id: str,
    output_path: str,
    artifact_id: str | None,
    output_format: str,
) -> dict[str, Any]:
    auth_tokens = await AuthService(settings).notebooklm_auth()
    cookie_jar = await _build_cookie_jar(settings)

    async with NotebookLMClient(auth_tokens) as client:
        resolved_artifact_id, signed_url = await _extract_slide_deck_url(
            client, notebook_id, artifact_id, output_format
        )

    downloaded = await _stream_download(signed_url, output_path, cookie_jar)
    return {"output_path": downloaded}


async def download_infographic(
    settings: Settings,
    notebook_id: str,
    output_path: str,
    artifact_id: str | None,
) -> dict[str, Any]:
    auth_tokens = await AuthService(settings).notebooklm_auth()
    cookie_jar = await _build_cookie_jar(settings)

    async with NotebookLMClient(auth_tokens) as client:
        resolved_artifact_id, signed_url = await _extract_infographic_url(
            client, notebook_id, artifact_id
        )

    downloaded = await _stream_download(signed_url, output_path, cookie_jar)
    return {"output_path": downloaded}


async def download_quiz(
    settings: Settings,
    notebook_id: str,
    output_path: str,
    artifact_id: str | None,
    output_format: str,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        path = await client.artifacts.download_quiz(
            notebook_id,
            output_path,
            artifact_id=artifact_id,
            output_format=output_format,
        )
    return {"output_path": path}


async def download_flashcards(
    settings: Settings,
    notebook_id: str,
    output_path: str,
    artifact_id: str | None,
    output_format: str,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        path = await client.artifacts.download_flashcards(
            notebook_id,
            output_path,
            artifact_id=artifact_id,
            output_format=output_format,
        )
    return {"output_path": path}


async def download_data_table(
    settings: Settings,
    notebook_id: str,
    output_path: str,
    artifact_id: str | None,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        path = await client.artifacts.download_data_table(
            notebook_id,
            output_path,
            artifact_id=artifact_id,
        )
    return {"output_path": path}


async def download_mind_map(
    settings: Settings,
    notebook_id: str,
    output_path: str,
    artifact_id: str | None,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        path = await client.artifacts.download_mind_map(
            notebook_id,
            output_path,
            artifact_id=artifact_id,
        )
    return {"output_path": path}


async def get_output_language(settings: Settings) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        language = await client.settings.get_output_language()
    return {"language": language, "name": get_language_name(language)}


async def set_output_language(settings: Settings, language: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        result = await client.settings.set_output_language(language)
    language_code = result or language
    return {"language": language_code, "name": get_language_name(language_code)}


async def list_notes(settings: Settings, notebook_id: str) -> list[dict[str, Any]]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        notes = await client.notes.list(notebook_id)
    return [_note_to_dict(note) for note in notes]


async def get_note(settings: Settings, notebook_id: str, note_id: str) -> dict[str, Any] | None:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        note = await client.notes.get(notebook_id, note_id)
    if note is None:
        return None
    return _note_to_dict(note)


async def create_note(
    settings: Settings,
    notebook_id: str,
    title: str,
    content: str,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        note = await client.notes.create(notebook_id, title=title, content=content)
    return _note_to_dict(note)


async def save_note(
    settings: Settings,
    notebook_id: str,
    note_id: str,
    content: str,
    title: str | None,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        existing = await client.notes.get(notebook_id, note_id)
        resolved_title = title if title is not None else (existing.title if existing else "")
        await client.notes.update(notebook_id, note_id, content, resolved_title)
        note = await client.notes.get(notebook_id, note_id)
    if note is None:
        return {
            "id": note_id,
            "notebook_id": notebook_id,
            "title": resolved_title,
            "content": content,
            "created_at": None,
        }
    return _note_to_dict(note)


async def rename_note(
    settings: Settings,
    notebook_id: str,
    note_id: str,
    title: str,
) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        existing = await client.notes.get(notebook_id, note_id)
        content = existing.content if existing else ""
        await client.notes.update(notebook_id, note_id, content, title)
        note = await client.notes.get(notebook_id, note_id)
    if note is None:
        return {
            "id": note_id,
            "notebook_id": notebook_id,
            "title": title,
            "content": content,
            "created_at": None,
        }
    return _note_to_dict(note)


async def delete_note(settings: Settings, notebook_id: str, note_id: str) -> dict[str, Any]:
    auth = await AuthService(settings).notebooklm_auth()
    async with NotebookLMClient(auth) as client:
        deleted = await client.notes.delete(notebook_id, note_id)
    return {"deleted": bool(deleted), "note_id": note_id}
