from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli


def test_doctor_json_output(monkeypatch):
    runner = CliRunner()

    async def fake_run_doctor(settings):
        return {
            "browser": {
                "connected": True,
                "browser": "Chrome/134.0.0.0",
                "web_socket_url": "ws://127.0.0.1:9222/devtools/browser/abc",
                "notebooklm_targets": 1,
                "google_targets": 2,
                "error": None,
            },
            "auth": {
                "ok": True,
                "browser_connected": True,
                "cookie_count": 2,
                "has_sid_cookie": True,
                "tokens": {
                    "csrf_token": "csrf123",
                    "session_id": "sess456",
                },
                "error": None,
            },
        }

    monkeypatch.setattr("notebooklm_cdp_cli.cli.run_doctor", fake_run_doctor)

    result = runner.invoke(cli, ["doctor", "--json"])

    assert result.exit_code == 0
    assert '"connected": true' in result.output
    assert '"csrf_token": "csrf123"' in result.output
