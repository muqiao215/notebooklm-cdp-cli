from notebooklm_cdp_cli.core.product import GEMINI_PRODUCT
from notebooklm_cdp_cli.core.targets import resolve_target


def test_resolve_target_prefers_gemini_page_websocket():
    resolution = resolve_target(
        [
            {
                "id": "page-other",
                "type": "page",
                "title": "Other",
                "url": "https://example.com",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/other",
            },
            {
                "id": "page-gemini",
                "type": "page",
                "title": "Gemini",
                "url": "https://gemini.google.com/app",
                "webSocketDebuggerUrl": "http://127.0.0.1:9222/devtools/page/gemini",
            },
        ],
        GEMINI_PRODUCT,
    )

    assert resolution.target is not None
    assert resolution.target.target_id == "page-gemini"
    assert resolution.target.web_socket_url == "ws://127.0.0.1:9222/devtools/page/gemini"
    assert resolution.resolution_source == "product_page"


def test_resolve_target_reports_no_match_without_product_page():
    resolution = resolve_target(
        [
            {
                "id": "worker-1",
                "type": "service_worker",
                "title": "Worker",
                "url": "https://gemini.google.com/sw.js",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/worker",
            },
            {
                "id": "page-other",
                "type": "page",
                "title": "Other",
                "url": "https://example.com",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/other",
            },
        ],
        GEMINI_PRODUCT,
    )

    assert resolution.target is None
    assert resolution.resolution_source == "none"
