import json

from click.testing import CliRunner

from notebooklm_cdp_cli.cli import cli


def test_artifact_list_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_list_artifacts(settings, notebook_id, kind):
        assert notebook_id == "nb-current"
        assert kind is None
        return [{"id": "art1", "title": "Briefing Doc", "kind": "report", "status": 3}]

    monkeypatch.setattr("notebooklm_cdp_cli.cli.list_artifacts", fake_list_artifacts)

    result = runner.invoke(cli, ["artifact", "list", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["artifacts"][0]["id"] == "art1"


def test_generate_report_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_report(settings, notebook_id, report_format, custom_prompt, wait):
        assert notebook_id == "nb-current"
        assert report_format == "briefing_doc"
        assert custom_prompt is None
        assert wait is False
        return {"task_id": "task-1", "status": "pending"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.generate_report", fake_generate_report)

    result = runner.invoke(cli, ["generate", "report", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["task_id"] == "task-1"


def test_artifact_get_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_get_artifact(settings, notebook_id, artifact_id):
        assert notebook_id == "nb-current"
        assert artifact_id == "art-1"
        return {"id": "art-1", "title": "Deck", "kind": "slide_deck", "status": 2}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.get_artifact", fake_get_artifact, raising=False)

    result = runner.invoke(cli, ["artifact", "get", "art-1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "art-1"
    assert payload["kind"] == "slide_deck"


def test_artifact_rename_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_rename_artifact(settings, notebook_id, artifact_id, title):
        assert notebook_id == "nb-current"
        assert artifact_id == "art-1"
        assert title == "Renamed Deck"
        return {"id": "art-1", "title": "Renamed Deck", "kind": "slide_deck", "status": 2}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.rename_artifact", fake_rename_artifact, raising=False)

    result = runner.invoke(cli, ["artifact", "rename", "art-1", "Renamed Deck", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["title"] == "Renamed Deck"


def test_artifact_delete_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_delete_artifact(settings, notebook_id, artifact_id):
        assert notebook_id == "nb-current"
        assert artifact_id == "art-1"
        return {"deleted": True, "artifact_id": "art-1"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.delete_artifact", fake_delete_artifact, raising=False)

    result = runner.invoke(cli, ["artifact", "delete", "art-1", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["deleted"] is True
    assert payload["artifact_id"] == "art-1"


def test_artifact_export_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_export_artifact(settings, notebook_id, artifact_id, export_type, title):
        assert notebook_id == "nb-current"
        assert artifact_id == "art-1"
        assert export_type == "sheets"
        assert title == "Competitive Matrix"
        return {"artifact_id": "art-1", "export_type": "sheets", "url": "https://docs.google.com/sheets/d/1"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.export_artifact", fake_export_artifact, raising=False)

    result = runner.invoke(
        cli,
        [
            "artifact",
            "export",
            "art-1",
            "--type",
            "sheets",
            "--title",
            "Competitive Matrix",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["export_type"] == "sheets"
    assert payload["artifact_id"] == "art-1"


def test_artifact_poll_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_poll_artifact(settings, notebook_id, task_id):
        assert notebook_id == "nb-current"
        assert task_id == "task-42"
        return {"task_id": "task-42", "status": "in_progress", "url": None}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.poll_artifact", fake_poll_artifact, raising=False)

    result = runner.invoke(cli, ["artifact", "poll", "task-42", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["task_id"] == "task-42"
    assert payload["status"] == "in_progress"


def test_artifact_wait_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_wait_for_artifact(settings, notebook_id, task_id, initial_interval, max_interval, timeout):
        assert notebook_id == "nb-current"
        assert task_id == "task-99"
        assert initial_interval == 1.5
        assert max_interval == 4.0
        assert timeout == 60.0
        return {"task_id": "task-99", "status": "completed", "url": "https://example.com/artifact"}

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.wait_for_artifact",
        fake_wait_for_artifact,
        raising=False,
    )

    result = runner.invoke(
        cli,
        [
            "artifact",
            "wait",
            "task-99",
            "--initial-interval",
            "1.5",
            "--max-interval",
            "4",
            "--timeout",
            "60",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "completed"
    assert payload["url"] == "https://example.com/artifact"


def test_artifact_suggest_reports_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_suggest_report_formats(settings, notebook_id):
        assert notebook_id == "nb-current"
        return [
            {
                "title": "Executive Brief",
                "description": "Summarize the main decisions.",
                "prompt": "Focus on strategic decisions.",
                "audience_level": 1,
            }
        ]

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.suggest_report_formats",
        fake_suggest_report_formats,
        raising=False,
    )

    result = runner.invoke(cli, ["artifact", "suggest-reports", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["suggestions"][0]["title"] == "Executive Brief"


def test_generate_video_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_video(settings, notebook_id, instructions, video_format, style, wait):
        assert notebook_id == "nb-current"
        assert instructions == "narrate the tradeoffs"
        assert video_format == "brief"
        assert style == "whiteboard"
        assert wait is True
        return {"task_id": "vid-1", "status": "completed", "url": "https://example.com/video.mp4"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.generate_video", fake_generate_video, raising=False)

    result = runner.invoke(
        cli,
        [
            "generate",
            "video",
            "--instructions",
            "narrate the tradeoffs",
            "--format",
            "brief",
            "--style",
            "whiteboard",
            "--wait",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["task_id"] == "vid-1"
    assert payload["status"] == "completed"


def test_generate_cinematic_video_alias_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_cinematic_video(settings, notebook_id, instructions, wait):
        assert notebook_id == "nb-current"
        assert instructions == "documentary overview"
        assert wait is True
        return {"task_id": "cin-1", "status": "completed", "kind": "video"}

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
            "documentary overview",
            "--wait",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["task_id"] == "cin-1"


def test_generate_revise_slide_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_revise_slide(settings, notebook_id, artifact_id, slide_index, prompt, wait):
        assert notebook_id == "nb-current"
        assert artifact_id == "art-slide"
        assert slide_index == 2
        assert prompt == "Tighten the headline"
        assert wait is True
        return {"task_id": "rev-1", "status": "completed"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.revise_slide", fake_revise_slide, raising=False)

    result = runner.invoke(
        cli,
        [
            "generate",
            "revise-slide",
            "art-slide",
            "2",
            "Tighten the headline",
            "--wait",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["task_id"] == "rev-1"


def test_generate_slide_deck_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_slide_deck(settings, notebook_id, instructions, slide_format, length, wait):
        assert notebook_id == "nb-current"
        assert instructions == "condense for exec review"
        assert slide_format == "presenter_slides"
        assert length == "short"
        assert wait is True
        return {"task_id": "slides-1", "status": "completed"}

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.generate_slide_deck",
        fake_generate_slide_deck,
        raising=False,
    )

    result = runner.invoke(
        cli,
        [
            "generate",
            "slide-deck",
            "--instructions",
            "condense for exec review",
            "--format",
            "presenter_slides",
            "--length",
            "short",
            "--wait",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["task_id"] == "slides-1"


def test_generate_infographic_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_infographic(
        settings,
        notebook_id,
        instructions,
        orientation,
        detail,
        style,
        wait,
    ):
        assert notebook_id == "nb-current"
        assert instructions == "highlight the adoption trend"
        assert orientation == "portrait"
        assert detail == "detailed"
        assert style == "professional"
        assert wait is True
        return {"task_id": "info-1", "status": "completed"}

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.generate_infographic",
        fake_generate_infographic,
        raising=False,
    )

    result = runner.invoke(
        cli,
        [
            "generate",
            "infographic",
            "--instructions",
            "highlight the adoption trend",
            "--orientation",
            "portrait",
            "--detail",
            "detailed",
            "--style",
            "professional",
            "--wait",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["task_id"] == "info-1"


def test_generate_quiz_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_quiz(settings, notebook_id, instructions, quantity, difficulty, wait):
        assert notebook_id == "nb-current"
        assert instructions == "test terminology"
        assert quantity == "fewer"
        assert difficulty == "hard"
        assert wait is True
        return {"task_id": "quiz-1", "status": "completed"}

    monkeypatch.setattr("notebooklm_cdp_cli.cli.generate_quiz", fake_generate_quiz, raising=False)

    result = runner.invoke(
        cli,
        [
            "generate",
            "quiz",
            "--instructions",
            "test terminology",
            "--quantity",
            "fewer",
            "--difficulty",
            "hard",
            "--wait",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["task_id"] == "quiz-1"


def test_generate_flashcards_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_flashcards(settings, notebook_id, instructions, quantity, difficulty, wait):
        assert notebook_id == "nb-current"
        assert instructions == "focus on recall"
        assert quantity == "fewer"
        assert difficulty == "medium"
        assert wait is True
        return {"task_id": "flash-1", "status": "completed"}

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.generate_flashcards",
        fake_generate_flashcards,
        raising=False,
    )

    result = runner.invoke(
        cli,
        [
            "generate",
            "flashcards",
            "--instructions",
            "focus on recall",
            "--quantity",
            "fewer",
            "--difficulty",
            "medium",
            "--wait",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["task_id"] == "flash-1"


def test_generate_data_table_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_data_table(settings, notebook_id, instructions, wait):
        assert notebook_id == "nb-current"
        assert instructions == "compare the vendors"
        assert wait is True
        return {"task_id": "table-1", "status": "completed"}

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.generate_data_table",
        fake_generate_data_table,
        raising=False,
    )

    result = runner.invoke(
        cli,
        [
            "generate",
            "data-table",
            "--instructions",
            "compare the vendors",
            "--wait",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["task_id"] == "table-1"


def test_generate_mind_map_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    async def fake_generate_mind_map(settings, notebook_id):
        assert notebook_id == "nb-current"
        return {
            "kind": "mind_map",
            "note_id": "note-1",
            "mind_map": {"name": "Root", "children": []},
        }

    monkeypatch.setattr(
        "notebooklm_cdp_cli.cli.generate_mind_map",
        fake_generate_mind_map,
        raising=False,
    )

    result = runner.invoke(cli, ["generate", "mind-map", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["note_id"] == "note-1"
    assert payload["kind"] == "mind_map"


def test_download_extended_artifacts_json(monkeypatch, tmp_path):
    runner = CliRunner()
    monkeypatch.setenv("NOTEBOOKLM_CDP_HOME", str(tmp_path))
    (tmp_path / "context.json").write_text(json.dumps({"notebook_id": "nb-current"}), encoding="utf-8")

    commands = {
        "video": (
            ["download", "video", "video.mp4", "--json"],
            "download_video",
            ("nb-current", "video.mp4", None),
        ),
        "slide-deck": (
            ["download", "slide-deck", "deck.pptx", "--format", "pptx", "--json"],
            "download_slide_deck",
            ("nb-current", "deck.pptx", None, "pptx"),
        ),
        "infographic": (
            ["download", "infographic", "info.png", "--json"],
            "download_infographic",
            ("nb-current", "info.png", None),
        ),
        "quiz": (
            ["download", "quiz", "quiz.md", "--format", "markdown", "--json"],
            "download_quiz",
            ("nb-current", "quiz.md", None, "markdown"),
        ),
        "flashcards": (
            ["download", "flashcards", "cards.md", "--format", "markdown", "--json"],
            "download_flashcards",
            ("nb-current", "cards.md", None, "markdown"),
        ),
        "data-table": (
            ["download", "data-table", "table.csv", "--json"],
            "download_data_table",
            ("nb-current", "table.csv", None),
        ),
        "mind-map": (
            ["download", "mind-map", "mind-map.json", "--json"],
            "download_mind_map",
            ("nb-current", "mind-map.json", None),
        ),
    }

    for command_name, (argv, attr_name, expected_args) in commands.items():
        async def fake_download(settings, *args, expected_args=expected_args):
            assert args == expected_args
            return {"output_path": args[1]}

        monkeypatch.setattr(
            f"notebooklm_cdp_cli.cli.{attr_name}",
            fake_download,
            raising=False,
        )

        result = runner.invoke(cli, argv)

        assert result.exit_code == 0, command_name
        payload = json.loads(result.output)
        assert payload["output_path"] == expected_args[1]
