import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import attrs
import click
from click import confirm, prompt

from . import ghlib
from .ghlib import Repo

THIS_DIR = Path(__file__).parent
ROOT_DIR = THIS_DIR.parent
WEB_DIR = (ROOT_DIR / "web")
DEFAULT_CONFIG_PATH = (ROOT_DIR / "config.json")
VIEWS = {
    "issue-counts": "open issues over time",
    "pull-counts": "open pull requests over time",
    "issue-deltas": "monthly delta of open issues over time",
    "issue-closers": "number of issues closed by collaborators over time",
}

JSON = Dict[str, Any]


def log(msg: str, level: str = "info") -> None:
    bold = level in ("warning", "error")
    color = {"info": "magenta", "warning": "yellow", "error": "red"}[level]
    if bold:
        formatted = click.style(f"[ghstats] {msg}", bold=True, fg=color)
    else:
        formatted = click.style("[ghstats] ", bold=True, fg=color) + click.style(msg, fg=color)
    click.secho(formatted)


@attrs.frozen
class AuthorInfo:
    name: Optional[str] = None
    link: Optional[str] = None


@attrs.define
class Config:
    title: str
    username: str
    base_path: str
    repos: Dict[Repo, JSON]

    author: AuthorInfo = attrs.field(factory=AuthorInfo)

    @classmethod
    def load_path(cls, path: Path) -> "Config":
        data = json.loads(path.read_text())
        data["repos"] = {Repo.parse(r): repo_config for r, repo_config in data["repos"].items()}
        if "author" in data:
            data["author"] = AuthorInfo(**data["author"])
        return cls(**data)

    def save_path(self, path: Path) -> None:

        def serialize(instance: Any, field: attrs.Attribute, value: Any) -> Any:
            if isinstance(instance, self.__class__) and field.name == "repos":
                return {str(r): config for r, config in value.items()}
            return value

        blob = json.dumps(attrs.asdict(self, value_serializer=serialize), indent=2)
        path.write_text(blob + "\n", encoding="utf-8")


@click.group
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_CONFIG_PATH,
    help="Path to GHstats configuration file.",
)
@click.pass_context
def main(ctx: click.Context, config_path: Path) -> None:
    ctx.obj = {}
    ctx.obj["config-path"] = config_path
    ctx.obj["config"] = Config.load_path(config_path)


@main.command("setup", help="Set up a new instance of GHstats.")
@click.pass_context
def setup_instance(ctx: click.Context) -> None:
    if WEB_DIR.exists():
        shutil.rmtree(WEB_DIR)
        log("Deleted web directory.")

    title = prompt("Instance title")
    base = "/" + prompt("Instance repository name (used to set up relative URLs)") + "/"
    username = prompt("GitHub username (used in user-agent + footer)")

    ctx.obj["config"] = Config(title=title, username=username, base_path=base, repos={})
    ctx.obj["config"].save_path(ctx.obj["config-path"])
    log("Configuration saved!")
    if confirm("Would you like to add a repository to your instance?", default=True):
        ctx.invoke(add_repository, repo_str=None)


@main.command("add-repository", help="Add a repository to instance configuration.")
@click.argument("repo_str", metavar="$owner/$name", required=False)
@click.pass_context
def add_repository(ctx: click.Context, repo_str: Optional[str]) -> None:
    config, config_path = ctx.obj["config"], ctx.obj["config-path"]
    if not repo_str:
        repo_str = prompt("Repository ($owner/$name)")

    repo = Repo.parse(repo_str)
    repo_config = {"views": []}
    for view, view_description in VIEWS.items():
        if confirm(f"Add '{view}' ({view_description}) view?", default=True):
            repo_config["views"].append(view)

    config.repos[repo] = repo_config
    config.save_path(config_path)
    ctx.obj["config"] = config
    log(f"Added '{repo}' to configuration.")
    ctx.invoke(generate_html)


@main.command("generate-html", help="Generate web directory.")
@click.pass_context
def generate_html(ctx: click.Context) -> None:
    # https://realpython.com/primer-on-jinja-templating/
    config = ctx.obj["config"]
    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        log("jinja2 not installed, please install it.", "error")
        ctx.exit(1)

    environment = Environment(
        loader=FileSystemLoader(ROOT_DIR / "templates"), trim_blocks=True, lstrip_blocks=True
    )
    environment.globals = {
        "title": config.title,
        "author": {
            "name": config.author.name or f"@{config.username}",
            "link": config.author.link or f"https://github.com/{config.username}",
        }
    }

    index_template = environment.get_template("index.html")
    index_html = index_template.render(repositories=config.repos)
    WEB_DIR.mkdir(exist_ok=True)
    (WEB_DIR / "index.html").write_text(index_html, "utf-8")
    log("Wrote index page.")

    repo_template = environment.get_template("repository.html")
    for repo, repo_config in config.repos.items():
        repo_dir = WEB_DIR / repo.name
        repo_html = repo_template.render(repo=repo, views=repo_config["views"])
        repo_dir.mkdir(exist_ok=True)
        (repo_dir / "index.html").write_text(repo_html, "utf-8")
        log(f"Wrote HTML for '{repo.fullname}'.")

    vite_template = environment.get_template("vite.config.js")
    vite_config = vite_template.render(repositories=config.repos)
    (WEB_DIR / "vite.config.js").write_text(vite_config, "utf-8")
    log("Wrote Vite build configuration.")
    shutil.copytree(ROOT_DIR / "assets", WEB_DIR / "_assets", dirs_exist_ok=True)
    log("Copied static assets. Web directory is ready!")


@main.command("base-path", help="(INTERNAL) Print base path.")
@click.pass_context
def print_base_path(ctx: click.Context) -> None:
    config = ctx.obj["config"]
    click.echo(config.base_path)


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


@main.command("generate-ghstats-data", help="Generate data files used by GHstats' front-end.")
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
