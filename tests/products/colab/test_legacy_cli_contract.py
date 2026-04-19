from click.testing import CliRunner

from notebooklm_cdp_cli.products.colab.legacy_cli import colab_cli


def test_colab_help_lists_primary_groups():
    result = CliRunner().invoke(colab_cli, ["--help"])

    assert result.exit_code == 0
    assert "notebook" in result.output
    assert "cell" in result.output
    assert "runtime" in result.output
    assert "file" in result.output
    assert "artifact" in result.output


def test_colab_notebook_help_lists_primary_commands():
    result = CliRunner().invoke(colab_cli, ["notebook", "--help"])

    assert result.exit_code == 0
    assert "info" in result.output
    assert "summary" in result.output
    assert "list" in result.output
    assert "select" in result.output
    assert "current" in result.output
    assert "open" in result.output
    assert "export" in result.output


def test_colab_subcommand_helps_are_safe_to_render():
    runner = CliRunner()

    assert runner.invoke(colab_cli, ["cell", "--help"]).exit_code == 0
    assert runner.invoke(colab_cli, ["runtime", "--help"]).exit_code == 0
    assert runner.invoke(colab_cli, ["file", "--help"]).exit_code == 0
    assert runner.invoke(colab_cli, ["artifact", "--help"]).exit_code == 0
