#!/usr/bin/env python

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, List

import click

from . import ghlib
from .ghlib import Issue, IssueSet


def months_between(start_date: date, end_date: date) -> Iterator[date]:
    # https://alexwlchan.net/2020/06/finding-the-months-between-two-dates-in-python/
    """
    Given two instances of ``datetime.date``, generate a list of dates on
    the 1st of every month between the two dates (inclusive).

    e.g. "5 Jan 2020" to "17 May 2020" would generate:

        1 Jan 2020, 1 Feb 2020, 1 Mar 2020, 1 Apr 2020, 1 May 2020
    """
    if start_date > end_date:
        raise ValueError(f"Start date {start_date} is not before end date {end_date}")

    year = start_date.year
    month = start_date.month

    while (year, month) <= (end_date.year, end_date.month + 1):
        yield date(year, month, 1)
        # Move to the next month.  If we're at the end of the year, wrap around
        # to the start of the next.
        #
        # Example: Nov 2017
        #       -> Dec 2017 (month += 1)
        #       -> Jan 2018 (end of year, month = 1, year += 1)
        #
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1


def get_days(issues: IssueSet) -> List[date]:
    sdate = issues[1].created_at.date()
    edate = datetime.utcnow().date()
    delta = edate - sdate
    return [sdate + timedelta(days=i) for i in range(delta.days + 1)]


def get_months(issues: IssueSet) -> List[date]:
    sdate = issues[1].created_at.date()
    edate = datetime.utcnow().date()
    return list(months_between(sdate, edate))


def generate_command_args(func: Callable) -> Callable:

    @click.argument("data-file", type=click.Path(exists=True, path_type=Path))
    @click.option("-o", "--output", type=click.Path(exists=False, path_type=Path), required=True)
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        func(*args, **kwargs)

    return wrapper


def cal_open_issues_over_time(days, issues: Iterable[Issue]):
    issues_per_day = []
    for day in days:
        open_ = 0
        for i in issues:
            if i.created_at.date() <= day:
                if i.closed_at is None:
                    open_ += 1
                elif i.closed_at.date() > day:
                    open_ += 1
        issues_per_day.append(open_)
    return issues_per_day


def get_rid_of_prs(issues):
    return IssueSet([i for i in issues if not i.is_pr])


def get_closed_issues(issues):
    return IssueSet([i for i in issues if i.closed_at is not None])


def get_closers(issues):
    return set([i.closed_by for i in issues])


def timeseries_line_dataset(label: str, data: List[int], days: List[date]) -> Any:
    return {"label": label, "data": [{"x": dt.isoformat(), "y": n} for dt, n in zip(days, data)]}


@click.group()
def main() -> None:
    pass


@main.command("issue-counts")
@generate_command_args
def issue_counts(data_file: Path, output: Path) -> None:
    issues, record = ghlib.load(data_file)

    print("[*] Data file loaded")
    days = get_days(issues)
    print("[*] Supporting data generation finished")

    issues_noprs = IssueSet([v for v in issues if not v.is_pr])
    issues_noprs_bug = IssueSet([v for v in issues_noprs if "T: bug" in v.labels])
    issues_noprs_doc = IssueSet([v for v in issues_noprs if "T: documentation" in v.labels])
    issues_noprs_enhanc = IssueSet([v for v in issues_noprs if "T: enhancement" in v.labels])
    issues_noprs_style = IssueSet([v for v in issues_noprs if "T: style" in v.labels])

    print("[*] Data preparation finished")

    ydata = cal_open_issues_over_time(days, issues_noprs)
    ydata_bug = cal_open_issues_over_time(days, issues_noprs_bug)
    ydata_doc = cal_open_issues_over_time(days, issues_noprs_doc)
    ydata_enhanc = cal_open_issues_over_time(days, issues_noprs_enhanc)
    ydata_style = cal_open_issues_over_time(days, issues_noprs_style)

    print("[*] Data chrunching finished")

    data = [
        timeseries_line_dataset("open issues (total)", ydata, days),
        timeseries_line_dataset("open issues (bug)", ydata_bug, days),
        timeseries_line_dataset("open issues (docs)", ydata_doc, days),
        timeseries_line_dataset("open issues (feature)", ydata_enhanc, days),
        timeseries_line_dataset("open issues (style)", ydata_style, days)
    ]
    blob = json.dumps(data)
    output.write_text(blob)


@main.command("pull-counts")
@generate_command_args
def pr_counts(data_file: Path, output: Path) -> None:
    issues, record = ghlib.load(data_file)

    print("[*] Data file loaded")
    days = get_days(issues)
    print("[*] Supporting data generation finished")

    pulls_noprs = IssueSet([v for v in issues if v.is_pr])

    print("[*] Data preparation finished")

    ydata = cal_open_issues_over_time(days, pulls_noprs)

    print("[*] Data chrunching finished")

    data = [timeseries_line_dataset("open PRs", ydata, days)]
    blob = json.dumps(data)
    output.write_text(blob)


@main.command("issue-closers")
@generate_command_args
def issue_closers(data_file: Path, output: Path) -> None:
    issues, record = ghlib.load(data_file)

    print("[*] JSON file loaded")
    days = get_days(issues)
    print("[*] Supporting data generation finished")

    def prepare_data_collection(days, closers):
        template = []
        for day in days:
            close_data_template = {}
            for c in closers:
                close_data_template[c.closed_by] = [0, 0]
            template.append(close_data_template)
        return template

    def cal_closes_over_time(template, days, issues):
        for idx, day in enumerate(days):
            for i in issues:
                if i.closed_at.date() <= day:
                    index = 0
                    if i.created_by == i.closed_by:
                        index = 1
                    template[idx][i.closed_by][index] += 1
        return template

    def parse_closing_data(data):
        groups = defaultdict(list)
        for day_data in data:
            default_close = 0
            for user, close_data in day_data.items():
                groups[user].append(close_data[0])
                default_close += close_data[1]
            groups["{issue-author}"].append(default_close)
        kill = {name for name, data in groups.items() if all(not day for day in data)}
        for target in kill:
            del groups[target]
        return groups

    closed_issues = get_closed_issues(get_rid_of_prs(issues))
    template = prepare_data_collection(days, closed_issues)

    print("[*] Data preparation finished")

    closing_data = cal_closes_over_time(template, days, closed_issues)
    parsed_data = parse_closing_data(closing_data)

    print("[*] Data chrunching finished")

    data = []
    for gname, ydata in parsed_data.items():
        data.append(timeseries_line_dataset(gname, ydata, days))
    blob = json.dumps(data, indent=2)
    output.write_text(blob)


@main.command("issue-deltas")
@generate_command_args
def issue_deltas(data_file: Path, output: Path) -> None:
    issues, record = ghlib.load(data_file)

    print("[*] Data file loaded")
    months = get_months(issues)
    print("[*] Supporting data generation finished")

    def cal_delta_over_time(open_issues_over_time):
        delta_per_month = []
        baseline = open_issues_over_time[0]
        for month in open_issues_over_time:
            delta_per_month.append(month - baseline)
            baseline = month
        return delta_per_month

    issues_noprs = get_rid_of_prs(issues)

    print("[*] Data preparation finished")

    open_issues_over_time_withoutprs = cal_open_issues_over_time(months, issues_noprs)
    ydata = cal_delta_over_time(open_issues_over_time_withoutprs)

    print("[*] Data chrunching finished")

    data = [timeseries_line_dataset("changes (issues)", ydata, months)]
    blob = json.dumps(data)
    output.write_text(blob)


if __name__ == "__main__":
    main()
