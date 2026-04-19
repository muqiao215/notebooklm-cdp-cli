from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from ...config import Settings
from ...core.product import FLOW_PRODUCT
from ...core.targets import TargetSession, open_or_create_target_session


@dataclass(slots=True)
class FlowCommandResult:
    command: str
    title: str | None = None
    url: str | None = None
    path: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    evidence: dict[str, object] = field(default_factory=dict)
    target: dict[str, object] | None = None
    session: dict[str, object] | None = None

    @property
    def is_error(self) -> bool:
        return self.error_code is not None


class FlowOperationError(RuntimeError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        target: dict[str, object] | None = None,
        session: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.target = target
        self.session = session


class FlowPage:
    def __init__(self, session: TargetSession):
        self.session = session
        self.transport = session.transport
        self._page_loaded = False

    async def open(self) -> FlowCommandResult:
        await self.transport.navigate(FLOW_PRODUCT.default_url)
        self._page_loaded = True
        await asyncio.sleep(1)
        await self.transport.wait_for_load_state("networkidle", timeout=15000)
        return FlowCommandResult(
            command="open",
            title=await self.transport.get_title(),
            url=await self.transport.get_url(),
            evidence={"opened_via": "created_target" if self.session.resolution_source == "created" else "product_page"},
        )

    async def _ensure_page(self) -> None:
        if self._page_loaded:
            return
        await self.open()

    async def _fill_prompt(self, prompt: str) -> bool:
        prompt_literal = json.dumps(prompt)
        result = await self.transport.evaluate(
            f"""
            (() => {{
                const selectors = [
                    'textarea[placeholder*="prompt" i]',
                    'textarea[placeholder*="描述" i]',
                    'textarea[placeholder*="text" i]',
                    'input[placeholder*="prompt" i]',
                    'input[aria-label="可编辑文本"]',
                    'input[type="text"]'
                ];
                for (const selector of selectors) {{
                    const el = document.querySelector(selector);
                    if (el && el.offsetParent !== null) {{
                        el.focus();
                        el.value = {prompt_literal};
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                }}
                return false;
            }})()
            """
        )
        return bool(result.get("result", {}).get("value")) if result else False

    async def _upload_image(self, image_path: str) -> bool:
        absolute_path = os.path.abspath(image_path)
        if not os.path.exists(absolute_path):
            return False

        result = await self.transport.evaluate(
            """
            (() => document.querySelectorAll('input[type="file"]').length > 0)()
            """
        )
        if result and result.get("result", {}).get("value"):
            try:
                await self.transport.set_upload_files('input[type="file"]', [absolute_path])
                return True
            except Exception:
                return False

        result = await self.transport.evaluate(
            """
            (() => {
                const container = document.querySelector('[class*="upload"], [class*="drop"], [class*="image"]');
                if (container) {
                    container.click();
                    return true;
                }
                return false;
            })()
            """
        )
        return bool(result.get("result", {}).get("value")) if result else False

    async def _click_generate(self) -> bool:
        result = await self.transport.evaluate(
            """
            (() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const button = buttons.find((node) => {
                    const label = `${node.getAttribute('aria-label') || ''} ${node.innerText || node.textContent || ''}`;
                    return /generate|create|创建/i.test(label);
                });
                if (!button) return false;
                button.click();
                return true;
            })()
            """
        )
        return bool(result.get("result", {}).get("value")) if result else False

    async def text_to_video(self, prompt: str, output_dir: str = ".", timeout: int = 180000) -> FlowCommandResult:
        await self._ensure_page()
        if not await self._fill_prompt(prompt):
            return FlowCommandResult(
                command="text_to_video",
                error_code="prompt_input_unavailable",
                error_message="Could not find prompt input",
                evidence={"prompt_filled": False},
            )
        await self._click_generate()
        result = await self._wait_for_video(output_dir, timeout=timeout)
        result.command = "text_to_video"
        return result

    async def image_to_video(
        self,
        image_path: str,
        prompt: str | None = None,
        output_dir: str = ".",
        timeout: int = 180000,
    ) -> FlowCommandResult:
        await self._ensure_page()
        if not await self._upload_image(image_path):
            return FlowCommandResult(
                command="image_to_video",
                error_code="image_upload_failed",
                error_message="Could not upload image",
                evidence={"image_path": os.path.abspath(image_path)},
            )
        if prompt:
            await self._fill_prompt(prompt)
        await self._click_generate()
        result = await self._wait_for_video(output_dir, timeout=timeout)
        result.command = "image_to_video"
        return result

    async def screenshot(self, path: str) -> FlowCommandResult:
        await self._ensure_page()
        data = await self.transport.capture_screenshot()
        if not data:
            return FlowCommandResult(
                command="screenshot",
                path=path,
                error_code="screenshot_failed",
                error_message="Failed to capture Flow screenshot",
            )
        with open(path, "wb") as handle:
            handle.write(data)
        return FlowCommandResult(command="screenshot", path=path)

    async def _wait_for_video(self, output_dir: str, timeout: int = 180000) -> FlowCommandResult:
        os.makedirs(output_dir, exist_ok=True)
        start_time = time.time()
        poll_interval = 5

        while time.time() - start_time < timeout / 1000:
            result = await self.transport.evaluate(
                """
                (() => {
                    const video = document.querySelector('video');
                    if (video && video.src) {
                        return { type: 'video', src: video.src };
                    }

                    const link = document.querySelector('a[download*="video"], a[download*=".mp4"]');
                    if (link && link.href) {
                        return { type: 'download-link', src: link.href };
                    }

                    const button = document.querySelector('button[aria-label*="Download"], button[aria-label*="download"]');
                    if (button) {
                        const onclick = button.getAttribute('onclick') || '';
                        const match = onclick.match(/https?:\\/\\/[^"'\\s]+/);
                        if (match) return { type: 'download-btn', src: match[0] };
                    }

                    const loading = document.querySelector('[aria-busy="true"], [class*="loading"], [class*="spinner"]');
                    if (loading) return { type: 'loading' };

                    return null;
                })()
                """
            )
            data = result.get("result", {}).get("value") if result else None

            if data:
                if data.get("type") == "loading":
                    await asyncio.sleep(poll_interval)
                    continue

                video_url = data.get("src")
                if video_url:
                    path = await self._download_video(video_url, output_dir)
                    if path:
                        return FlowCommandResult(
                            command="text_to_video",
                            path=path,
                            evidence={"source_type": data.get("type")},
                        )
                    return FlowCommandResult(
                        command="text_to_video",
                        error_code="download_failed",
                        error_message="Failed to download generated video",
                        evidence={
                            "source_type": data.get("type"),
                            "video_url": video_url,
                        },
                    )
            await asyncio.sleep(poll_interval)

        return FlowCommandResult(
            command="text_to_video",
            error_code="video_generation_timeout",
            error_message="Video generation timeout",
            evidence={"completion_strategy": "video_element_probe"},
        )

    async def _download_video(self, url: str, output_dir: str) -> str | None:
        path = os.path.join(output_dir, "flow_video.mp4")
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


def _target_dict(session: TargetSession) -> dict[str, object]:
    evidence = session.evidence()
    return {
        "target_id": evidence["target_id"],
        "url": evidence["target_url"],
        "resolution_source": evidence["resolution_source"],
    }


def _session_dict(session: TargetSession) -> dict[str, object]:
    return {
        "attached": True,
        "session_id": session.session_id,
    }


def _attach_evidence(result: FlowCommandResult, session: TargetSession) -> FlowCommandResult:
    result.target = _target_dict(session)
    result.session = _session_dict(session)
    return result


async def _open_page(settings: Settings) -> tuple[TargetSession, FlowPage]:
    try:
        session = await open_or_create_target_session(settings, FLOW_PRODUCT)
    except RuntimeError as exc:
        raise FlowOperationError(code="target_unavailable", message=str(exc)) from exc
    return session, FlowPage(session)


async def open_flow(settings: Settings) -> FlowCommandResult:
    session, page = await _open_page(settings)
    try:
        return _attach_evidence(await page.open(), session)
    finally:
        await session.close()


async def text_to_video(settings: Settings, prompt: str, output_dir: str, timeout: float) -> FlowCommandResult:
    session, page = await _open_page(settings)
    try:
        result = await page.text_to_video(prompt, output_dir=output_dir, timeout=int(timeout * 1000))
        return _attach_evidence(result, session)
    finally:
        await session.close()


async def image_to_video(
    settings: Settings,
    image_path: str,
    prompt: str | None,
    output_dir: str,
    timeout: float,
) -> FlowCommandResult:
    session, page = await _open_page(settings)
    try:
        result = await page.image_to_video(image_path, prompt=prompt, output_dir=output_dir, timeout=int(timeout * 1000))
        return _attach_evidence(result, session)
    finally:
        await session.close()


async def take_screenshot(settings: Settings, path: str) -> FlowCommandResult:
    session, page = await _open_page(settings)
    try:
        result = await page.screenshot(path)
        return _attach_evidence(result, session)
    finally:
        await session.close()
