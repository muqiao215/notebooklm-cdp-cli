import json

from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli


def test_ask_supports_source_filters_and_save_as_note(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_ask_question(settings, notebook_id, question, conversation_id, source_ids):
        assert notebook_id == "nb-current"
        assert question == "what changed?"
        assert conversation_id is None
        assert source_ids == ["src-1", "src-2"]
        return {
            "answer": "The core ideas changed.",
            "conversation_id": "conv-1",
            "turn_number": 1,
            "is_follow_up": False,
            "references": [],
        }

    async def fake_create_note(settings, notebook_id, title, content):
        assert notebook_id == "nb-current"
        assert title == "Answer Note"
        assert content == "The core ideas changed."
        return {"id": "note-1", "title": title, "content": content, "notebook_id": notebook_id}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.ask_question", fake_ask_question, raising=False)
    monkeypatch.setattr("notebooklm_cdp_cli.cli.create_note", fake_create_note, raising=False)

    result = runner.invoke(
        cli,
        [
            "ask",
            "what changed?",
            "--source",
            "src-1",
            "--source",
            "src-2",
            "--save-as-note",
            "--note-title",
            "Answer Note",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["conversation_id"] == "conv-1"
    assert payload["saved_note"]["id"] == "note-1"


def test_ask_new_ignores_persisted_conversation(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    context_path = tmp_path / "context.json"
    context_path.write_text(
        json.dumps({"notebook_id": "nb-current", "conversation_id": "conv-old"}),
        encoding="utf-8",
    )

    async def fake_ask_question(settings, notebook_id, question, conversation_id):
        assert notebook_id == "nb-current"
        assert question == "start over"
        assert conversation_id is None
        return {
            "answer": "Fresh thread.",
            "conversation_id": "conv-new",
            "turn_number": 1,
            "is_follow_up": False,
            "references": [],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.cli.ask_question", fake_ask_question, raising=False)

    result = runner.invoke(cli, ["ask", "start over", "--new", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["conversation_id"] == "conv-new"
    assert json.loads(context_path.read_text(encoding="utf-8"))["conversation_id"] == "conv-new"


def test_history_save_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(
        json.dumps({"notebook_id": "nb-current", "conversation_id": "conv-current"}),
        encoding="utf-8",
    )

    async def fake_get_chat_history(settings, notebook_id, limit, conversation_id):
        assert notebook_id == "nb-current"
        assert limit == 100
        assert conversation_id == "conv-current"
        return {
            "notebook_id": notebook_id,
            "conversation_id": conversation_id,
            "count": 1,
            "qa_pairs": [{"turn": 1, "question": "What changed?", "answer": "Share support."}],
        }

    async def fake_create_note(settings, notebook_id, title, content):
        assert notebook_id == "nb-current"
        assert title == "History Note"
        assert "What changed?" in content
        assert "Share support." in content
        return {"id": "note-hist", "title": title, "content": content, "notebook_id": notebook_id}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.get_chat_history", fake_get_chat_history, raising=False)
    monkeypatch.setattr("notebooklm_cdp_cli.cli.create_note", fake_create_note, raising=False)

    result = runner.invoke(
        cli,
        ["history", "--save", "--note-title", "History Note", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["saved_note"]["id"] == "note-hist"


def test_history_show_all_text(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(
        json.dumps({"notebook_id": "nb-current", "conversation_id": "conv-current"}),
        encoding="utf-8",
    )

    async def fake_get_chat_history(settings, notebook_id, limit, conversation_id):
        return {
            "notebook_id": notebook_id,
            "conversation_id": conversation_id,
            "count": 1,
            "qa_pairs": [
                {
                    "turn": 1,
                    "question": "Full question text for inspection",
                    "answer": "Full answer text for inspection",
                }
            ],
        }

    monkeypatch.setattr("notebooklm_cdp_cli.cli.get_chat_history", fake_get_chat_history, raising=False)

    result = runner.invoke(cli, ["history", "--show-all"])

    assert result.exit_code == 0
    assert "Full question text for inspection" in result.output
    assert "Full answer text for inspection" in result.output


def test_generate_report_advanced_params(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_report(
        settings,
        notebook_id,
        report_format,
        custom_prompt,
        extra_instructions,
        language,
        source_ids,
        wait,
    ):
        assert notebook_id == "nb-current"
        assert report_format == "study_guide"
        assert custom_prompt is None
        assert extra_instructions == "Focus on tradeoffs"
        assert language == "zh-CN"
        assert source_ids == ["src-1", "src-2"]
        assert wait is False
        return {"task_id": "report-1", "status": "pending"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.generate_report", fake_generate_report, raising=False)

    result = runner.invoke(
        cli,
        [
            "generate",
            "report",
            "--format",
            "study_guide",
            "--instructions",
            "Focus on tradeoffs",
            "--language",
            "zh-CN",
            "--source",
            "src-1",
            "--source",
            "src-2",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["task_id"] == "report-1"


def test_generate_audio_advanced_params(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_audio(
        settings,
        notebook_id,
        instructions,
        language,
        source_ids,
        audio_format,
        audio_length,
        wait,
    ):
        assert notebook_id == "nb-current"
        assert instructions == "Debate the options"
        assert language == "fr"
        assert source_ids == ["src-a"]
        assert audio_format == "debate"
        assert audio_length == "long"
        assert wait is True
        return {"task_id": "audio-1", "status": "completed"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.generate_audio", fake_generate_audio, raising=False)

    result = runner.invoke(
        cli,
        [
            "generate",
            "audio",
            "--instructions",
            "Debate the options",
            "--language",
            "fr",
            "--source",
            "src-a",
            "--format",
            "debate",
            "--length",
            "long",
            "--wait",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["task_id"] == "audio-1"


def test_generate_slide_and_infographic_advanced_params(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_slide_deck(settings, notebook_id, instructions, slide_format, length, language, source_ids, wait):
        assert notebook_id == "nb-current"
        assert instructions == "Pitch the roadmap"
        assert slide_format == "presenter_slides"
        assert length == "short"
        assert language == "es"
        assert source_ids == ["src-1"]
        assert wait is False
        return {"task_id": "slides-1", "status": "pending"}

    async def fake_generate_infographic(settings, notebook_id, instructions, orientation, detail, style, language, source_ids, wait):
        assert notebook_id == "nb-current"
        assert instructions == "Use a comparison layout"
        assert orientation == "square"
        assert detail == "detailed"
        assert style == "scientific"
        assert language == "de"
        assert source_ids == ["src-2"]
        assert wait is True
        return {"task_id": "info-1", "status": "completed"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.generate_slide_deck", fake_generate_slide_deck, raising=False)
    monkeypatch.setattr("notebooklm_cdp_cli.cli.generate_infographic", fake_generate_infographic, raising=False)

    slide_result = runner.invoke(
        cli,
        [
            "generate",
            "slide-deck",
            "--instructions",
            "Pitch the roadmap",
            "--format",
            "presenter_slides",
            "--length",
            "short",
            "--language",
            "es",
            "--source",
            "src-1",
            "--json",
        ],
    )
    assert slide_result.exit_code == 0
    assert json.loads(slide_result.output)["task_id"] == "slides-1"

    info_result = runner.invoke(
        cli,
        [
            "generate",
            "infographic",
            "--instructions",
            "Use a comparison layout",
            "--orientation",
            "square",
            "--detail",
            "detailed",
            "--style",
            "scientific",
            "--language",
            "de",
            "--source",
            "src-2",
            "--wait",
            "--json",
        ],
    )
    assert info_result.exit_code == 0
    assert json.loads(info_result.output)["task_id"] == "info-1"


def test_generate_video_advanced_params(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_video(
        settings,
        notebook_id,
        instructions,
        video_format,
        style,
        language,
        source_ids,
        wait,
    ):
        assert notebook_id == "nb-current"
        assert instructions == "Explain the architecture"
        assert video_format == "brief"
        assert style == "whiteboard"
        assert language == "ja"
        assert source_ids == ["src-1", "src-2"]
        assert wait is True
        return {"task_id": "vid-2", "status": "completed"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.generate_video", fake_generate_video, raising=False)

    result = runner.invoke(
        cli,
        [
            "generate",
            "video",
            "--instructions",
            "Explain the architecture",
            "--format",
            "brief",
            "--style",
            "whiteboard",
            "--language",
            "ja",
            "--source",
            "src-1",
            "--source",
            "src-2",
            "--wait",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["task_id"] == "vid-2"


def test_generate_cinematic_video_advanced_params(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_cinematic_video(
        settings,
        notebook_id,
        instructions,
        language,
        source_ids,
        wait,
    ):
        assert notebook_id == "nb-current"
        assert instructions == "Documentary treatment"
        assert language == "it"
        assert source_ids == ["src-cine"]
        assert wait is False
        return {"task_id": "cine-2", "status": "pending"}

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.generate_cinematic_video",
        fake_generate_cinematic_video,
        raising=False,
    )

    result = runner.invoke(
        cli,
        [
            "generate",
            "cinematic-video",
            "--instructions",
            "Documentary treatment",
            "--language",
            "it",
            "--source",
            "src-cine",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["task_id"] == "cine-2"


def test_download_cinematic_video_alias(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_download_video(settings, notebook_id, output_path, artifact_id):
        assert notebook_id == "nb-current"
        assert output_path == "/tmp/out.mp4"
        assert artifact_id == "art-cine"
        return {"output_path": output_path}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.download_video", fake_download_video, raising=False)

    result = runner.invoke(
        cli,
        ["download", "cinematic-video", "/tmp/out.mp4", "--artifact-id", "art-cine", "--json"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output)["output_path"] == "/tmp/out.mp4"
