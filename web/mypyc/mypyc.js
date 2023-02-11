import { dataBaseURL, barOptions, createChartElement, lineOptions, loadTimeSeriesJSON } from '../_assets/lib.js'

const issueCountsURL = dataBaseURL + "mypyc/mypyc/issue-counts.json";
const issueDeltasURL = dataBaseURL + "mypyc/mypyc/issue-deltas.json";

async function loadCharts() {
    let startTime = performance.now()

    let response = await fetch(issueCountsURL);
    const issue_data = await response.json();
    createChartElement("issues", {
        type: 'line',
        data: { datasets: loadTimeSeriesJSON(issue_data) },
        options: lineOptions("Open issues"),
    });

    response = await fetch(issueDeltasURL);
    const deltas_data = await response.json();
    createChartElement("issue-deltas", {
        type: 'bar',
        data: { datasets: loadTimeSeriesJSON(deltas_data, true, false) },
        options: barOptions("changes"),
    });

    const elapsed = Math.round(performance.now() - startTime);
    console.log(
        `[debug] loading charts took ${elapsed} milliseconds`
    )
}

loadCharts();
