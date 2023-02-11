import json
from pathlib import Path
from typing import Any, Dict

import attrs
import click

from . import ghlib
from .ghlib import Repo

THIS_DIR = Path(__file__).parent
DEFAULT_CONFIG_PATH = Path(THIS_DIR, "../config.json")

JSON = Dict[str, Any]


def log(msg: str, level: str = "info") -> None:
    bold = level in ("warning", "error")
    color = {"info": "magenta", "warning": "yellow", "error": "red"}[level]
    if bold:
        formatted = click.style(f"[ghstats] {msg}", bold=True, fg=color)
    else:
        formatted = click.style("[ghstats] ", bold=True, fg=color) + click.style(msg, fg=color)
    click.secho(formatted)


@attrs.define
class Config:
    repos: Dict[Repo, JSON]
    username: str
    base_path: str

    @classmethod
    def load_path(cls, path: Path) -> "Config":
        data = json.loads(path.read_text())
        data["repos"] = {Repo.parse(r): repo_config for r, repo_config in data["repos"].items()}
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
    click.secho(config.base_path)


@main.command("fetch-issue-data", help="Download or update issue data files.")
@click.argument("base-path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.pass_context
def fetch_issue_data(ctx: click.Context, base_path: Path) -> None:
    from . import download

    config = ctx.obj["config"]
    for r in config.repos:
        repo_path = Path(base_path, r.owner, r.name)
        data_path = Path(repo_path, "issues.json")
        if not data_path.exists():
            log(f"No data exists for {r}, fetching all issues/pulls instead.")
            repo_path.mkdir(parents=True, exist_ok=True)
            download.main(
                ["--id", config.username, "fetch", f"--repo={r!s}", str(data_path)],
                standalone_mode=False
            )
        else:
            log(f"Updating {r}.")
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
    for r, repo_config in config.repos.items():
        data_path = Path(base_path, r.owner, r.name, "issues.json")
        if not data_path.exists():
            log(f"Skipping {r} because there's no data saved.", "warning")
            continue

        for cmd in repo_config["views"]:
            log(f"Generating '{cmd}' for {r}")
            out_path = data_path.with_name(cmd + ".json")
            args = [cmd, str(data_path), "--output", str(out_path)]

            if cmd == "issue-counts" and "view:issue-counts:groups" in repo_config:
                for group, gh_label in repo_config["view:issue-counts:groups"].items():
                    args.extend(("--show-label", group, gh_label))

            generate_data.main(args, standalone_mode=False)


if __name__ == "__main__":
    main()
