from __future__ import annotations

import asyncio
import json
from typing import Any

import click

from ...config import Settings
from ...core.targets import TargetResolutionError
from ...core.targets_cli import (
    emit_targets_current,
    emit_targets_list,
    emit_targets_open,
    emit_targets_select,
)
from .ops import (
    ColabOperationError,
    cell_count,
    download_artifact,
    download_file,
    export_notebook,
    get_artifact,
    latest_artifact,
    list_artifacts,
    list_files,
    notebook_info,
    notebook_summary,
    run_cell_code,
    run_cell_file,
    runtime_status,
    upload_file,
)


def _settings_from_ctx(ctx: click.Context) -> Settings:
    return Settings(
        host=ctx.obj["host"],
        port=ctx.obj["port"],
        timeout=ctx.obj["timeout"],
    )


def _emit(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        click.echo(str(payload))
    if payload.get("status") == "error":
        raise click.exceptions.Exit(1)


def _with_command(payload: dict[str, Any], command: str) -> dict[str, Any]:
    return {**payload, "command": command}


def _error_payload(command: str, stability: str, code: str, message: str, **fields: Any) -> dict[str, Any]:
    return {
        "product": "colab",
        "command": command,
        "stability": stability,
        "status": "error",
        "error": {
            "code": code,
            "message": message,
        },
        **fields,
    }


def _operation_error(
    command: str,
    exc: ColabOperationError | TargetResolutionError,
    *,
    default_stability: str = "supported",
) -> dict[str, Any]:
    if isinstance(exc, TargetResolutionError):
        return _error_payload(
            command,
            default_stability,
            exc.code,
            exc.message,
            evidence=exc.evidence,
        )
    return _error_payload(
        command,
        exc.stability or default_stability,
        exc.code,
        exc.message,
        target=exc.target,
        session=exc.session,
        evidence=exc.evidence,
        uncertainty=exc.uncertainty,
        **exc.extra,
    )


@click.group("colab")
def colab_group() -> None:
    """Colab commands."""


@colab_group.group("notebook")
def colab_notebook_group() -> None:
    """Colab notebook commands."""


@colab_notebook_group.command("list")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_notebook_list(ctx: click.Context, json_output: bool) -> None:
    emit_targets_list(ctx, "colab", json_output, command="notebook_list")


@colab_notebook_group.command("select")
@click.argument("target_ref")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_notebook_select(ctx: click.Context, target_ref: str, json_output: bool) -> None:
    emit_targets_select(ctx, "colab", target_ref, json_output, command="notebook_select")


@colab_notebook_group.command("current")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_notebook_current(ctx: click.Context, json_output: bool) -> None:
    emit_targets_current(ctx, "colab", json_output, command="notebook_current")


@colab_notebook_group.command("open")
@click.argument("target_ref", required=False)
@click.option("--target-id", "target_id", default=None, help="Target ID/reference")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_notebook_open(
    ctx: click.Context,
    target_ref: str | None,
    target_id: str | None,
    json_output: bool,
) -> None:
    if target_ref and target_id:
        raise click.ClickException("Use either positional target_ref or --target-id, not both.")
    emit_targets_open(ctx, "colab", target_id or target_ref, json_output, command="notebook_open")


@colab_notebook_group.command("info")
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_notebook_info(ctx: click.Context, target_id: str | None, json_output: bool) -> None:
    command = "notebook_info"
    try:
        payload = _with_command(asyncio.run(notebook_info(_settings_from_ctx(ctx), target_id)), command)
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc)
    _emit(payload, json_output)


@colab_notebook_group.command("summary")
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_notebook_summary(ctx: click.Context, target_id: str | None, json_output: bool) -> None:
    command = "notebook_summary"
    try:
        payload = _with_command(asyncio.run(notebook_summary(_settings_from_ctx(ctx), target_id)), command)
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc)
    _emit(payload, json_output)


@colab_notebook_group.command("export")
@click.option("--format", "format_", type=click.Choice(["ipynb", "py"]), default="ipynb", show_default=True)
@click.option("--output", required=True, help="Output file path")
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--timeout", default=45.0, show_default=True, type=float, help="Export timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_notebook_export(
    ctx: click.Context,
    format_: str,
    output: str,
    target_id: str | None,
    timeout: float,
    json_output: bool,
) -> None:
    command = "notebook_export"
    try:
        payload = _with_command(
            asyncio.run(export_notebook(_settings_from_ctx(ctx), format_, output, target_id, timeout)),
            command,
        )
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc, default_stability="best_effort")
    _emit(payload, json_output)


@colab_group.group("cell")
def colab_cell_group() -> None:
    """Colab cell commands."""


@colab_cell_group.command("count")
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_cell_count(ctx: click.Context, target_id: str | None, json_output: bool) -> None:
    command = "cell_count"
    try:
        payload = _with_command(asyncio.run(cell_count(_settings_from_ctx(ctx), target_id)), command)
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc)
    _emit(payload, json_output)


@colab_cell_group.command("run")
@click.option("--code", required=True, help="Python code to execute")
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--timeout", default=30.0, show_default=True, type=float, help="Execution timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_cell_run(
    ctx: click.Context,
    code: str,
    target_id: str | None,
    timeout: float,
    json_output: bool,
) -> None:
    command = "cell_run"
    try:
        payload = _with_command(asyncio.run(run_cell_code(_settings_from_ctx(ctx), code, target_id, timeout)), command)
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc)
    _emit(payload, json_output)


@colab_cell_group.command("run-file")
@click.argument("file_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--timeout", default=60.0, show_default=True, type=float, help="Execution timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_cell_run_file(
    ctx: click.Context,
    file_path: str,
    target_id: str | None,
    timeout: float,
    json_output: bool,
) -> None:
    command = "cell_run_file"
    try:
        payload = _with_command(asyncio.run(run_cell_file(_settings_from_ctx(ctx), file_path, target_id, timeout)), command)
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc)
    _emit(payload, json_output)


@colab_group.group("file")
def colab_file_group() -> None:
    """Best-effort Colab file commands."""


@colab_file_group.command("upload")
@click.argument("file_path", type=click.Path(dir_okay=False))
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--timeout", default=30.0, show_default=True, type=float, help="Upload timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_file_upload(
    ctx: click.Context,
    file_path: str,
    target_id: str | None,
    timeout: float,
    json_output: bool,
) -> None:
    command = "file_upload"
    try:
        payload = _with_command(asyncio.run(upload_file(_settings_from_ctx(ctx), file_path, target_id, timeout)), command)
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc, default_stability="best_effort")
    _emit(payload, json_output)


@colab_file_group.command("list")
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_file_list(ctx: click.Context, target_id: str | None, json_output: bool) -> None:
    command = "file_list"
    try:
        payload = _with_command(asyncio.run(list_files(_settings_from_ctx(ctx), target_id)), command)
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc, default_stability="best_effort")
    _emit(payload, json_output)


@colab_file_group.command("download")
@click.argument("file_name")
@click.option("--output", default=None, help="Destination file path")
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--timeout", default=30.0, show_default=True, type=float, help="Download timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_file_download(
    ctx: click.Context,
    file_name: str,
    output: str | None,
    target_id: str | None,
    timeout: float,
    json_output: bool,
) -> None:
    command = "file_download"
    try:
        payload = _with_command(
            asyncio.run(download_file(_settings_from_ctx(ctx), file_name, output, target_id, timeout)),
            command,
        )
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc, default_stability="best_effort")
    _emit(payload, json_output)


@colab_group.group("artifact")
def colab_artifact_group() -> None:
    """Best-effort Colab artifact commands."""


@colab_artifact_group.command("list")
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_artifact_list(ctx: click.Context, target_id: str | None, json_output: bool) -> None:
    command = "artifact_list"
    try:
        payload = _with_command(asyncio.run(list_artifacts(_settings_from_ctx(ctx), target_id)), command)
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc, default_stability="best_effort")
    _emit(payload, json_output)


@colab_artifact_group.command("latest")
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_artifact_latest(ctx: click.Context, target_id: str | None, json_output: bool) -> None:
    command = "artifact_latest"
    try:
        payload = _with_command(asyncio.run(latest_artifact(_settings_from_ctx(ctx), target_id)), command)
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc, default_stability="best_effort")
    _emit(payload, json_output)


@colab_artifact_group.command("get")
@click.argument("artifact_id")
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_artifact_get(ctx: click.Context, artifact_id: str, target_id: str | None, json_output: bool) -> None:
    command = "artifact_get"
    try:
        payload = _with_command(asyncio.run(get_artifact(_settings_from_ctx(ctx), artifact_id, target_id)), command)
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc, default_stability="best_effort")
    _emit(payload, json_output)


@colab_artifact_group.command("download")
@click.argument("artifact_id")
@click.option("--output", default=None, help="Destination file path")
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--timeout", default=30.0, show_default=True, type=float, help="Download timeout in seconds")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_artifact_download(
    ctx: click.Context,
    artifact_id: str,
    output: str | None,
    target_id: str | None,
    timeout: float,
    json_output: bool,
) -> None:
    command = "artifact_download"
    try:
        payload = _with_command(
            asyncio.run(download_artifact(_settings_from_ctx(ctx), artifact_id, output, target_id, timeout)),
            command,
        )
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc, default_stability="best_effort")
    _emit(payload, json_output)


@colab_group.group("runtime")
def colab_runtime_group() -> None:
    """Colab runtime commands."""


@colab_runtime_group.command("status")
@click.option("--target-id", default=None, help="Target ID/reference")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def colab_runtime_status(ctx: click.Context, target_id: str | None, json_output: bool) -> None:
    command = "runtime_status"
    try:
        payload = _with_command(asyncio.run(runtime_status(_settings_from_ctx(ctx), target_id)), command)
    except (ColabOperationError, TargetResolutionError) as exc:
        payload = _operation_error(command, exc)
    _emit(payload, json_output)
