import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

import attrs
import click
import requests
from click import secho

from . import ghlib
from .ghlib import Issue, IssueSet, Record, Repo

DEFAULT_TIMEOUT = (3.1, 11.9)
GITHUB_API = "https://api.github.com"
GITHUB_GRAPHQL_API = "https://api.github.com/graphql"

ISSUES_QUERY = """\
query GraphQLQuery {
  repository(name: "black", owner: "psf") {
    kind(orderBy: {field: CREATED_AT, direction: ASC}, first: 100, after: null) {
      totalCount
      pageInfo {
        endCursor
        hasNextPage
      }
      edges {
        node {
          number
          title
          labels(first: 15) {
            nodes {
              name
            }
          }
          author {
            login
          }
          createdAt
          closedAt
          timelineItems(itemTypes: CLOSED_EVENT, first: 1) {
            nodes {
              ... on ClosedEvent {
                actor {
                  login
                }
              }
            }
          }
        }
      }
    }
  }
  rateLimit {
    limit
    remaining
    resetAt
  }
}
"""

RateLimit = Tuple[int, int, datetime]


@attrs.define(slots=False)
class Fetcher:
    api: str = attrs.field(validator=attrs.validators.in_(("rest", "graphql")))
    auth: Tuple[str, Optional[str]]
    debug: bool = False

    _rate_limit: Optional[RateLimit] = attrs.field(default=None, init=False)

    def __enter__(self) -> "Fetcher":
        self.session = requests.Session()
        self.session.headers["User-Agent"] = f"{self.auth[0]} using requests/{requests.__version__}"
        if self.auth[1] is not None:
            self.session.auth = self.auth
        return self

    def __exit__(self, *exc: Any) -> None:
        self.session.close()

    def _extract_rate_limit(self, resp: requests.Response) -> RateLimit:
        if self.api == "rest":
            headers = resp.headers
            limit = int(headers["X-Ratelimit-Limit"])
            remaining = int(headers["X-Ratelimit-Remaining"])
            reset = int(headers["X-Ratelimit-Reset"])
            reset_datetime = datetime.fromtimestamp(reset, tz=timezone.utc)
        else:
            rate_data = resp.json()["data"]["rateLimit"]
            limit = rate_data["limit"]
            remaining = rate_data["remaining"]
            reset_datetime = ghlib.convert_iso8601_string(rate_data["resetAt"])
            assert reset_datetime is not None

        return (limit, remaining, reset_datetime)

    def root_url(self) -> str:
        if self.api == "rest":
            return GITHUB_API
        else:
            return GITHUB_GRAPHQL_API

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        if not (path.startswith("https://") or path.startswith("http://")):
            path = self.root_url() + path

        t0 = time.perf_counter()
        resp = self.session.request(method, path, timeout=DEFAULT_TIMEOUT, **kwargs)
        t1 = time.perf_counter()
        if self.debug:
            print(path, round(t1 - t0, 3))

        self._rate_limit = self._extract_rate_limit(resp)
        resp.raise_for_status()
        return resp

    def get(self, path: str) -> requests.Response:
        return self.request("GET", path)

    def rate_limit(self) -> RateLimit:
        return self._rate_limit


def get_current_datetime() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def print_rate_limit(rate_limit: RateLimit) -> None:
    reset_date = rate_limit[2].astimezone().strftime('%b %d %I:%M:%S %p')
    print(f"{rate_limit[1]} API calls/points remain out of {rate_limit[0]}.", end="")
    print(f" Rate limit resets after {reset_date}.")


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


def _parse_graphql_issues_json(payload: Any, *, is_pr: bool) -> IssueSet:
    issues = IssueSet()
    payload = payload["edges"]
    for edge_entry in payload:
        node = edge_entry["node"]
        get_user = lambda key, n: n[key]["login"] if n[key] else "ghost"
        data = {
            "number": node["number"],
            "title": node["title"],
            "is_pr": is_pr,
            "created_at": node["createdAt"],
            "created_by": get_user("author", node),
            "closed_at": node["closedAt"],
            "closed_by": (
                get_user("actor", node["timelineItems"]["nodes"][0])
                if node["closedAt"] and node["timelineItems"]["nodes"]
                else None
            ),
            "labels": [label_node["name"] for label_node in node["labels"]["nodes"]]
        }
        issues.add(Issue(**data))

    return issues


def fetch_issues_graphql(repo: Repo, fetcher: Fetcher) -> IssueSet:
    issues = IssueSet()
    query = ISSUES_QUERY.replace("psf", repo.owner).replace("black", repo.name)
    for kind in ("issues", "pullRequests"):
        kind_issues = IssueSet()
        next_page_cursor = None
        more_pages = True
        while more_pages:
            this_query = query.replace("kind", kind)
            if next_page_cursor:
                this_query = this_query.replace("null", f'"{next_page_cursor}"')
            r = fetcher.request("POST", "", json={"query": this_query})

            query_data = r.json()["data"]["repository"][kind]
            kind_issues.extend(_parse_graphql_issues_json(query_data, is_pr=(kind != "issues")))
            skind = kind if kind == "issues" else "pull requests"
            print(f"\rFetching {skind} ...", len(kind_issues), end="", flush=True)

            more_pages = query_data["pageInfo"]["hasNextPage"]
            next_page_cursor = query_data["pageInfo"]["endCursor"]
        issues.extend(kind_issues)
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
        secho("ERROR: GitHub API key or Personal Access Token unavailable.", fg="red")
        ctx.exit(0)

    t0 = time.perf_counter()

    def _elapsed() -> float:
        return time.perf_counter() - t0

    fetcher = Fetcher(api="rest", auth=(id, api_key), debug=debug)
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
        # issues = enumerate_issues(repo, fetcher)
        # issues = fetch_issueset_data(repo, issues, issues, fetcher)
        fetcher.api = "graphql"
        issues = fetch_issues_graphql(repo, fetcher)

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
            secho(f"Update operation for {df!s} starting", bold=True)
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
                    styling = "green"
                    change = "NEW"
                else:
                    if not original_issue_set[i].closed and i.closed:
                        styling = "red"
                        change = "CLOSED"
                    else:
                        styling = "yellow"
                        change = "UPDATED"
                secho("  " + click.style(change, fg=styling), nl=False)
                print(f" - {kind} {int(i)} '{i.title}'")

            new_record = attrs.evolve(record, last_updated=ctx.obj["current-dt"])
            print("Saving updated data ... ", end="")
            ghlib.save(updated_issues, new_record, df)
            print("done\n")

    print_rate_limit(fetcher.rate_limit())
    print(f"Command took {elapsed():.3f} seconds to complete.")


if __name__ == "__main__":
    main()
