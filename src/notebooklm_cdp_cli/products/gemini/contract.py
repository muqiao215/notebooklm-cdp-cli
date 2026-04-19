from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PROBE_ATTRIBUTE = "data-notebooklm-cdp-gemini-probe"

PROMPT_INPUT_LABELS = (
    "enter a prompt",
    "enter prompt",
    "message gemini",
    "ask gemini",
    "for gemini input prompt",
    "为 gemini 输入提示",
    "向 gemini 提问",
    "输入提示",
)
SEND_BUTTON_LABELS = (
    "send",
    "send message",
    "发送",
)
IMAGE_ENTRY_LABELS = (
    "generate image",
    "make image",
    "create image",
    "制作图片",
    "生成图片",
)
UPLOAD_BUTTON_LABELS = (
    "open upload file menu",
    "upload file",
    "add photos and files",
    "add photos & files",
    "打开文件上传菜单",
    "上传文件",
    "添加照片和文件",
)


@dataclass(slots=True)
class UiNode:
    selector: str
    label: str
    kind: str
    tag: str
    aria_label: str = ""
    text: str = ""
    placeholder: str = ""


@dataclass(slots=True)
class GeminiContract:
    prompt_input: UiNode | None = None
    send_button: UiNode | None = None
    image_entry: UiNode | None = None
    upload_button: UiNode | None = None

    def missing_capabilities(self, *names: str) -> list[str]:
        names = names or ("prompt_input", "send_button", "image_entry", "upload_button")
        return [f"{name}_not_found" for name in names if getattr(self, name) is None]


def probe_gemini_contract(dom_snapshot: dict[str, Any] | None) -> GeminiContract:
    dom_snapshot = dom_snapshot or {}
    buttons = [_to_ui_node(node, default_kind="button") for node in dom_snapshot.get("buttons", [])]
    inputs = [_to_ui_node(node, default_kind="input") for node in dom_snapshot.get("inputs", [])]
    return GeminiContract(
        prompt_input=_find_prompt_input(inputs),
        send_button=_find_button(buttons, SEND_BUTTON_LABELS),
        image_entry=_find_button(buttons, IMAGE_ENTRY_LABELS),
        upload_button=_find_button(buttons, UPLOAD_BUTTON_LABELS),
    )


def _find_prompt_input(nodes: list[UiNode]) -> UiNode | None:
    labelled = [node for node in nodes if _matches(node, PROMPT_INPUT_LABELS)]
    if labelled:
        return _prefer_input_node(labelled)
    return _prefer_input_node(nodes)


def _prefer_input_node(nodes: list[UiNode]) -> UiNode | None:
    if not nodes:
        return None
    return min(
        nodes,
        key=lambda node: (
            0 if node.kind == "contenteditable" else 1,
            0 if node.kind == "textarea" else 1,
            node.selector,
        ),
    )


def _find_button(nodes: list[UiNode], variants: tuple[str, ...]) -> UiNode | None:
    matches = [node for node in nodes if _matches(node, variants)]
    if not matches:
        return None
    return min(matches, key=lambda node: (_normalize(node.label), node.selector))


def _matches(node: UiNode, variants: tuple[str, ...]) -> bool:
    label = _normalize(" ".join(part for part in (node.label, node.text, node.aria_label, node.placeholder) if part))
    return any(variant in label for variant in variants)


def _to_ui_node(node: dict[str, Any], default_kind: str) -> UiNode:
    tag = str(node.get("tag", "") or "").upper()
    aria_label = str(node.get("aria", "") or "")
    text = str(node.get("text", "") or "")
    placeholder = str(node.get("placeholder", "") or "")
    selector = str(node.get("selector", "") or "")

    label = next((value for value in (aria_label, text, placeholder) if value), "")
    kind = default_kind
    if node.get("contenteditable"):
        kind = "contenteditable"
    elif tag == "TEXTAREA":
        kind = "textarea"

    return UiNode(
        selector=selector,
        label=label,
        kind=kind,
        tag=tag,
        aria_label=aria_label,
        text=text,
        placeholder=placeholder,
    )


def _normalize(value: str) -> str:
    return " ".join(value.lower().split())
