import json
from pathlib import Path
from typing import List

import attrs
import click
from click import secho

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
    secho(config.base_path)


@main.command("fetch-issue-data", help="Download or update issue data files.")
@click.argument("base-path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.pass_context
def fetch_issue_data(ctx: click.Context, base_path: Path) -> None:
    from . import download

    config = ctx.obj["config"]
    for r in config.repos:
        repo_path = Path(base_path, r.user, r.name)
        if not repo_path.exists():
            secho(f"[ghstats:warn] Skipping {r} because there's no data saved.", fg="yellow")
            continue

        data_path = Path(repo_path, "issues.json")
        assert data_path.exists(), f"{data_path} should exist!"
        download.main(
            ["--id", config.username, "update", str(data_path)],
            standalone_mode=False,
        )


@main.command("generate-ghstats-data", help="Generate data files used by ghstats' front-end.")
@click.argument("base-path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.pass_context
def generate_ghstats_data(ctx: click.Context, base_path: Path) -> None:
    from . import generate_data

    config = ctx.obj["config"]
    for r in config.repos:
        data_path = Path(base_path, r.user, r.name, "issues.json")
        if not data_path.exists():
            secho(f"[ghstats:warn] Skipping {r} because there's no data saved.", fg="yellow")
            continue

        for cmd in ("issue-counts", "issue-closers", "issue-deltas", "pull-counts"):
            secho(f"[ghstats] Generating '{cmd}' for {r}", bold=True)
            out_path = data_path.with_name(cmd + ".json")
            generate_data.main(
                [cmd, str(data_path), "--output", str(out_path)],
                standalone_mode=False,
            )


if __name__ == "__main__":
    main()
