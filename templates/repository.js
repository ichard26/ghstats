import { dataBaseURL, barOptions, createChartElement, lineOptions, loadTimeSeriesJSON } from '../_assets/lib.js'

const issueCountsURL = dataBaseURL + "{{ repo.fullname }}/issue-counts.json";
const pullCountsURL = dataBaseURL + "{{ repo.fullname }}/pull-counts.json";
const issueDeltasURL = dataBaseURL + "{{ repo.fullname }}/issue-deltas.json";
const issueClosersURL = dataBaseURL + "{{ repo.fullname }}/issue-closers.json";

async function loadCharts() {
    let startTime = performance.now()

    {% if 'issue-counts' in views %}
    let response = await fetch(issueCountsURL);
    const issue_data = await response.json();
    createChartElement("issue-counts", {
        type: 'line',
        data: { datasets: loadTimeSeriesJSON(issue_data) },
        options: lineOptions("Open issues"),
    });
    {% endif %}

    {% if 'pull-counts' in views %}
    response = await fetch(pullCountsURL);
    const pull_data = await response.json();
    createChartElement("pull-counts", {
        type: 'line',
        data: { datasets: loadTimeSeriesJSON(pull_data) },
        options: lineOptions("Open pulls"),
    });
    {% endif %}

    {% if 'issue-deltas' in views %}
    response = await fetch(issueDeltasURL);
    const deltas_data = await response.json();
    createChartElement("issue-deltas", {
        type: 'bar',
        data: { datasets: loadTimeSeriesJSON(deltas_data, true, false) },
        options: barOptions("changes"),
    });
    {% endif %}

    {% if 'issue-closers' in views %}
    response = await fetch(issueClosersURL);
    const closers_data = await response.json();
    createChartElement("issue-closers", {
        type: 'line',
        data: { datasets: loadTimeSeriesJSON(closers_data) },
        options: lineOptions("Closed issues"),
    });
    {% endif %}

    const elapsed = Math.round(performance.now() - startTime);
    console.log(
        `[debug] loading charts took ${elapsed} milliseconds`
    )
}

loadCharts();
