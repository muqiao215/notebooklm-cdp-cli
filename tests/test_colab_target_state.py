from notebooklm_cdp_cli.state import get_product_target_selection, set_product_target_selection


def test_product_target_selection_is_namespaced(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))

    set_product_target_selection(
        "gemini",
        target_id="gemini-1",
        title="Gemini",
        url="https://gemini.google.com/app",
    )
    set_product_target_selection(
        "colab",
        target_id="colab-1",
        title="Notebook",
        url="https://colab.research.google.com/drive/1",
    )

    assert get_product_target_selection("gemini") == {
        "target_id": "gemini-1",
        "title": "Gemini",
        "url": "https://gemini.google.com/app",
    }
    assert get_product_target_selection("colab") == {
        "target_id": "colab-1",
        "title": "Notebook",
        "url": "https://colab.research.google.com/drive/1",
    }
