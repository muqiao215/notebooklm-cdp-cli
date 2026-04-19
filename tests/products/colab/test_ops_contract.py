from notebooklm_cdp_cli.products.colab.ops import classify_runtime_probe, summarize_notebook_probe


def test_classify_runtime_probe_prefers_colab_api_signal():
    result = classify_runtime_probe(
        {
            "colab_api_available": True,
            "kernel_id": "kernel-1",
            "connect_button_visible": False,
            "running_cells": 0,
            "output_cells": 2,
        }
    )

    assert result["state"] == "connected"
    assert result["attached"] is True
    assert result["confidence"] == "high"
    assert result["executor_hint"] == "google.colab.kernel"


def test_classify_runtime_probe_is_conservative_for_dom_only_signal():
    result = classify_runtime_probe(
        {
            "colab_api_available": False,
            "kernel_id": None,
            "connect_button_visible": True,
            "running_cells": 0,
            "output_cells": 0,
        }
    )

    assert result["state"] == "disconnected"
    assert result["attached"] is False
    assert result["confidence"] == "medium"
    assert result["uncertainty"]


def test_summarize_notebook_probe_trims_output_and_error_excerpts():
    summary = summarize_notebook_probe(
        probe={
            "title": "Notebook",
            "url": "https://colab.research.google.com/drive/1",
            "total_cells": 8,
            "current_cell": 2,
            "last_output": "x" * 200,
            "last_error": "y" * 220,
        },
        runtime={
            "state": "unknown",
            "confidence": "low",
            "uncertainty": ["dom_only"],
        },
        resolution_source="first",
    )

    assert summary["title"] == "Notebook"
    assert summary["runtime_state"] == "unknown"
    assert summary["runtime_confidence"] == "low"
    assert summary["resolution_source"] == "first"
    assert len(summary["last_output_excerpt"]) <= 121
    assert len(summary["last_error_excerpt"]) <= 121

