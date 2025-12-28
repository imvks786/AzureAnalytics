// Placeholder for real-time data
let timeData = [];
let userCounts = [];

// Line Chart (initialized with empty data)
const lineCtx = document.getElementById('lineChart').getContext('2d');
const lineChart = new Chart(lineCtx, {
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

// Pie Chart (empty data)
const pieCtx = document.getElementById('pieChart').getContext('2d');
const pieChart = new Chart(pieCtx, {
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

// Update pages table
function updateTableFromApi(pages) {
    const tbody = document.querySelector('#pagesTable tbody');
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
    document.getElementById('activeUsers').textContent = data.activeUsers || 0;
    document.getElementById('pageViews').textContent = (data.pageViews || 0).toLocaleString();

    // avgDuration is seconds -> format as m:ss
    const d = Math.max(0, data.avgDuration || 0);
    const mins = Math.floor(d / 60);
    const secs = Math.floor(d % 60).toString().padStart(2, '0');
    document.getElementById('avgDuration').textContent = `${mins}:${secs}`;

    document.getElementById('bounceRate').textContent = `${(data.bounceRate || 0)}%`;
    document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();

    // small change indicators (rudimentary)
    const userChangeEl = document.getElementById('userChange');
    userChangeEl.textContent = '+'; // server can provide deltas if desired
    userChangeEl.className = `change positive`;

    document.getElementById('viewChange').textContent = '+0%';

    // Update chart
    if (data.timeseries && data.timeseries.labels) {
        timeData = data.timeseries.labels;
        userCounts = data.timeseries.values;
        lineChart.data.labels = timeData;
        lineChart.data.datasets[0].data = userCounts;
        lineChart.update();
    }

    // Update pie chart
    if (data.trafficSources) {
        const keys = ['Direct', 'Organic', 'Social', 'Referral', 'Email'];
        const counts = keys.map(k => data.trafficSources[k] || 0);
        pieChart.data.datasets[0].data = counts;
        pieChart.update();
    }

    // Update top pages
    updateTableFromApi(data.topPages || []);
}

// Fetch event counts from server
async function fetchEventCounts() {
    try {
        const res = await fetch('/api/event_counts?minutes=30', { credentials: 'same-origin' });
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

// Fetch realtime data from server (and event counts)
async function fetchRealtime() {
    try {
        const res = await fetch('/api/realtime', { credentials: 'same-origin' });
        if (res.status === 401) {
            alert("Not authenticated. Please sign in and refresh the page.");
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

// initial load and periodic refresh every 60s
fetchRealtime();
//setInterval(fetchRealtime, 60000);