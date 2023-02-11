import { dataBaseURL, barOptions, createChartElement, lineOptions, loadTimeSeriesJSON } from '../_assets/lib.js'

const blackIssueCountsURL = dataBaseURL + "psf/black/issue-counts.json";
const blackPullCountsURL = dataBaseURL + "psf/black/pull-counts.json";
const blackIssueDeltasURL = dataBaseURL + "psf/black/issue-deltas.json";
const blackIssueClosersURL = dataBaseURL + "psf/black/issue-closers.json";

async function loadCharts() {
    let startTime = performance.now()

    let response = await fetch(blackIssueCountsURL);
    const issue_data = await response.json();
    createChartElement("black-issues", {
        type: 'line',
        data: { datasets: loadTimeSeriesJSON(issue_data) },
        options: lineOptions("Open issues"),
    });

    response = await fetch(blackPullCountsURL);
    const pull_data = await response.json();
    createChartElement("black-pulls", {
        type: 'line',
        data: { datasets: loadTimeSeriesJSON(pull_data) },
        options: lineOptions("Open pulls"),
    });

    response = await fetch(blackIssueDeltasURL);
    const deltas_data = await response.json();
    createChartElement("black-issue-deltas", {
        type: 'bar',
        data: { datasets: loadTimeSeriesJSON(deltas_data, true, false) },
        options: barOptions("changes"),
    });

    response = await fetch(blackIssueClosersURL);
    const closers_data = await response.json();
    createChartElement("black-issue-closers", {
        type: 'line',
        data: { datasets: loadTimeSeriesJSON(closers_data) },
        options: lineOptions("Closed issues"),
    });

    const elapsed = Math.round(performance.now() - startTime);
    console.log(
        `[debug] loading charts took ${elapsed} milliseconds`
    )
}

loadCharts();
