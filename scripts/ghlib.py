from __future__ import annotations

import json
from datetime import datetime
from functools import partial
from operator import attrgetter
from pathlib import Path
from typing import Any, Collection, Dict, Iterable, Iterator, List, Optional, Tuple, Union

import attrs

JSON = Dict[str, Any]


def serialize(inst: type, field: attrs.Attribute, value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, IssueSet):
        return list(sorted(value._issues.values(), key=attrgetter("number")))

    return value


asdict = partial(attrs.asdict, value_serializer=serialize)


def convert_iso8601_string(string: Optional[str]) -> Optional[datetime]:
    return datetime.strptime(string, "%Y-%m-%dT%H:%M:%S%z") if string else None


@attrs.define
class Issue:
    """Read-only issue data and metadata representation object."""

    number: int
    title: str
    labels: List[str]
    is_pr: bool
    created_at: datetime = attrs.field(converter=convert_iso8601_string)
    created_by: str
    closed_at: Optional[datetime] = attrs.field(default=None, converter=convert_iso8601_string)
    closed_by: Optional[str] = None

    def __init__(self, **kwargs: Any) -> None:
        api_format = "login" in kwargs or "created_by" not in kwargs
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
                **filtered, created_by=created_by, closed_by=closed_by, is_pr=is_pr, labels=labels
            )
        else:
            self.__attrs_init__(**kwargs)

    def __int__(self) -> int:
        return self.number

    @property
    def closed(self) -> bool:
        return bool(self.closed_at)


@attrs.define
class IssueSet(Collection[Issue]):
    _issues: Dict[int, Issue]

    def __init__(self, issues: Union[Iterable[Issue], "IssueSet"] = ()) -> None:
        if isinstance(issues, self.__class__):
            self._issues = issues._issues.copy()
        else:
            self._issues = {i.number: i for i in issues}

    def add(self, i: Issue) -> None:
        self._issues[i.number] = i

    def extend(self, issues: Union["IssueSet", Iterable[Issue]]) -> None:
        if isinstance(issues, IssueSet):
            issues_as_dict = issues._issues
        elif isinstance(issues, Iterable):
            issues_as_dict = IssueSet(issues)._issues

        self._issues.update(issues_as_dict)

    def oldest(self) -> Issue:
        return self._issues[min(self._issues)]

    def newest(self) -> Issue:
        return self._issues[max(self._issues)]

    def __len__(self) -> int:
        return len(self._issues)

    def __iter__(self) -> Iterator[Issue]:
        return iter(self._issues.values())

    def __contains__(self, item: object) -> bool:
        if isinstance(item, int):
            return item in self._issues
        if isinstance(item, Issue):
            return item.number in self._issues

        return False

    def __getitem__(self, issue_number: Union[int, Issue]) -> Issue:
        if not isinstance(issue_number, (int, Issue)):
            raise TypeError("Only integers/issues are supported as keys for item lookup.")

        try:
            return self._issues[int(issue_number)]
        except KeyError:
            raise KeyError(f"Issue {issue_number} doesn't exist in the set") from None

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
    def from_json(cls, issues: Union[Iterable[Issue], Iterable[JSON]]) -> "IssueSet":
        parsed_issues = []
        for i in issues:
            if isinstance(i, Issue):
                parsed_issues.append(i)
            elif isinstance(i, dict):
                parsed_issues.append(Issue(**i))
            else:
                raise TypeError("Issue data must be an Issue object or a dictionary.")

        return cls(parsed_issues)


@attrs.define
class Repo:
    owner: str
    name: str

    def __str__(self) -> str:
        return f"{self.owner}/{self.name}"

    @classmethod
    def parse(cls, r: str) -> "Repo":
        repo = tuple(r.split("/"))
        return cls(owner=repo[0], name=repo[1])


@attrs.define
class Record:
    repo: Repo
    last_updated: datetime
    version: int = 1


def save(issues: IssueSet, record: Record, output_path: Path) -> None:
    data = {
        "issues": [asdict(i) for i in sorted(issues, key=attrgetter("number"))],
        "record": asdict(record),
    }
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load(data_path: Path) -> Tuple[IssueSet, Record]:
    data = json.loads(data_path.read_text("utf-8"))

    last_updated = convert_iso8601_string(data["record"]["last_updated"])
    assert last_updated is not None
    repo = Repo(**data["record"]["repo"])

    return IssueSet.from_json(data["issues"]), Record(repo, last_updated)
