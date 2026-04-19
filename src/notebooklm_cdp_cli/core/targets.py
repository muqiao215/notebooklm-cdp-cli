from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings
from ..state import get_product_target_selection, set_product_target_selection
from .cdp import CDPTransport
from .product import ProductSpec


@dataclass(frozen=True, slots=True)
class TargetRecord:
    target_id: str
    target_type: str
    title: str
    url: str
    web_socket_url: str | None
    kind: str
    matches_product: bool
    attached: bool = False


@dataclass(frozen=True, slots=True)
class TargetResolution:
    target: TargetRecord | None
    resolution_source: str
    selected: "TargetSelection | None" = None


@dataclass(frozen=True, slots=True)
class TargetSelection:
    target_id: str | None
    title: str | None
    url: str | None
    status: str


class TargetResolutionError(RuntimeError):
    def __init__(self, code: str, message: str, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.evidence = evidence or {}


@dataclass(slots=True)
class TargetSession:
    target: TargetRecord
    transport: CDPTransport
    resolution_source: str
    session_id: str | None = None

    def evidence(self) -> dict[str, Any]:
        return {
            "target_id": self.target.target_id,
            "session_id": self.session_id,
            "target_url": self.target.url,
            "web_socket_url": self.target.web_socket_url,
            "resolution_source": self.resolution_source,
            "via": "page_websocket",
        }

    async def close(self) -> None:
        await self.transport.close()


def _normalize_ws_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("http://"):
        return "ws://" + value[7:]
    if value.startswith("https://"):
        return "wss://" + value[8:]
    return value


def _to_record(raw: dict[str, Any], spec: ProductSpec) -> TargetRecord:
    url = str(raw.get("url", "") or "")
    matches_product = spec.matches_url(url)
    return TargetRecord(
        target_id=str(raw.get("id", "") or ""),
        target_type=str(raw.get("type", "") or ""),
        title=str(raw.get("title", "") or ""),
        url=url,
        web_socket_url=_normalize_ws_url(raw.get("webSocketDebuggerUrl")),
        kind="product" if matches_product else "other",
        matches_product=matches_product,
        attached=bool(raw.get("attached", False)),
    )


def target_to_dict(target: TargetRecord | None, *, resolution_source: str | None = None) -> dict[str, Any] | None:
    if target is None:
        return None
    payload = {
        "target_id": target.target_id,
        "title": target.title,
        "url": target.url,
        "attached": target.attached,
    }
    if resolution_source is not None:
        payload["resolution_source"] = resolution_source
    return payload

def selection_to_dict(selection: TargetSelection | None) -> dict[str, Any]:
    if selection is None:
        return {
            "target_id": None,
            "title": None,
            "url": None,
            "status": "none",
        }
    return {
        "target_id": selection.target_id,
        "title": selection.title,
        "url": selection.url,
        "status": selection.status,
    }


def resolve_target(raw_targets: list[dict[str, Any]], spec: ProductSpec) -> TargetResolution:
    candidates = [
        _to_record(raw, spec)
        for raw in raw_targets
        if str(raw.get("type", "")) == "page"
    ]
    product_targets = [candidate for candidate in candidates if candidate.matches_product and candidate.web_socket_url]
    if not product_targets:
        return TargetResolution(target=None, resolution_source="none")
    return TargetResolution(
        target=min(product_targets, key=lambda target: (target.url, target.target_id, target.web_socket_url or "")),
        resolution_source="product_page",
    )


def discover_product_targets(raw_targets: list[dict[str, Any]], spec: ProductSpec) -> list[TargetRecord]:
    return [
        _to_record(raw, spec)
        for raw in raw_targets
        if str(raw.get("type", "")) == "page"
        and spec.matches_url(str(raw.get("url", "") or ""))
        and raw.get("webSocketDebuggerUrl")
    ]


def resolve_selected_target(
    targets: list[TargetRecord],
    *,
    selected_target_id: str | None,
    selected_url: str | None = None,
    selected_title: str | None = None,
) -> TargetSelection:
    if not selected_target_id:
        return TargetSelection(target_id=None, title=None, url=None, status="none")

    for target in targets:
        if target.target_id == selected_target_id:
            return TargetSelection(
                target_id=target.target_id,
                title=target.title,
                url=target.url,
                status="selected",
            )

    return TargetSelection(
        target_id=selected_target_id,
        title=selected_title,
        url=selected_url,
        status="stale",
    )


def _matches_target_token(target: TargetRecord, token: str) -> bool:
    normalized = token.strip()
    if not normalized:
        return False
    return (
        target.target_id == normalized
        or target.target_id.startswith(normalized)
        or target.url == normalized
        or target.title == normalized
    )


def _resolve_requested_target(targets: list[TargetRecord], requested_target: str) -> TargetRecord:
    matches = [target for target in targets if _matches_target_token(target, requested_target)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise TargetResolutionError(
            "ambiguous_target",
            f"Target reference is ambiguous: {requested_target}",
            evidence={
                "requested_target": requested_target,
                "candidate_ids": [target.target_id for target in matches],
            },
        )
    raise TargetResolutionError(
        "target_not_found",
        f"Target not found: {requested_target}",
        evidence={"requested_target": requested_target},
    )


def resolve_product_target(
    raw_targets: list[dict[str, Any]],
    spec: ProductSpec,
    *,
    requested_target: str | None = None,
    selected_target_id: str | None = None,
    selected_url: str | None = None,
    selected_title: str | None = None,
) -> TargetResolution:
    targets = discover_product_targets(raw_targets, spec)
    selected = resolve_selected_target(
        targets,
        selected_target_id=selected_target_id,
        selected_url=selected_url,
        selected_title=selected_title,
    )

    if requested_target:
        return TargetResolution(
            target=_resolve_requested_target(targets, requested_target),
            resolution_source="manual",
            selected=selected,
        )

    if selected.status == "selected" and selected.target_id:
        for target in targets:
            if target.target_id == selected.target_id:
                return TargetResolution(target=target, resolution_source="explicit", selected=selected)

    for target in targets:
        if target.attached:
            return TargetResolution(target=target, resolution_source="active", selected=selected)

    if targets:
        return TargetResolution(target=targets[0], resolution_source="first", selected=selected)

    return TargetResolution(target=None, resolution_source="none", selected=selected)


def _selection_from_state(product: str) -> dict[str, Any]:
    return get_product_target_selection(product) or {}


def _resolve_from_state(
    raw_targets: list[dict[str, Any]],
    spec: ProductSpec,
    product: str,
    *,
    requested_target: str | None = None,
) -> TargetResolution:
    selection = _selection_from_state(product)
    return resolve_product_target(
        raw_targets,
        spec,
        requested_target=requested_target,
        selected_target_id=selection.get("target_id"),
        selected_url=selection.get("url"),
        selected_title=selection.get("title"),
    )


async def list_product_targets(settings: Settings, spec: ProductSpec, product: str) -> dict[str, Any]:
    raw_targets = await TargetService(settings).list_raw_targets()
    targets = discover_product_targets(raw_targets, spec)
    resolution = _resolve_from_state(raw_targets, spec, product)
    selected = resolution.selected or TargetSelection(target_id=None, title=None, url=None, status="none")
    selected_id = selected.target_id if selected.status == "selected" else None
    return {
        "count": len(targets),
        "targets": [
            {
                **(target_to_dict(target) or {}),
                "selected": target.target_id == selected_id,
            }
            for target in targets
        ],
        "selected": selection_to_dict(selected),
        "resolved": target_to_dict(resolution.target, resolution_source=resolution.resolution_source),
        "evidence": {
            "candidate_count": len(targets),
            "resolution_source": resolution.resolution_source,
        },
    }


async def select_product_target(settings: Settings, spec: ProductSpec, product: str, target_ref: str) -> dict[str, Any]:
    raw_targets = await TargetService(settings).list_raw_targets()
    targets = discover_product_targets(raw_targets, spec)
    selected_target = _resolve_requested_target(targets, target_ref)
    set_product_target_selection(
        product,
        target_id=selected_target.target_id,
        title=selected_target.title,
        url=selected_target.url,
    )
    selected = TargetSelection(
        target_id=selected_target.target_id,
        title=selected_target.title,
        url=selected_target.url,
        status="selected",
    )
    return {
        "selected": selection_to_dict(selected),
        "resolved": target_to_dict(selected_target, resolution_source="manual"),
        "evidence": {
            "candidate_count": len(targets),
            "resolution_source": "manual",
            "selection_scope": "product",
        },
    }


async def current_product_target(settings: Settings, spec: ProductSpec, product: str) -> dict[str, Any]:
    raw_targets = await TargetService(settings).list_raw_targets()
    targets = discover_product_targets(raw_targets, spec)
    resolution = _resolve_from_state(raw_targets, spec, product)
    return {
        "selected": selection_to_dict(resolution.selected),
        "resolved": target_to_dict(resolution.target, resolution_source=resolution.resolution_source),
        "evidence": {
            "candidate_count": len(targets),
            "resolution_source": resolution.resolution_source,
        },
    }


async def open_product_target_session(
    settings: Settings,
    spec: ProductSpec,
    product: str,
    *,
    requested_target: str | None = None,
) -> tuple[TargetSession, TargetResolution]:
    raw_targets = await TargetService(settings).list_raw_targets()
    resolution = _resolve_from_state(raw_targets, spec, product, requested_target=requested_target)
    if resolution.target is None or resolution.target.web_socket_url is None:
        raise TargetResolutionError(
            "target_not_found",
            f"No {spec.name} tab is available",
            evidence={
                "resolution_source": resolution.resolution_source,
                "selected": selection_to_dict(resolution.selected),
            },
        )
    transport = await CDPTransport(resolution.target.web_socket_url).connect()
    return (
        TargetSession(
            target=resolution.target,
            transport=transport,
            resolution_source=resolution.resolution_source,
        ),
        resolution,
    )


async def open_product_target(settings: Settings, spec: ProductSpec, product: str, target_ref: str | None = None) -> dict[str, Any]:
    session, resolution = await open_product_target_session(
        settings,
        spec,
        product,
        requested_target=target_ref,
    )
    try:
        return {
            "selected": selection_to_dict(resolution.selected),
            "resolved": target_to_dict(resolution.target, resolution_source=resolution.resolution_source),
            "session": {
                "attached": True,
                "session_id": session.session_id,
            },
            "evidence": {
                "resolution_source": resolution.resolution_source,
                "via": "page_websocket",
            },
        }
    finally:
        await session.close()


class TargetService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.settings.base_url, timeout=self.settings.timeout)

    async def list_raw_targets(self) -> list[dict[str, Any]]:
        async with self._client() as client:
            response = await client.get("/json/list")
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else []

    async def resolve_target(self, spec: ProductSpec) -> TargetResolution:
        return resolve_target(await self.list_raw_targets(), spec)

    async def create_target(self, spec: ProductSpec, url: str | None = None) -> TargetRecord:
        target_url = url or spec.default_url
        async with self._client() as client:
            response = await client.put("/json/new", params={"url": target_url})
            if response.status_code >= 400:
                response = await client.get("/json/new", params={"url": target_url})
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"Could not create a {spec.name} tab")
        record = _to_record(payload, spec)
        if not record.web_socket_url:
            raise RuntimeError(f"Created {spec.name} tab is missing a websocket debugger URL")
        return record


async def open_target_session(settings: Settings, spec: ProductSpec) -> TargetSession:
    resolution = await TargetService(settings).resolve_target(spec)
    if resolution.target is None or resolution.target.web_socket_url is None:
        raise RuntimeError(f"No {spec.name} tab is available")
    transport = await CDPTransport(resolution.target.web_socket_url).connect()
    return TargetSession(target=resolution.target, transport=transport, resolution_source=resolution.resolution_source)


async def open_or_create_target_session(settings: Settings, spec: ProductSpec) -> TargetSession:
    service = TargetService(settings)
    resolution = await service.resolve_target(spec)
    if resolution.target is not None and resolution.target.web_socket_url is not None:
        transport = await CDPTransport(resolution.target.web_socket_url).connect()
        return TargetSession(target=resolution.target, transport=transport, resolution_source=resolution.resolution_source)

    target = await service.create_target(spec)
    transport = await CDPTransport(target.web_socket_url or "").connect()
    return TargetSession(target=target, transport=transport, resolution_source="created")
