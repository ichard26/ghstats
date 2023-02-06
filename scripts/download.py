import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

import attrs
import click
import colorama
import requests
from colorama import Fore, Style

from . import ghlib
from .ghlib import Issue, IssueSet, Record, Repo

DEFAULT_TIMEOUT = (3.1, 11.9)
GITHUB_API = "https://api.github.com"

colorama.init(autoreset=True)


class HTTPAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, timeout: Tuple[float, float], *args: Any, **kwargs: Any):
        self.timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, *args: Any, **kwargs: Any):
        if "timeout" not in kwargs.keys():
            kwargs["timeout"] = self.timeout
        return super().send(*args, **kwargs)


@attrs.define(slots=False)
class Fetcher:
    url: str = attrs.field()
    auth: Tuple[str, str] = attrs.field()
    timeout: Tuple[float, float] = DEFAULT_TIMEOUT
    debug: bool = False

    @url.validator
    def check(self, attribute: attrs.Attribute, value: str):
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError(f"url should start with 'http://' or 'https://': {self.url}")

    def __enter__(self) -> "Fetcher":
        self.session = requests.Session()
        self.session.mount("http://", HTTPAdapter(timeout=self.timeout))
        self.session.mount("https://", HTTPAdapter(timeout=self.timeout))
        self.session.headers["User-Agent"] = f"{self.auth[0]} using requests/{requests.__version__}"
        if self.auth is not None:
            self.session.auth = self.auth
        return self

    def __exit__(self, *exc: Any) -> None:
        self.session.close()

    @staticmethod
    def _extract_rate_limit(resp: requests.Response) -> Tuple[int, int, datetime]:
        headers = resp.headers
        limit = int(headers["X-Ratelimit-Limit"])
        remaining = int(headers["X-Ratelimit-Remaining"])
        reset = int(headers["X-Ratelimit-Reset"])
        reset_datetime = datetime.fromtimestamp(reset, tz=timezone.utc)
        return (limit, remaining, reset_datetime)

    def get(self, path: str, check_status_code: bool = True, **kwargs: Any) -> requests.Response:
        if not (path.startswith("https://") or path.startswith("http://")):
            path = self.url + path

        t0 = time.perf_counter()
        resp = self.session.get(path, **kwargs)
        t1 = time.perf_counter()
        if self.debug:
            print(path, round(t1 - t0, 3))

        self._rate_limit = self._extract_rate_limit(resp)
        if check_status_code:
            resp.raise_for_status()

        return resp

    def rate_limit(self) -> Tuple[int, int, datetime]:
        if not hasattr(self, "_rate_limit"):
            self.get("/rate_limit")

        return self._rate_limit


def get_current_datetime() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def print_rate_limit(headers: Tuple[int, int, datetime]) -> None:
    print(
        f"{headers[1]} API calls remain out of {headers[0]}."
        " Rate limit resets after"
        f" {headers[2].astimezone().strftime('%b %d %I:%M:%S %p')}."
    )


def enumerate_issues(
    repo: Repo, fetcher: Fetcher, last_updated: Optional[datetime] = None
) -> IssueSet:
    print("Enumerating how many to fetch ...", end="", flush=True)
    if last_updated is not None:
        stringified = last_updated.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        since = f"&since={stringified}"
    else:
        since = ""
    url = f"/repos/{repo.owner}/{repo.name}/issues?per_page=100&state=all&direction=asc{since}"

    issues = IssueSet()
    while True:
        resp = fetcher.get(url)
        issues.extend(Issue(**entry) for entry in resp.json())
        print(f"\rEnumerating how many to fetch ... {len(issues)}", end="", flush=True)
        try:
            url = resp.links["next"]["url"]
        except KeyError:
            break

    print()
    return issues


def fetch_issue_data(repo: Repo, issue: Issue, fetcher: Fetcher) -> Issue:
    endpoint = "pulls" if issue.is_pr else "issues"
    url = f"/repos/{repo.owner}/{repo.name}/{endpoint}/{issue.number}"
    resp = fetcher.get(url)
    return Issue(**resp.json())


def fetch_issueset_data(
    repo: Repo, to_fetch: IssueSet, container: IssueSet, fetcher: Fetcher
) -> IssueSet:
    count = len(to_fetch)
    fetched = 0

    print(f"Fetching issues and pull requests ... 0/{count}", end="", flush=True)
    for i in to_fetch:
        issue = fetch_issue_data(repo, i, fetcher)
        container[issue.number] = issue
        fetched += 1
        print(
            "\rFetching issues and pull requests ..."
            f" {fetched}/{count} ({int(fetched / count * 100)}%)",
            end="",
            flush=True,
        )
    print()

    return container


def repo_callback(ctx: click.Context, param: click.Parameter, value: str) -> Repo:
    if value.count("/") != 1:
        raise click.BadParameter(
            "There should be only one backslash splitting the repo owner and name.",
            ctx=ctx,
            param=param,
        )

    return Repo.parse(value)


@click.group()
@click.option("--id", default="ichard26/ghstats", help="GitHub username (for User-Agent).")
@click.option(
    "--api-key",
    envvar="GITHUB_API_KEY",
    help="GitHub PAT to authenticate with the GitHub API.",
)
@click.option("--debug", is_flag=True, help="Print debug information.")
@click.pass_context
def main(ctx: click.Context, id: str, api_key: str, debug: bool) -> None:
    if not api_key:
        print(Fore.RED + "ERROR: GitHub API key or Personal Access Token unavailable.")
        ctx.exit(0)

    t0 = time.perf_counter()

    def _elapsed() -> float:
        return time.perf_counter() - t0

    fetcher = Fetcher(url=GITHUB_API, auth=(id, api_key), debug=debug)
    ctx.obj = {"fetcher": fetcher, "elapsed": _elapsed, "current-dt": get_current_datetime()}


@main.command(help="Fetch and save all issue data to a file.")
@click.argument("output_path", type=click.Path(writable=True, path_type=Path))
@click.option(
    "--repo",
    help="Repository to fetch issue data for. Format is {owner}/{name}.",
    callback=repo_callback,
    required=True,
)
@click.pass_context
def fetch(ctx: click.Context, output_path: Path, repo: Repo) -> None:
    elapsed = ctx.obj["elapsed"]

    with ctx.obj["fetcher"] as fetcher:
        issues = enumerate_issues(repo, fetcher)
        issues = fetch_issueset_data(repo, issues, issues, fetcher)

    record = Record(last_updated=ctx.obj["current-dt"], repo=repo)
    ghlib.save(issues, record, output_path)

    print()
    print_rate_limit(fetcher.rate_limit())
    print(f"Command took {elapsed():.3f} seconds to complete.")


@main.command(help="Update files holding issue and pull request data.")
@click.argument(
    "data-files",
    type=click.Path(exists=True, writable=True, readable=True, path_type=Path),
    nargs=-1,
)
@click.pass_context
def update(ctx: click.Context, data_files: Iterable[Path]) -> None:
    elapsed = ctx.obj["elapsed"]

    with ctx.obj["fetcher"] as fetcher:
        for df in data_files:
            print(Style.BRIGHT + f"Update operation for {df!s} starting")
            print("Loading data file ... ", end="")
            issue_set, record = ghlib.load(df)
            original_issue_set = IssueSet(issue_set)
            print("done")

            outdated = enumerate_issues(record.repo, fetcher, record.last_updated)
            if not outdated:
                print()
                continue

            updated_issues = fetch_issueset_data(record.repo, outdated, issue_set, fetcher)

            print("Summary of changes:")
            for i in outdated:
                kind = "pull request" if i.is_pr else "issue"
                if i.number not in original_issue_set:
                    styling = Fore.GREEN
                    change = "NEW"
                else:
                    if not original_issue_set[i].closed and i.closed:
                        styling = Fore.RED
                        change = "CLOSED"
                    else:
                        styling = Fore.YELLOW
                        change = "UPDATED"
                print(styling + f"  {change}", end="")
                print(f" - {kind} {int(i)} '{i.title}'")

            new_record = attrs.evolve(record, last_updated=ctx.obj["current-dt"])
            print("Saving updated data ... ", end="")
            ghlib.save(updated_issues, new_record, df)
            print("done\n")

    print_rate_limit(fetcher.rate_limit())
    print(f"Command took {elapsed():.3f} seconds to complete.")


if __name__ == "__main__":
    main()
