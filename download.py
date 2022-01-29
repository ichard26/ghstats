import datetime
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

import attrs
import click
import colorama
from colorama import Fore, Style
import requests

import lib
from lib import Issue, IssueSet, Record, Repo

DEFAULT_TIMEOUT = (3.1, 11.9)
GITHUB_API = "https://api.github.com"
USERNAME = "@ichard26"
USER_AGENT = f"{USERNAME} using python-requests/{requests.__version__}"

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
    auth: Optional[Tuple[str, str]] = None
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
        self.session.headers["User-Agent"] = USER_AGENT
        if self.auth is not None:
            self.session.auth = self.auth
        return self

    def __exit__(self, *exc: Any) -> None:
        self.session.close()

    @staticmethod
    def _extract_rate_limit(
        resp: requests.Response,
    ) -> Tuple[int, int, datetime.datetime]:
        headers = resp.headers
        limit = int(headers["X-Ratelimit-Limit"])
        remaining = int(headers["X-Ratelimit-Remaining"])
        reset = int(headers["X-Ratelimit-Reset"])
        reset_datetime = datetime.datetime.fromtimestamp(reset, tz=datetime.timezone.utc)
        return (limit, remaining, reset_datetime)

    def get(
        self, path: str, check_status_code: bool = True, **kwargs: Any
    ) -> requests.Response:
        if not (path.startswith("https://") or path.startswith("http://")):
            path = self.url + path

        t0 = time.perf_counter()
        resp = self.session.get(path, **kwargs)
        t1 = time.perf_counter()

        self._rate_limit = self._extract_rate_limit(resp)

        if self.debug:
            print(path, round(t1 - t0, 3))

        if check_status_code:
            resp.raise_for_status()

        return resp

    @property
    def rate_limit(self) -> Tuple[int, int, datetime.datetime]:
        if not hasattr(self, "_rate_limit"):
            self.get("/rate_limit")

        return self._rate_limit


def get_current_datetime() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def print_rate_limit(headers: Tuple[int, int, datetime.datetime]) -> None:
    print(
        f"{headers[1]} API calls remain out of {headers[0]}."
        " Rate limit resets after"
        f" {headers[2].astimezone().strftime('%b %d %I:%M:%S %p')}."
    )


def enumerate_issues(
    repo: Repo, fetcher: Fetcher, last_updated: Optional[datetime.datetime] = None
) -> IssueSet:
    print("Enumerating how many to fetch ...", end="", flush=True)
    since = ""
    if last_updated is not None:
        last_updated = last_updated.replace(microsecond=0)
        stringified = last_updated.isoformat().replace("+00:00", "Z")
        since = f"&since={stringified}"
    url = (
        f"/repos/{repo.user}/{repo.name}/issues"
        f"?per_page=100&state=all&direction=asc{since}"
    )

    issues = IssueSet()
    while True:
        resp = fetcher.get(url)
        issues.extend(resp.json())
        sys.stdout.write(f"\rEnumerating how many to fetch ... {len(issues)}")
        sys.stdout.flush()

        try:
            url = resp.links["next"]["url"]
        except KeyError:
            break

    print()
    return issues


def fetch_issue_data(repo: Repo, issue: Issue, fetcher: Fetcher) -> Issue:
    endpoint = "pulls" if issue.is_pr else "issues"
    url = f"/repos/{repo.user}/{repo.name}/{endpoint}/{issue.number}"
    resp = fetcher.get(url)
    return Issue(**resp.json())


def fetch_issueset_data(
    repo: Repo, issues: IssueSet, container: IssueSet, fetcher: Fetcher
) -> IssueSet:
    count = len(issues)
    fetched = 0

    print(f"Fetching issues and pull requests ... 0/{count}", end="", flush=True)
    for i in issues:
        issue = fetch_issue_data(repo, i, fetcher)
        container[issue.number] = issue
        fetched += 1
        sys.stdout.write(
            "\rFetching issues and pull requests ..."
            f" {fetched}/{count} ({int(fetched / count * 100)}%)"
        )
        sys.stdout.flush()
    print()

    return container


def repo_callback(ctx: click.Context, param: click.Parameter, value: str) -> Repo:
    if value.count("/") != 1:
        raise click.BadParameter(
            "There should be exactly one backslash splitting the repo owner and name.",
            ctx=ctx,
            param=param,
        )

    repo = tuple(value.split("/"))
    return Repo(user=repo[0], name=repo[1])


@click.group()
@click.option(
    "-k",
    "--api-key",
    envvar="GITHUB_API_KEY",
    help="The OAuth2 token or PAT to authenticate with the GitHub API.",
)
@click.pass_context
def main(ctx: click.Context, api_key: str) -> None:
    if not api_key:
        print(Fore.RED + "ERROR: API key / Personal Access Token unavailable.")
        ctx.exit(0)

    ctx.obj = {
        "api_key": api_key,
        "t0": time.perf_counter(),
    }


@main.command(help="Fetch and save all issue data to a file.")
@click.argument(
    "output_path",
    type=click.Path(
        file_okay=True,
        writable=True,
        resolve_path=True,
        path_type=Path
    ),
)
@click.option(
    "-r",
    "--repo",
    help="Repository to fetch issue data for. Format is {user}/{name}.",
    callback=repo_callback,
)
@click.pass_context
def fetch(ctx: click.Context, output_path: Path, repo: Repo) -> None:
    api_key = ctx.obj["api_key"]
    t0 = ctx.obj["t0"]

    last_updated = get_current_datetime()
    with Fetcher(url=GITHUB_API, auth=(USERNAME, api_key)) as fetcher:
        issues = enumerate_issues(repo, fetcher)
        issues = fetch_issueset_data(repo, issues, issues, fetcher)

    record = Record(last_updated=last_updated, repo=repo)
    lib.save(issues, record, output_path)

    print_rate_limit(fetcher.rate_limit)
    t1 = time.perf_counter()
    print(f"Command took {round(t1 - t0, 3)} seconds to complete.")
    ctx.exit(0)


@main.command(help="Update files holding issue and pull request data.")
@click.argument(
    "data_files",
    type=click.Path(
        exists=True,
        writable=True,
        readable=True,
        resolve_path=True,
        path_type=Path
    ),
    nargs=-1,
)
@click.option("-d", "--debug", is_flag=True, help="Print debug information.")
@click.pass_context
def update(ctx: click.Context, data_files: Iterable[Path], debug: bool) -> None:
    t0 = ctx.obj["t0"]
    api_key = ctx.obj["api_key"]

    new_last_updated = get_current_datetime()
    with Fetcher(url=GITHUB_API, auth=(USERNAME, api_key), debug=debug) as fetcher:
        for df in data_files:
            try:
                pretty_path = df.relative_to(Path.cwd())
            except Exception:
                pretty_path = df
            print(Style.BRIGHT + f"Update operation for {pretty_path!s} starting")
            print("Loading data file ... ", end="")
            issue_set, record = lib.load(df)
            original_issue_set = IssueSet(issue_set)
            print("done")

            issues_to_update = enumerate_issues(
                record.repo, fetcher, last_updated=record.last_updated
            )
            if not issues_to_update:
                print()
                continue

            updated_issues = fetch_issueset_data(
                record.repo, issues_to_update, issue_set, fetcher
            )

            print("Summary of changes:")
            for i in issues_to_update:
                kind = "pull request" if i.is_pr else "issue"
                if i.number not in original_issue_set:
                    styling = Fore.GREEN
                    change = "NEW"
                else:
                    if not issue_set[i.number].closed and i.closed:
                        styling = Fore.RED
                        change = "CLOSED"
                    else:
                        styling = Fore.YELLOW
                        change = "UPDATED"
                print(
                    styling + f"  {change}" + Style.RESET_ALL,
                    f"- {kind} {int(i)} '{i.title}'",
                )

            new_record = attrs.evolve(record, last_updated=new_last_updated)
            print("Saving updated data ... ", end="")
            lib.save(updated_issues, new_record, df)
            print("done\n")

    print_rate_limit(fetcher.rate_limit)
    t1 = time.perf_counter()
    print(f"Command took {round(t1 - t0, 3)} seconds to complete.")
    ctx.exit(0)


if __name__ == "__main__":
    main()
