from __future__ import annotations

import datetime
import json
from functools import partial
from operator import attrgetter
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import attrs


def serialize(inst: type, field: attrs.Attribute, value: object) -> object:
    if isinstance(value, datetime.datetime):
        return value.isoformat()

    if isinstance(value, IssueSet):
        return list(sorted(value._issues.values(), key=attrgetter("number")))

    return value


asdict = partial(attrs.asdict, value_serializer=serialize)


def convert_iso8601_string(string: str) -> Optional[datetime.datetime]:
    if string:
        return datetime.datetime.strptime(string, "%Y-%m-%dT%H:%M:%S%z")
    else:
        return None


@attrs.define
class Issue:
    """Read-only issue data and metadata representation object."""

    title: str
    number: int
    created_at: datetime.datetime = attrs.field(converter=convert_iso8601_string)
    created_by: str
    labels: List[str]
    url: str
    html_url: str
    is_pr: bool
    closed_at: Optional[datetime.datetime] = attrs.field(
        default=None, converter=convert_iso8601_string
    )
    closed_by: Optional[str] = None

    def __init__(self, **kwargs: Any) -> None:
        api_format = "login" in kwargs or not "created_by" in kwargs
        if api_format:
            created_by = kwargs.pop("user")["login"]
            closed_by = None
            if "closed_by" in kwargs:
                closed_by_data = kwargs.pop("closed_by")
                closed_by = closed_by_data["login"] if closed_by_data else None
            is_pr = "pull_request" in kwargs or "merged_at" in kwargs
            labels = [l["name"] for l in kwargs.pop("labels")]
            filtered = {
                attribute.name: kwargs[attribute.name]
                for attribute in self.__attrs_attrs__
                if attribute.name in kwargs
            }
            self.__attrs_init__(
                **filtered,
                created_by=created_by,
                closed_by=closed_by,
                is_pr=is_pr,
                labels=labels,
            )
        else:
            self.__attrs_init__(**kwargs)

    def __int__(self) -> int:
        return self.number

    @property
    def closed(self) -> bool:
        return bool(self.closed_at)


@attrs.define
class IssueSet(Sequence[Issue]):
    _issues: Dict[int, Issue]

    def __init__(
        self, issues: Optional[Union[Sequence[Issue], "IssueSet"]] = None
    ) -> None:
        if isinstance(issues, Sequence):
            issues = {i.number: i for i in issues}
        elif isinstance(issues, self.__class__):
            issues = issues._issues.copy()

        assert isinstance(issues, dict) or issues is None 
        self._issues = issues or {}

    def add(self, issue: Union[Issue, dict]) -> None:
        issue = issue if isinstance(issue, Issue) else Issue(**issue)
        self._issues[issue.number] = issue

    def extend(
        self, issues: Union["IssueSet", Sequence[Issue], Mapping[int, Any]]
    ) -> None:
        issues_as_dict: Mapping[int, Issue]
        if isinstance(issues, IssueSet):
            issues_as_dict = issues._issues
        elif isinstance(issues, Sequence):
            issues_as_dict = IssueSet.from_json(issues)._issues
        else:
            issues_as_dict = IssueSet.from_json(list(issues.values()))._issues

        self._issues.update(issues_as_dict)

    def oldest(self) -> Issue:
        lowest = min(i for i in self._issues.keys())
        return self._issues[lowest]

    def newest(self) -> Issue:
        newest = max(i for i in self._issues.keys())
        return self._issues[newest]

    def __len__(self) -> int:
        return len(self._issues.keys())

    def __iter__(self) -> Iterator[Issue]:
        return iter(self._issues.values())

    def __contains__(self, item: object) -> bool:
        if isinstance(item, int):
            return item in self._issues.keys()

        if not isinstance(item, Issue) or item.number not in self._issues.keys():
            return False

        return True

    def __getitem__(self, issue_number: int) -> Issue:
        if not isinstance(issue_number, int):
            raise TypeError("Only integers are supported as keys for item lookup.")

        try:
            issue = self._issues[issue_number]
        except KeyError:
            raise KeyError(f"Issue {issue_number} doesn't exist in the set") from None

        return issue

    def __setitem__(self, issue_number: int, issue_obj: Issue) -> None:
        if not isinstance(issue_number, int):
            raise TypeError("Only integers are supported as keys.")
        if not isinstance(issue_obj, Issue):
            raise TypeError("Only Issue objects are supported as values.")

        self._issues[issue_number] = issue_obj

    def __delitem__(self, issue_number: int) -> None:
        if not isinstance(issue_number, int):
            raise TypeError("Only integers are supported as keys for item deletion.")

        try:
            del self._issues[issue_number]
        except KeyError:
            raise KeyError(f"Cannot delete non-existent issue {issue_number}")

    @classmethod
    def from_json(
        cls, issues: Union[Sequence[Issue], Sequence[Dict[str, Any]]]
    ) -> "IssueSet":
        if not isinstance(issues, Sequence):
            raise TypeError("Issue set data must be a sequence.")

        parsed_issues = {}
        for i in issues:
            if isinstance(i, Issue):
                parsed_issues[i.number] = i
            elif isinstance(i, dict):
                parsed_issue = Issue(**i)
                parsed_issues[parsed_issue.number] = parsed_issue
            else:
                raise TypeError("Issue data must be an Issue object or a dictionary.")

        return cls(parsed_issues)


@attrs.define
class Repo:
    user: str
    name: str

    def __str__(self) -> str:
        return f"{self.user}/{self.name}"


@attrs.define
class Record:
    last_updated: datetime.datetime
    repo: Repo


def _parse_record_json(contents: Dict) -> Record:
    last_updated = datetime.datetime.strptime(
        contents["last_updated"], "%Y-%m-%dT%H:%M:%S%z"
    )
    repo = Repo(**contents["repo"])
    return Record(last_updated=last_updated, repo=repo)


def save(issues: IssueSet, record: Record, output_path: Path) -> None:
    data = {
        "issues": [asdict(i) for i in sorted(issues, key=attrgetter("number"))],
        "record": asdict(record),
    }
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load(data_path: Path) -> Tuple[IssueSet, Record]:
    data = json.loads(data_path.read_text("utf-8"))
    return IssueSet.from_json(data["issues"]), _parse_record_json(data["record"])
