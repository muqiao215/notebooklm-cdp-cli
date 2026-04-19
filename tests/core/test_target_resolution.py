import pytest

from notebooklm_cdp_cli.core.product import COLAB_PRODUCT
from notebooklm_cdp_cli.core.targets import (
    TargetResolutionError,
    discover_product_targets,
    resolve_product_target,
    resolve_selected_target,
)


def _raw_colab_targets() -> list[dict]:
    return [
        {
            "id": "colab-active",
            "type": "page",
            "title": "Active Notebook",
            "url": "https://colab.research.google.com/drive/active",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/active",
            "attached": True,
        },
        {
            "id": "colab-first",
            "type": "page",
            "title": "First Notebook",
            "url": "https://colab.research.google.com/drive/first",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/first",
            "attached": False,
        },
        {
            "id": "search-tab",
            "type": "page",
            "title": "Search",
            "url": "https://google.com/search?q=colab",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/search",
            "attached": False,
        },
    ]


def test_discover_product_targets_only_returns_colab_pages():
    targets = discover_product_targets(_raw_colab_targets(), COLAB_PRODUCT)

    assert [target.target_id for target in targets] == ["colab-active", "colab-first"]


def test_resolve_selected_target_reports_selected_state():
    selected = resolve_selected_target(
        discover_product_targets(_raw_colab_targets(), COLAB_PRODUCT),
        selected_target_id="colab-first",
        selected_url="https://colab.research.google.com/drive/first",
    )

    assert selected.target_id == "colab-first"
    assert selected.url == "https://colab.research.google.com/drive/first"
    assert selected.status == "selected"


def test_resolve_product_target_prefers_explicit_selection():
    resolution = resolve_product_target(
        _raw_colab_targets(),
        COLAB_PRODUCT,
        selected_target_id="colab-first",
        selected_url="https://colab.research.google.com/drive/first",
    )

    assert resolution.target is not None
    assert resolution.target.target_id == "colab-first"
    assert resolution.resolution_source == "explicit"
    assert resolution.selected is not None
    assert resolution.selected.status == "selected"


def test_resolve_product_target_reports_stale_selection_and_falls_back_to_active():
    resolution = resolve_product_target(
        _raw_colab_targets(),
        COLAB_PRODUCT,
        selected_target_id="stale-colab",
        selected_url="https://colab.research.google.com/drive/stale",
    )

    assert resolution.target is not None
    assert resolution.target.target_id == "colab-active"
    assert resolution.resolution_source == "active"
    assert resolution.selected is not None
    assert resolution.selected.target_id == "stale-colab"
    assert resolution.selected.status == "stale"


def test_resolve_product_target_falls_back_to_first_when_no_active_target():
    raw_targets = _raw_colab_targets()
    raw_targets[0]["attached"] = False

    resolution = resolve_product_target(raw_targets, COLAB_PRODUCT)

    assert resolution.target is not None
    assert resolution.target.target_id == "colab-active"
    assert resolution.resolution_source == "first"


def test_resolve_product_target_reports_none_when_no_candidate_exists():
    resolution = resolve_product_target(
        [
            {
                "id": "search-tab",
                "type": "page",
                "title": "Search",
                "url": "https://google.com/search?q=colab",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/search",
                "attached": False,
            }
        ],
        COLAB_PRODUCT,
    )

    assert resolution.target is None
    assert resolution.resolution_source == "none"
    assert resolution.selected is not None
    assert resolution.selected.status == "none"


def test_resolve_product_target_rejects_ambiguous_requested_token():
    with pytest.raises(TargetResolutionError) as exc:
        resolve_product_target(
            [
                {
                    "id": "colab-alpha",
                    "type": "page",
                    "title": "Alpha Notebook",
                    "url": "https://colab.research.google.com/drive/alpha",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/alpha",
                    "attached": False,
                },
                {
                    "id": "colab-beta",
                    "type": "page",
                    "title": "Beta Notebook",
                    "url": "https://colab.research.google.com/drive/beta",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/beta",
                    "attached": False,
                },
            ],
            COLAB_PRODUCT,
            requested_target="colab-",
        )

    assert exc.value.code == "ambiguous_target"
