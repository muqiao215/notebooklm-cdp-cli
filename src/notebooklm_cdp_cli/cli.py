from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4
from typing import Any

import click
from click.core import ParameterSource

from .auth import AuthService
from .browser import BrowserInspector, attach_browser
from .config import Settings
from .doctor import run_doctor
from .notebooklm_ops import (
    add_research_source,
    add_share_user,
    add_source_drive,
    add_source_file,
    add_source_text,
    add_source_url,
    add_source_url_batch,
    ask_question,
    configure_chat,
    create_notebook,
    create_note,
    delete_artifact,
    delete_notebook,
    delete_note,
    delete_source,
    describe_notebook,
    download_audio,
    download_data_table,
    download_flashcards,
    download_infographic,
    download_mind_map,
    download_report,
    download_quiz,
    download_slide_deck,
    download_video,
    export_artifact,
    check_source_freshness,
    generate_audio,
    generate_cinematic_video,
    generate_data_table,
    generate_flashcards,
    generate_infographic,
    generate_mind_map,
    generate_report,
    generate_quiz,
    generate_slide_deck,
    generate_video,
    get_artifact,
    get_chat_history,
    get_language_name,
    get_note,
    get_notebook,
    get_notebook_metadata,
    get_notebook_summary,
    get_output_language,
    get_research_status,
    get_share_status,
    get_source,
    get_source_fulltext,
    get_source_guide,
    inspect_pending_artifacts,
    list_artifacts,
    list_languages,
    list_notes,
    list_notebooks,
    list_sources,
    poll_artifact,
    refresh_source,
    remove_notebook_from_recent,
    remove_share_user,
    rename_artifact,
    rename_note,
    rename_notebook,
    rename_source,
    revise_slide,
    save_note,
    set_share_public,
    set_share_view_level,
    set_output_language,
    suggest_report_formats,
    update_share_user,
    wait_for_artifact,
    wait_for_research,
    wait_for_source,
    wait_for_sources,
)
from .state import (
    clear_context,
    get_browser_config,
    get_config_path,
    get_current_conversation,
    get_current_notebook,
    get_context_path,
    get_home_dir,
    get_pending_submission,
    load_context,
    list_pending_submissions,
    set_current_conversation,
    set_current_notebook,
    upsert_pending_submission,
)


def _run(coro):
    return asyncio.run(coro)


def _settings_from_ctx(ctx: click.Context) -> Settings:
    return Settings(
        host=ctx.obj["host"],
        port=ctx.obj["port"],
        timeout=ctx.obj["timeout"],
    )


def _emit(data: Any, json_output: bool) -> None:
    if json_output:
        click.echo(json.dumps(data, indent=2, sort_keys=True))
        return
    if isinstance(data, dict):
        for key, value in data.items():
            click.echo(f"{key}: {value}")
        return
    click.echo(str(data))


def _require_notebook(notebook_id: str | None) -> str:
    resolved = notebook_id or get_current_notebook()
    if not resolved:
        raise click.ClickException("No notebook specified and no current notebook is set.")
    return resolved


async def check_auth(settings: Settings) -> dict[str, Any]:
    status = await AuthService(settings).status()
    payload = status.to_dict()
    payload["has_saved_browser"] = bool(get_browser_config())
    payload["tokens_present"] = status.tokens is not None
    return payload


async def bootstrap_login(
    settings: Settings,
    user_data_dir: str | None,
    validate: bool,
) -> dict[str, Any]:
    browser = attach_browser(user_data_dir=user_data_dir, host=None, port=None)
    payload: dict[str, Any] = {
        "mode": "attach-first",
        "attached": True,
        "validated": False,
        "browser": browser,
        "next_steps": ["run auth check", "run notebook list"],
    }
    if validate:
        auth_status = await AuthService(Settings.from_env()).status()
        payload["validated"] = auth_status.ok
        payload["auth"] = auth_status.to_dict()
    return payload


ARTIFACT_FORMAT_CHOICES = click.Choice(["brief", "explainer", "cinematic"], case_sensitive=False)
REPORT_FORMAT_CHOICES = click.Choice(
    ["briefing_doc", "study_guide", "blog_post", "custom"],
    case_sensitive=False,
)
VIDEO_STYLE_CHOICES = click.Choice(
    [
        "auto_select",
        "custom",
        "classic",
        "whiteboard",
        "kawaii",
        "anime",
        "watercolor",
        "retro_print",
        "heritage",
        "paper_craft",
    ],
    case_sensitive=False,
)
SLIDE_FORMAT_CHOICES = click.Choice(["detailed_deck", "presenter_slides"], case_sensitive=False)
SLIDE_LENGTH_CHOICES = click.Choice(["default", "short"], case_sensitive=False)
INFOGRAPHIC_ORIENTATION_CHOICES = click.Choice(["landscape", "portrait", "square"], case_sensitive=False)
INFOGRAPHIC_DETAIL_CHOICES = click.Choice(["concise", "standard", "detailed"], case_sensitive=False)
INFOGRAPHIC_STYLE_CHOICES = click.Choice(
    [
        "auto_select",
        "sketch_note",
        "professional",
        "bento_grid",
        "editorial",
        "instructional",
        "bricks",
        "clay",
        "anime",
        "kawaii",
        "scientific",
    ],
    case_sensitive=False,
)
QUIZ_QUANTITY_CHOICES = click.Choice(["fewer", "standard"], case_sensitive=False)
QUIZ_DIFFICULTY_CHOICES = click.Choice(["easy", "medium", "hard"], case_sensitive=False)
INTERACTIVE_DOWNLOAD_FORMAT_CHOICES = click.Choice(["json", "markdown", "html"], case_sensitive=False)
SLIDE_DOWNLOAD_FORMAT_CHOICES = click.Choice(["pdf", "pptx"], case_sensitive=False)
EXPORT_TYPE_CHOICES = click.Choice(["docs", "sheets"], case_sensitive=False)
SHARE_PERMISSION_CHOICES = click.Choice(["editor", "viewer"], case_sensitive=False)
SHARE_VIEW_LEVEL_CHOICES = click.Choice(["full", "chat"], case_sensitive=False)
RESEARCH_SOURCE_CHOICES = click.Choice(["web", "drive"], case_sensitive=False)
RESEARCH_MODE_CHOICES = click.Choice(["fast", "deep"], case_sensitive=False)
CHAT_MODE_CHOICES = click.Choice(["default", "learning-guide", "concise", "detailed"], case_sensitive=False)
CHAT_RESPONSE_LENGTH_CHOICES = click.Choice(["default", "longer", "shorter"], case_sensitive=False)
AUDIO_FORMAT_CHOICES = click.Choice(["deep-dive", "brief", "critique", "debate"], case_sensitive=False)
AUDIO_LENGTH_CHOICES = click.Choice(["short", "default", "long"], case_sensitive=False)

_PENDING_INSPECT_TIMEOUT = 4.0
_PENDING_INSPECT_INTERVAL = 1.0
_DOWNLOAD_COMMANDS = {
    "report": ("report", "./report.md"),
    "audio": ("audio", "./audio.mp3"),
    "video": ("video", "./video.mp4"),
    "slide_deck": ("slide-deck", "./slides.pdf"),
    "infographic": ("infographic", "./infographic.png"),
    "quiz": ("quiz", "./quiz.json"),
    "flashcards": ("flashcards", "./flashcards.json"),
    "data_table": ("data-table", "./data-table.csv"),
}


def _capture_artifact_baseline(
    settings: Settings,
    notebook_id: str,
    artifact_kind: str | None,
    inspect_pending: bool,
) -> list[str]:
    del inspect_pending
    if artifact_kind is None:
        return []
    try:
        artifacts = _run(list_artifacts(settings, notebook_id, artifact_kind))
    except Exception:
        return []
    return [artifact["id"] for artifact in artifacts if artifact.get("id")]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _prompt_fingerprint(
    *,
    instructions: str | None,
    custom_prompt: str | None,
    extra_instructions: str | None,
    baseline_artifact_ids: list[str],
) -> str:
    payload = {
        "instructions": instructions,
        "custom_prompt": custom_prompt,
        "extra_instructions": extra_instructions,
        "baseline_artifact_ids": list(baseline_artifact_ids),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _record_pending_submission(
    payload: dict[str, Any],
    *,
    notebook_id: str,
    artifact_kind: str,
    submission_kind: str,
    baseline_artifact_ids: list[str],
    language: str | None,
    source_ids: list[str],
    format_value: str | None = None,
    style: str | None = None,
    detail: str | None = None,
    length: str | None = None,
    orientation: str | None = None,
    instructions: str | None = None,
    custom_prompt: str | None = None,
    extra_instructions: str | None = None,
) -> dict[str, Any]:
    if payload.get("status") != "pending":
        return payload

    submitted_at = _utcnow_iso()
    artifact_id = payload.get("artifact_id")
    entry = {
        "submission_id": uuid4().hex,
        "notebook_id": notebook_id,
        "artifact_kind": artifact_kind,
        "submission_kind": submission_kind,
        "submitted_at": submitted_at,
        "task_id": payload.get("task_id"),
        "accepted_without_task_id": bool((payload.get("metadata") or {}).get("accepted_without_task_id")),
        "source_ids": list(source_ids),
        "language": language,
        "format": format_value,
        "style": style,
        "detail": detail,
        "length": length,
        "orientation": orientation,
        "prompt_fingerprint": _prompt_fingerprint(
            instructions=instructions,
            custom_prompt=custom_prompt,
            extra_instructions=extra_instructions,
            baseline_artifact_ids=baseline_artifact_ids,
        ),
        "baseline_artifact_ids": list(baseline_artifact_ids),
        "resolution_status": "resolved" if artifact_id else "pending",
    }
    if artifact_id:
        entry["resolved_artifact_id"] = artifact_id
        entry["resolved_at"] = submitted_at

    upsert_pending_submission(entry)

    enriched = dict(payload)
    enriched["submission_id"] = entry["submission_id"]
    enriched["resolution_status"] = entry["resolution_status"]
    next_steps = list(enriched.get("next_steps") or [])
    for step in (f"artifact resolve-pending {entry['submission_id']}", "artifact pending"):
        if step not in next_steps:
            next_steps.append(step)
    if next_steps:
        enriched["next_steps"] = next_steps
    return enriched


def _filter_submission_records(
    submissions: list[dict[str, Any]],
    *,
    notebook_id: str,
    artifact_kind: str | None,
) -> list[dict[str, Any]]:
    return [
        submission
        for submission in submissions
        if submission.get("notebook_id") == notebook_id
        and (artifact_kind is None or submission.get("artifact_kind") == artifact_kind)
    ]


def _rank_submission_candidates(
    submission: dict[str, Any],
    artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    artifact_kind = submission.get("artifact_kind")
    submitted_at = _parse_timestamp(submission.get("submitted_at"))
    baseline_ids = set(submission.get("baseline_artifact_ids", []))
    ranked: list[tuple[int, datetime, str, dict[str, Any]]] = []

    for artifact in artifacts:
        artifact_id = artifact.get("id")
        if not artifact_id or artifact.get("kind") != artifact_kind or artifact_id in baseline_ids:
            continue
        created_at = _parse_timestamp(artifact.get("created_at"))
        strong_candidate = bool(
            created_at is not None and submitted_at is not None and created_at > submitted_at
        )
        if strong_candidate:
            reasons = [
                "same_notebook_and_kind",
                "created_after_submission",
                "not_in_baseline",
            ]
        elif created_at is None:
            reasons = [
                "same_notebook_and_kind",
                "created_at_missing",
                "not_in_baseline",
            ]
        else:
            reasons = [
                "same_notebook_and_kind",
                "created_not_after_submission",
                "not_in_baseline",
            ]

        sort_created_at = created_at or datetime.min.replace(tzinfo=timezone.utc)
        ranked.append(
            (
                1 if strong_candidate else 0,
                sort_created_at,
                artifact_id,
                {
                    "artifact": artifact,
                    "strong_candidate": strong_candidate,
                    "seconds_after_submission": (
                        int((created_at - submitted_at).total_seconds())
                        if strong_candidate and created_at is not None and submitted_at is not None
                        else None
                    ),
                    "reasons": reasons,
                },
            )
        )

    ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return [candidate for *_prefix, candidate in ranked]


def _pending_next_steps(artifact_kind: str, task_id: str | None, artifact_id: str | None) -> list[str]:
    download_command, example_path = _DOWNLOAD_COMMANDS.get(
        artifact_kind,
        (artifact_kind.replace("_", "-"), "./artifact.out"),
    )
    if artifact_id:
        return [
            f"artifact get {artifact_id}",
            f"download {download_command} {example_path} --artifact-id {artifact_id}",
        ]
    if task_id:
        return [
            f"artifact wait {task_id}",
            f"artifact list --kind {artifact_kind}",
        ]
    return [
        f"artifact list --kind {artifact_kind}",
        f"download {download_command} {example_path} --artifact-id <artifact-id>",
    ]


def _pending_message(artifact_kind: str, task_id: str | None, artifact_id: str | None) -> str:
    readable_kind = artifact_kind.replace("_", " ")
    if artifact_id:
        return f"Generation is still pending, but {readable_kind} artifact {artifact_id} is already visible."
    if task_id:
        return f"Generation is still pending. Wait on task {task_id} or re-list {readable_kind} artifacts."
    return (
        f"Generation was accepted without a task ID. No new {readable_kind} artifact is visible yet."
    )


def _finalize_pending_generation_payload(
    settings: Settings,
    notebook_id: str,
    artifact_kind: str | None,
    baseline_artifact_ids: list[str] | None,
    payload: dict[str, Any],
    inspect_pending: bool,
) -> dict[str, Any]:
    if not inspect_pending or artifact_kind is None or payload.get("status") != "pending":
        return payload

    follow_up: dict[str, Any] = {
        "checked": False,
        "artifact_kind": artifact_kind,
        "artifact_visible": False,
        "visible_artifacts": [],
    }
    if baseline_artifact_ids is None:
        follow_up["inspect_error"] = "Artifact inspection baseline was unavailable."
    else:
        try:
            follow_up = _run(
                inspect_pending_artifacts(
                    settings,
                    notebook_id,
                    artifact_kind,
                    baseline_artifact_ids,
                    timeout=_PENDING_INSPECT_TIMEOUT,
                    interval=_PENDING_INSPECT_INTERVAL,
                )
            )
        except Exception as exc:
            follow_up.update({"inspect_error": str(exc)})

    visible_artifact = follow_up.get("visible_artifact")
    artifact_id = visible_artifact.get("id") if isinstance(visible_artifact, dict) else None
    follow_up["next_steps"] = _pending_next_steps(artifact_kind, payload.get("task_id"), artifact_id)
    payload["pending_follow_up"] = follow_up
    payload["next_steps"] = follow_up["next_steps"]
    payload["message"] = _pending_message(artifact_kind, payload.get("task_id"), artifact_id)

    metadata = dict(payload.get("metadata") or {})
    if artifact_id:
        payload["artifact_id"] = artifact_id
        payload["visible_artifact"] = visible_artifact
        metadata["tracking_hint"] = (
            f"Artifact {artifact_id} is already visible. Use artifact get or download with --artifact-id."
        )
    elif payload.get("task_id"):
        metadata["tracking_hint"] = (
            f"Use artifact wait {payload['task_id']} or artifact list --kind {artifact_kind}."
        )
    else:
        metadata["tracking_hint"] = (
            f"No task_id was returned. Re-run artifact list --kind {artifact_kind} until the artifact appears."
        )
    payload["metadata"] = metadata
    return payload
@click.group()
@click.option("--host", default=None, help="Chrome remote debugging host")
@click.option("--port", default=None, type=int, help="Chrome remote debugging port")
@click.option("--timeout", default=None, type=float, help="HTTP timeout in seconds")
@click.pass_context
def cli(ctx: click.Context, host: str | None, port: int | None, timeout: float | None) -> None:
    env_settings = Settings.from_env()
    ctx.ensure_object(dict)
    ctx.obj["explicit_host"] = host if ctx.get_parameter_source("host") is not ParameterSource.DEFAULT else None
    ctx.obj["explicit_port"] = port if ctx.get_parameter_source("port") is not ParameterSource.DEFAULT else None
    ctx.obj["host"] = host or env_settings.host
    ctx.obj["port"] = port or env_settings.port
    ctx.obj["timeout"] = timeout or env_settings.timeout


@cli.group("browser")
def browser_group() -> None:
    """Browser discovery commands."""


@browser_group.command("status")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def browser_status(ctx: click.Context, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    status = _run(BrowserInspector(settings).status())
    _emit(status.to_dict(), json_output)


@browser_group.command("attach")
@click.option("--user-data-dir", default=None, help="Chrome user-data-dir containing DevToolsActivePort")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def browser_attach(
    ctx: click.Context,
    user_data_dir: str | None,
    json_output: bool,
) -> None:
    browser = attach_browser(
        user_data_dir=user_data_dir,
        host=ctx.obj["explicit_host"],
        port=ctx.obj["explicit_port"],
    )
    _emit(browser, json_output)


@cli.group("auth")
def auth_group() -> None:
    """Authentication status commands."""


@auth_group.command("status")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def auth_status(ctx: click.Context, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    status = _run(AuthService(settings).status())
    _emit(status.to_dict(), json_output)


@auth_group.command("check")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def auth_check(ctx: click.Context, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    payload = _run(check_auth(settings))
    _emit(payload, json_output)


@cli.command("paths")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def paths(json_output: bool) -> None:
    payload = {
        "home_dir": str(get_home_dir()),
        "config_path": str(get_config_path()),
        "context_path": str(get_context_path()),
        "browser_config": get_browser_config(),
    }
    _emit(payload, json_output)


@cli.command("login")
@click.option("--user-data-dir", default=None, help="Chrome user-data-dir containing DevToolsActivePort")
@click.option("--validate/--no-validate", default=True, help="Validate NotebookLM auth after attach")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def login(
    ctx: click.Context,
    user_data_dir: str | None,
    validate: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    payload = _run(bootstrap_login(settings, user_data_dir, validate))
    _emit(payload, json_output)


@cli.command("doctor")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def doctor(ctx: click.Context, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    data = _run(run_doctor(settings))
    _emit(data, json_output)


@cli.group("context")
def context_group() -> None:
    """Local state commands."""


@context_group.command("show")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def context_show(json_output: bool) -> None:
    _emit(load_context(), json_output)


@context_group.command("clear")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def context_clear(json_output: bool) -> None:
    clear_context()
    _emit({"cleared": True}, json_output)


@cli.command("status")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def status(json_output: bool) -> None:
    context = load_context()
    notebook_id = context.get("notebook_id")
    payload = {
        "has_context": bool(notebook_id),
        "notebook": {"id": notebook_id} if notebook_id else None,
        "conversation_id": context.get("conversation_id"),
    }
    _emit(payload, json_output)


@cli.command("clear")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def clear(json_output: bool) -> None:
    clear_context()
    _emit({"cleared": True}, json_output)


@cli.group("notebook")
def notebook_group() -> None:
    """Notebook commands."""


@notebook_group.command("list")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notebook_list(ctx: click.Context, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    notebooks = _run(list_notebooks(settings))
    payload = {"count": len(notebooks), "notebooks": notebooks}
    _emit(payload, json_output)


@notebook_group.command("get")
@click.argument("notebook_id", required=False)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notebook_get(ctx: click.Context, notebook_id: str | None, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    payload = _run(get_notebook(settings, _require_notebook(notebook_id)))
    _emit(payload, json_output)


@notebook_group.command("create")
@click.argument("title")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notebook_create(ctx: click.Context, title: str, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    payload = _run(create_notebook(settings, title))
    _emit(payload, json_output)


@notebook_group.command("rename")
@click.argument("notebook_id")
@click.argument("title")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notebook_rename(ctx: click.Context, notebook_id: str, title: str, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    payload = _run(rename_notebook(settings, notebook_id, title))
    _emit(payload, json_output)


@notebook_group.command("delete")
@click.argument("notebook_id")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notebook_delete(ctx: click.Context, notebook_id: str, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    payload = _run(delete_notebook(settings, notebook_id))
    if get_current_notebook() == notebook_id:
        clear_context()
    _emit(payload, json_output)


@notebook_group.command("summary")
@click.argument("notebook_id", required=False)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notebook_summary(ctx: click.Context, notebook_id: str | None, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(get_notebook_summary(settings, resolved))
    _emit(payload, json_output)


@notebook_group.command("describe")
@click.argument("notebook_id", required=False)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notebook_describe(ctx: click.Context, notebook_id: str | None, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(describe_notebook(settings, resolved))
    _emit(payload, json_output)


@notebook_group.command("metadata")
@click.argument("notebook_id", required=False)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notebook_metadata(ctx: click.Context, notebook_id: str | None, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(get_notebook_metadata(settings, resolved))
    _emit(payload, json_output)


@notebook_group.command("remove-from-recent")
@click.argument("notebook_id")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notebook_remove_from_recent(ctx: click.Context, notebook_id: str, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    payload = _run(remove_notebook_from_recent(settings, notebook_id))
    _emit(payload, json_output)


@notebook_group.command("use")
@click.argument("notebook_id")
@click.pass_context
def notebook_use(ctx: click.Context, notebook_id: str) -> None:
    settings = _settings_from_ctx(ctx)
    notebook = _run(get_notebook(settings, notebook_id))
    set_current_notebook(notebook["id"])
    click.echo(f"current_notebook: {notebook['id']}")


@cli.group("source")
def source_group() -> None:
    """Source commands."""


@source_group.command("list")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_list(ctx: click.Context, notebook_id: str | None, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    sources = _run(list_sources(settings, resolved))
    payload = {"notebook_id": resolved, "count": len(sources), "sources": sources}
    _emit(payload, json_output)


@source_group.command("get")
@click.argument("source_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_get(
    ctx: click.Context,
    source_id: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(get_source(settings, resolved, source_id))
    if payload is None:
        raise click.ClickException(f"Source not found: {source_id}")
    _emit(payload, json_output)


@source_group.command("wait")
@click.argument("source_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--initial-interval", default=1.0, type=float, show_default=True, help="Initial poll interval in seconds")
@click.option("--max-interval", default=10.0, type=float, show_default=True, help="Maximum poll interval in seconds")
@click.option("--timeout", default=120.0, type=float, show_default=True, help="Overall wait timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_wait(
    ctx: click.Context,
    source_id: str,
    notebook_id: str | None,
    initial_interval: float,
    max_interval: float,
    timeout: float,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(wait_for_source(settings, resolved, source_id, initial_interval, max_interval, timeout))
    _emit(payload, json_output)


@source_group.command("add-url")
@click.argument("url")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--wait/--no-wait", default=True, help="Wait for source processing")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_add_url(
    ctx: click.Context,
    url: str,
    notebook_id: str | None,
    wait: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(add_source_url(settings, resolved, url, wait))
    _emit(payload, json_output)


@source_group.command("add-urls")
@click.argument("urls", nargs=-1, required=False)
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--wait/--no-wait", default=True, help="Wait for source processing")
@click.option("--from-file", "from_file", default=None, type=click.Path(exists=True), help="Read URLs from a file (one per line) or JSON array")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.option("--workers", default=5, type=int, help="Max concurrent requests")
@click.option("--skip-paywall/--no-skip-paywall", default=True, help="Skip known paywall domains (default: skip)")
@click.option("--skip-feed/--no-skip-feed", default=True, help="Skip RSS/Atom feed URLs (default: skip)")
@click.option("--retry", default=2, type=int, help="Max retries per URL on timeout (default: 2)")
@click.pass_context
def source_add_urls(
    ctx: click.Context,
    urls: tuple[str, ...],
    notebook_id: str | None,
    wait: bool,
    from_file: str | None,
    json_output: bool,
    workers: int,
    skip_paywall: bool,
    skip_feed: bool,
    retry: int,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)

    # Collect URLs
    url_list: list[str] = list(urls)
    if from_file:
        import json as _json
        with open(from_file) as f:
            content = f.read().strip()
        # Try JSON array first
        try:
            parsed = _json.loads(content)
            if isinstance(parsed, list):
                url_list.extend(str(u) for u in parsed)
            else:
                click.echo(f"Warning: --from-file JSON is not a list, treating as plain text", err=True)
                url_list.extend(content.splitlines())
        except _json.JSONDecodeError:
            url_list.extend(line.strip() for line in content.splitlines() if line.strip())

    if not url_list:
        click.echo("No URLs provided. Use positional args or --from-file.", err=True)
        return

    click.echo(f"Pre-checking + adding {len(url_list)} URLs to notebook {resolved} ...")
    payload = _run(add_source_url_batch(
        settings, resolved, url_list,
        wait=wait,
        max_concurrency=workers,
        skip_paywall=skip_paywall,
        skip_feed=skip_feed,
        retry_count=max(0, retry),
    ))

    if json_output:
        _emit(payload, True)
        return

    success = [r for r in payload if r["status"] == "success"]
    skipped = [r for r in payload if r["status"] == "skipped"]
    errors = [r for r in payload if r["status"] == "error"]

    click.echo(f"\n✓ {len(success)} added  ✗ {len(errors)} failed  ⊘ {len(skipped)} skipped")

    for r in errors:
        click.echo(f"  [FAIL][{r['category']}] {r['url']}: {r['message']}")

    for r in skipped:
        click.echo(f"  [SKIP][{r['reason']}] {r['url']}")

    for r in success:
        click.echo(f"  [OK]   {r.get('title', r.get('url'))}")


@source_group.command("add-file")
@click.argument("file_path")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--wait/--no-wait", default=True, help="Wait for source processing")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_add_file(
    ctx: click.Context,
    file_path: str,
    notebook_id: str | None,
    wait: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(add_source_file(settings, resolved, file_path, wait))
    _emit(payload, json_output)


@source_group.command("add-text")
@click.argument("title")
@click.argument("content")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--wait/--no-wait", default=False, help="Wait for source processing")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_add_text_cmd(
    ctx: click.Context,
    title: str,
    content: str,
    notebook_id: str | None,
    wait: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(add_source_text(settings, resolved, title, content, wait))
    _emit(payload, json_output)


@source_group.command("add-drive")
@click.argument("file_id")
@click.argument("title")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--mime-type", default="application/vnd.google-apps.document", show_default=True, help="Google Drive MIME type")
@click.option("--wait/--no-wait", default=False, help="Wait for source processing")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_add_drive_cmd(
    ctx: click.Context,
    file_id: str,
    title: str,
    notebook_id: str | None,
    mime_type: str,
    wait: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(add_source_drive(settings, resolved, file_id, title, mime_type, wait))
    _emit(payload, json_output)


@source_group.command("rename")
@click.argument("source_id")
@click.argument("title")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_rename_cmd(
    ctx: click.Context,
    source_id: str,
    title: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(rename_source(settings, resolved, source_id, title))
    _emit(payload, json_output)


@source_group.command("delete")
@click.argument("source_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_delete_cmd(
    ctx: click.Context,
    source_id: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(delete_source(settings, resolved, source_id))
    _emit(payload, json_output)


@source_group.command("refresh")
@click.argument("source_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_refresh_cmd(
    ctx: click.Context,
    source_id: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(refresh_source(settings, resolved, source_id))
    _emit(payload, json_output)


@source_group.command("check-freshness")
@click.argument("source_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_check_freshness_cmd(
    ctx: click.Context,
    source_id: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(check_source_freshness(settings, resolved, source_id))
    _emit(payload, json_output)


source_group.add_command(
    click.Command(
        name="stale",
        callback=source_check_freshness_cmd.callback,
        params=list(source_check_freshness_cmd.params),
        help="Alias for check-freshness.",
    )
)


@source_group.command("guide")
@click.argument("source_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_guide_cmd(
    ctx: click.Context,
    source_id: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(get_source_guide(settings, resolved, source_id))
    _emit(payload, json_output)


@source_group.command("fulltext")
@click.argument("source_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_fulltext_cmd(
    ctx: click.Context,
    source_id: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(get_source_fulltext(settings, resolved, source_id))
    _emit(payload, json_output)


@source_group.command("wait-for-sources")
@click.argument("source_ids", nargs=-1, required=True)
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--initial-interval", default=1.0, type=float, show_default=True, help="Initial poll interval in seconds")
@click.option("--max-interval", default=10.0, type=float, show_default=True, help="Maximum poll interval in seconds")
@click.option("--timeout", default=120.0, type=float, show_default=True, help="Overall wait timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_wait_for_sources_cmd(
    ctx: click.Context,
    source_ids: tuple[str, ...],
    notebook_id: str | None,
    initial_interval: float,
    max_interval: float,
    timeout: float,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    sources = _run(
        wait_for_sources(
            settings,
            resolved,
            list(source_ids),
            initial_interval,
            max_interval,
            timeout,
        )
    )
    payload = {"notebook_id": resolved, "count": len(sources), "sources": sources}
    _emit(payload, json_output)


@source_group.command("add-research")
@click.argument("query")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--source", "search_source", default="web", type=RESEARCH_SOURCE_CHOICES, show_default=True, help="Research source")
@click.option("--mode", default="fast", type=RESEARCH_MODE_CHOICES, show_default=True, help="Research mode")
@click.option("--wait/--no-wait", default=True, help="Wait for research completion")
@click.option("--import-all", is_flag=True, help="Import discovered sources when research completes")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def source_add_research_cmd(
    ctx: click.Context,
    query: str,
    notebook_id: str | None,
    search_source: str,
    mode: str,
    wait: bool,
    import_all: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(add_research_source(settings, resolved, query, search_source, mode, wait, import_all))
    _emit(payload, json_output)


@cli.group("research")
def research_group() -> None:
    """Research commands."""


@research_group.command("status")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def research_status_cmd(ctx: click.Context, notebook_id: str | None, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(get_research_status(settings, resolved))
    _emit(payload, json_output)


@research_group.command("wait")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--timeout", default=300, type=int, show_default=True, help="Wait timeout in seconds")
@click.option("--interval", default=5, type=int, show_default=True, help="Poll interval in seconds")
@click.option("--import-all", is_flag=True, help="Import discovered sources when research completes")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def research_wait_cmd(
    ctx: click.Context,
    notebook_id: str | None,
    timeout: int,
    interval: int,
    import_all: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(wait_for_research(settings, resolved, timeout, interval, import_all))
    _emit(payload, json_output)


@cli.group("share")
def share_group() -> None:
    """Share commands."""


@share_group.command("status")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def share_status_cmd(ctx: click.Context, notebook_id: str | None, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(get_share_status(settings, resolved))
    _emit(payload, json_output)


@share_group.command("public")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--enable/--disable", "public", default=True, help="Enable or disable public sharing")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def share_public_cmd(
    ctx: click.Context,
    notebook_id: str | None,
    public: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(set_share_public(settings, resolved, public))
    _emit(payload, json_output)


@share_group.command("view-level")
@click.argument("level", type=SHARE_VIEW_LEVEL_CHOICES)
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def share_view_level_cmd(
    ctx: click.Context,
    level: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    value = "full_notebook" if level == "full" else "chat_only"
    payload = _run(set_share_view_level(settings, resolved, value))
    _emit(payload, json_output)


@share_group.command("add")
@click.argument("email")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--permission", default="viewer", type=SHARE_PERMISSION_CHOICES, show_default=True, help="Permission level")
@click.option("--no-notify", is_flag=True, help="Do not send an email notification")
@click.option("--message", default="", help="Welcome message")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def share_add_cmd(
    ctx: click.Context,
    email: str,
    notebook_id: str | None,
    permission: str,
    no_notify: bool,
    message: str,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(add_share_user(settings, resolved, email, permission, not no_notify, message))
    _emit(payload, json_output)


@share_group.command("update")
@click.argument("email")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--permission", required=True, type=SHARE_PERMISSION_CHOICES, help="Permission level")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def share_update_cmd(
    ctx: click.Context,
    email: str,
    notebook_id: str | None,
    permission: str,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(update_share_user(settings, resolved, email, permission))
    _emit(payload, json_output)


@share_group.command("remove")
@click.argument("email")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def share_remove_cmd(
    ctx: click.Context,
    email: str,
    notebook_id: str | None,
    yes: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    if not yes and not json_output and not click.confirm(f"Remove access for {email}?"):
        return
    payload = _run(remove_share_user(settings, resolved, email))
    _emit(payload, json_output)


@cli.command("ask")
@click.argument("question")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--conversation-id", default=None, help="Conversation ID override")
@click.option("--new", "start_new", is_flag=True, help="Ignore the persisted conversation and start a new thread")
@click.option("--source", "source_ids", multiple=True, help="Limit the ask to specific source IDs")
@click.option("--save-as-note", is_flag=True, help="Save the answer as a note")
@click.option("--note-title", default=None, help="Saved note title")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def ask(
    ctx: click.Context,
    question: str,
    notebook_id: str | None,
    conversation_id: str | None,
    start_new: bool,
    source_ids: tuple[str, ...],
    save_as_note: bool,
    note_title: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved_notebook = _require_notebook(notebook_id)
    resolved_conversation = None if start_new else (conversation_id or get_current_conversation())
    if source_ids:
        payload = _run(
            ask_question(
                settings,
                resolved_notebook,
                question,
                resolved_conversation,
                list(source_ids),
            )
        )
    else:
        payload = _run(
            ask_question(
                settings,
                resolved_notebook,
                question,
                resolved_conversation,
            )
        )
    set_current_conversation(payload.get("conversation_id"))
    if save_as_note and payload.get("answer"):
        saved_note = _run(
            create_note(
                settings,
                resolved_notebook,
                note_title or f"Chat: {question[:50]}",
                payload["answer"],
            )
        )
        payload["saved_note"] = saved_note
    _emit(payload, json_output)


@cli.command("history")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--limit", default=100, type=int, show_default=True, help="Maximum number of turns")
@click.option("--conversation-id", default=None, help="Conversation ID override")
@click.option("--save", "save_as_note", is_flag=True, help="Save history as a note")
@click.option("--note-title", default=None, help="Saved note title")
@click.option("--show-all", is_flag=True, help="Show full question and answer text")
@click.option("--clear-cache", is_flag=True, help="Clear the locally persisted conversation pointer")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def history(
    ctx: click.Context,
    notebook_id: str | None,
    limit: int,
    conversation_id: str | None,
    save_as_note: bool,
    note_title: str | None,
    show_all: bool,
    clear_cache: bool,
    json_output: bool,
) -> None:
    if clear_cache:
        set_current_conversation(None)
        payload = {"cleared": True, "conversation_id": None}
        _emit(payload, json_output)
        return

    settings = _settings_from_ctx(ctx)
    resolved_notebook = _require_notebook(notebook_id)
    resolved_conversation = conversation_id or get_current_conversation()
    payload = _run(get_chat_history(settings, resolved_notebook, limit, resolved_conversation))
    if save_as_note:
        lines = []
        for item in payload.get("qa_pairs", []):
            lines.append(f"### Turn {item['turn']}")
            lines.append(f"Q: {item['question']}")
            lines.append(f"A: {item['answer']}")
            lines.append("")
        saved_note = _run(
            create_note(
                settings,
                resolved_notebook,
                note_title or "Chat History",
                "\n".join(lines).strip(),
            )
        )
        payload["saved_note"] = saved_note

    if show_all and not json_output:
        for item in payload.get("qa_pairs", []):
            click.echo(f"Q: {item['question']}")
            click.echo(f"A: {item['answer']}")
            click.echo("")
        return

    _emit(payload, json_output)


@cli.command("configure")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--mode", default=None, type=CHAT_MODE_CHOICES, help="Predefined chat mode")
@click.option("--persona", default=None, help="Custom persona")
@click.option("--response-length", default=None, type=CHAT_RESPONSE_LENGTH_CHOICES, help="Response length")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def configure(
    ctx: click.Context,
    notebook_id: str | None,
    mode: str | None,
    persona: str | None,
    response_length: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(configure_chat(settings, resolved, mode, persona, response_length))
    _emit(payload, json_output)


@cli.group("artifact")
def artifact_group() -> None:
    """Artifact commands."""


@artifact_group.command("list")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--kind", default=None, help="Artifact kind filter, e.g. report, audio")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def artifact_list(
    ctx: click.Context,
    notebook_id: str | None,
    kind: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    artifacts = _run(list_artifacts(settings, resolved, kind))
    payload = {"notebook_id": resolved, "count": len(artifacts), "artifacts": artifacts}
    _emit(payload, json_output)


@artifact_group.command("get")
@click.argument("artifact_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def artifact_get(
    ctx: click.Context,
    artifact_id: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(get_artifact(settings, resolved, artifact_id))
    if payload is None:
        raise click.ClickException(f"Artifact not found: {artifact_id}")
    _emit(payload, json_output)


@artifact_group.command("rename")
@click.argument("artifact_id")
@click.argument("title")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def artifact_rename(
    ctx: click.Context,
    artifact_id: str,
    title: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(rename_artifact(settings, resolved, artifact_id, title))
    _emit(payload, json_output)


@artifact_group.command("delete")
@click.argument("artifact_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def artifact_delete(
    ctx: click.Context,
    artifact_id: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(delete_artifact(settings, resolved, artifact_id))
    _emit(payload, json_output)


@artifact_group.command("export")
@click.argument("artifact_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--type", "export_type", default="docs", type=EXPORT_TYPE_CHOICES, show_default=True, help="Export target")
@click.option("--title", default="Export", show_default=True, help="Export title")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def artifact_export(
    ctx: click.Context,
    artifact_id: str,
    notebook_id: str | None,
    export_type: str,
    title: str,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(export_artifact(settings, resolved, artifact_id, export_type, title))
    _emit(payload, json_output)


@artifact_group.command("poll")
@click.argument("task_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def artifact_poll(
    ctx: click.Context,
    task_id: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(poll_artifact(settings, resolved, task_id))
    _emit(payload, json_output)


@artifact_group.command("wait")
@click.argument("task_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--initial-interval", default=2.0, type=float, show_default=True, help="Initial poll interval in seconds")
@click.option("--max-interval", default=10.0, type=float, show_default=True, help="Maximum poll interval in seconds")
@click.option("--timeout", default=300.0, type=float, show_default=True, help="Overall wait timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def artifact_wait(
    ctx: click.Context,
    task_id: str,
    notebook_id: str | None,
    initial_interval: float,
    max_interval: float,
    timeout: float,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(
        wait_for_artifact(
            settings,
            resolved,
            task_id,
            initial_interval,
            max_interval,
            timeout,
        )
    )
    _emit(payload, json_output)


@artifact_group.command("pending")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--kind", default=None, help="Artifact kind filter, e.g. report, audio")
@click.option("--include-resolved", is_flag=True, help="Include resolved ledger entries")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def artifact_pending(
    ctx: click.Context,
    notebook_id: str | None,
    kind: str | None,
    include_resolved: bool,
    json_output: bool,
) -> None:
    """List pending-generation ledger entries for the current notebook."""
    resolved = _require_notebook(notebook_id)
    submissions = _filter_submission_records(
        list_pending_submissions(include_resolved=include_resolved),
        notebook_id=resolved,
        artifact_kind=kind,
    )
    payload = {"notebook_id": resolved, "count": len(submissions), "submissions": submissions}
    _emit(payload, json_output)


artifact_group.add_command(
    click.Command(
        name="pending-list",
        callback=artifact_pending.callback,
        params=list(artifact_pending.params),
        help="Alias for artifact pending.",
    )
)


@artifact_group.command("resolve-pending")
@click.argument("submission_id")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def artifact_resolve_pending(
    ctx: click.Context,
    submission_id: str,
    json_output: bool,
) -> None:
    """Resolve one ledgered pending generation against the current artifact list."""
    settings = _settings_from_ctx(ctx)
    submission = get_pending_submission(submission_id)
    if submission is None:
        raise click.ClickException(f"Pending submission not found: {submission_id}")

    if submission.get("resolution_status") == "resolved" and submission.get("resolved_artifact_id"):
        payload = {
            "status": "resolved",
            "resolution_status": "resolved",
            "already_resolved": True,
            "artifact_id": submission["resolved_artifact_id"],
            "artifact": {"id": submission["resolved_artifact_id"]},
            "submission": submission,
        }
        _emit(payload, json_output)
        return

    artifacts = _run(list_artifacts(settings, submission["notebook_id"], submission["artifact_kind"]))
    candidates = _rank_submission_candidates(submission, artifacts)

    updated_submission = dict(submission)
    if len(candidates) == 1 and candidates[0].get("strong_candidate"):
        artifact = candidates[0]["artifact"]
        updated_submission["resolution_status"] = "resolved"
        updated_submission["resolved_artifact_id"] = artifact["id"]
        updated_submission["resolved_at"] = _utcnow_iso()
        upsert_pending_submission(updated_submission)
        payload = {
            "status": "resolved",
            "resolution_status": "resolved",
            "already_resolved": False,
            "artifact_id": artifact["id"],
            "artifact": artifact,
            "candidate_count": 1,
            "candidates": candidates,
            "submission": updated_submission,
        }
        _emit(payload, json_output)
        return

    updated_submission["resolution_status"] = "ambiguous" if candidates else "pending"
    upsert_pending_submission(updated_submission)
    payload = {
        "status": "unresolved",
        "resolution_status": "ambiguous" if len(candidates) > 1 else "pending",
        "artifact_id": None,
        "artifact": None,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "submission": updated_submission,
    }
    _emit(payload, json_output)


@artifact_group.command("suggest-reports")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def artifact_suggest_reports(
    ctx: click.Context,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    suggestions = _run(suggest_report_formats(settings, resolved))
    payload = {"notebook_id": resolved, "count": len(suggestions), "suggestions": suggestions}
    _emit(payload, json_output)


@cli.group("generate")
def generate_group() -> None:
    """Generation commands."""


@generate_group.command("report")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option(
    "--format",
    "report_format",
    default="briefing_doc",
    type=REPORT_FORMAT_CHOICES,
    show_default=True,
    help="Report format: briefing_doc|study_guide|blog_post|custom",
)
@click.option(
    "--prompt",
    "custom_prompt",
    default=None,
    help="Only used with --format custom",
)
@click.option("--instructions", "extra_instructions", default=None, help="Additional report instructions")
@click.option("--language", default=None, help="Per-command output language")
@click.option("--source", "source_ids", multiple=True, help="Restrict to specific source IDs")
@click.option("--wait/--no-wait", default=False, help="Wait for completion")
@click.option(
    "--inspect-pending/--no-inspect-pending",
    default=True,
    help="Attempt a short artifact-list follow-up when submit returns pending.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def generate_report_cmd(
    ctx: click.Context,
    notebook_id: str | None,
    report_format: str,
    custom_prompt: str | None,
    extra_instructions: str | None,
    language: str | None,
    source_ids: tuple[str, ...],
    wait: bool,
    inspect_pending: bool,
    json_output: bool,
) -> None:
    """Valid report formats: briefing_doc, study_guide, blog_post, custom; summary is not a valid report format."""
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    baseline_artifact_ids = _capture_artifact_baseline(settings, resolved, "report", inspect_pending)
    if extra_instructions is None and language is None and not source_ids:
        payload = _run(generate_report(settings, resolved, report_format, custom_prompt, wait))
    else:
        payload = _run(
            generate_report(
                settings=settings,
                notebook_id=resolved,
                report_format=report_format,
                custom_prompt=custom_prompt,
                extra_instructions=extra_instructions,
                language=language,
                source_ids=list(source_ids),
                wait=wait,
            )
        )
    payload = _finalize_pending_generation_payload(
        settings,
        resolved,
        "report",
        baseline_artifact_ids,
        payload,
        inspect_pending,
    )
    payload = _record_pending_submission(
        payload=payload,
        notebook_id=resolved,
        artifact_kind="report",
        submission_kind="report",
        baseline_artifact_ids=baseline_artifact_ids,
        source_ids=list(source_ids),
        language=language or "en",
        format_value=report_format,
        style=None,
        detail=None,
        length=None,
        orientation=None,
        custom_prompt=custom_prompt,
        extra_instructions=extra_instructions,
    )
    _emit(payload, json_output)


@generate_group.command("audio")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--instructions", default=None, help="Custom audio instructions")
@click.option("--language", default=None, help="Per-command output language")
@click.option("--source", "source_ids", multiple=True, help="Restrict to specific source IDs")
@click.option("--format", "audio_format", default=None, type=AUDIO_FORMAT_CHOICES, help="Audio format")
@click.option("--length", "audio_length", default=None, type=AUDIO_LENGTH_CHOICES, help="Audio length")
@click.option("--wait/--no-wait", default=False, help="Wait for completion")
@click.option(
    "--inspect-pending/--no-inspect-pending",
    default=True,
    help="Attempt a short artifact-list follow-up when submit returns pending.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def generate_audio_cmd(
    ctx: click.Context,
    notebook_id: str | None,
    instructions: str | None,
    language: str | None,
    source_ids: tuple[str, ...],
    audio_format: str | None,
    audio_length: str | None,
    wait: bool,
    inspect_pending: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    baseline_artifact_ids = _capture_artifact_baseline(settings, resolved, "audio", inspect_pending)
    if language is None and not source_ids and audio_format is None and audio_length is None:
        payload = _run(generate_audio(settings, resolved, instructions, wait))
    else:
        payload = _run(
            generate_audio(
                settings=settings,
                notebook_id=resolved,
                instructions=instructions,
                language=language,
                source_ids=list(source_ids),
                audio_format=audio_format,
                audio_length=audio_length,
                wait=wait,
            )
        )
    payload = _finalize_pending_generation_payload(
        settings,
        resolved,
        "audio",
        baseline_artifact_ids,
        payload,
        inspect_pending,
    )
    payload = _record_pending_submission(
        payload=payload,
        notebook_id=resolved,
        artifact_kind="audio",
        submission_kind="audio",
        baseline_artifact_ids=baseline_artifact_ids,
        source_ids=list(source_ids),
        language=language or "en",
        format_value=audio_format,
        style=None,
        detail=None,
        length=audio_length,
        orientation=None,
        instructions=instructions,
    )
    _emit(payload, json_output)


@generate_group.command("video")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--instructions", default=None, help="Custom video instructions")
@click.option("--format", "video_format", default=None, type=ARTIFACT_FORMAT_CHOICES, help="Video format")
@click.option("--style", default=None, type=VIDEO_STYLE_CHOICES, help="Video visual style")
@click.option("--language", default=None, help="Per-command output language")
@click.option("--source", "source_ids", multiple=True, help="Restrict to specific source IDs")
@click.option("--wait/--no-wait", default=False, help="Wait for completion")
@click.option(
    "--inspect-pending/--no-inspect-pending",
    default=True,
    help="Attempt a short artifact-list follow-up when submit returns pending.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def generate_video_cmd(
    ctx: click.Context,
    notebook_id: str | None,
    instructions: str | None,
    video_format: str | None,
    style: str | None,
    language: str | None,
    source_ids: tuple[str, ...],
    wait: bool,
    inspect_pending: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    baseline_artifact_ids = _capture_artifact_baseline(settings, resolved, "video", inspect_pending)
    if language is None and not source_ids:
        payload = _run(generate_video(settings, resolved, instructions, video_format, style, wait))
    else:
        payload = _run(
            generate_video(
                settings=settings,
                notebook_id=resolved,
                instructions=instructions,
                video_format=video_format,
                style=style,
                language=language,
                source_ids=list(source_ids),
                wait=wait,
            )
        )
    payload = _finalize_pending_generation_payload(
        settings,
        resolved,
        "video",
        baseline_artifact_ids,
        payload,
        inspect_pending,
    )
    payload = _record_pending_submission(
        payload=payload,
        notebook_id=resolved,
        artifact_kind="video",
        submission_kind="video",
        baseline_artifact_ids=baseline_artifact_ids,
        source_ids=list(source_ids),
        language=language or "en",
        format_value=video_format,
        style=style,
        detail=None,
        length=None,
        orientation=None,
        instructions=instructions,
    )
    _emit(payload, json_output)


@generate_group.command("cinematic-video")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--instructions", default=None, help="Custom video instructions")
@click.option("--language", default=None, help="Per-command output language")
@click.option("--source", "source_ids", multiple=True, help="Restrict to specific source IDs")
@click.option("--wait/--no-wait", default=False, help="Wait for completion")
@click.option(
    "--inspect-pending/--no-inspect-pending",
    default=True,
    help="Attempt a short artifact-list follow-up when submit returns pending.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def generate_cinematic_video_cmd(
    ctx: click.Context,
    notebook_id: str | None,
    instructions: str | None,
    language: str | None,
    source_ids: tuple[str, ...],
    wait: bool,
    inspect_pending: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    baseline_artifact_ids = _capture_artifact_baseline(settings, resolved, "video", inspect_pending)
    if language is None and not source_ids:
        payload = _run(generate_cinematic_video(settings, resolved, instructions, wait))
    else:
        payload = _run(
            generate_cinematic_video(
                settings=settings,
                notebook_id=resolved,
                instructions=instructions,
                language=language,
                source_ids=list(source_ids),
                wait=wait,
            )
        )
    payload = _finalize_pending_generation_payload(
        settings,
        resolved,
        "video",
        baseline_artifact_ids,
        payload,
        inspect_pending,
    )
    payload = _record_pending_submission(
        payload=payload,
        notebook_id=resolved,
        artifact_kind="video",
        submission_kind="cinematic-video",
        baseline_artifact_ids=baseline_artifact_ids,
        source_ids=list(source_ids),
        language=language or "en",
        format_value="cinematic",
        style=None,
        detail=None,
        length=None,
        orientation=None,
        instructions=instructions,
    )
    _emit(payload, json_output)


@generate_group.command("slide-deck")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--instructions", default=None, help="Custom slide deck instructions")
@click.option("--format", "slide_format", default=None, type=SLIDE_FORMAT_CHOICES, help="Slide deck format")
@click.option("--length", default=None, type=SLIDE_LENGTH_CHOICES, help="Slide deck length")
@click.option("--language", default=None, help="Per-command output language")
@click.option("--source", "source_ids", multiple=True, help="Restrict to specific source IDs")
@click.option("--wait/--no-wait", default=False, help="Wait for completion")
@click.option(
    "--inspect-pending/--no-inspect-pending",
    default=True,
    help="Attempt a short artifact-list follow-up when submit returns pending.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def generate_slide_deck_cmd(
    ctx: click.Context,
    notebook_id: str | None,
    instructions: str | None,
    slide_format: str | None,
    length: str | None,
    language: str | None,
    source_ids: tuple[str, ...],
    wait: bool,
    inspect_pending: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    baseline_artifact_ids = _capture_artifact_baseline(settings, resolved, "slide_deck", inspect_pending)
    if language is None and not source_ids:
        payload = _run(generate_slide_deck(settings, resolved, instructions, slide_format, length, wait))
    else:
        payload = _run(
            generate_slide_deck(
                settings=settings,
                notebook_id=resolved,
                instructions=instructions,
                slide_format=slide_format,
                length=length,
                language=language,
                source_ids=list(source_ids),
                wait=wait,
            )
        )
    payload = _finalize_pending_generation_payload(
        settings,
        resolved,
        "slide_deck",
        baseline_artifact_ids,
        payload,
        inspect_pending,
    )
    payload = _record_pending_submission(
        payload=payload,
        notebook_id=resolved,
        artifact_kind="slide_deck",
        submission_kind="slide-deck",
        baseline_artifact_ids=baseline_artifact_ids,
        source_ids=list(source_ids),
        language=language or "en",
        format_value=slide_format,
        style=None,
        detail=None,
        length=length,
        orientation=None,
        instructions=instructions,
    )
    _emit(payload, json_output)


@generate_group.command("revise-slide")
@click.argument("artifact_id")
@click.argument("slide_index", type=int)
@click.argument("prompt")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--wait/--no-wait", default=False, help="Wait for completion")
@click.option(
    "--inspect-pending/--no-inspect-pending",
    default=True,
    help="Attempt a short artifact-list follow-up when submit returns pending.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def generate_revise_slide_cmd(
    ctx: click.Context,
    artifact_id: str,
    slide_index: int,
    prompt: str,
    notebook_id: str | None,
    wait: bool,
    inspect_pending: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    baseline_artifact_ids = _capture_artifact_baseline(settings, resolved, "slide_deck", inspect_pending)
    payload = _run(revise_slide(settings, resolved, artifact_id, slide_index, prompt, wait))
    payload = _finalize_pending_generation_payload(
        settings,
        resolved,
        "slide_deck",
        baseline_artifact_ids,
        payload,
        inspect_pending,
    )
    _emit(payload, json_output)


@generate_group.command("infographic")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--instructions", default=None, help="Custom infographic instructions")
@click.option("--orientation", default=None, type=INFOGRAPHIC_ORIENTATION_CHOICES, help="Infographic orientation")
@click.option("--detail", default=None, type=INFOGRAPHIC_DETAIL_CHOICES, help="Infographic detail level")
@click.option("--style", default=None, type=INFOGRAPHIC_STYLE_CHOICES, help="Infographic visual style")
@click.option("--language", default=None, help="Per-command output language")
@click.option("--source", "source_ids", multiple=True, help="Restrict to specific source IDs")
@click.option("--wait/--no-wait", default=False, help="Wait for completion")
@click.option(
    "--inspect-pending/--no-inspect-pending",
    default=True,
    help="Attempt a short artifact-list follow-up when submit returns pending.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def generate_infographic_cmd(
    ctx: click.Context,
    notebook_id: str | None,
    instructions: str | None,
    orientation: str | None,
    detail: str | None,
    style: str | None,
    language: str | None,
    source_ids: tuple[str, ...],
    wait: bool,
    inspect_pending: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    baseline_artifact_ids = _capture_artifact_baseline(settings, resolved, "infographic", inspect_pending)
    if language is None and not source_ids:
        payload = _run(
            generate_infographic(settings, resolved, instructions, orientation, detail, style, wait)
        )
    else:
        payload = _run(
            generate_infographic(
                settings=settings,
                notebook_id=resolved,
                instructions=instructions,
                orientation=orientation,
                detail=detail,
                style=style,
                language=language,
                source_ids=list(source_ids),
                wait=wait,
            )
        )
    payload = _finalize_pending_generation_payload(
        settings,
        resolved,
        "infographic",
        baseline_artifact_ids,
        payload,
        inspect_pending,
    )
    payload = _record_pending_submission(
        payload=payload,
        notebook_id=resolved,
        artifact_kind="infographic",
        submission_kind="infographic",
        baseline_artifact_ids=baseline_artifact_ids,
        source_ids=list(source_ids),
        language=language or "en",
        format_value=None,
        style=style,
        detail=detail,
        length=None,
        orientation=orientation,
        instructions=instructions,
    )
    _emit(payload, json_output)


@generate_group.command("quiz")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--instructions", default=None, help="Custom quiz instructions")
@click.option("--quantity", default=None, type=QUIZ_QUANTITY_CHOICES, help="Quiz size")
@click.option("--difficulty", default=None, type=QUIZ_DIFFICULTY_CHOICES, help="Quiz difficulty")
@click.option("--wait/--no-wait", default=False, help="Wait for completion")
@click.option(
    "--inspect-pending/--no-inspect-pending",
    default=True,
    help="Attempt a short artifact-list follow-up when submit returns pending.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def generate_quiz_cmd(
    ctx: click.Context,
    notebook_id: str | None,
    instructions: str | None,
    quantity: str | None,
    difficulty: str | None,
    wait: bool,
    inspect_pending: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    baseline_artifact_ids = _capture_artifact_baseline(settings, resolved, "quiz", inspect_pending)
    payload = _run(generate_quiz(settings, resolved, instructions, quantity, difficulty, wait))
    payload = _finalize_pending_generation_payload(
        settings,
        resolved,
        "quiz",
        baseline_artifact_ids,
        payload,
        inspect_pending,
    )
    _emit(payload, json_output)


@generate_group.command("flashcards")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--instructions", default=None, help="Custom flashcard instructions")
@click.option("--quantity", default=None, type=QUIZ_QUANTITY_CHOICES, help="Flashcard set size")
@click.option("--difficulty", default=None, type=QUIZ_DIFFICULTY_CHOICES, help="Flashcard difficulty")
@click.option("--wait/--no-wait", default=False, help="Wait for completion")
@click.option(
    "--inspect-pending/--no-inspect-pending",
    default=True,
    help="Attempt a short artifact-list follow-up when submit returns pending.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def generate_flashcards_cmd(
    ctx: click.Context,
    notebook_id: str | None,
    instructions: str | None,
    quantity: str | None,
    difficulty: str | None,
    wait: bool,
    inspect_pending: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    baseline_artifact_ids = _capture_artifact_baseline(settings, resolved, "flashcards", inspect_pending)
    payload = _run(generate_flashcards(settings, resolved, instructions, quantity, difficulty, wait))
    payload = _finalize_pending_generation_payload(
        settings,
        resolved,
        "flashcards",
        baseline_artifact_ids,
        payload,
        inspect_pending,
    )
    _emit(payload, json_output)


@generate_group.command("data-table")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--instructions", default=None, help="Describe the desired table")
@click.option("--wait/--no-wait", default=False, help="Wait for completion")
@click.option(
    "--inspect-pending/--no-inspect-pending",
    default=True,
    help="Attempt a short artifact-list follow-up when submit returns pending.",
)
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def generate_data_table_cmd(
    ctx: click.Context,
    notebook_id: str | None,
    instructions: str | None,
    wait: bool,
    inspect_pending: bool,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    baseline_artifact_ids = _capture_artifact_baseline(settings, resolved, "data_table", inspect_pending)
    payload = _run(generate_data_table(settings, resolved, instructions, wait))
    payload = _finalize_pending_generation_payload(
        settings,
        resolved,
        "data_table",
        baseline_artifact_ids,
        payload,
        inspect_pending,
    )
    _emit(payload, json_output)


@generate_group.command("mind-map")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def generate_mind_map_cmd(
    ctx: click.Context,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(generate_mind_map(settings, resolved))
    _emit(payload, json_output)


@cli.group("download")
def download_group() -> None:
    """Download commands."""


@download_group.command("report")
@click.argument("output_path")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--artifact-id", default=None, help="Specific artifact ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def download_report_cmd(
    ctx: click.Context,
    output_path: str,
    notebook_id: str | None,
    artifact_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(download_report(settings, resolved, output_path, artifact_id))
    _emit(payload, json_output)


@download_group.command("audio")
@click.argument("output_path")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--artifact-id", default=None, help="Specific artifact ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def download_audio_cmd(
    ctx: click.Context,
    output_path: str,
    notebook_id: str | None,
    artifact_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(download_audio(settings, resolved, output_path, artifact_id))
    _emit(payload, json_output)


@download_group.command("video")
@click.argument("output_path")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--artifact-id", default=None, help="Specific artifact ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def download_video_cmd(
    ctx: click.Context,
    output_path: str,
    notebook_id: str | None,
    artifact_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(download_video(settings, resolved, output_path, artifact_id))
    _emit(payload, json_output)


download_group.add_command(
    click.Command(
        name="cinematic-video",
        callback=download_video_cmd.callback,
        params=list(download_video_cmd.params),
        help="Alias for video download, suitable for cinematic video artifacts.",
    )
)


@download_group.command("slide-deck")
@click.argument("output_path")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--artifact-id", default=None, help="Specific artifact ID")
@click.option("--format", "output_format", default="pdf", type=SLIDE_DOWNLOAD_FORMAT_CHOICES, show_default=True, help="Download format")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def download_slide_deck_cmd(
    ctx: click.Context,
    output_path: str,
    notebook_id: str | None,
    artifact_id: str | None,
    output_format: str,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(download_slide_deck(settings, resolved, output_path, artifact_id, output_format))
    _emit(payload, json_output)


@download_group.command("infographic")
@click.argument("output_path")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--artifact-id", default=None, help="Specific artifact ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def download_infographic_cmd(
    ctx: click.Context,
    output_path: str,
    notebook_id: str | None,
    artifact_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(download_infographic(settings, resolved, output_path, artifact_id))
    _emit(payload, json_output)


@download_group.command("quiz")
@click.argument("output_path")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--artifact-id", default=None, help="Specific artifact ID")
@click.option("--format", "output_format", default="json", type=INTERACTIVE_DOWNLOAD_FORMAT_CHOICES, show_default=True, help="Download format")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def download_quiz_cmd(
    ctx: click.Context,
    output_path: str,
    notebook_id: str | None,
    artifact_id: str | None,
    output_format: str,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(download_quiz(settings, resolved, output_path, artifact_id, output_format))
    _emit(payload, json_output)


@download_group.command("flashcards")
@click.argument("output_path")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--artifact-id", default=None, help="Specific artifact ID")
@click.option("--format", "output_format", default="json", type=INTERACTIVE_DOWNLOAD_FORMAT_CHOICES, show_default=True, help="Download format")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def download_flashcards_cmd(
    ctx: click.Context,
    output_path: str,
    notebook_id: str | None,
    artifact_id: str | None,
    output_format: str,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(download_flashcards(settings, resolved, output_path, artifact_id, output_format))
    _emit(payload, json_output)


@download_group.command("data-table")
@click.argument("output_path")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--artifact-id", default=None, help="Specific artifact ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def download_data_table_cmd(
    ctx: click.Context,
    output_path: str,
    notebook_id: str | None,
    artifact_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(download_data_table(settings, resolved, output_path, artifact_id))
    _emit(payload, json_output)


@download_group.command("mind-map")
@click.argument("output_path")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--artifact-id", default=None, help="Specific artifact ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def download_mind_map_cmd(
    ctx: click.Context,
    output_path: str,
    notebook_id: str | None,
    artifact_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(download_mind_map(settings, resolved, output_path, artifact_id))
    _emit(payload, json_output)


@cli.group("language")
def language_group() -> None:
    """Language commands."""


@language_group.command("list")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def language_list_cmd(json_output: bool) -> None:
    languages = list_languages()
    payload = {"count": len(languages), "languages": languages}
    _emit(payload, json_output)


@language_group.command("get")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def language_get_cmd(ctx: click.Context, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    payload = _run(get_output_language(settings))
    _emit(payload, json_output)


@language_group.command("set")
@click.argument("language")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def language_set_cmd(ctx: click.Context, language: str, json_output: bool) -> None:
    if get_language_name(language) is None:
        raise click.ClickException(f"Unknown language code: {language}")
    settings = _settings_from_ctx(ctx)
    payload = _run(set_output_language(settings, language))
    _emit(payload, json_output)


@cli.group("notes")
def notes_group() -> None:
    """Notes commands."""


@notes_group.command("list")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notes_list_cmd(ctx: click.Context, notebook_id: str | None, json_output: bool) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    notes = _run(list_notes(settings, resolved))
    payload = {"notebook_id": resolved, "count": len(notes), "notes": notes}
    _emit(payload, json_output)


@notes_group.command("create")
@click.argument("title")
@click.argument("content", required=False, default="")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notes_create_cmd(
    ctx: click.Context,
    title: str,
    content: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(create_note(settings, resolved, title, content))
    _emit(payload, json_output)


@notes_group.command("get")
@click.argument("note_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notes_get_cmd(
    ctx: click.Context,
    note_id: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(get_note(settings, resolved, note_id))
    if payload is None:
        raise click.ClickException(f"Note not found: {note_id}")
    _emit(payload, json_output)


@notes_group.command("save")
@click.argument("note_id")
@click.argument("content")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--title", default=None, help="Optional title override")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notes_save_cmd(
    ctx: click.Context,
    note_id: str,
    content: str,
    notebook_id: str | None,
    title: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(save_note(settings, resolved, note_id, content, title))
    _emit(payload, json_output)


@notes_group.command("rename")
@click.argument("note_id")
@click.argument("title")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notes_rename_cmd(
    ctx: click.Context,
    note_id: str,
    title: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(rename_note(settings, resolved, note_id, title))
    _emit(payload, json_output)


@notes_group.command("delete")
@click.argument("note_id")
@click.option("-n", "--notebook", "notebook_id", default=None, help="Notebook ID")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def notes_delete_cmd(
    ctx: click.Context,
    note_id: str,
    notebook_id: str | None,
    json_output: bool,
) -> None:
    settings = _settings_from_ctx(ctx)
    resolved = _require_notebook(notebook_id)
    payload = _run(delete_note(settings, resolved, note_id))
    _emit(payload, json_output)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
