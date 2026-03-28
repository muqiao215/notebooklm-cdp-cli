import json

from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli


def test_language_list_json(monkeypatch):
    runner = CliRunner()

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.list_languages",
        lambda: [
            {"code": "en", "name": "English"},
            {"code": "zh_Hans", "name": "中文（简体）"},
        ],
        raising=False,
    )

    result = runner.invoke(cli, ["language", "list", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 2
    assert payload["languages"][1]["code"] == "zh_Hans"


def test_language_get_json(monkeypatch):
    runner = CliRunner()

    async def fake_get_output_language(settings):
        return {"language": "ja", "name": "日本語"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.get_output_language", fake_get_output_language, raising=False)

    result = runner.invoke(cli, ["language", "get", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["language"] == "ja"


def test_language_set_json(monkeypatch):
    runner = CliRunner()

    async def fake_set_output_language(settings, language):
        assert language == "zh_Hans"
        return {"language": "zh_Hans", "name": "中文（简体）"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.set_output_language", fake_set_output_language, raising=False)

    result = runner.invoke(cli, ["language", "set", "zh_Hans", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["language"] == "zh_Hans"
