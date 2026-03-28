from notebooklm_cdp_cli.config import Settings, default_user_data_dir_candidates


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


def test_default_user_data_dir_candidates_excludes_environment_specific_hardcoded_path(monkeypatch):
    monkeypatch.delenv("NOTEBOOKLM_CDP_USER_DATA_DIR", raising=False)

    candidates = default_user_data_dir_candidates()

    assert "/root/.browser-login/google-chrome-user-data" not in candidates


def test_default_user_data_dir_candidates_prefers_explicit_env_path(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_CDP_USER_DATA_DIR", "/profiles/explicit")

    candidates = default_user_data_dir_candidates()

    assert candidates[0] == "/profiles/explicit"
    assert "/profiles/explicit" in candidates
