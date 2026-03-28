import json

from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli


def test_notebook_list_json(monkeypatch):
    runner = CliRunner()

    async def fake_list_notebooks(settings):
        return [
            {"id": "nb1", "title": "Notebook One", "is_owner": True},
            {"id": "nb2", "title": "Notebook Two", "is_owner": False},
        ]

    monkeypatch.setattr("notebooklm_cdp_cli.cli.list_notebooks", fake_list_notebooks)

    result = runner.invoke(cli, ["notebook", "list", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 2
    assert payload["notebooks"][0]["id"] == "nb1"


def test_notebook_create_json(monkeypatch):
    runner = CliRunner()

    async def fake_create_notebook(settings, title):
        assert title == "New Notebook"
        return {"id": "nb-new", "title": "New Notebook", "is_owner": True, "created_at": None}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.create_notebook", fake_create_notebook)

    result = runner.invoke(cli, ["notebook", "create", "New Notebook", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "nb-new"


def test_notebook_rename_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))

    async def fake_rename_notebook(settings, notebook_id, title):
        assert notebook_id == "nb-1"
        assert title == "Renamed Notebook"
        return {"id": "nb-1", "title": "Renamed Notebook", "is_owner": True, "created_at": None}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.rename_notebook", fake_rename_notebook, raising=False)

    result = runner.invoke(cli, ["notebook", "rename", "nb-1", "Renamed Notebook", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["title"] == "Renamed Notebook"


def test_notebook_delete_json_clears_current_context(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(
        json.dumps({"notebook_id": "nb-1", "conversation_id": "conv-1"}),
        encoding="utf-8",
    )

    async def fake_delete_notebook(settings, notebook_id):
        assert notebook_id == "nb-1"
        return {"deleted": True, "notebook_id": "nb-1"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.delete_notebook", fake_delete_notebook, raising=False)

    result = runner.invoke(cli, ["notebook", "delete", "nb-1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["deleted"] is True
    saved_context = json.loads((tmp_path / "context.json").read_text(encoding="utf-8"))
    assert saved_context == {}


def test_notebook_summary_json_uses_current_notebook(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_get_notebook_summary(settings, notebook_id):
        assert notebook_id == "nb-current"
        return {"notebook_id": "nb-current", "summary": "Core themes and tensions."}

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.get_notebook_summary",
        fake_get_notebook_summary,
        raising=False,
    )

    result = runner.invoke(cli, ["notebook", "summary", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"] == "Core themes and tensions."


def test_notebook_describe_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_describe_notebook(settings, notebook_id):
        assert notebook_id == "nb-current"
        return {
            "notebook_id": "nb-current",
            "summary": "A concise synthesis.",
            "suggested_topics": [
                {"question": "What changed?", "prompt": "Summarize the deltas."},
            ],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.cli.describe_notebook", fake_describe_notebook, raising=False)

    result = runner.invoke(cli, ["notebook", "describe", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["suggested_topics"][0]["question"] == "What changed?"


def test_notebook_metadata_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_get_notebook_metadata(settings, notebook_id):
        assert notebook_id == "nb-current"
        return {
            "id": "nb-current",
            "title": "Strategy Notes",
            "created_at": None,
            "is_owner": True,
            "sources": [
                {"kind": "web_page", "title": "Market Map", "url": "https://example.com/map"},
            ],
        }

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.get_notebook_metadata",
        fake_get_notebook_metadata,
        raising=False,
    )

    result = runner.invoke(cli, ["notebook", "metadata", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "nb-current"
    assert payload["sources"][0]["kind"] == "web_page"


def test_notebook_remove_from_recent_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))

    async def fake_remove_notebook_from_recent(settings, notebook_id):
        assert notebook_id == "nb-archive"
        return {"notebook_id": "nb-archive", "removed_from_recent": True}

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.remove_notebook_from_recent",
        fake_remove_notebook_from_recent,
        raising=False,
    )

    result = runner.invoke(cli, ["notebook", "remove-from-recent", "nb-archive", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["removed_from_recent"] is True
    assert payload["notebook_id"] == "nb-archive"


def test_context_show_and_clear_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    context_path = tmp_path / "context.json"
    context_path.write_text(
        json.dumps({"notebook_id": "nb-current", "conversation_id": "conv-1"}),
        encoding="utf-8",
    )

    show_result = runner.invoke(cli, ["context", "show", "--json"])

    assert show_result.exit_code == 0
    show_payload = json.loads(show_result.output)
    assert show_payload["notebook_id"] == "nb-current"
    assert show_payload["conversation_id"] == "conv-1"

    clear_result = runner.invoke(cli, ["context", "clear", "--json"])

    assert clear_result.exit_code == 0
    clear_payload = json.loads(clear_result.output)
    assert clear_payload["cleared"] is True
    assert json.loads(context_path.read_text(encoding="utf-8")) == {}


def test_source_list_json_uses_current_notebook(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_list_sources(settings, notebook_id):
        assert notebook_id == "nb-current"
        return [
            {"id": "src1", "title": "AI", "url": "https://example.com/ai", "kind": "web_page"},
        ]

    monkeypatch.setattr("notebooklm_cdp_cli.cli.list_sources", fake_list_sources)

    result = runner.invoke(cli, ["source", "list", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["sources"][0]["id"] == "src1"


def test_ask_json_returns_answer(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_ask_question(settings, notebook_id, question, conversation_id):
        assert notebook_id == "nb-current"
        assert question == "what changed?"
        assert conversation_id is None
        return {
            "answer": "The core ideas changed.",
            "conversation_id": "conv-1",
            "turn_number": 1,
            "is_follow_up": False,
            "references": [],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.cli.ask_question", fake_ask_question)

    result = runner.invoke(cli, ["ask", "what changed?", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["answer"] == "The core ideas changed."
    saved_context = json.loads((tmp_path / "context.json").read_text(encoding="utf-8"))
    assert saved_context["conversation_id"] == "conv-1"
