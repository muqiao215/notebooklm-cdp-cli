import json

from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli


def test_source_get_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_get_source(settings, notebook_id, source_id):
        assert notebook_id == "nb-current"
        assert source_id == "src-1"
        return {"id": "src-1", "title": "AI Memo", "kind": "pasted_text", "status": 2}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.get_source", fake_get_source, raising=False)

    result = runner.invoke(cli, ["source", "get", "src-1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "src-1"


def test_source_wait_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_wait_for_source(settings, notebook_id, source_id, initial_interval, max_interval, timeout):
        assert notebook_id == "nb-current"
        assert source_id == "src-1"
        assert initial_interval == 1.0
        assert max_interval == 5.0
        assert timeout == 30.0
        return {"id": "src-1", "title": "AI Memo", "kind": "pasted_text", "status": 2}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.wait_for_source", fake_wait_for_source, raising=False)

    result = runner.invoke(
        cli,
        [
            "source",
            "wait",
            "src-1",
            "--initial-interval",
            "1",
            "--max-interval",
            "5",
            "--timeout",
            "30",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == 2


def test_source_add_text_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_add_source_text(settings, notebook_id, title, content, wait):
        assert notebook_id == "nb-current"
        assert title == "Working Notes"
        assert content == "Bullet one\nBullet two"
        assert wait is True
        return {"id": "src-2", "title": "Working Notes", "kind": "pasted_text", "status": 2}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.add_source_text", fake_add_source_text, raising=False)

    result = runner.invoke(
        cli,
        ["source", "add-text", "Working Notes", "Bullet one\nBullet two", "--wait", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["title"] == "Working Notes"


def test_source_add_drive_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_add_source_drive(settings, notebook_id, file_id, title, mime_type, wait):
        assert notebook_id == "nb-current"
        assert file_id == "drive-file-1"
        assert title == "Planning Deck"
        assert mime_type == "application/vnd.google-apps.presentation"
        assert wait is False
        return {"id": "src-3", "title": "Planning Deck", "kind": "google_other", "status": 1}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.add_source_drive", fake_add_source_drive, raising=False)

    result = runner.invoke(
        cli,
        [
            "source",
            "add-drive",
            "drive-file-1",
            "Planning Deck",
            "--mime-type",
            "application/vnd.google-apps.presentation",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "src-3"


def test_source_rename_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_rename_source(settings, notebook_id, source_id, title):
        assert notebook_id == "nb-current"
        assert source_id == "src-1"
        assert title == "Renamed Source"
        return {"id": "src-1", "title": "Renamed Source", "kind": "web_page", "status": 2}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.rename_source", fake_rename_source, raising=False)

    result = runner.invoke(cli, ["source", "rename", "src-1", "Renamed Source", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["title"] == "Renamed Source"


def test_source_delete_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_delete_source(settings, notebook_id, source_id):
        assert notebook_id == "nb-current"
        assert source_id == "src-1"
        return {"deleted": True, "source_id": "src-1"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.delete_source", fake_delete_source, raising=False)

    result = runner.invoke(cli, ["source", "delete", "src-1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["deleted"] is True


def test_source_refresh_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_refresh_source(settings, notebook_id, source_id):
        assert notebook_id == "nb-current"
        assert source_id == "src-1"
        return {"source_id": "src-1", "refreshed": True}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.refresh_source", fake_refresh_source, raising=False)

    result = runner.invoke(cli, ["source", "refresh", "src-1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["refreshed"] is True


def test_source_check_freshness_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_check_source_freshness(settings, notebook_id, source_id):
        assert notebook_id == "nb-current"
        assert source_id == "src-1"
        return {"source_id": "src-1", "is_fresh": False, "is_stale": True}

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.check_source_freshness",
        fake_check_source_freshness,
        raising=False,
    )

    result = runner.invoke(cli, ["source", "check-freshness", "src-1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["is_fresh"] is False
    assert payload["is_stale"] is True


def test_source_stale_alias_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_check_source_freshness(settings, notebook_id, source_id):
        assert notebook_id == "nb-current"
        assert source_id == "src-2"
        return {"source_id": "src-2", "is_fresh": True, "is_stale": False}

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.check_source_freshness",
        fake_check_source_freshness,
        raising=False,
    )

    result = runner.invoke(cli, ["source", "stale", "src-2", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["is_fresh"] is True
    assert payload["source_id"] == "src-2"


def test_source_guide_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_get_source_guide(settings, notebook_id, source_id):
        assert notebook_id == "nb-current"
        assert source_id == "src-1"
        return {
            "source_id": "src-1",
            "summary": "A concise guide.",
            "keywords": ["market", "adoption"],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.cli.get_source_guide", fake_get_source_guide, raising=False)

    result = runner.invoke(cli, ["source", "guide", "src-1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["keywords"] == ["market", "adoption"]


def test_source_fulltext_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_get_source_fulltext(settings, notebook_id, source_id):
        assert notebook_id == "nb-current"
        assert source_id == "src-1"
        return {
            "source_id": "src-1",
            "title": "Market Map",
            "kind": "web_page",
            "content": "Full indexed content",
            "char_count": 20,
            "url": "https://example.com/map",
        }

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.get_source_fulltext",
        fake_get_source_fulltext,
        raising=False,
    )

    result = runner.invoke(cli, ["source", "fulltext", "src-1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["kind"] == "web_page"
    assert payload["content"] == "Full indexed content"


def test_source_wait_for_sources_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_wait_for_sources(settings, notebook_id, source_ids, initial_interval, max_interval, timeout):
        assert notebook_id == "nb-current"
        assert source_ids == ["src-1", "src-2"]
        assert initial_interval == 1.0
        assert max_interval == 5.0
        assert timeout == 45.0
        return [
            {"id": "src-1", "title": "One", "kind": "web_page", "status": 2},
            {"id": "src-2", "title": "Two", "kind": "pdf", "status": 2},
        ]

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.wait_for_sources",
        fake_wait_for_sources,
        raising=False,
    )

    result = runner.invoke(
        cli,
        [
            "source",
            "wait-for-sources",
            "src-1",
            "src-2",
            "--initial-interval",
            "1",
            "--max-interval",
            "5",
            "--timeout",
            "45",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 2
    assert payload["sources"][1]["id"] == "src-2"
