from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
import uuid
from typing import Any

import click

from ...config import Settings
from ...core.output import experimental_error_payload, experimental_success_payload
from .ops import (
    GeminiOperationError,
    ImageGenerationResult,
    TextGenerationResult,
    VideoGenerationResult,
    create_chat_session,
    deep_research,
    generate_image,
    generate_text,
    generate_video,
    generate_vision,
    list_chat_state,
    resolve_chat_session_id,
    send_chat_message,
    use_chat_session,
)
from .state import session_summary


def _settings_from_ctx(ctx: click.Context) -> Settings:
    return Settings(
        host=ctx.obj["host"],
        port=ctx.obj["port"],
        timeout=ctx.obj["timeout"],
    )


def _emit_result(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if "text" in payload:
            click.echo(payload.get("text", ""))
        elif "reply" in payload:
            click.echo(payload.get("reply", ""))
        elif "report" in payload:
            click.echo(payload.get("report", ""))
        elif "path" in payload and payload.get("path"):
            click.echo(payload["path"])
        elif "paths" in payload:
            for path in payload.get("paths", []):
                click.echo(path)
        else:
            click.echo(str(payload))

    if payload.get("status") == "error":
        raise click.exceptions.Exit(1)


def _text_payload(command: str, result: TextGenerationResult, image_path: str | None = None) -> dict[str, Any]:
    payload = {
        "command": command,
        "product": "gemini",
        "stability": "supported",
        "status": "ok",
        "error": None,
        "text": result.text,
        "images": result.images,
        "thinking": result.thinking,
        "target": asdict(result.target) if result.target else None,
        "session": asdict(result.session) if result.session else None,
    }
    if image_path is not None:
        payload["image"] = image_path
    return payload


def _image_payload(result: ImageGenerationResult) -> dict[str, Any]:
    is_error = result.error_code is not None
    return {
        "command": "generate_image",
        "product": "gemini",
        "stability": "supported",
        "status": "error" if is_error else "ok",
        "error": None
        if not is_error
        else {
            "code": result.error_code,
            "message": (result.error_code or "image_generation_failed").replace("_", " "),
        },
        "error_code": result.error_code,
        "paths": result.paths,
        "state_path": result.state_path,
        "evidence": result.evidence,
        "target": asdict(result.target) if result.target else None,
        "session": asdict(result.session) if result.session else None,
    }


def _stable_error_payload(command: str, exc: GeminiOperationError) -> dict[str, Any]:
    return {
        "command": command,
        "product": "gemini",
        "stability": "supported",
        "status": "error",
        "error": {
            "code": exc.code,
            "message": exc.message,
        },
        "target": asdict(exc.target),
        "session": asdict(exc.session),
    }


def _experimental_error(command: str, exc: GeminiOperationError) -> dict[str, Any]:
    return experimental_error_payload(
        "gemini",
        command,
        code=exc.code,
        message=exc.message,
        target=asdict(exc.target),
        session=asdict(exc.session),
    )


def _video_payload(result: VideoGenerationResult) -> dict[str, Any]:
    if result.is_error:
        return experimental_error_payload(
            "gemini",
            "generate_video",
            code=result.error_code or "video_generation_failed",
            message=result.error_message or "Gemini video generation failed.",
            target=asdict(result.target) if result.target else None,
            session=asdict(result.session) if result.session else None,
            evidence=result.evidence,
            path=result.path,
        )
    return experimental_success_payload(
        "gemini",
        "generate_video",
        target=asdict(result.target) if result.target else None,
        session=asdict(result.session) if result.session else None,
        evidence=result.evidence,
        path=result.path,
    )


def _deep_research_payload(result) -> dict[str, Any]:
    if result.is_error:
        return experimental_error_payload(
            "gemini",
            "deep_research",
            code=result.error_code or "deep_research_failed",
            message=result.error_message or "Gemini deep research failed.",
            query=result.query,
            target=asdict(result.target) if result.target else None,
            session=asdict(result.session) if result.session else None,
            evidence=result.evidence,
            report=result.report,
            sources=result.sources,
        )
    return experimental_success_payload(
        "gemini",
        "deep_research",
        query=result.query,
        report=result.report,
        sources=result.sources,
        evidence=result.evidence,
        target=asdict(result.target) if result.target else None,
        session=asdict(result.session) if result.session else None,
    )


@click.group("gemini")
def gemini_group() -> None:
    """Gemini Web commands with stable and experimental packs."""


@gemini_group.group("generate")
def gemini_generate_group() -> None:
    """Stable Gemini generation commands."""


@gemini_generate_group.command("text")
@click.argument("prompt")
@click.option("--timeout", default=60.0, show_default=True, type=float, help="Timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def gemini_generate_text(ctx: click.Context, prompt: str, timeout: float, json_output: bool) -> None:
    try:
        result = asyncio.run(generate_text(_settings_from_ctx(ctx), prompt, timeout))
        payload = _text_payload("generate_text", result)
    except GeminiOperationError as exc:
        payload = _stable_error_payload("generate_text", exc)
    _emit_result(payload, json_output)


@gemini_group.command("ask")
@click.argument("prompt")
@click.option("--timeout", default=30.0, show_default=True, type=float, help="Timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def gemini_ask(ctx: click.Context, prompt: str, timeout: float, json_output: bool) -> None:
    try:
        result = asyncio.run(generate_text(_settings_from_ctx(ctx), prompt, timeout))
        payload = _text_payload("ask", result)
    except GeminiOperationError as exc:
        payload = _stable_error_payload("ask", exc)
    _emit_result(payload, json_output)


@gemini_generate_group.command("image")
@click.argument("prompt")
@click.option("--output", default=".", help="Directory for generated images")
@click.option("--timeout", default=120.0, show_default=True, type=float, help="Timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def gemini_generate_image(
    ctx: click.Context,
    prompt: str,
    output: str,
    timeout: float,
    json_output: bool,
) -> None:
    try:
        result = asyncio.run(generate_image(_settings_from_ctx(ctx), prompt, output, timeout))
        payload = _image_payload(result)
    except GeminiOperationError as exc:
        payload = _stable_error_payload("generate_image", exc)
    _emit_result(payload, json_output)


@gemini_generate_group.command("vision")
@click.argument("prompt")
@click.option("-i", "--image", "image_path", required=True, type=click.Path(exists=True), help="Image path")
@click.option("--timeout", default=90.0, show_default=True, type=float, help="Timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def gemini_generate_vision(
    ctx: click.Context,
    prompt: str,
    image_path: str,
    timeout: float,
    json_output: bool,
) -> None:
    try:
        result = asyncio.run(generate_vision(_settings_from_ctx(ctx), prompt, image_path, timeout))
        payload = _text_payload("generate_vision", result, image_path=image_path)
    except GeminiOperationError as exc:
        payload = _stable_error_payload("generate_vision", exc)
    _emit_result(payload, json_output)


@gemini_generate_group.command("video")
@click.argument("prompt")
@click.option("--output", default=".", help="Directory for generated video")
@click.option("--timeout", default=180.0, show_default=True, type=float, help="Timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def gemini_generate_video(
    ctx: click.Context,
    prompt: str,
    output: str,
    timeout: float,
    json_output: bool,
) -> None:
    """Experimental Gemini video generation."""
    try:
        result = asyncio.run(generate_video(_settings_from_ctx(ctx), prompt, output, timeout))
        payload = _video_payload(result)
    except GeminiOperationError as exc:
        payload = _experimental_error("generate_video", exc)
    _emit_result(payload, json_output)


@gemini_group.command("deep-research")
@click.argument("query")
@click.option("--timeout", default=300.0, show_default=True, type=float, help="Timeout in seconds")
@click.option("--output", "output_path", default=None, help="Optional file path for the report")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def gemini_deep_research(
    ctx: click.Context,
    query: str,
    timeout: float,
    output_path: str | None,
    json_output: bool,
) -> None:
    """Experimental Gemini deep research."""
    try:
        result = asyncio.run(deep_research(_settings_from_ctx(ctx), query, timeout, output_path))
        payload = _deep_research_payload(result)
    except GeminiOperationError as exc:
        payload = _experimental_error("deep_research", exc)
    _emit_result(payload, json_output)


@gemini_group.group("chat")
def gemini_chat_group() -> None:
    """Experimental Gemini chat sessions."""


@gemini_chat_group.command("start")
@click.option("--session-id", default=None, help="Session ID to create")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def gemini_chat_start(session_id: str | None, json_output: bool) -> None:
    """Experimental Gemini chat start."""
    resolved = session_id or uuid.uuid4().hex[:8]
    session = create_chat_session(resolved)
    payload = experimental_success_payload(
        "gemini",
        "chat_start",
        chat_session=session_summary(session),
    )
    _emit_result(payload, json_output)


@gemini_chat_group.command("list")
@click.option("--limit", default=10, show_default=True, type=int, help="Number of sessions to show")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def gemini_chat_list(limit: int, json_output: bool) -> None:
    """Experimental Gemini chat list."""
    payload = experimental_success_payload(
        "gemini",
        "chat_list",
        chat_sessions=[session_summary(session) for session in list_chat_state(limit)],
    )
    _emit_result(payload, json_output)


@gemini_chat_group.command("use")
@click.argument("session_id")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
def gemini_chat_use(session_id: str, json_output: bool) -> None:
    """Experimental Gemini chat use."""
    try:
        session = use_chat_session(session_id)
        payload = experimental_success_payload(
            "gemini",
            "chat_use",
            chat_session=session_summary(session),
        )
    except RuntimeError as exc:
        payload = experimental_error_payload(
            "gemini",
            "chat_use",
            code="chat_session_not_found",
            message=str(exc),
        )
    _emit_result(payload, json_output)


@gemini_chat_group.command("send")
@click.argument("message")
@click.option("--session", "session_id", default=None, help="Chat session ID")
@click.option("--timeout", default=60.0, show_default=True, type=float, help="Timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def gemini_chat_send(
    ctx: click.Context,
    message: str,
    session_id: str | None,
    timeout: float,
    json_output: bool,
) -> None:
    """Experimental Gemini chat send."""
    try:
        resolved = resolve_chat_session_id(session_id)
        result = asyncio.run(send_chat_message(_settings_from_ctx(ctx), resolved, message, timeout))
        payload = experimental_success_payload(
            "gemini",
            "chat_send",
            **result,
        )
    except RuntimeError as exc:
        payload = experimental_error_payload(
            "gemini",
            "chat_send",
            code="chat_session_not_found",
            message=str(exc),
        )
    except GeminiOperationError as exc:
        payload = _experimental_error("chat_send", exc)
    _emit_result(payload, json_output)
