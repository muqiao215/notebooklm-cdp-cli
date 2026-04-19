from __future__ import annotations

from typing import Any


def ok_payload(product: str, *, evidence: dict[str, Any] | None = None, **data: Any) -> dict[str, Any]:
    payload = {
        "product": product,
        "status": "ok",
        "error": None,
        **data,
    }
    if evidence is not None:
        payload["evidence"] = evidence
    return payload


def error_payload(
    product: str,
    *,
    code: str,
    message: str,
    evidence: dict[str, Any] | None = None,
    **data: Any,
) -> dict[str, Any]:
    payload = {
        "product": product,
        "status": "error",
        "error": {
            "code": code,
            "message": message,
        },
        **data,
    }
    if evidence is not None:
        payload["evidence"] = evidence
    return payload


def success_payload(product: str, command: str, **fields: Any) -> dict[str, Any]:
    payload = {
        "product": product,
        "command": command,
        "status": "ok",
        "stability": "supported",
        "error": None,
    }
    payload.update(fields)
    return payload


def stable_error_payload(product: str, command: str, *, code: str, message: str, **fields: Any) -> dict[str, Any]:
    payload = {
        "product": product,
        "command": command,
        "status": "error",
        "stability": "supported",
        "error": {
            "code": code,
            "message": message,
        },
    }
    payload.update(fields)
    return payload


def experimental_success_payload(product: str, command: str, **fields: Any) -> dict[str, Any]:
    payload = {
        "product": product,
        "command": command,
        "status": "ok",
        "stability": "experimental",
        "error": None,
    }
    payload.update(fields)
    return payload


def experimental_error_payload(
    product: str,
    command: str,
    *,
    code: str,
    message: str,
    **fields: Any,
) -> dict[str, Any]:
    payload = {
        "product": product,
        "command": command,
        "status": "error",
        "stability": "experimental",
        "error": {
            "code": code,
            "message": message,
        },
    }
    payload.update(fields)
    return payload
