from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any

from ...config import Settings
from ...core.product import COLAB_PRODUCT
from ...core.targets import TargetResolution, TargetSession, open_product_target_session


class ColabOperationError(RuntimeError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        target: dict[str, Any] | None = None,
        session: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
        uncertainty: list[str] | None = None,
        stability: str = "supported",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.target = target
        self.session = session
        self.evidence = evidence or {}
        self.uncertainty = list(uncertainty or [])
        self.stability = stability
        self.extra = extra or {}


_BEST_EFFORT_INLINE_TRANSFER_LIMIT = 5 * 1024 * 1024


def _supported_result(**fields: Any) -> dict[str, Any]:
    return {
        "product": "colab",
        "stability": "supported",
        "status": "ok",
        "error": None,
        **fields,
    }


def _best_effort_result(**fields: Any) -> dict[str, Any]:
    return {
        "product": "colab",
        "stability": "best_effort",
        "status": "ok",
        "error": None,
        **fields,
    }


def _target_evidence(session: TargetSession, resolution: TargetResolution) -> dict[str, Any]:
    return {
        "target_id": session.target.target_id,
        "title": session.target.title,
        "url": session.target.url,
        "resolution_source": resolution.resolution_source,
    }


def _session_evidence(session: TargetSession) -> dict[str, Any]:
    return {
        "attached": True,
        "session_id": session.session_id,
    }


def _excerpt(value: str | None, limit: int = 120) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _normalize_file_entry(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(raw.get("name", "") or "unknown"),
        "size": int(raw.get("size") or 0),
        "type": str(raw.get("type", "") or "file"),
        "path": str(raw.get("path", "") or ""),
        "download_url": str(raw.get("download_url", "") or ""),
        "source": str(raw.get("source", "") or ""),
    }


def _normalize_artifact_entry(raw: dict[str, Any]) -> dict[str, Any]:
    artifact_id = str(raw.get("artifact_id", "") or raw.get("id", "") or "")
    return {
        "artifact_id": artifact_id,
        "name": str(raw.get("name", "") or "unknown"),
        "type": str(raw.get("type", "") or "file"),
        "url": str(raw.get("url", "") or ""),
        "size": int(raw.get("size") or 0),
        "created_at": raw.get("created_at"),
        "source": str(raw.get("source", "") or ""),
    }


def _write_bytes(path: str, data: bytes) -> int:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination.stat().st_size


def _unsupported_download_url(url: str) -> bool:
    if not url:
        return True
    lowered = url.lower()
    return lowered.startswith("blob:") or lowered.startswith("data:") or not (
        lowered.startswith("http://") or lowered.startswith("https://")
    )


def _merge_uncertainty(*groups: list[str] | None) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for item in group or []:
            if item not in merged:
                merged.append(item)
    return merged


def classify_runtime_probe(probe: dict[str, Any]) -> dict[str, Any]:
    if probe.get("colab_api_available"):
        return {
            "state": "connected",
            "attached": True,
            "interactive": True,
            "executor_hint": "google.colab.kernel",
            "kernel_id": probe.get("kernel_id"),
            "confidence": "high",
            "uncertainty": [],
        }

    if probe.get("connect_button_visible"):
        return {
            "state": "disconnected",
            "attached": False,
            "interactive": True,
            "executor_hint": None,
            "kernel_id": None,
            "confidence": "medium",
            "uncertainty": ["dom_only", "kernel_api_unavailable"],
        }

    if int(probe.get("running_cells") or 0) > 0:
        return {
            "state": "running",
            "attached": None,
            "interactive": True,
            "executor_hint": "running_cell_dom_signal",
            "kernel_id": None,
            "confidence": "low",
            "uncertainty": ["dom_only", "kernel_api_unavailable"],
        }

    if int(probe.get("output_cells") or 0) > 0 or int(probe.get("execution_counts") or 0) > 0:
        return {
            "state": "unknown",
            "attached": None,
            "interactive": True,
            "executor_hint": "prior_output_dom_signal",
            "kernel_id": None,
            "confidence": "low",
            "uncertainty": ["prior_outputs_do_not_prove_current_runtime", "kernel_api_unavailable"],
        }

    return {
        "state": "unknown",
        "attached": None,
        "interactive": None,
        "executor_hint": None,
        "kernel_id": None,
        "confidence": "low",
        "uncertainty": ["no_reliable_runtime_signal"],
    }


def summarize_notebook_probe(
    *,
    probe: dict[str, Any],
    runtime: dict[str, Any],
    resolution_source: str,
) -> dict[str, Any]:
    return {
        "title": probe.get("title") or "",
        "url": probe.get("url") or "",
        "runtime_state": runtime.get("state"),
        "runtime_confidence": runtime.get("confidence"),
        "runtime_uncertainty": list(runtime.get("uncertainty") or []),
        "total_cells": int(probe.get("total_cells") or 0),
        "current_cell": int(probe.get("current_cell") if probe.get("current_cell") is not None else -1),
        "last_output_excerpt": _excerpt(probe.get("last_output")),
        "last_error_excerpt": _excerpt(probe.get("last_error")),
        "resolution_source": resolution_source,
    }


class ColabPage:
    def __init__(self, session: TargetSession):
        self.session = session
        self.transport = session.transport

    async def _value(self, expression: str) -> Any:
        result = await self.transport.evaluate(expression)
        return result.get("result", {}).get("value") if result else None

    async def _value_with_timeout(self, expression: str, timeout: float) -> Any:
        try:
            result = await asyncio.wait_for(self.transport.evaluate(expression), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise ColabOperationError(
                code="colab_dom_timeout",
                message="Timed out while waiting for the Colab page to respond.",
                evidence={"timeout_seconds": timeout},
                uncertainty=["browser_ui_timeout"],
                stability="best_effort",
            ) from exc
        return result.get("result", {}).get("value") if result else None

    async def notebook_probe(self) -> dict[str, Any]:
        value = await self._value(
            """
            (() => {
                const cells = Array.from(document.querySelectorAll('.cell, [data-cell-id], .jp-Cell'));
                const selected = document.querySelector('.cell.selected, .cell.focused, [data-cell-id].selected, .jp-mod-selected');
                const currentCell = selected ? cells.indexOf(selected) : -1;
                const outputs = Array.from(document.querySelectorAll('.output pre, .cell-output, [data-outputs], .output-area, pre.output'));
                const errors = Array.from(document.querySelectorAll('.traceback, .error, .exception, [data-error]'));
                const lastOutput = outputs.length ? (outputs[outputs.length - 1].innerText || outputs[outputs.length - 1].textContent || '') : '';
                const lastError = errors.length ? (errors[errors.length - 1].innerText || errors[errors.length - 1].textContent || '') : null;
                return {
                    title: document.title || '',
                    url: window.location.href || '',
                    total_cells: cells.length,
                    current_cell: currentCell,
                    last_output: lastOutput.slice(0, 1000),
                    last_error: lastError ? lastError.slice(0, 1000) : null
                };
            })()
            """
        )
        return value if isinstance(value, dict) else {}

    async def runtime_probe(self) -> dict[str, Any]:
        value = await self._value(
            """
            (() => {
                const lower = (value) => String(value || '').toLowerCase();
                let kernelId = null;
                let colabApiAvailable = false;
                try {
                    colabApiAvailable = !!(window.google && google.colab && google.colab.kernel);
                    const kernel = colabApiAvailable ? google.colab.kernel : null;
                    if (kernel && typeof kernel.getKernelId === 'function') {
                        const raw = kernel.getKernelId();
                        kernelId = typeof raw === 'object' ? (raw.kernelId || raw.id || JSON.stringify(raw)) : raw;
                    }
                } catch (err) {}
                const buttons = Array.from(document.querySelectorAll('button, [role="button"], paper-button'));
                const connectButtonVisible = buttons.some((button) => {
                    const text = lower(`${button.getAttribute('aria-label') || ''} ${button.getAttribute('title') || ''} ${button.innerText || button.textContent || ''}`);
                    const rect = button.getBoundingClientRect();
                    const visible = rect.width > 0 && rect.height > 0;
                    return visible && text.includes('connect') && !text.includes('disconnect');
                });
                return {
                    colab_api_available: colabApiAvailable,
                    kernel_id: kernelId,
                    connect_button_visible: connectButtonVisible,
                    running_cells: document.querySelectorAll('.running, .executing, [aria-busy="true"]').length,
                    output_cells: document.querySelectorAll('.output, .cell-output, [data-outputs], .output-area').length,
                    execution_counts: document.querySelectorAll('.execution-count, .input_prompt').length
                };
            })()
            """
        )
        return value if isinstance(value, dict) else {}

    async def count_cells(self) -> int:
        probe = await self.notebook_probe()
        return int(probe.get("total_cells") or 0)

    async def run_code(self, code: str, timeout: float) -> dict[str, Any]:
        code_literal = json.dumps(code)
        start = time.monotonic()
        submit = await self._value(
            f"""
            (() => {{
                const code = {code_literal};
                const cells = Array.from(document.querySelectorAll('.cell, [data-cell-id], .jp-Cell'));
                const cell = cells.find((node) => node.matches('.selected, .focused, .jp-mod-selected')) || cells[0];
                if (!cell) {{
                    return {{submitted: false, state_path: ['cell_not_found'], error: 'No editable Colab cell was found.'}};
                }}
                const statePath = [];
                const cellId = cell.getAttribute('data-cell-id') || String(cells.indexOf(cell));
                let wrote = false;
                const cm = cell.querySelector('.CodeMirror');
                if (cm && cm.CodeMirror) {{
                    cm.CodeMirror.setValue(code);
                    wrote = true;
                    statePath.push('codemirror_set');
                }}
                if (!wrote) {{
                    const textarea = cell.querySelector('textarea');
                    if (textarea) {{
                        textarea.value = code;
                        textarea.dispatchEvent(new Event('input', {{bubbles: true}}));
                        textarea.dispatchEvent(new Event('change', {{bubbles: true}}));
                        wrote = true;
                        statePath.push('textarea_set');
                    }}
                }}
                if (!wrote) {{
                    const editable = cell.querySelector('[contenteditable="true"]');
                    if (editable) {{
                        editable.textContent = code;
                        editable.dispatchEvent(new Event('input', {{bubbles: true}}));
                        wrote = true;
                        statePath.push('contenteditable_set');
                    }}
                }}
                if (!wrote) {{
                    return {{submitted: false, cell_id: cellId, state_path: statePath, error: 'Could not write code into a visible cell.'}};
                }}
                const runButton = cell.querySelector('[data-action="run"], [aria-label*="Run"], [title*="Run"], .run-button, .run-icon, button[name="run"]');
                if (runButton) {{
                    runButton.click();
                    statePath.push('run_button_clicked');
                    return {{submitted: true, cell_id: cellId, state_path: statePath}};
                }}
                cell.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', code: 'Enter', shiftKey: true, bubbles: true}}));
                statePath.push('shift_enter_dispatched');
                return {{submitted: true, cell_id: cellId, state_path: statePath}};
            }})()
            """
        )
        if not isinstance(submit, dict) or not submit.get("submitted"):
            return {
                "state": "error",
                "cell_id": (submit or {}).get("cell_id") if isinstance(submit, dict) else None,
                "output": "",
                "error_message": (submit or {}).get("error", "Cell submission failed") if isinstance(submit, dict) else "Cell submission failed",
                "execution_time": time.monotonic() - start,
                "evidence": {
                    "completion_strategy": "dom_probe",
                    "state_path": (submit or {}).get("state_path", []) if isinstance(submit, dict) else [],
                    "confidence": "low",
                },
            }

        deadline = start + timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            snapshot = await self._cell_output_probe()
            elapsed = time.monotonic() - start
            if snapshot.get("error"):
                return {
                    "state": "error",
                    "cell_id": submit.get("cell_id"),
                    "output": snapshot.get("output", ""),
                    "error_message": snapshot.get("error"),
                    "execution_time": elapsed,
                    "evidence": {
                        "completion_strategy": "dom_probe",
                        "state_path": submit.get("state_path", []),
                        "confidence": "medium",
                    },
                }
            if snapshot.get("output") or (elapsed >= 1.0 and not snapshot.get("running")):
                return {
                    "state": "completed",
                    "cell_id": submit.get("cell_id"),
                    "output": snapshot.get("output", ""),
                    "error_message": None,
                    "execution_time": elapsed,
                    "evidence": {
                        "completion_strategy": "dom_probe",
                        "state_path": submit.get("state_path", []),
                        "confidence": "medium" if snapshot.get("output") else "low",
                        "uncertainty": [] if snapshot.get("output") else ["completion_inferred_without_output"],
                    },
                }

        return {
            "state": "timeout",
            "cell_id": submit.get("cell_id"),
            "output": "",
            "error_message": "Cell execution timed out.",
            "execution_time": time.monotonic() - start,
            "evidence": {
                "completion_strategy": "dom_probe",
                "state_path": submit.get("state_path", []),
                "confidence": "low",
            },
        }

    async def _cell_output_probe(self) -> dict[str, Any]:
        value = await self._value(
            """
            (() => {
                const outputs = Array.from(document.querySelectorAll('.output pre, .cell-output, [data-outputs], .output-area, pre.output'));
                const errors = Array.from(document.querySelectorAll('.traceback, .error, .exception, [data-error]'));
                const lastOutput = outputs.length ? (outputs[outputs.length - 1].innerText || outputs[outputs.length - 1].textContent || '') : '';
                const lastError = errors.length ? (errors[errors.length - 1].innerText || errors[errors.length - 1].textContent || '') : null;
                return {
                    running: document.querySelectorAll('.running, .executing, [aria-busy="true"]').length > 0,
                    output: lastOutput,
                    error: lastError
                };
            })()
            """
        )
        return value if isinstance(value, dict) else {"running": False, "output": "", "error": None}

    async def list_files(self) -> dict[str, Any]:
        value = await self._value(
            """
            (() => {
                try {
                    const files = [];
                    const sources = [];
                    const seen = new Set();
                    const pushFile = (entry, source) => {
                        const name = String(entry?.name || entry?.filename || "").trim();
                        const downloadUrl = String(entry?.download_url || entry?.downloadUrl || entry?.href || entry?.url || "").trim();
                        const key = `${name}::${downloadUrl}`;
                        if (!name || seen.has(key)) {
                            return;
                        }
                        seen.add(key);
                        files.push({
                            name,
                            size: Number(entry?.size || 0),
                            type: String(entry?.type || "file"),
                            path: String(entry?.path || ""),
                            download_url: downloadUrl,
                            source,
                        });
                    };

                    try {
                        const colabFiles = window.google?.colab?.files?._files;
                        if (colabFiles) {
                            sources.push("colab_files_api");
                            const items = Array.isArray(colabFiles) ? colabFiles : Object.values(colabFiles);
                            items.forEach((item) => pushFile(item, "colab_files_api"));
                        }
                    } catch (error) {}

                    const links = Array.from(document.querySelectorAll('a[href*="download"], a[href*="files"]'));
                    if (links.length) {
                        sources.push("dom_links");
                    }
                    links.forEach((link) => {
                        pushFile(
                            {
                                name: link.textContent || link.innerText || link.getAttribute('download') || 'download',
                                size: 0,
                                type: 'link',
                                download_url: link.href || '',
                            },
                            "dom_links",
                        );
                    });

                    return {
                        files,
                        probe_sources: sources,
                    };
                } catch (error) {
                    return {
                        files: [],
                        probe_sources: [],
                        error: error?.message || String(error),
                    };
                }
            })()
            """
        )
        if not isinstance(value, dict):
            return {"files": [], "evidence": {"probe_sources": []}, "uncertainty": ["file_probe_invalid_result"]}
        files = [_normalize_file_entry(item) for item in value.get("files", []) if isinstance(item, dict)]
        probe_sources = [str(item) for item in value.get("probe_sources", []) if item]
        uncertainty = []
        if "dom_links" in probe_sources:
            uncertainty.append("dom_link_fallback")
        if not files:
            uncertainty.append("file_collection_empty")
        if value.get("error"):
            uncertainty.append("file_probe_runtime_error")
        return {
            "files": files,
            "evidence": {
                "probe_sources": probe_sources,
                "error": value.get("error"),
            },
            "uncertainty": uncertainty,
        }

    async def upload_local_file(self, file_name: str, encoded_content: str, file_size: int, timeout: float) -> dict[str, Any]:
        file_name_literal = json.dumps(file_name)
        encoded_literal = json.dumps(encoded_content)
        value = await self._value_with_timeout(
            f"""
            (async () => {{
                try {{
                    const fileName = {file_name_literal};
                    const encoded = {encoded_literal};
                    const fileSize = {file_size};
                    const binary = atob(encoded);
                    const bytes = new Uint8Array(binary.length);
                    for (let index = 0; index < binary.length; index += 1) {{
                        bytes[index] = binary.charCodeAt(index);
                    }}
                    const file = new File([bytes], fileName, {{type: "application/octet-stream"}});
                    const statePath = [];

                    if (window.google?.colab && typeof google.colab.upload === "function") {{
                        statePath.push("google.colab.upload");
                        await google.colab.upload(file);
                        return {{
                            success: true,
                            state: "uploaded",
                            method: "google.colab.upload",
                            state_path: statePath,
                        }};
                    }}

                    const uploadFiles = window.google?.colab?.files?.uploadFiles;
                    if (typeof uploadFiles === "function") {{
                        statePath.push("google.colab.files.uploadFiles");
                        await uploadFiles([file]);
                        return {{
                            success: true,
                            state: "uploaded",
                            method: "google.colab.files.uploadFiles",
                            state_path: statePath,
                        }};
                    }}

                    const input = document.querySelector('input[type="file"]');
                    if (input) {{
                        const transfer = new DataTransfer();
                        transfer.items.add(file);
                        input.files = transfer.files;
                        input.dispatchEvent(new Event("change", {{bubbles: true}}));
                        statePath.push("dom_file_input_change");
                        return {{
                            success: true,
                            state: "submitted",
                            method: "dom_file_input_change",
                            state_path: statePath,
                        }};
                    }}

                    return {{
                        success: false,
                        error: "No supported Colab upload API or visible file input was found.",
                        unsupported_reason: "upload_api_missing",
                        state_path: statePath,
                    }};
                }} catch (error) {{
                    return {{
                        success: false,
                        error: error?.message || String(error),
                        unsupported_reason: null,
                        state_path: [],
                    }};
                }}
            }})()
            """,
            timeout,
        )
        if not isinstance(value, dict) or not value.get("success"):
            raise ColabOperationError(
                code="file_upload_failed",
                message=(value or {}).get("error", "Colab file upload failed.") if isinstance(value, dict) else "Colab file upload failed.",
                evidence={
                    "timeout_seconds": timeout,
                    "state_path": (value or {}).get("state_path", []) if isinstance(value, dict) else [],
                    "unsupported_reason": (value or {}).get("unsupported_reason") if isinstance(value, dict) else None,
                    "file_name": file_name,
                    "file_size": file_size,
                },
                uncertainty=["browser_upload_heuristic"],
                stability="best_effort",
            )
        uncertainty = ["browser_upload_heuristic"]
        if value.get("state") != "uploaded":
            uncertainty.append("upload_completion_unconfirmed")
        return {
            "upload": {
                "state": value.get("state", "submitted"),
                "method": value.get("method", "unknown"),
            },
            "evidence": {
                "timeout_seconds": timeout,
                "state_path": value.get("state_path", []),
            },
            "uncertainty": uncertainty,
        }

    async def download_url_to_path(self, url: str, destination_path: str, timeout: float) -> dict[str, Any]:
        url_literal = json.dumps(url)
        value = await self._value_with_timeout(
            f"""
            (async () => {{
                try {{
                    const response = await fetch({url_literal});
                    if (!response.ok) {{
                        return {{
                            success: false,
                            error: `Fetch failed: ${{response.status}}`,
                            status: response.status,
                        }};
                    }}
                    const blob = await response.blob();
                    if (blob.size > {_BEST_EFFORT_INLINE_TRANSFER_LIMIT}) {{
                        return {{
                            success: false,
                            error: "Resource is too large for best-effort browser download.",
                            unsupported_reason: "size_limit",
                            size: blob.size,
                        }};
                    }}
                    const buffer = await blob.arrayBuffer();
                    const bytes = new Uint8Array(buffer);
                    let binary = "";
                    for (let index = 0; index < bytes.length; index += 1) {{
                        binary += String.fromCharCode(bytes[index]);
                    }}
                    return {{
                        success: true,
                        data: btoa(binary),
                        size: blob.size,
                        mime_type: blob.type || null,
                        method: "fetch",
                    }};
                }} catch (error) {{
                    return {{
                        success: false,
                        error: error?.message || String(error),
                    }};
                }}
            }})()
            """,
            timeout,
        )
        if not isinstance(value, dict) or not value.get("success"):
            error_value = value or {}
            unsupported_reason = error_value.get("unsupported_reason") if isinstance(error_value, dict) else None
            code = "download_too_large_for_best_effort_transfer" if unsupported_reason == "size_limit" else "download_failed"
            raise ColabOperationError(
                code=code,
                message=error_value.get("error", "Browser download failed.") if isinstance(error_value, dict) else "Browser download failed.",
                evidence={
                    "timeout_seconds": timeout,
                    "source_url": url,
                    "unsupported_reason": unsupported_reason,
                    "size": error_value.get("size") if isinstance(error_value, dict) else None,
                },
                uncertainty=["browser_fetch_download"],
                stability="best_effort",
            )
        data = value.get("data", "")
        bytes_written = _write_bytes(destination_path, base64.b64decode(data))
        return {
            "download": {
                "state": "downloaded",
                "path": str(Path(destination_path)),
                "bytes_written": bytes_written,
                "mime_type": value.get("mime_type"),
            },
            "evidence": {
                "timeout_seconds": timeout,
                "source_url": url,
                "method": value.get("method", "fetch"),
            },
            "uncertainty": ["browser_fetch_download"],
        }

    async def list_artifacts(self) -> dict[str, Any]:
        value = await self._value(
            """
            (() => {
                try {
                    const artifacts = [];
                    const sources = [];
                    const seen = new Set();
                    const pushArtifact = (entry, source) => {
                        const artifactId = String(entry?.artifact_id || entry?.id || "").trim();
                        const name = String(entry?.name || entry?.filename || "artifact").trim();
                        const url = String(entry?.url || entry?.download_url || entry?.href || "").trim();
                        const key = `${artifactId}::${name}::${url}`;
                        if (!artifactId || seen.has(key)) {
                            return;
                        }
                        seen.add(key);
                        artifacts.push({
                            artifact_id: artifactId,
                            name,
                            type: String(entry?.type || "file"),
                            url,
                            size: Number(entry?.size || 0),
                            created_at: entry?.created_at || null,
                            source,
                        });
                    };

                    try {
                        const colabArtifacts = window.google?.colab?._artifacts;
                        const items = Array.isArray(colabArtifacts?.items) ? colabArtifacts.items : [];
                        if (items.length) {
                            sources.push("colab_artifacts_api");
                        }
                        items.forEach((item, index) => {
                            pushArtifact(
                                {
                                    artifact_id: `artifact-${index}`,
                                    name: item?.name || item?.filename || `artifact-${index}`,
                                    type: item?.type || "file",
                                    url: item?.url || item?.download_url || "",
                                    size: item?.size || 0,
                                    created_at: item?.created_at || null,
                                },
                                "colab_artifacts_api",
                            );
                        });
                    } catch (error) {}

                    try {
                        if (Array.isArray(window._artifacts) && window._artifacts.length) {
                            sources.push("global_artifacts");
                            window._artifacts.forEach((item, index) => {
                                pushArtifact(
                                    {
                                        artifact_id: item?.artifact_id || `artifact-global-${index}`,
                                        name: item?.name || item?.filename || `artifact-${index}`,
                                        type: item?.type || "file",
                                        url: item?.url || item?.download_url || "",
                                        size: item?.size || 0,
                                        created_at: item?.created_at || null,
                                    },
                                    "global_artifacts",
                                );
                            });
                        }
                    } catch (error) {}

                    const links = Array.from(document.querySelectorAll('a[href*="download"], a[href*="artifact"]'));
                    if (links.length) {
                        sources.push("dom_links");
                    }
                    links.forEach((link, index) => {
                        pushArtifact(
                            {
                                artifact_id: `dl-${index}`,
                                name: link.textContent || link.innerText || link.getAttribute("download") || `download-${index}`,
                                type: "download",
                                url: link.href || "",
                                size: 0,
                                created_at: null,
                            },
                            "dom_links",
                        );
                    });

                    const blobOutputs = Array.from(document.querySelectorAll("[src^='blob:'], [href^='blob:']"));
                    if (blobOutputs.length) {
                        sources.push("blob_outputs");
                    }
                    blobOutputs.forEach((node, index) => {
                        pushArtifact(
                            {
                                artifact_id: `blob-${index}`,
                                name: node.getAttribute("download") || node.getAttribute("aria-label") || `blob-${index}`,
                                type: "blob",
                                url: node.getAttribute("src") || node.getAttribute("href") || "",
                                size: 0,
                                created_at: null,
                            },
                            "blob_outputs",
                        );
                    });

                    return {
                        artifacts,
                        probe_sources: sources,
                    };
                } catch (error) {
                    return {
                        artifacts: [],
                        probe_sources: [],
                        error: error?.message || String(error),
                    };
                }
            })()
            """
        )
        if not isinstance(value, dict):
            return {"artifacts": [], "evidence": {"probe_sources": []}, "uncertainty": ["artifact_probe_invalid_result"]}
        artifacts = [_normalize_artifact_entry(item) for item in value.get("artifacts", []) if isinstance(item, dict)]
        probe_sources = [str(item) for item in value.get("probe_sources", []) if item]
        uncertainty = []
        if "blob_outputs" in probe_sources:
            uncertainty.append("blob_artifacts_may_not_be_downloadable")
        if "dom_links" in probe_sources:
            uncertainty.append("dom_link_fallback")
        if not artifacts:
            uncertainty.append("artifact_collection_empty")
        if value.get("error"):
            uncertainty.append("artifact_probe_runtime_error")
        return {
            "artifacts": artifacts,
            "evidence": {
                "probe_sources": probe_sources,
                "error": value.get("error"),
            },
            "uncertainty": uncertainty,
        }

    async def export_notebook(self, format: str, output: str, timeout: float) -> dict[str, Any]:
        format_literal = json.dumps(format)
        value = await self._value_with_timeout(
            f"""
            (() => {{
                try {{
                    const format = {format_literal};
                    const cells = Array.from(document.querySelectorAll('.cell, [data-cell-id], .jp-Cell'));
                    const extracted = cells.map((cell, index) => {{
                        let code = "";
                        const cm = cell.querySelector(".CodeMirror");
                        if (cm && cm.CodeMirror) {{
                            code = cm.CodeMirror.getValue();
                        }} else {{
                            const textarea = cell.querySelector("textarea");
                            if (textarea) {{
                                code = textarea.value || "";
                            }} else {{
                                const editable = cell.querySelector('[contenteditable="true"]');
                                code = editable ? (editable.innerText || editable.textContent || "") : "";
                            }}
                        }}

                        const outputs = [];
                        const outputNodes = Array.from(cell.querySelectorAll('.output pre, .cell-output, [data-outputs], .output-area, pre.output'));
                        outputNodes.forEach((node) => {{
                            const text = node.innerText || node.textContent || "";
                            if (text) {{
                                outputs.push({{
                                    output_type: "stream",
                                    name: "stdout",
                                    text,
                                }});
                            }}
                        }});

                        return {{
                            cell_type: "code",
                            execution_count: null,
                            metadata: {{}},
                            outputs,
                            source: code ? code.split("\\n").map((line) => line + "\\n") : [],
                        }};
                    }});

                    if (format === "py") {{
                        const text = extracted
                            .map((cell, index) => {{
                                const source = Array.isArray(cell.source) ? cell.source.join("") : "";
                                return `# Cell ${{index}}\\n${{source.trimEnd()}}`;
                            }})
                            .join("\\n\\n");
                        return {{
                            success: true,
                            format,
                            data: text,
                            serializer: "dom_reconstruction",
                            total_cells: extracted.length,
                        }};
                    }}

                    const notebook = {{
                        nbformat: 4,
                        nbformat_minor: 5,
                        metadata: {{
                            kernelspec: {{
                                display_name: "Python 3",
                                language: "python",
                                name: "python3",
                            }},
                        }},
                        cells: extracted,
                    }};
                    return {{
                        success: true,
                        format,
                        data: JSON.stringify(notebook, null, 2),
                        serializer: "dom_reconstruction",
                        total_cells: extracted.length,
                    }};
                }} catch (error) {{
                    return {{
                        success: false,
                        error: error?.message || String(error),
                    }};
                }}
            }})()
            """,
            timeout,
        )
        if not isinstance(value, dict) or not value.get("success"):
            raise ColabOperationError(
                code="notebook_export_failed",
                message=(value or {}).get("error", "Notebook export failed.") if isinstance(value, dict) else "Notebook export failed.",
                evidence={"timeout_seconds": timeout, "format": format},
                uncertainty=["notebook_export_fidelity_not_guaranteed"],
                stability="best_effort",
            )
        bytes_written = len(str(value.get("data", "")).encode("utf-8"))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(str(value.get("data", "")), encoding="utf-8")
        return {
            "export": {
                "state": "exported",
                "format": format,
                "path": str(Path(output)),
                "bytes_written": bytes_written,
            },
            "evidence": {
                "serializer": value.get("serializer", "dom_reconstruction"),
                "timeout_seconds": timeout,
                "total_cells": value.get("total_cells"),
            },
            "uncertainty": ["notebook_export_fidelity_not_guaranteed"],
        }


async def _open_page(settings: Settings, target_id: str | None = None) -> tuple[TargetSession, TargetResolution, ColabPage]:
    session, resolution = await open_product_target_session(
        settings,
        COLAB_PRODUCT,
        "colab",
        requested_target=target_id,
    )
    return session, resolution, ColabPage(session)


async def notebook_info(settings: Settings, target_id: str | None = None) -> dict[str, Any]:
    session, resolution, page = await _open_page(settings, target_id)
    try:
        probe = await page.notebook_probe()
        runtime_probe = await page.runtime_probe()
        runtime = classify_runtime_probe(runtime_probe)
        return _supported_result(
            target=_target_evidence(session, resolution),
            session=_session_evidence(session),
            notebook={
                "title": probe.get("title") or session.target.title,
                "url": probe.get("url") or session.target.url,
                "total_cells": int(probe.get("total_cells") or 0),
                "current_cell": int(probe.get("current_cell") if probe.get("current_cell") is not None else -1),
                "last_output_excerpt": _excerpt(probe.get("last_output")),
                "last_error_excerpt": _excerpt(probe.get("last_error")),
            },
            runtime=runtime,
            evidence={
                "probe_sources": ["context", "runtime"],
                "runtime_probe": runtime_probe,
            },
        )
    finally:
        await session.close()


async def notebook_summary(settings: Settings, target_id: str | None = None) -> dict[str, Any]:
    session, resolution, page = await _open_page(settings, target_id)
    try:
        probe = await page.notebook_probe()
        runtime_probe = await page.runtime_probe()
        runtime = classify_runtime_probe(runtime_probe)
        summary = summarize_notebook_probe(
            probe=probe,
            runtime=runtime,
            resolution_source=resolution.resolution_source,
        )
        return _supported_result(
            target=_target_evidence(session, resolution),
            session=_session_evidence(session),
            **summary,
            evidence={
                "probe_sources": ["summary"],
                "runtime_probe": runtime_probe,
            },
        )
    finally:
        await session.close()


async def runtime_status(settings: Settings, target_id: str | None = None) -> dict[str, Any]:
    session, resolution, page = await _open_page(settings, target_id)
    try:
        probe = await page.runtime_probe()
        return _supported_result(
            target=_target_evidence(session, resolution),
            session=_session_evidence(session),
            runtime=classify_runtime_probe(probe),
            evidence={
                "probe_sources": ["colab_api", "dom"],
                "runtime_probe": probe,
            },
        )
    finally:
        await session.close()


async def cell_count(settings: Settings, target_id: str | None = None) -> dict[str, Any]:
    session, resolution, page = await _open_page(settings, target_id)
    try:
        return _supported_result(
            target=_target_evidence(session, resolution),
            session=_session_evidence(session),
            cell_count=await page.count_cells(),
            evidence={"probe_sources": ["dom"]},
        )
    finally:
        await session.close()


async def run_cell_code(
    settings: Settings,
    code: str,
    target_id: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    session, resolution, page = await _open_page(settings, target_id)
    try:
        return _supported_result(
            target=_target_evidence(session, resolution),
            session=_session_evidence(session),
            **await page.run_code(code, timeout),
        )
    finally:
        await session.close()


async def run_cell_file(
    settings: Settings,
    file_path: str,
    target_id: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    code_path = Path(file_path)
    code = code_path.read_text(encoding="utf-8")
    result = await run_cell_code(settings, code, target_id=target_id, timeout=timeout)
    result["file"] = str(code_path)
    return result


async def upload_file(
    settings: Settings,
    file_path: str,
    target_id: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    local_path = Path(file_path)
    if not local_path.exists():
        raise ColabOperationError(
            code="local_file_not_found",
            message=f"Local file not found: {file_path}",
            evidence={"file_path": file_path},
            uncertainty=["local_precondition_failed"],
            stability="best_effort",
            extra={"file": {"name": local_path.name, "local_path": str(local_path)}},
        )
    file_bytes = local_path.read_bytes()
    if len(file_bytes) > _BEST_EFFORT_INLINE_TRANSFER_LIMIT:
        raise ColabOperationError(
            code="file_too_large_for_best_effort_upload",
            message="File is too large for best-effort Colab upload.",
            evidence={
                "file_path": str(local_path),
                "size": len(file_bytes),
                "size_limit": _BEST_EFFORT_INLINE_TRANSFER_LIMIT,
            },
            uncertainty=["large_files_untested"],
            stability="best_effort",
            extra={"file": {"name": local_path.name, "size": len(file_bytes), "local_path": str(local_path)}},
        )
    session, resolution, page = await _open_page(settings, target_id)
    try:
        upload = await page.upload_local_file(
            local_path.name,
            base64.b64encode(file_bytes).decode("utf-8"),
            len(file_bytes),
            timeout,
        )
        return _best_effort_result(
            target=_target_evidence(session, resolution),
            session=_session_evidence(session),
            file={
                "name": local_path.name,
                "size": len(file_bytes),
                "local_path": str(local_path),
            },
            upload=upload["upload"],
            evidence=upload["evidence"],
            uncertainty=upload["uncertainty"],
        )
    finally:
        await session.close()


async def list_files(settings: Settings, target_id: str | None = None) -> dict[str, Any]:
    session, resolution, page = await _open_page(settings, target_id)
    try:
        listing = await page.list_files()
        return _best_effort_result(
            target=_target_evidence(session, resolution),
            session=_session_evidence(session),
            count=len(listing["files"]),
            files=listing["files"],
            evidence=listing["evidence"],
            uncertainty=listing["uncertainty"],
        )
    finally:
        await session.close()


async def download_file(
    settings: Settings,
    file_name: str,
    output: str | None = None,
    target_id: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    session, resolution, page = await _open_page(settings, target_id)
    try:
        listing = await page.list_files()
        file_info = next(
            (
                item
                for item in listing["files"]
                if item["name"] == file_name or file_name in item.get("download_url", "")
            ),
            None,
        )
        if file_info is None:
            raise ColabOperationError(
                code="file_not_found",
                message=f"Colab file not found: {file_name}",
                target=_target_evidence(session, resolution),
                session=_session_evidence(session),
                evidence={
                    **listing["evidence"],
                    "requested_file": file_name,
                    "available_files": [item["name"] for item in listing["files"]],
                },
                uncertainty=listing["uncertainty"],
                stability="best_effort",
                extra={"file": {"name": file_name}},
            )
        download_url = file_info.get("download_url", "")
        if _unsupported_download_url(download_url):
            raise ColabOperationError(
                code="file_download_unsupported",
                message="This Colab file does not expose a supported browser-download URL.",
                target=_target_evidence(session, resolution),
                session=_session_evidence(session),
                evidence={
                    **listing["evidence"],
                    "requested_file": file_name,
                    "download_url": download_url,
                },
                uncertainty=_merge_uncertainty(listing["uncertainty"], ["unsupported_download_url"]),
                stability="best_effort",
                extra={"file": file_info},
            )
        destination = output or file_info["name"]
        download = await page.download_url_to_path(download_url, destination, timeout)
        return _best_effort_result(
            target=_target_evidence(session, resolution),
            session=_session_evidence(session),
            file=file_info,
            download=download["download"],
            evidence={**listing["evidence"], **download["evidence"]},
            uncertainty=_merge_uncertainty(listing["uncertainty"], download["uncertainty"]),
        )
    finally:
        await session.close()


async def list_artifacts(settings: Settings, target_id: str | None = None) -> dict[str, Any]:
    session, resolution, page = await _open_page(settings, target_id)
    try:
        listing = await page.list_artifacts()
        return _best_effort_result(
            target=_target_evidence(session, resolution),
            session=_session_evidence(session),
            count=len(listing["artifacts"]),
            artifacts=listing["artifacts"],
            evidence=listing["evidence"],
            uncertainty=listing["uncertainty"],
        )
    finally:
        await session.close()


async def latest_artifact(settings: Settings, target_id: str | None = None) -> dict[str, Any]:
    session, resolution, page = await _open_page(settings, target_id)
    try:
        listing = await page.list_artifacts()
        artifact = listing["artifacts"][-1] if listing["artifacts"] else None
        return _best_effort_result(
            target=_target_evidence(session, resolution),
            session=_session_evidence(session),
            artifact=artifact,
            evidence={**listing["evidence"], "selection_strategy": "last_detected"},
            uncertainty=_merge_uncertainty(
                listing["uncertainty"],
                ["artifact_order_is_dom_inferred"] if artifact is not None else ["no_artifacts_detected"],
            ),
        )
    finally:
        await session.close()


async def get_artifact(settings: Settings, artifact_id: str, target_id: str | None = None) -> dict[str, Any]:
    session, resolution, page = await _open_page(settings, target_id)
    try:
        listing = await page.list_artifacts()
        artifact = next((item for item in listing["artifacts"] if item["artifact_id"] == artifact_id), None)
        if artifact is None:
            raise ColabOperationError(
                code="artifact_not_found",
                message=f"Colab artifact not found: {artifact_id}",
                target=_target_evidence(session, resolution),
                session=_session_evidence(session),
                evidence={
                    **listing["evidence"],
                    "requested_artifact_id": artifact_id,
                    "available_artifact_ids": [item["artifact_id"] for item in listing["artifacts"]],
                },
                uncertainty=listing["uncertainty"],
                stability="best_effort",
                extra={"artifact": {"artifact_id": artifact_id}},
            )
        return _best_effort_result(
            target=_target_evidence(session, resolution),
            session=_session_evidence(session),
            artifact=artifact,
            evidence={**listing["evidence"], "lookup": "artifact_id"},
            uncertainty=listing["uncertainty"],
        )
    finally:
        await session.close()


async def download_artifact(
    settings: Settings,
    artifact_id: str,
    output: str | None = None,
    target_id: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    session, resolution, page = await _open_page(settings, target_id)
    try:
        listing = await page.list_artifacts()
        artifact = next((item for item in listing["artifacts"] if item["artifact_id"] == artifact_id), None)
        if artifact is None:
            raise ColabOperationError(
                code="artifact_not_found",
                message=f"Colab artifact not found: {artifact_id}",
                target=_target_evidence(session, resolution),
                session=_session_evidence(session),
                evidence={
                    **listing["evidence"],
                    "requested_artifact_id": artifact_id,
                    "available_artifact_ids": [item["artifact_id"] for item in listing["artifacts"]],
                },
                uncertainty=listing["uncertainty"],
                stability="best_effort",
                extra={"artifact": {"artifact_id": artifact_id}},
            )
        artifact_url = artifact.get("url", "")
        if _unsupported_download_url(artifact_url):
            raise ColabOperationError(
                code="artifact_download_unsupported",
                message="This Colab artifact does not expose a supported browser-download URL.",
                target=_target_evidence(session, resolution),
                session=_session_evidence(session),
                evidence={
                    **listing["evidence"],
                    "requested_artifact_id": artifact_id,
                    "artifact_url": artifact_url,
                },
                uncertainty=_merge_uncertainty(listing["uncertainty"], ["unsupported_download_url"]),
                stability="best_effort",
                extra={"artifact": artifact},
            )
        destination = output or artifact["name"]
        download = await page.download_url_to_path(artifact_url, destination, timeout)
        return _best_effort_result(
            target=_target_evidence(session, resolution),
            session=_session_evidence(session),
            artifact=artifact,
            download=download["download"],
            evidence={**listing["evidence"], **download["evidence"]},
            uncertainty=_merge_uncertainty(listing["uncertainty"], download["uncertainty"]),
        )
    finally:
        await session.close()


async def export_notebook(
    settings: Settings,
    format: str,
    output: str,
    target_id: str | None = None,
    timeout: float = 45.0,
) -> dict[str, Any]:
    session, resolution, page = await _open_page(settings, target_id)
    try:
        exported = await page.export_notebook(format, output, timeout)
        return _best_effort_result(
            target=_target_evidence(session, resolution),
            session=_session_evidence(session),
            export=exported["export"],
            evidence=exported["evidence"],
            uncertainty=exported["uncertainty"],
        )
    finally:
        await session.close()
