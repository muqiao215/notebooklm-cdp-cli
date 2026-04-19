from __future__ import annotations

import asyncio
import json
from typing import Any

import click

from ..config import Settings
from .output import stable_error_payload, success_payload
from .product import PRODUCT_SPECS
from .targets import (
    TargetResolutionError,
    current_product_target,
    list_product_targets,
    open_product_target,
    select_product_target,
)


PRODUCT_CHOICE = click.Choice(sorted(PRODUCT_SPECS), case_sensitive=False)


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


def _payload(product: str, command: str, data: dict[str, Any]) -> dict[str, Any]:
    return success_payload(product, command, **data)


def _error_payload(product: str, command: str, exc: TargetResolutionError) -> dict[str, Any]:
    return stable_error_payload(
        product,
        command,
        code=exc.code,
        message=exc.message,
        evidence=exc.evidence,
    )


async def list_targets_for_product(settings: Settings, product: str) -> dict[str, Any]:
    return {
        "product": product,
        "stability": "supported",
        "status": "ok",
        "error": None,
        **await list_product_targets(settings, PRODUCT_SPECS[product], product),
    }


async def select_target_for_product(settings: Settings, product: str, target_ref: str) -> dict[str, Any]:
    return {
        "product": product,
        "stability": "supported",
        "status": "ok",
        "error": None,
        **await select_product_target(settings, PRODUCT_SPECS[product], product, target_ref),
    }


async def current_target_for_product(settings: Settings, product: str) -> dict[str, Any]:
    return {
        "product": product,
        "stability": "supported",
        "status": "ok",
        "error": None,
        **await current_product_target(settings, PRODUCT_SPECS[product], product),
    }


async def open_target_for_product(settings: Settings, product: str, target_ref: str | None) -> dict[str, Any]:
    return {
        "product": product,
        "stability": "supported",
        "status": "ok",
        "error": None,
        **await open_product_target(settings, PRODUCT_SPECS[product], product, target_ref),
    }


def emit_targets_list(ctx: click.Context, product: str, json_output: bool, *, command: str = "targets_list") -> None:
    try:
        data = asyncio.run(list_targets_for_product(_settings_from_ctx(ctx), product))
        payload = {**data, "command": command}
    except TargetResolutionError as exc:
        payload = _error_payload(product, command, exc)
    _emit(payload, json_output)


def emit_targets_select(
    ctx: click.Context,
    product: str,
    target_ref: str,
    json_output: bool,
    *,
    command: str = "targets_select",
) -> None:
    try:
        data = asyncio.run(select_target_for_product(_settings_from_ctx(ctx), product, target_ref))
        payload = {**data, "command": command}
    except TargetResolutionError as exc:
        payload = _error_payload(product, command, exc)
    _emit(payload, json_output)


def emit_targets_current(ctx: click.Context, product: str, json_output: bool, *, command: str = "targets_current") -> None:
    try:
        data = asyncio.run(current_target_for_product(_settings_from_ctx(ctx), product))
        payload = {**data, "command": command}
    except TargetResolutionError as exc:
        payload = _error_payload(product, command, exc)
    _emit(payload, json_output)


def emit_targets_open(
    ctx: click.Context,
    product: str,
    target_ref: str | None,
    json_output: bool,
    *,
    command: str = "targets_open",
) -> None:
    try:
        data = asyncio.run(open_target_for_product(_settings_from_ctx(ctx), product, target_ref))
        payload = {**data, "command": command}
    except TargetResolutionError as exc:
        payload = _error_payload(product, command, exc)
    _emit(payload, json_output)


@click.group("targets")
def targets_group() -> None:
    """Shared browser target commands."""


@targets_group.command("list")
@click.option("--product", required=True, type=PRODUCT_CHOICE, help="Product target namespace")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def targets_list(ctx: click.Context, product: str, json_output: bool) -> None:
    emit_targets_list(ctx, product.lower(), json_output)


@targets_group.command("select")
@click.argument("target_ref")
@click.option("--product", required=True, type=PRODUCT_CHOICE, help="Product target namespace")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def targets_select(ctx: click.Context, target_ref: str, product: str, json_output: bool) -> None:
    emit_targets_select(ctx, product.lower(), target_ref, json_output)


@targets_group.command("current")
@click.option("--product", required=True, type=PRODUCT_CHOICE, help="Product target namespace")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def targets_current(ctx: click.Context, product: str, json_output: bool) -> None:
    emit_targets_current(ctx, product.lower(), json_output)


@targets_group.command("open")
@click.argument("target_ref", required=False)
@click.option("--target-id", "target_id", default=None, help="Target ID/reference")
@click.option("--product", required=True, type=PRODUCT_CHOICE, help="Product target namespace")
@click.option("--json", "json_output", is_flag=True, help="Emit JSON")
@click.pass_context
def targets_open(ctx: click.Context, target_ref: str | None, target_id: str | None, product: str, json_output: bool) -> None:
    if target_ref and target_id:
        raise click.ClickException("Use either positional target_ref or --target-id, not both.")
    emit_targets_open(ctx, product.lower(), target_id or target_ref, json_output)
