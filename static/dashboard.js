// Placeholder for real-time data
let timeData = [];
let userCounts = [];

let lineChart;
let pieChart;

// Line Chart (initialized with empty data)
const lineCanvas = document.getElementById('lineChart');
if (lineCanvas) {
    const lineCtx = lineCanvas.getContext('2d');
    lineChart = new Chart(lineCtx, {
        type: 'line',
        data: {
            labels: timeData,
            datasets: [{
                label: 'Active Users',
                data: userCounts,
                borderColor: '#1a73e8',
                backgroundColor: 'rgba(26, 115, 232, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { maxTicksLimit: 6 }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: '#e8eaed' }
                }
            }
        }
    });
}

// Pie Chart (empty data)
const pieCanvas = document.getElementById('pieChart');
if (pieCanvas) {
    const pieCtx = pieCanvas.getContext('2d');
    pieChart = new Chart(pieCtx, {
        type: 'doughnut',
        data: {
            labels: ['Direct', 'Organic', 'Social', 'Referral', 'Email'],
            datasets: [{
                data: [0, 0, 0, 0, 0],
                backgroundColor: [
                    '#1a73e8',
                    '#34a853',
                    '#fbbc04',
                    '#ea4335',
                    '#9334e6'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { padding: 15, font: { size: 12 } }
                }
            }
        }
    });
}

// Update pages table
function updateTableFromApi(pages) {
    const tbody = document.querySelector('#pagesTable tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    pages.forEach(page => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td>${page.url || '(unknown)'}</td>
            <td>${page.users}</td>
            <td>${page.views} <span class="bar-graph" style="width: ${Math.min(200, page.views) / 3}px"></span></td>
        `;
    });
}

// Update metrics from API response
function updateMetricsFromApi(data) {
    const activeUsersEl = document.getElementById('activeUsers');
    if (activeUsersEl) activeUsersEl.textContent = data.activeUsers || 0;

    const activeUsers30El = document.getElementById('activeUsers30');
    if (activeUsers30El) activeUsers30El.textContent = data.activeUsers30 || 0;

    const pageViewsEl = document.getElementById('pageViews');
    if (pageViewsEl) pageViewsEl.textContent = (data.pageViews || 0).toLocaleString();

    // avgDuration is seconds -> format as m:ss
    const avgDurationEl = document.getElementById('avgDuration');
    if (avgDurationEl) {
        const d = Math.max(0, data.avgDuration || 0);
        const mins = Math.floor(d / 60);
        const secs = Math.floor(d % 60).toString().padStart(2, '0');
        avgDurationEl.textContent = `${mins}:${secs}`;
    }

    const bounceRateEl = document.getElementById('bounceRate');
    if (bounceRateEl) bounceRateEl.textContent = `${(data.bounceRate || 0)}%`;

    const lastUpdateEl = document.getElementById('lastUpdate');
    if (lastUpdateEl) lastUpdateEl.textContent = new Date().toLocaleTimeString();

    // small change indicators (rudimentary)
    const userChangeEl = document.getElementById('userChange');
    if (userChangeEl) {
        userChangeEl.textContent = '+';
        userChangeEl.className = `change positive`;
    }

    const viewChangeEl = document.getElementById('viewChange');
    if (viewChangeEl) viewChangeEl.textContent = '+0%';

    // Update chart
    if (lineChart && data.timeseries && data.timeseries.labels) {
        timeData = data.timeseries.labels;
        userCounts = data.timeseries.values;
        lineChart.data.labels = timeData;
        lineChart.data.datasets[0].data = userCounts;
        lineChart.update();
    }

    // Update pie chart
    if (pieChart && data.trafficSources) {
        const keys = ['Direct', 'Organic', 'Social', 'Referral', 'Email'];
        const counts = keys.map(k => data.trafficSources[k] || 0);
        pieChart.data.datasets[0].data = counts;
        pieChart.update();
    }

    // Update traffic table
    const trafficTableBody = document.querySelector('#trafficTable tbody');
    if (trafficTableBody && data.trafficSources) {
        trafficTableBody.innerHTML = '';
        const sortedSources = Object.entries(data.trafficSources).sort((a, b) => b[1] - a[1]);
        sortedSources.forEach(([source, count]) => {
            const row = trafficTableBody.insertRow();
            row.innerHTML = `<td>${source}</td><td style="text-align: right;">${count}</td>`;
        });
    }

    // Update top pages
    updateTableFromApi(data.topPages || []);
}

// Removed localized selectedSiteId declaration to assume usage of global one from navbar.js or fallback to localStorage
// But to be safe, let's just use a local getter or refer to the global one if it exists.
// Since navbar.js uses 'let selectedSiteId', it is global. 
// We will just NOT declare it here.

// Listen for site changes from navbar
document.addEventListener('siteChanged', function (e) {
    // We can rely on localStorage as the source of truth if we want to avoid variable coupling
    // selectedSiteId = e.detail.siteId; // This would assign to the global one
    fetchRealtime();
    fetchEventCounts();
});

// Fetch event counts from server
async function fetchEventCounts() {
    try {
        let siteId = localStorage.getItem('selectedSiteId');
        let url = '/api/event_counts?minutes=30';
        if (siteId) url += `&site_id=${encodeURIComponent(siteId)}`;
        const res = await fetch(url, { credentials: 'same-origin' });
        if (res.status === 401) {
            console.warn('Not authenticated for event counts');
            return;
        }
        if (!res.ok) {
            console.error('Failed to fetch event counts', res.status);
            return;
        }
        const json = await res.json();
        const counts = json.counts || [];
        const container = document.getElementById('eventsList');
        if (!container) return;
        container.innerHTML = '';
        if (!counts.length) {
            container.innerHTML = '<div style="color:#5f6368">No events in the selected window.</div>';
            return;
        }
        const max = Math.max(...counts.map(c => c.count), 1);
        counts.forEach(item => {
            const row = document.createElement('div');
            row.className = 'event-row';
            const name = document.createElement('div');
            name.className = 'event-name';
            name.textContent = item.event;
            const right = document.createElement('div');
            right.className = 'event-right';
            const count = document.createElement('div');
            count.className = 'event-count';
            count.textContent = item.count;
            const barWrapper = document.createElement('div');
            barWrapper.className = 'event-bar-wrapper';
            const bar = document.createElement('div');
            bar.className = 'event-bar';
            bar.style.width = `${Math.round((item.count / max) * 100)}%`;
            barWrapper.appendChild(bar);
            right.appendChild(count);
            right.appendChild(barWrapper);
            row.appendChild(name);
            row.appendChild(right);
            container.appendChild(row);
        });
    } catch (err) {
        console.error('Error fetching event counts', err);
    }
}

// call init on load
window.addEventListener('DOMContentLoaded', function () {
    // initial load
    fetchRealtime();
    fetchEventCounts();
    // refresh every minute
    setInterval(fetchRealtime, 60000);
});

// Fetch realtime data from server (and event counts)
async function fetchRealtime() {
    try {
        let siteId = localStorage.getItem('selectedSiteId');
        let url = '/api/realtime';
        if (siteId) url += `?site_id=${encodeURIComponent(siteId)}`;
        const res = await fetch(url, { credentials: 'same-origin' });
        if (res.status === 401) {
            // Only alert if we're on the dashboard page proper, or just suppress
            // alert("Not authenticated. Please sign in and refresh the page.");
            return;
        }
        if (!res.ok) {
            console.error('Failed to fetch realtime data', res.status);
            return;
        }
        const data = await res.json();
        updateMetricsFromApi(data);
        // also fetch event counts
        fetchEventCounts();
    } catch (err) {
        console.error('Error fetching realtime data', err);
    }
}
