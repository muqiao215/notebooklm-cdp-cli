from __future__ import annotations

import asyncio
import base64
import contextlib
import json
from typing import Any

import websockets


class CDPTransport:
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._message_id = 0
        self._responses: dict[int, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None

    async def connect(self) -> "CDPTransport":
        self._ws = await websockets.connect(self.websocket_url)
        self._reader_task = asyncio.create_task(self._handle_messages())
        await self.send_command("Page.enable")
        await self.send_command("Runtime.enable")
        await self.send_command("DOM.enable")
        return self

    async def close(self) -> None:
        ws = self._ws
        self._ws = None
        if ws is not None:
            await ws.close()

        if self._reader_task is not None:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None

        self._cancel_pending_responses()

    async def _handle_messages(self) -> None:
        if self._ws is None:
            return
        try:
            async for message in self._ws:
                data = json.loads(message)
                if "id" in data:
                    future = self._responses.get(data["id"])
                    if future is not None and not future.done():
                        future.set_result(data)
        except websockets.exceptions.ConnectionClosed:
            pass
        except asyncio.CancelledError:
            raise
        finally:
            self._cancel_pending_responses()

    def _cancel_pending_responses(self) -> None:
        for future in self._responses.values():
            if not future.done():
                future.cancel()
        self._responses.clear()

    async def send_command(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        await_response: bool = True,
    ) -> Any:
        if self._ws is None:
            raise RuntimeError("CDP transport is not connected")

        message_id = self._message_id
        self._message_id += 1

        future: asyncio.Future | None = None
        if await_response:
            future = asyncio.get_running_loop().create_future()
            self._responses[message_id] = future

        await self._ws.send(
            json.dumps(
                {
                    "id": message_id,
                    "method": method,
                    "params": params or {},
                }
            )
        )

        if future is None:
            return None

        try:
            response = await future
            return response.get("result")
        finally:
            self._responses.pop(message_id, None)

    async def evaluate(self, expression: str) -> Any:
        return await self.send_command(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )

    async def navigate(self, url: str) -> str:
        result = await self.send_command("Page.navigate", {"url": url})
        return result.get("frameId", "") if result else ""

    async def wait_for_load_state(self, state: str = "networkidle", timeout: int = 30000) -> bool:
        await asyncio.sleep(0.5)
        expected = state.replace("networkidle", "complete")
        for _ in range(max(1, timeout // 500)):
            result = await self.evaluate(f"document.readyState === '{expected}'")
            if result and result.get("result", {}).get("value"):
                return True
            await asyncio.sleep(0.5)
        return False

    async def get_document(self) -> dict[str, Any]:
        result = await self.send_command("DOM.getDocument")
        return result or {}

    async def query_selector(self, selector: str, node_id: int = 0) -> int | None:
        if node_id == 0:
            document = await self.get_document()
            node_id = document.get("root", {}).get("nodeId", 0)

        result = await self.send_command(
            "DOM.querySelector",
            {
                "selector": selector,
                "nodeId": node_id,
            },
        )
        return result.get("nodeId") if result else None

    async def get_box_model(self, node_id: int) -> dict[str, Any] | None:
        result = await self.send_command("DOM.getBoxModel", {"nodeId": node_id})
        return result or None

    async def _get_element_center(self, selector: str) -> tuple[float, float] | None:
        node_id = await self.query_selector(selector)
        if not node_id:
            return None

        box = await self.get_box_model(node_id)
        if not box:
            return None

        content = box.get("model", {}).get("content", [])
        if len(content) < 6:
            return None
        return ((content[0] + content[2]) / 2, (content[1] + content[5]) / 2)

    async def click(self, selector: str) -> None:
        center = await self._get_element_center(selector)
        if center is None:
            raise RuntimeError(f"Element not found: {selector}")
        x, y = center
        await self.send_command(
            "Input.dispatchMouseEvent",
            {
                "type": "mousePressed",
                "x": x,
                "y": y,
                "button": "left",
                "clickCount": 1,
            },
        )
        await self.send_command(
            "Input.dispatchMouseEvent",
            {
                "type": "mouseReleased",
                "x": x,
                "y": y,
                "button": "left",
                "clickCount": 1,
            },
        )

    async def fill(self, selector: str, text: str) -> None:
        text_literal = json.dumps(text)
        await self.evaluate(
            f"""
            (function() {{
                const el = document.querySelector('{selector}');
                if (!el) return false;
                el.focus();
                el.value = {text_literal};
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }})()
            """
        )

    async def press_key(self, key: str) -> None:
        await self.send_command(
            "Input.dispatchKeyEvent",
            {
                "type": "keyPressed",
                "text": key,
                "key": key,
            },
        )
        await self.send_command(
            "Input.dispatchKeyEvent",
            {
                "type": "keyReleased",
                "key": key,
            },
        )

    async def press_enter(self) -> None:
        await self.press_key("Enter")

    async def get_inner_text(self, selector: str) -> str | None:
        result = await self.evaluate(f"document.querySelector('{selector}')?.innerText")
        return result.get("result", {}).get("value") if result else None

    async def capture_screenshot(self, *, clip: dict[str, float] | None = None, format: str = "png") -> bytes:
        params: dict[str, Any] = {
            "format": format,
            "quality": 100 if format == "png" else 80,
        }
        if clip is not None:
            params["clip"] = {
                "x": clip["x"],
                "y": clip["y"],
                "width": clip["width"],
                "height": clip["height"],
                "scale": 1,
            }
        result = await self.send_command("Page.captureScreenshot", params)
        if result and "data" in result:
            return base64.b64decode(result["data"])
        return b""

    async def set_upload_files(self, selector: str, files: list[str]) -> None:
        node_id = await self.query_selector(selector)
        if not node_id:
            raise RuntimeError(f"File input not found: {selector}")
        await self.send_command(
            "DOM.setFileInputFiles",
            {
                "nodeId": node_id,
                "files": files,
            },
        )

    async def get_url(self) -> str:
        result = await self.evaluate("window.location.href")
        return result.get("result", {}).get("value", "") if result else ""

    async def get_title(self) -> str:
        result = await self.evaluate("document.title")
        return result.get("result", {}).get("value", "") if result else ""
