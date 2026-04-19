from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from ...config import Settings
from ...core.product import GEMINI_PRODUCT
from ...core.targets import TargetSession, open_or_create_target_session, open_target_session
from .contract import PROBE_ATTRIBUTE, GeminiContract, probe_gemini_contract
from .state import (
    ChatMessageRecord,
    ChatSessionRecord,
    get_current_chat_session_id,
    list_chat_sessions,
    load_chat_session,
    save_chat_session,
    set_current_chat_session_id,
)

_LOADING_SELECTOR = '[aria-busy="true"], .loading-spinner'
_MODEL_RESPONSE_SELECTOR = '[data-message-type="model"]'
_ERROR_SELECTOR = '[data-error], .error-message, [role="alert"]'


@dataclass(frozen=True, slots=True)
class TargetEvidence:
    target_id: str | None
    url: str | None
    resolution_source: str


@dataclass(frozen=True, slots=True)
class SessionEvidence:
    attached: bool
    session_id: str | None


class GeminiOperationError(RuntimeError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        target: TargetEvidence | None = None,
        session: SessionEvidence | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.target = target or TargetEvidence(target_id=None, url=None, resolution_source="none")
        self.session = session or SessionEvidence(attached=False, session_id=None)


@dataclass(slots=True)
class GeminiResponse:
    text: str
    images: list[str] = field(default_factory=list)
    thinking: str | None = None
    is_error: bool = False
    error_message: str | None = None


@dataclass(slots=True)
class ImageGenerationResult:
    paths: list[str] = field(default_factory=list)
    error_code: str | None = None
    state_path: list[str] = field(default_factory=list)
    evidence: dict[str, object] = field(default_factory=dict)
    target: TargetEvidence | None = None
    session: SessionEvidence | None = None

    @property
    def is_error(self) -> bool:
        return self.error_code is not None


@dataclass(slots=True)
class TextGenerationResult:
    text: str
    images: list[str] = field(default_factory=list)
    thinking: str | None = None
    target: TargetEvidence | None = None
    session: SessionEvidence | None = None


@dataclass(slots=True)
class DeepResearchResult:
    query: str
    report: str = ""
    sources: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    evidence: dict[str, object] = field(default_factory=dict)
    target: TargetEvidence | None = None
    session: SessionEvidence | None = None

    @property
    def is_error(self) -> bool:
        return self.error_code is not None


@dataclass(slots=True)
class VideoGenerationResult:
    path: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    evidence: dict[str, object] = field(default_factory=dict)
    target: TargetEvidence | None = None
    session: SessionEvidence | None = None

    @property
    def is_error(self) -> bool:
        return self.error_code is not None


@dataclass(slots=True)
class MediaExtractionResult:
    paths: list[str] = field(default_factory=list)
    error_code: str | None = None
    evidence: dict[str, object] = field(default_factory=dict)


class MediaExtractionError(RuntimeError):
    def __init__(self, error_code: str, evidence: dict[str, object] | None = None):
        super().__init__(error_code)
        self.error_code = error_code
        self.evidence = evidence or {}


class GeminiPage:
    def __init__(self, session: TargetSession):
        self.session = session
        self.transport = session.transport
        self._page_loaded = False

    async def _ensure_page(self) -> None:
        if self._page_loaded:
            return
        await self.transport.navigate(GEMINI_PRODUCT.default_url)
        await asyncio.sleep(1)
        await self.transport.wait_for_load_state("networkidle", timeout=10000)
        self._page_loaded = True

    async def _capture_dom_snapshot(self) -> dict[str, Any]:
        probe_attribute_literal = json.dumps(PROBE_ATTRIBUTE)
        result = await self.transport.evaluate(
            f"""
            (() => {{
                const probeAttribute = {probe_attribute_literal};
                const isVisible = (el) => {{
                    if (!(el instanceof HTMLElement)) return false;
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') return false;
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                }};
                const mark = (el, prefix, index) => {{
                    const value = `${{prefix}}-${{index}}`;
                    el.setAttribute(probeAttribute, value);
                    return `[${{probeAttribute}}="${{value}}"]`;
                }};
                const buttons = Array.from(document.querySelectorAll('button, [role="button"]'))
                    .filter(isVisible)
                    .map((el, index) => ({{
                        selector: mark(el, 'button', index),
                        tag: el.tagName,
                        aria: el.getAttribute('aria-label') || '',
                        text: el.innerText || el.textContent || '',
                    }}));
                const inputs = Array.from(document.querySelectorAll('textarea, div[contenteditable="true"], input:not([type="hidden"])'))
                    .filter(isVisible)
                    .map((el, index) => ({{
                        selector: mark(el, 'input', index),
                        tag: el.tagName,
                        aria: el.getAttribute('aria-label') || '',
                        placeholder: el.getAttribute('placeholder') || '',
                        contenteditable: el.getAttribute('contenteditable') === 'true' || el.isContentEditable === true,
                    }}));
                return {{ buttons, inputs }};
            }})()
            """
        )
        return result.get("result", {}).get("value") or {"buttons": [], "inputs": []}

    async def _probe_contract(self) -> GeminiContract:
        await self._ensure_page()
        return probe_gemini_contract(await self._capture_dom_snapshot())

    async def _find_input(self) -> dict[str, Any] | None:
        contract = await self._probe_contract()
        if contract.prompt_input is None:
            return None
        return {
            "selector": contract.prompt_input.selector,
            "tagName": contract.prompt_input.tag,
            "isContentEditable": contract.prompt_input.kind == "contenteditable",
        }

    async def _fill_prompt_node(self, selector: str, kind: str, prompt: str) -> None:
        if kind == "contenteditable":
            prompt_literal = json.dumps(prompt)
            result = await self.transport.evaluate(
                f"""
                (function() {{
                    const el = document.querySelector('{selector}');
                    if (!el) return false;
                    el.textContent = {prompt_literal};
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    return true;
                }})()
                """
            )
            if not result.get("result", {}).get("value"):
                raise RuntimeError(f"Prompt input not found: {selector}")
            return
        await self.transport.fill(selector, prompt)

    async def _send_prompt_internal(self, prompt: str) -> None:
        input_node = await self._find_input()
        if input_node is None:
            raise RuntimeError("prompt_input_not_found")

        if input_node["isContentEditable"]:
            prompt_literal = json.dumps(prompt)
            await self.transport.evaluate(
                f"""
                (function() {{
                    const el = document.querySelector('{input_node["selector"]}');
                    if (!el) return false;
                    el.textContent = {prompt_literal};
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    return true;
                }})()
                """
            )
        else:
            await self.transport.fill(input_node["selector"], prompt)

        await asyncio.sleep(0.3)
        contract = await self._probe_contract()
        if contract.send_button is not None:
            await self.transport.click(contract.send_button.selector)
            return
        await self.transport.press_enter()

    async def _wait_for_response(self, timeout: int = 60000) -> GeminiResponse:
        start_time = time.time()
        while time.time() - start_time < timeout / 1000:
            try:
                error_text = await self.transport.get_inner_text(_ERROR_SELECTOR)
                if error_text:
                    return GeminiResponse(text="", is_error=True, error_message=error_text)
            except Exception:
                pass

            result = await self.transport.evaluate(
                f"""
                (() => {{
                    const containers = document.querySelectorAll('{_MODEL_RESPONSE_SELECTOR}');
                    if (containers.length === 0) return null;
                    const last = containers[containers.length - 1];
                    const text = last.innerText || last.textContent || '';
                    const images = [];
                    last.querySelectorAll('img').forEach((img) => {{
                        if (img.src && !img.src.startsWith('data:') && img.naturalWidth > 0) {{
                            images.push(img.src);
                        }}
                    }});
                    return {{ text, images, length: text.length }};
                }})()
                """
            )
            value = result.get("result", {}).get("value") if result else None
            if value and value.get("length", 0) > 10:
                return GeminiResponse(text=value["text"], images=value.get("images", []))
            await asyncio.sleep(1)

        return GeminiResponse(text="", is_error=True, error_message="Response timeout")

    async def send_prompt(self, prompt: str, timeout: int = 60000) -> GeminiResponse:
        await self._ensure_page()
        await self._send_prompt_internal(prompt)
        return await self._wait_for_response(timeout)

    async def _click_button_by_labels(self, labels: tuple[str, ...]) -> bool:
        labels_literal = json.dumps([label.lower() for label in labels])
        result = await self.transport.evaluate(
            f"""
            (() => {{
                const labels = {labels_literal};
                const nodes = Array.from(document.querySelectorAll('button, [role="button"]'));
                for (const node of nodes) {{
                    const label = `${{node.getAttribute('aria-label') || ''}} ${{node.innerText || node.textContent || ''}}`
                        .toLowerCase()
                        .replace(/\\s+/g, ' ')
                        .trim();
                    if (!label) continue;
                    if (labels.some((token) => label.includes(token))) {{
                        node.click();
                        return true;
                    }}
                }}
                return false;
            }})()
            """
        )
        return bool(result.get("result", {}).get("value")) if result else False

    async def _collect_latest_response(self) -> dict[str, Any] | None:
        result = await self.transport.evaluate(
            """
            (() => {
                const containers = document.querySelectorAll('[data-message-type="model"]');
                if (containers.length === 0) return null;
                const last = containers[containers.length - 1];
                const text = (last.innerText || last.textContent || '').trim();
                const urls = Array.from(new Set(
                    Array.from(text.matchAll(/https?:\\/\\/[^\\s)\\]]+/g)).map((match) => match[0])
                ));
                return {
                    text,
                    length: text.length,
                    urls,
                    hasSourcesHeading: /sources?:|references?:/i.test(text),
                };
            })()
            """
        )
        return result.get("result", {}).get("value") if result else None

    async def deep_research(self, query: str, timeout: int = 300000) -> DeepResearchResult:
        await self._ensure_page()
        enabled = await self._click_button_by_labels(("deep research", "深度研究"))
        if not enabled:
            return DeepResearchResult(
                query=query,
                error_code="deep_research_unavailable",
                error_message=_message_for_error("deep_research_unavailable"),
                evidence={"activation": "button_not_found"},
            )

        await asyncio.sleep(0.5)
        await self._send_prompt_internal(query)

        start_time = time.time()
        poll_interval = 5.0
        while time.time() - start_time < timeout / 1000:
            snapshot = await self._collect_latest_response()
            if snapshot and (
                snapshot.get("length", 0) >= 500
                or (snapshot.get("length", 0) >= 200 and snapshot.get("hasSourcesHeading"))
            ):
                return DeepResearchResult(
                    query=query,
                    report=snapshot.get("text", ""),
                    sources=list(snapshot.get("urls") or []),
                    evidence={
                        "completion_strategy": "body_text_probe",
                        "content_length": snapshot.get("length", 0),
                    },
                )
            await asyncio.sleep(poll_interval)

        return DeepResearchResult(
            query=query,
            error_code="deep_research_timeout",
            error_message=_message_for_error("deep_research_timeout"),
            evidence={"completion_strategy": "body_text_probe"},
        )

    async def upload_image(self, image_path: str) -> bool:
        await self._ensure_page()
        contract = await self._probe_contract()
        if contract.upload_button is not None:
            await self.transport.click(contract.upload_button.selector)
            await asyncio.sleep(0.5)

        result = await self.transport.evaluate(
            """
            (() => {
                const inputs = document.querySelectorAll('input[type="file"]');
                if (inputs.length > 0) return 'found';
                return null;
            })()
            """
        )
        if result and result.get("result", {}).get("value"):
            await self.transport.set_upload_files("input[type=\"file\"]", [os.path.abspath(image_path)])
            await asyncio.sleep(1)
            return True
        return False

    def _is_image_mode_latched(self, contract: GeminiContract) -> bool:
        if contract.upload_button is not None:
            return True
        if contract.image_entry is None:
            return True
        label = " ".join(
            part
            for part in (
                contract.image_entry.label,
                contract.image_entry.aria_label,
                contract.image_entry.text,
            )
            if part
        ).lower()
        return any(token in label for token in ("取消选择", "deselect", "cancel"))

    async def _probe_home_state(self) -> GeminiContract:
        return await self._probe_contract()

    def _classify_home_state_failure(self, contract: GeminiContract) -> str | None:
        if contract.image_entry is not None and contract.send_button is None and contract.upload_button is None:
            return "home_state_after_submit"
        return None

    async def _is_generation_loading(self) -> bool:
        result = await self.transport.evaluate(
            f"document.querySelector('{_LOADING_SELECTOR}') !== null"
        )
        return bool(result.get("result", {}).get("value")) if result else False

    async def _is_generation_pending(self) -> bool:
        result = await self.transport.evaluate(
            """
            (() => {
                const models = document.querySelectorAll('[data-message-type="model"]');
                if (models.length === 0) return false;
                const last = models[models.length - 1];
                if (!last) return false;
                if (last.querySelectorAll('img').length > 0) return false;
                const busy = last.querySelector('[aria-busy="true"], .loading-spinner, [role="progressbar"]') !== null;
                if (busy) return true;
                const text = (last.innerText || last.textContent || '').trim();
                return text.length === 0;
            })()
            """
        )
        return bool(result.get("result", {}).get("value")) if result else False

    async def _capture_blob_image(self, blob_url: str) -> bytes:
        result = await self.transport.evaluate(
            f"""
            (() => {{
                const image = Array.from(document.querySelectorAll('img')).find((item) => item.src === {json.dumps(blob_url)});
                if (!image) return null;
                const rect = image.getBoundingClientRect();
                return {{
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height,
                }};
            }})()
            """
        )
        clip = result.get("result", {}).get("value")
        if not clip:
            raise MediaExtractionError("blob_capture_failed", {"blob_url": blob_url})
        return await self.transport.capture_screenshot(clip=clip)

    @staticmethod
    def _is_generated_image_candidate(image: dict[str, Any]) -> bool:
        class_name = str(image.get("class_name", "") or "").lower()
        alt = str(image.get("alt", "") or "").lower()
        role = str(image.get("role", "") or "").lower()
        width = int(image.get("natural_width", 0) or 0)
        height = int(image.get("natural_height", 0) or 0)
        if "icon" in class_name or "avatar" in class_name:
            return False
        if "icon" in alt or "profile" in alt or role in {"avatar", "icon"}:
            return False
        if width < 256 or height < 256:
            return False
        return bool(image.get("in_gallery") or image.get("data_generated"))

    async def _extract_and_save_images(self, output_dir: str) -> list[str]:
        os.makedirs(output_dir, exist_ok=True)
        result = await self.transport.evaluate(
            """
            (() => {
                const images = [];
                document.querySelectorAll('img').forEach((img) => {
                    const parent = img.parentElement;
                    const container = img.closest('[data-image-gallery], .image-gallery, [class*="generated"], [class*="gallery"], [class*="result"]');
                    images.push({
                        src: img.src,
                        alt: img.alt || '',
                        natural_width: img.naturalWidth || 0,
                        natural_height: img.naturalHeight || 0,
                        role: img.getAttribute('role') || parent?.getAttribute('role') || '',
                        class_name: [img.className, parent?.className, container?.className].filter(Boolean).join(' '),
                        in_gallery: container !== null,
                        data_generated:
                            img.getAttribute('data-generated') === 'true' ||
                            parent?.getAttribute('data-generated') === 'true',
                    });
                });
                return images;
            })()
            """
        )
        images_data = result.get("result", {}).get("value", []) if result else []
        candidates = [image for image in images_data if self._is_generated_image_candidate(image)]
        if not candidates:
            return []

        saved_paths: list[str] = []
        for index, image in enumerate(candidates[:4], start=1):
            src = image.get("src", "")
            if not src:
                continue
            filepath = os.path.join(output_dir, f"gemini_image_{index}.png")
            if src.startswith("data:"):
                data = src.split(",", 1)[1]
                with open(filepath, "wb") as handle:
                    handle.write(base64.b64decode(data))
            elif src.startswith("blob:"):
                with open(filepath, "wb") as handle:
                    handle.write(await self._capture_blob_image(src))
            else:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.get(src)
                    response.raise_for_status()
                with open(filepath, "wb") as handle:
                    handle.write(response.content)
            saved_paths.append(filepath)
        return saved_paths

    async def _wait_for_generated_images(
        self,
        *,
        output_dir: str,
        timeout: int,
        poll_interval_ms: int = 1000,
    ) -> MediaExtractionResult:
        max_attempts = max(1, timeout // poll_interval_ms)
        stale_grace_attempts = min(max_attempts, 6)
        saw_loading = False
        saw_pending = False
        last_loading_state = False

        for attempt in range(max_attempts):
            if await self._is_generation_loading():
                saw_loading = True
                last_loading_state = True
            else:
                last_loading_state = False

            if await self._is_generation_pending():
                saw_pending = True

            try:
                paths = await self._extract_and_save_images(output_dir)
            except MediaExtractionError as exc:
                return MediaExtractionResult(error_code=exc.error_code, evidence=exc.evidence)

            if paths:
                return MediaExtractionResult(paths=paths)

            if not saw_loading and not saw_pending and attempt + 1 >= stale_grace_attempts:
                return MediaExtractionResult(error_code="stale_page_state", evidence={"attempts": attempt + 1})

            if attempt + 1 < max_attempts:
                await asyncio.sleep(poll_interval_ms / 1000)

        if last_loading_state or saw_pending:
            return MediaExtractionResult(error_code="image_generation_timeout", evidence={"attempts": max_attempts})
        if saw_loading:
            return MediaExtractionResult(error_code="empty_gallery", evidence={"attempts": max_attempts})
        return MediaExtractionResult(error_code="stale_page_state", evidence={"attempts": max_attempts})

    async def generate_image(self, prompt: str, output_dir: str = ".", timeout: int = 120000) -> ImageGenerationResult:
        await self._ensure_page()
        state_path: list[str] = []
        contract = await self._probe_contract()
        if contract.image_entry is None:
            return ImageGenerationResult(error_code="image_mode_unavailable", state_path=state_path)

        try:
            await self.transport.click(contract.image_entry.selector)
        except Exception:
            return ImageGenerationResult(error_code="image_mode_enter_failed", state_path=state_path)

        await asyncio.sleep(0.3)
        contract = await self._probe_contract()
        if not self._is_image_mode_latched(contract):
            return ImageGenerationResult(
                error_code="image_mode_not_latched",
                state_path=state_path,
                evidence={"reason": "image_entry_still_visible"},
            )

        state_path.append("image_mode_entered")
        if contract.prompt_input is None:
            return ImageGenerationResult(error_code="prompt_input_inactive", state_path=state_path)

        try:
            await self._fill_prompt_node(contract.prompt_input.selector, contract.prompt_input.kind, prompt)
        except Exception:
            return ImageGenerationResult(error_code="prompt_fill_failed", state_path=state_path)

        state_path.append("prompt_filled")
        await asyncio.sleep(0.5)
        contract = await self._probe_contract()
        try:
            if contract.send_button is not None:
                await self.transport.click(contract.send_button.selector)
            else:
                await self.transport.press_enter()
        except Exception:
            return ImageGenerationResult(error_code="submit_failed", state_path=state_path)

        state_path.append("submitted")
        extraction_result = await self._wait_for_generated_images(output_dir=output_dir, timeout=timeout)
        if extraction_result.paths:
            state_path.append("images_saved")
            return ImageGenerationResult(paths=extraction_result.paths, state_path=state_path)

        error_code = extraction_result.error_code or "image_generation_timeout"
        evidence = dict(extraction_result.evidence)
        if error_code == "stale_page_state":
            home_state = await self._probe_home_state()
            specific_error = self._classify_home_state_failure(home_state)
            if specific_error is not None:
                error_code = specific_error
        return ImageGenerationResult(error_code=error_code, state_path=state_path, evidence=evidence)

    async def _extract_video_candidate(self) -> dict[str, str] | None:
        result = await self.transport.evaluate(
            """
            (() => {
                const video = document.querySelector('video');
                if (video && video.src) {
                    return { type: 'video', src: video.src };
                }

                const downloadLink = document.querySelector('a[download*="video"], a[download*=".mp4"]');
                if (downloadLink && downloadLink.href) {
                    return { type: 'download-link', src: downloadLink.href };
                }

                const loading = document.querySelector('[aria-busy="true"], .loading-spinner, [role="progressbar"]');
                if (loading) {
                    return { type: 'loading', src: '' };
                }

                return null;
            })()
            """
        )
        return result.get("result", {}).get("value") if result else None

    async def _download_video(self, url: str, output_dir: str) -> str | None:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "gemini_video.mp4")
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with open(path, "wb") as handle:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            handle.write(chunk)
        except Exception:
            return None
        return path

    async def generate_video(self, prompt: str, output_dir: str = ".", timeout: int = 180000) -> VideoGenerationResult:
        await self._ensure_page()
        input_node = await self._find_input()
        if input_node is None:
            return VideoGenerationResult(
                error_code="prompt_input_not_found",
                error_message=_message_for_error("prompt_input_not_found"),
            )

        try:
            kind = "contenteditable" if input_node["isContentEditable"] else "textarea"
            await self._fill_prompt_node(input_node["selector"], kind, prompt)
        except Exception:
            return VideoGenerationResult(
                error_code="prompt_fill_failed",
                error_message=_message_for_error("prompt_fill_failed"),
            )

        await asyncio.sleep(0.5)
        activated = await self._click_button_by_labels(("generate video", "video", "生成视频", "制作视频"))
        if not activated:
            await self.transport.press_enter()

        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            candidate = await self._extract_video_candidate()
            if candidate and candidate.get("type") == "loading":
                await asyncio.sleep(5.0)
                continue
            if candidate and candidate.get("src"):
                path = await self._download_video(candidate["src"], output_dir)
                if path:
                    return VideoGenerationResult(
                        path=path,
                        evidence={"source_type": candidate.get("type", "video")},
                    )
                return VideoGenerationResult(
                    error_code="download_failed",
                    error_message=_message_for_error("download_failed"),
                    evidence={
                        "source_type": candidate.get("type", "video"),
                        "video_url": candidate["src"],
                    },
                )
            await asyncio.sleep(5.0)

        return VideoGenerationResult(
            error_code="video_generation_timeout",
            error_message=_message_for_error("video_generation_timeout"),
            evidence={"completion_strategy": "video_element_probe"},
        )


def _message_for_error(code: str) -> str:
    messages = {
        "prompt_input_not_found": "Gemini prompt input could not be located.",
        "response_timeout": "Gemini did not finish responding before timeout.",
        "image_mode_unavailable": "Gemini image mode is unavailable.",
        "image_mode_enter_failed": "Gemini image mode could not be entered.",
        "image_mode_not_latched": "Gemini image mode did not latch after activation.",
        "prompt_input_inactive": "Gemini prompt input is not active in image mode.",
        "prompt_fill_failed": "Gemini prompt text could not be filled.",
        "submit_failed": "Gemini request submission failed.",
        "image_generation_timeout": "Gemini image generation timed out.",
        "home_state_after_submit": "Gemini returned to the home state after submission.",
        "empty_gallery": "Gemini finished loading without exposing generated images.",
        "vision_upload_failed": "Gemini could not upload the provided image.",
        "deep_research_unavailable": "Gemini deep research is unavailable.",
        "deep_research_timeout": "Gemini deep research timed out.",
        "video_generation_timeout": "Gemini video generation timed out.",
        "download_failed": "Failed to download generated video",
    }
    return messages.get(code, code.replace("_", " "))


def _target_evidence_from_session(session: TargetSession) -> TargetEvidence:
    evidence = session.evidence()
    return TargetEvidence(
        target_id=evidence["target_id"],
        url=evidence["target_url"],
        resolution_source=evidence["resolution_source"],
    )


def _session_evidence_from_session(session: TargetSession) -> SessionEvidence:
    return SessionEvidence(attached=True, session_id=session.session_id)


async def _open_page(settings: Settings, *, create_if_missing: bool = False) -> tuple[TargetSession, GeminiPage]:
    try:
        if create_if_missing:
            session = await open_or_create_target_session(settings, GEMINI_PRODUCT)
        else:
            session = await open_target_session(settings, GEMINI_PRODUCT)
    except RuntimeError as exc:
        raise GeminiOperationError(
            code="target_not_found",
            message=str(exc),
        ) from exc
    return session, GeminiPage(session)


async def generate_text(settings: Settings, prompt: str, timeout: float) -> TextGenerationResult:
    session, page = await _open_page(settings)
    try:
        response = await page.send_prompt(prompt, timeout=int(timeout * 1000))
        if response.is_error:
            raise GeminiOperationError(
                code="response_timeout" if response.error_message == "Response timeout" else "prompt_failed",
                message=response.error_message or "Gemini request failed.",
                target=_target_evidence_from_session(session),
                session=_session_evidence_from_session(session),
            )
        return TextGenerationResult(
            text=response.text,
            images=response.images,
            thinking=response.thinking,
            target=_target_evidence_from_session(session),
            session=_session_evidence_from_session(session),
        )
    finally:
        await session.close()


async def ask(settings: Settings, prompt: str, timeout: float) -> TextGenerationResult:
    return await generate_text(settings, prompt, timeout)


async def generate_image(
    settings: Settings,
    prompt: str,
    output_dir: str,
    timeout: float,
) -> ImageGenerationResult:
    session, page = await _open_page(settings)
    try:
        result = await page.generate_image(prompt, output_dir=output_dir, timeout=int(timeout * 1000))
        result.target = _target_evidence_from_session(session)
        result.session = _session_evidence_from_session(session)
        return result
    finally:
        await session.close()


async def generate_vision(
    settings: Settings,
    prompt: str,
    image_path: str,
    timeout: float,
) -> TextGenerationResult:
    session, page = await _open_page(settings)
    try:
        uploaded = await page.upload_image(image_path)
        if not uploaded:
            raise GeminiOperationError(
                code="vision_upload_failed",
                message=_message_for_error("vision_upload_failed"),
                target=_target_evidence_from_session(session),
                session=_session_evidence_from_session(session),
            )
        response = await page.send_prompt(prompt, timeout=int(timeout * 1000))
        if response.is_error:
            raise GeminiOperationError(
                code="response_timeout" if response.error_message == "Response timeout" else "prompt_failed",
                message=response.error_message or "Gemini request failed.",
                target=_target_evidence_from_session(session),
                session=_session_evidence_from_session(session),
            )
        return TextGenerationResult(
            text=response.text,
            images=response.images,
            thinking=response.thinking,
            target=_target_evidence_from_session(session),
            session=_session_evidence_from_session(session),
        )
    finally:
        await session.close()


async def deep_research(
    settings: Settings,
    query: str,
    timeout: float,
    output_path: str | None = None,
) -> DeepResearchResult:
    session, page = await _open_page(settings, create_if_missing=True)
    try:
        result = await page.deep_research(query, timeout=int(timeout * 1000))
        result.target = _target_evidence_from_session(session)
        result.session = _session_evidence_from_session(session)
        if output_path and not result.is_error:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(result.report)
        return result
    finally:
        await session.close()


async def generate_video(
    settings: Settings,
    prompt: str,
    output_dir: str,
    timeout: float,
) -> VideoGenerationResult:
    session, page = await _open_page(settings, create_if_missing=True)
    try:
        result = await page.generate_video(prompt, output_dir=output_dir, timeout=int(timeout * 1000))
        result.target = _target_evidence_from_session(session)
        result.session = _session_evidence_from_session(session)
        return result
    finally:
        await session.close()


def create_chat_session(session_id: str) -> ChatSessionRecord:
    session = ChatSessionRecord(id=session_id)
    save_chat_session(session)
    return session


def list_chat_state(limit: int = 100) -> list[ChatSessionRecord]:
    return list_chat_sessions(limit=limit)


def use_chat_session(session_id: str) -> ChatSessionRecord:
    session = load_chat_session(session_id)
    if session is None:
        raise RuntimeError(f"Chat session not found: {session_id}")
    set_current_chat_session_id(session_id)
    return session


def resolve_chat_session_id(session_id: str | None) -> str:
    resolved = session_id or get_current_chat_session_id()
    if not resolved:
        raise RuntimeError("No chat session specified and no current Gemini chat session is selected.")
    return resolved


async def send_chat_message(
    settings: Settings,
    session_id: str,
    message: str,
    timeout: float,
) -> dict[str, Any]:
    chat_session = load_chat_session(session_id)
    if chat_session is None:
        raise RuntimeError(f"Chat session not found: {session_id}")

    session, page = await _open_page(settings, create_if_missing=True)
    try:
        response = await page.send_prompt(message, timeout=int(timeout * 1000))
        if response.is_error:
            raise GeminiOperationError(
                code="response_timeout" if response.error_message == "Response timeout" else "prompt_failed",
                message=response.error_message or "Gemini request failed.",
                target=_target_evidence_from_session(session),
                session=_session_evidence_from_session(session),
            )
        created_at = datetime.now(timezone.utc).isoformat()
        chat_session.messages.append(ChatMessageRecord(role="user", content=message, created_at=created_at))
        chat_session.messages.append(ChatMessageRecord(role="assistant", content=response.text, created_at=created_at))
        save_chat_session(chat_session)
        set_current_chat_session_id(chat_session.id)
        return {
            "reply": response.text,
            "chat_session": {"id": chat_session.id, "message_count": chat_session.message_count},
            "target": asdict(_target_evidence_from_session(session)),
            "session": asdict(_session_evidence_from_session(session)),
        }
    finally:
        await session.close()


class GeminiService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate_text(self, prompt: str) -> dict[str, Any]:
        result = await generate_text(self.settings, prompt, 60.0)
        return {
            "product": "gemini",
            "status": "ok",
            "error": None,
            "text": result.text,
            "images": result.images,
            "thinking": result.thinking,
            "evidence": {
                "target_id": result.target.target_id if result.target else None,
                "session_id": result.session.session_id if result.session else None,
                "resolution_source": result.target.resolution_source if result.target else "none",
                "via": "page_websocket",
            },
        }

    async def ask(self, prompt: str) -> dict[str, Any]:
        return await self.generate_text(prompt)

    async def generate_image(self, prompt: str, output_dir: str = ".") -> dict[str, Any]:
        result = await generate_image(self.settings, prompt, output_dir, 120.0)
        evidence = {
            "target_id": result.target.target_id if result.target else None,
            "session_id": result.session.session_id if result.session else None,
            "resolution_source": result.target.resolution_source if result.target else "none",
            "via": "page_websocket",
        }
        evidence.update(result.evidence)
        status = "error" if result.is_error else "ok"
        return {
            "product": "gemini",
            "status": status,
            "error": None
            if not result.is_error
            else {
                "code": result.error_code,
                "message": _message_for_error(result.error_code or "image_generation_failed"),
            },
            "paths": result.paths,
            "state_path": result.state_path,
            "evidence": evidence,
        }

    async def generate_vision(self, prompt: str, image_path: str) -> dict[str, Any]:
        result = await generate_vision(self.settings, prompt, image_path, 90.0)
        return {
            "product": "gemini",
            "status": "ok",
            "error": None,
            "text": result.text,
            "images": result.images,
            "thinking": result.thinking,
            "evidence": {
                "target_id": result.target.target_id if result.target else None,
                "session_id": result.session.session_id if result.session else None,
                "resolution_source": result.target.resolution_source if result.target else "none",
                "via": "page_websocket",
            },
        }
