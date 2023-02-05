import { DateTime } from 'luxon';
import { Chart, registerables } from 'chart.js';
import 'chartjs-adapter-luxon';
// broken with snowpack:
//   https://github.com/withastro/snowpack/discussions/1856#discussioncomment-809593
//   https://github.com/withastro/snowpack/issues/3692
import zoomPlugin from 'chartjs-plugin-zoom';

const blackIssueCountsURL = "https://ichard26.github.io/ghstats/issue-counts.json";
const blackPullCountsURL = "https://ichard26.github.io/ghstats/pull-counts.json";
const blackIssueDeltasURL = "https://ichard26.github.io/ghstats/issue-deltas.json";
const blackIssueClosersURL = "https://ichard26.github.io/ghstats/issue-closers.json";

// while this makes "copy as image" somewhat usable, the lack of a title
// is a problem >.<
const bgPlugin = {
    id: "custom_bg",
    beforeDraw: (chart) => {
        const ctx = chart.canvas.getContext('2d');
        ctx.save();
        ctx.globalCompositeOperation = 'destination-over';
        ctx.fillStyle = 'white';
        ctx.fillRect(0, 0, chart.width, chart.height);
        ctx.restore();
    }
};
const resetPlugin = {
    id: "reset_on_doubleclick",
    beforeEvent: (chart, event, options) => {
        if (event.event.type == "dblclick" && !event.replay) {
            console.log("[debug] caught dblclick: reseting zoon & pan");
            chart.resetZoom();
        }
    }
}

Chart.register(zoomPlugin, bgPlugin, resetPlugin, ...registerables);


function createChartElement(id, configuration) {
    const section = document.querySelector(`#${id}-chart-section`);
    // https://www.chartjs.org/docs/3.7.0/configuration/responsive.html#important-note
    // div.setAttribute("style", "position: relative; height:40vh; width:80vw");
    const canvas = section.children[section.children.length - 1].children[0];
    return new Chart(canvas, configuration);
}

const COLORS = [
    'rgba(255, 99, 132, 1)',  // RED
    'rgba(54, 162, 235, 1)',  // ORANGE
    'rgba(255, 206, 86, 1)',  // YELLOW
    'rgba(75, 192, 192, 1)',  // GREEN
    'rgba(153, 102, 255, 1)', // BLUE
    'rgba(255, 159, 64, 1)',  // PURPLE
    'rgba(255, 192, 203, 1)', // PINK
    'rgb(201, 203, 207)',  // GREY
    'rgba(0, 0, 0, 1) ' // BLACK
];
const RED = COLORS[0];
const GREEN = COLORS[3];

function loadTimeSeriesJSON(json, bar = false, autocolors = true) {
    const loaded = [];
    for (const [index, dataset] of json.entries()) {
        const points = [];
        dataset.data.forEach(entry => {
            const parts = entry.x.split("-")
            const dt = DateTime.utc(
                Number(parts[0]), Number(parts[1]), Number(parts[2])
            )
            points.push({ x: dt, y: entry.y })
        });
        const prepped_dt = {
            label: dataset.label,
            data: points,
            fill: false,
            borderWidth: !bar ? 2 : 0
        }
        if (autocolors) {
            prepped_dt.backgroundColor = COLORS[index];
            prepped_dt.borderColor = COLORS[index];
        }
        loaded.push(prepped_dt)
    }
    return loaded;
}

const BASE_OPTIONS = {
    // Animations are slowwww.
    animation: false,
    // Data points aren't necessary at all.
    elements: { point: { radius: 0 } },
    // I need to capture the dblclick event for the custom reset zoom plugin.
    events: ['mousemove', 'mouseout', 'click', 'touchstart', 'touchmove', "dblclick"],
    interaction: { axis: 'xy', mode: 'nearest', intersect: false },
    layout: { padding: 8 },
    plugins: {
        zoom: {
            pan: { enabled: true },
            zoom: {
                mode: 'xy',
                drag: { enabled: true, modifierKey: 'ctrl' }
            }
        },
    },
    scales: {
        x: {
            type: 'time',
            time: {
                // Luxon format string
                tooltipFormat: 'DD T',
            },
            title: { display: true, text: 'Date' }
        },
        y: {
            title: { display: true, text: 'undefined' }
        }
    },
};

function lineOptions(ytitle) {
    const options = JSON.parse(JSON.stringify(BASE_OPTIONS));
    options.scales.y.title.text = ytitle;
    return options;
}

function barOptions(ytitle) {
    const options = JSON.parse(JSON.stringify(BASE_OPTIONS));
    options.scales.y.title.text = ytitle;
    options.elements = { bar: {} };
    options.elements.bar.backgroundColor = (ctx) => {
        const value = ctx.parsed.y;
        return value > 0 ? GREEN : RED;
    }
    return options;
}

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
