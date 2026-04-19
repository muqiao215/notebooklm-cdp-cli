from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, is_dataclass
from typing import Any

import click

from ...config import Settings
from ...core.output import experimental_error_payload, experimental_success_payload
from .ops import (
    FlowCommandResult,
    FlowOperationError,
    image_to_video,
    open_flow,
    take_screenshot,
    text_to_video,
)


def _settings_from_ctx(ctx: click.Context) -> Settings:
    return Settings(
        host=ctx.obj["host"],
        port=ctx.obj["port"],
        timeout=ctx.obj["timeout"],
    )


def _dict(value: Any) -> Any:
    return asdict(value) if is_dataclass(value) else value


def _payload(result: FlowCommandResult) -> dict[str, Any]:
    fields = {
        "title": result.title,
        "url": result.url,
        "path": result.path,
        "evidence": result.evidence,
        "target": _dict(result.target),
        "session": _dict(result.session),
    }
    if result.is_error:
        return experimental_error_payload(
            "flow",
            result.command,
            code=result.error_code or "flow_operation_failed",
            message=result.error_message or "Flow operation failed",
            **fields,
        )
    return experimental_success_payload("flow", result.command, **fields)


def _emit(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
    elif payload.get("path"):
        click.echo(payload["path"])
    elif payload.get("url"):
        click.echo(payload["url"])
    else:
        click.echo(str(payload))

    if payload.get("status") == "error":
        raise click.exceptions.Exit(1)


def _operation_error_payload(command: str, exc: FlowOperationError) -> dict[str, Any]:
    return experimental_error_payload(
        "flow",
        command,
        code=exc.code,
        message=exc.message,
        target=exc.target,
        session=exc.session,
    )


@click.group("flow")
def flow_group() -> None:
    """Experimental Google Flow commands."""


@flow_group.command("open")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def flow_open(ctx: click.Context, json_output: bool) -> None:
    """Experimental Flow open."""
    try:
        payload = _payload(asyncio.run(open_flow(_settings_from_ctx(ctx))))
    except FlowOperationError as exc:
        payload = _operation_error_payload("open", exc)
    _emit(payload, json_output)


@flow_group.command("text-to-video")
@click.argument("prompt")
@click.option("--output", default=".", help="Directory for generated video")
@click.option("--timeout", default=180.0, show_default=True, type=float, help="Timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def flow_text_to_video(ctx: click.Context, prompt: str, output: str, timeout: float, json_output: bool) -> None:
    """Experimental Flow text-to-video."""
    try:
        payload = _payload(asyncio.run(text_to_video(_settings_from_ctx(ctx), prompt, output, timeout)))
    except FlowOperationError as exc:
        payload = _operation_error_payload("text_to_video", exc)
    _emit(payload, json_output)


@flow_group.command("image-to-video")
@click.argument("image_path", type=click.Path(exists=True))
@click.option("--prompt", default=None, help="Optional text prompt")
@click.option("--output", default=".", help="Directory for generated video")
@click.option("--timeout", default=180.0, show_default=True, type=float, help="Timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def flow_image_to_video(
    ctx: click.Context,
    image_path: str,
    prompt: str | None,
    output: str,
    timeout: float,
    json_output: bool,
) -> None:
    """Experimental Flow image-to-video."""
    try:
        payload = _payload(asyncio.run(image_to_video(_settings_from_ctx(ctx), image_path, prompt, output, timeout)))
    except FlowOperationError as exc:
        payload = _operation_error_payload("image_to_video", exc)
    _emit(payload, json_output)


@flow_group.command("screenshot")
@click.argument("path", default="flow_screenshot.png")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def flow_screenshot(ctx: click.Context, path: str, json_output: bool) -> None:
    """Experimental Flow screenshot."""
    try:
        payload = _payload(asyncio.run(take_screenshot(_settings_from_ctx(ctx), path)))
    except FlowOperationError as exc:
        payload = _operation_error_payload("screenshot", exc)
    _emit(payload, json_output)
