from __future__ import annotations

import click

from ...config import Settings
from .cli import colab_group


@click.group("colab")
@click.option("--host", default=None, help="CDP host")
@click.option("--port", default=None, type=int, help="CDP port")
@click.option("--timeout", default=None, type=float, help="CDP request timeout")
@click.pass_context
def colab_cli(ctx: click.Context, host: str | None, port: int | None, timeout: float | None) -> None:
    """Colab CLI backed by a live Chrome CDP session."""
    env_settings = Settings.from_env()
    ctx.ensure_object(dict)
    ctx.obj["host"] = host or env_settings.host
    ctx.obj["port"] = port or env_settings.port
    ctx.obj["timeout"] = timeout or env_settings.timeout


for command_name, command in colab_group.commands.items():
    colab_cli.add_command(command, command_name)


def main() -> None:
    colab_cli()


if __name__ == "__main__":
    main()
