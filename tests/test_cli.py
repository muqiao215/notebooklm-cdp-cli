from click.testing import CliRunner
from pathlib import Path
import tomllib

from notebooklm_cdp_cli import __version__
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


def test_chat_group_help_lists_chat_commands():
    runner = CliRunner()

    result = runner.invoke(cli, ["chat", "--help"])

    assert result.exit_code == 0
    assert "ask" in result.output
    assert "history" in result.output
    assert "configure" in result.output


def test_package_version_matches_pyproject():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert __version__ == project["project"]["version"]


def test_generate_report_help_lists_valid_formats_and_summary_warning():
    runner = CliRunner()

    result = runner.invoke(cli, ["generate", "report", "--help"])
    normalized = " ".join(result.output.split())

    assert result.exit_code == 0
    assert "briefing_doc" in normalized
    assert "study_guide" in normalized
    assert "blog_post" in normalized
    assert "custom" in normalized
    assert "summary is not a valid report format" in normalized


def test_readme_makes_report_formats_explicit():
    readme = Path(__file__).resolve().parents[1] / "README.md"
    text = readme.read_text(encoding="utf-8")
    normalized = text.replace("`", "")

    assert "briefing_doc" in normalized
    assert "study_guide" in normalized
    assert "blog_post" in normalized
    assert "custom" in normalized
    assert "summary is not a valid report format" in normalized


def test_readme_documents_linux_xvfb_chrome_cdp_flow():
    readme = Path(__file__).resolve().parents[1] / "README.md"
    text = readme.read_text(encoding="utf-8")

    assert "DISPLAY=:99" in text
    assert "--remote-debugging-port=9222" in text
    assert "--user-data-dir=$HOME/.browser-login/google-chrome-user-data" in text
    assert "--no-sandbox" in text
    assert "Xvfb" in text


def test_linux_launcher_script_exists_with_expected_flags():
    script = Path(__file__).resolve().parents[1] / "scripts" / "start-chrome-cdp-linux.sh"

    assert script.exists()

    text = script.read_text(encoding="utf-8")
    assert "DISPLAY=:99" in text
    assert "--remote-debugging-port=9222" in text
    assert "--user-data-dir=" in text
    assert "--no-sandbox" in text
    assert "Xvfb" in text
