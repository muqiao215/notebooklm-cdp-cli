import json

from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli


def test_share_status_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_get_share_status(settings, notebook_id):
        assert notebook_id == "nb-current"
        return {
            "notebook_id": notebook_id,
            "is_public": True,
            "access": "anyone_with_link",
            "view_level": "full_notebook",
            "share_url": "https://notebooklm.google.com/notebook/nb-current",
            "shared_users": [
                {
                    "email": "viewer@example.com",
                    "permission": "viewer",
                    "display_name": "Viewer User",
                    "avatar_url": None,
                }
            ],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.cli.get_share_status", fake_get_share_status, raising=False)

    result = runner.invoke(cli, ["share", "status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["is_public"] is True
    assert payload["shared_users"][0]["email"] == "viewer@example.com"


def test_share_public_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_set_share_public(settings, notebook_id, public):
        assert notebook_id == "nb-current"
        assert public is False
        return {
            "notebook_id": notebook_id,
            "is_public": False,
            "access": "restricted",
            "view_level": "full_notebook",
            "share_url": None,
            "shared_users": [],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.cli.set_share_public", fake_set_share_public, raising=False)

    result = runner.invoke(cli, ["share", "public", "--disable", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["is_public"] is False
    assert payload["share_url"] is None


def test_share_view_level_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_set_share_view_level(settings, notebook_id, level):
        assert notebook_id == "nb-current"
        assert level == "chat_only"
        return {
            "notebook_id": notebook_id,
            "is_public": False,
            "access": "restricted",
            "view_level": "chat_only",
            "share_url": None,
            "shared_users": [],
        }

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.set_share_view_level",
        fake_set_share_view_level,
        raising=False,
    )

    result = runner.invoke(cli, ["share", "view-level", "chat", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["view_level"] == "chat_only"


def test_share_add_update_remove_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_add(settings, notebook_id, email, permission, notify, message):
        assert notebook_id == "nb-current"
        assert email == "user@example.com"
        assert permission == "editor"
        assert notify is False
        assert message == "Please review"
        return {
            "notebook_id": notebook_id,
            "added_user": email,
            "permission": permission,
            "notified": notify,
        }

    async def fake_update(settings, notebook_id, email, permission):
        assert notebook_id == "nb-current"
        assert email == "user@example.com"
        assert permission == "viewer"
        return {
            "notebook_id": notebook_id,
            "updated_user": email,
            "permission": permission,
        }

    async def fake_remove(settings, notebook_id, email):
        assert notebook_id == "nb-current"
        assert email == "user@example.com"
        return {
            "notebook_id": notebook_id,
            "removed_user": email,
        }

    monkeypatch.setattr("notebooklm_cdp_cli.cli.add_share_user", fake_add, raising=False)
    monkeypatch.setattr("notebooklm_cdp_cli.cli.update_share_user", fake_update, raising=False)
    monkeypatch.setattr("notebooklm_cdp_cli.cli.remove_share_user", fake_remove, raising=False)

    add_result = runner.invoke(
        cli,
        [
            "share",
            "add",
            "user@example.com",
            "--permission",
            "editor",
            "--no-notify",
            "--message",
            "Please review",
            "--json",
        ],
    )
    assert add_result.exit_code == 0
    assert json.loads(add_result.output)["permission"] == "editor"

    update_result = runner.invoke(
        cli,
        ["share", "update", "user@example.com", "--permission", "viewer", "--json"],
    )
    assert update_result.exit_code == 0
    assert json.loads(update_result.output)["updated_user"] == "user@example.com"

    remove_result = runner.invoke(
        cli,
        ["share", "remove", "user@example.com", "--yes", "--json"],
    )
    assert remove_result.exit_code == 0
    assert json.loads(remove_result.output)["removed_user"] == "user@example.com"
