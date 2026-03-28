import json

from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli


def test_research_status_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_get_research_status(settings, notebook_id):
        assert notebook_id == "nb-current"
        return {
            "task_id": "task-1",
            "status": "in_progress",
            "query": "AI agents",
            "sources": [],
            "summary": "",
            "report": "",
            "tasks": [],
        }

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.get_research_status",
        fake_get_research_status,
        raising=False,
    )

    result = runner.invoke(cli, ["research", "status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "in_progress"
    assert payload["task_id"] == "task-1"


def test_research_wait_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_wait_for_research(settings, notebook_id, timeout, interval, import_all):
        assert notebook_id == "nb-current"
        assert timeout == 120
        assert interval == 3
        assert import_all is True
        return {
            "task_id": "task-2",
            "status": "completed",
            "query": "AI agents",
            "sources": [{"title": "One", "url": "https://example.com/one"}],
            "summary": "Done",
            "report": "# Report",
            "imported": 1,
            "imported_sources": [{"id": "src-1", "title": "One"}],
        }

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.wait_for_research",
        fake_wait_for_research,
        raising=False,
    )

    result = runner.invoke(
        cli,
        ["research", "wait", "--timeout", "120", "--interval", "3", "--import-all", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "completed"
    assert payload["imported"] == 1


def test_source_add_research_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_add_research_source(settings, notebook_id, query, search_source, mode, wait, import_all):
        assert notebook_id == "nb-current"
        assert query == "AI agents"
        assert search_source == "drive"
        assert mode == "fast"
        assert wait is False
        assert import_all is False
        return {
            "task_id": "task-3",
            "status": "started",
            "query": query,
            "mode": mode,
            "source": search_source,
        }

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.add_research_source",
        fake_add_research_source,
        raising=False,
    )

    result = runner.invoke(
        cli,
        ["source", "add-research", "AI agents", "--source", "drive", "--mode", "fast", "--no-wait", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "started"
    assert payload["source"] == "drive"


def test_history_json_uses_context_conversation(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(
        json.dumps({"notebook_id": "nb-current", "conversation_id": "conv-current"}),
        encoding="utf-8",
    )

    async def fake_get_chat_history(settings, notebook_id, limit, conversation_id):
        assert notebook_id == "nb-current"
        assert limit == 5
        assert conversation_id == "conv-current"
        return {
            "notebook_id": notebook_id,
            "conversation_id": conversation_id,
            "count": 1,
            "qa_pairs": [{"turn": 1, "question": "What changed?", "answer": "Share support."}],
        }

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.get_chat_history",
        fake_get_chat_history,
        raising=False,
    )

    result = runner.invoke(cli, ["history", "--limit", "5", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["conversation_id"] == "conv-current"
    assert payload["qa_pairs"][0]["answer"] == "Share support."


def test_configure_json_mode_and_persona(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_configure_chat(settings, notebook_id, mode, persona, response_length):
        assert notebook_id == "nb-current"
        assert mode == "learning-guide"
        assert persona == "Act as a tutor"
        assert response_length == "longer"
        return {
            "notebook_id": notebook_id,
            "mode": mode,
            "persona": persona,
            "response_length": response_length,
        }

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.configure_chat",
        fake_configure_chat,
        raising=False,
    )

    result = runner.invoke(
        cli,
        [
            "configure",
            "--mode",
            "learning-guide",
            "--persona",
            "Act as a tutor",
            "--response-length",
            "longer",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["mode"] == "learning-guide"
    assert payload["response_length"] == "longer"


def test_status_and_clear_aliases_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    context_path = tmp_path / "context.json"
    context_path.write_text(
        json.dumps({"notebook_id": "nb-current", "conversation_id": "conv-current"}),
        encoding="utf-8",
    )

    status_result = runner.invoke(cli, ["status", "--json"])

    assert status_result.exit_code == 0
    status_payload = json.loads(status_result.output)
    assert status_payload["has_context"] is True
    assert status_payload["notebook"]["id"] == "nb-current"
    assert status_payload["conversation_id"] == "conv-current"

    clear_result = runner.invoke(cli, ["clear", "--json"])

    assert clear_result.exit_code == 0
    clear_payload = json.loads(clear_result.output)
    assert clear_payload["cleared"] is True
    assert json.loads(context_path.read_text(encoding="utf-8")) == {}
