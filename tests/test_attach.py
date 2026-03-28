import json
from pathlib import Path

from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli


def test_browser_attach_reads_devtools_port_and_persists_config(monkeypatch, tmp_path):
    home = tmp_path / "home"
    profile = tmp_path / "chrome-profile"
    profile.mkdir()
    (profile / "DevToolsActivePort").write_text("34933\n/devtools/browser/abc\n", encoding="utf-8")
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(cli, ["browser", "attach", "--user-data-dir", str(profile), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["port"] == 34933
    assert payload["user_data_dir"] == str(profile)

    saved = json.loads((home / "config.json").read_text(encoding="utf-8"))
    assert saved["browser"]["port"] == 34933
    assert saved["browser"]["user_data_dir"] == str(profile)

