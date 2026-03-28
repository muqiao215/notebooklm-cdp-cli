import json

from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli


def test_auth_check_json(monkeypatch):
    runner = CliRunner()

    async def fake_check_auth(settings):
        return {
            "ok": True,
            "browser_connected": True,
            "has_saved_browser": True,
            "cookie_count": 12,
            "has_sid_cookie": True,
            "tokens_present": True,
            "error": None,
        }

    monkeypatch.setattr("notebooklm_cdp_cli.cli.check_auth", fake_check_auth, raising=False)

    result = runner.invoke(cli, ["auth", "check", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["tokens_present"] is True


def test_paths_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path / "home"))

    result = runner.invoke(cli, ["paths", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["home_dir"] == str(tmp_path / "home")
    assert payload["config_path"].endswith("config.json")
    assert payload["context_path"].endswith("context.json")


def test_login_json_bootstrap(monkeypatch):
    runner = CliRunner()

    async def fake_bootstrap_login(settings, user_data_dir, validate):
        assert user_data_dir == "/profiles/chrome-a"
        assert validate is True
        return {
            "mode": "attach-first",
            "attached": True,
            "validated": True,
            "browser": {"host": "127.0.0.1", "port": 9333},
            "next_steps": ["run auth check", "run notebook list"],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.cli.bootstrap_login", fake_bootstrap_login, raising=False)

    result = runner.invoke(
        cli,
        ["login", "--user-data-dir", "/profiles/chrome-a", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["mode"] == "attach-first"
    assert payload["validated"] is True


def test_history_clear_cache_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    context_path = tmp_path / "context.json"
    context_path.write_text(
        json.dumps({"notebook_id": "nb-current", "conversation_id": "conv-current"}),
        encoding="utf-8",
    )

    result = runner.invoke(cli, ["history", "--clear-cache", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["cleared"] is True
    assert payload["conversation_id"] is None
    assert json.loads(context_path.read_text(encoding="utf-8")) == {"notebook_id": "nb-current"}
