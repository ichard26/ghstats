import json
from pathlib import Path
from typing import List

import attrs
import click

from . import ghlib

THIS_DIR = Path(__file__).parent
DEFAULT_CONFIG_PATH = Path(THIS_DIR, "../config.json")


@attrs.define
class Config:
    repos: List[ghlib.Repo]
    username: str
    base_path: str

    @classmethod
    def load_path(cls, path: Path) -> "Config":
        data = json.loads(path.read_text())
        data["repos"] = list(ghlib.Repo.parse(r) for r in data["repos"])
        return cls(**data)


@click.group
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_CONFIG_PATH,
    help="Path to ghstats configuration file.",
)
@click.pass_context
def main(ctx: click.Context, config_path: Path) -> None:
    ctx.obj = {}
    ctx.obj["config"] = Config.load_path(config_path)


@main.command("base-path", help="Print base path.")
@click.pass_context
def print_base_path(ctx: click.Context) -> None:
    config = ctx.obj["config"]
    click.echo(config.base_path)


if __name__ == "__main__":
    main()
