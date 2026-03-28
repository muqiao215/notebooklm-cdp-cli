import json

from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli


def test_notes_list_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_list_notes(settings, notebook_id):
        assert notebook_id == "nb-current"
        return [{"id": "note-1", "title": "Plan", "content": "Draft", "notebook_id": "nb-current"}]

    monkeypatch.setattr("notebooklm_cdp_cli.cli.list_notes", fake_list_notes, raising=False)

    result = runner.invoke(cli, ["notes", "list", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["notes"][0]["id"] == "note-1"


def test_notes_create_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_create_note(settings, notebook_id, title, content):
        assert notebook_id == "nb-current"
        assert title == "Plan"
        assert content == "Initial draft"
        return {"id": "note-2", "title": "Plan", "content": "Initial draft", "notebook_id": "nb-current"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.create_note", fake_create_note, raising=False)

    result = runner.invoke(cli, ["notes", "create", "Plan", "Initial draft", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "note-2"


def test_notes_get_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_get_note(settings, notebook_id, note_id):
        assert notebook_id == "nb-current"
        assert note_id == "note-1"
        return {"id": "note-1", "title": "Plan", "content": "Initial draft", "notebook_id": "nb-current"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.get_note", fake_get_note, raising=False)

    result = runner.invoke(cli, ["notes", "get", "note-1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["content"] == "Initial draft"


def test_notes_save_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_save_note(settings, notebook_id, note_id, content, title):
        assert notebook_id == "nb-current"
        assert note_id == "note-1"
        assert content == "Revised draft"
        assert title is None
        return {"id": "note-1", "title": "Plan", "content": "Revised draft", "notebook_id": "nb-current"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.save_note", fake_save_note, raising=False)

    result = runner.invoke(cli, ["notes", "save", "note-1", "Revised draft", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["content"] == "Revised draft"


def test_notes_rename_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_rename_note(settings, notebook_id, note_id, title):
        assert notebook_id == "nb-current"
        assert note_id == "note-1"
        assert title == "Updated Plan"
        return {"id": "note-1", "title": "Updated Plan", "content": "Draft", "notebook_id": "nb-current"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.rename_note", fake_rename_note, raising=False)

    result = runner.invoke(cli, ["notes", "rename", "note-1", "Updated Plan", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["title"] == "Updated Plan"


def test_notes_delete_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_delete_note(settings, notebook_id, note_id):
        assert notebook_id == "nb-current"
        assert note_id == "note-1"
        return {"deleted": True, "note_id": "note-1"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.delete_note", fake_delete_note, raising=False)

    result = runner.invoke(cli, ["notes", "delete", "note-1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["deleted"] is True
