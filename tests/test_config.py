from notebooklm_cdp_cli.config import Settings


def test_settings_default_values():
    settings = Settings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 9222
    assert settings.timeout == 5.0


def test_settings_respects_environment(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOST", "localhost")
    monkeypatch.setenv("NOTEBOOKLM_CDP_PORT", "3333")
    monkeypatch.setenv("NOTEBOOKLM_CDP_TIMEOUT", "9.5")

    settings = Settings.from_env()

    assert settings.host == "localhost"
    assert settings.port == 3333
    assert settings.timeout == 9.5

