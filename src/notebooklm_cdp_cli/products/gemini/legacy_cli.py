from __future__ import annotations

import click

from ...config import Settings
from ..flow.cli import flow_group
from .cli import gemini_ask, gemini_chat_group, gemini_deep_research, gemini_generate_group


@click.group("gemini-web")
@click.option("--host", default=None, help="CDP host")
@click.option("--port", default=None, type=int, help="CDP port")
@click.option("--timeout", default=None, type=float, help="CDP request timeout")
@click.pass_context
def gemini_web_cli(ctx: click.Context, host: str | None, port: int | None, timeout: float | None) -> None:
    """Compatibility CLI for the original gemini-web command surface."""
    env_settings = Settings.from_env()
    ctx.ensure_object(dict)
    ctx.obj["host"] = host or env_settings.host
    ctx.obj["port"] = port or env_settings.port
    ctx.obj["timeout"] = timeout or env_settings.timeout


gemini_web_cli.add_command(gemini_generate_group)
gemini_web_cli.add_command(gemini_ask)
gemini_web_cli.add_command(gemini_deep_research)
gemini_web_cli.add_command(gemini_chat_group)
gemini_web_cli.add_command(flow_group)


def main() -> None:
    gemini_web_cli()


if __name__ == "__main__":
    main()
