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

let selectedSiteId = localStorage.getItem('selectedSiteId') || null;

function initSiteSelector() {
    const btn = document.getElementById('siteButton');
    const dropdown = document.getElementById('siteDropdown');
    if (!btn || !dropdown) return;

    // open/close toggle
    btn.addEventListener('click', function (e) {
        e.stopPropagation();
        dropdown.classList.toggle('open');
    });

    // item click
    dropdown.querySelectorAll('.site-item').forEach(item => {
        item.addEventListener('click', function () {
            const siteId = this.getAttribute('data-site-id');
            const name = this.querySelector('.site-item-name')?.textContent || siteId;
            // set selection (empty siteId means "All sites")
            if (!siteId) {
                selectedSiteId = null;
                localStorage.removeItem('selectedSiteId');
            } else {
                selectedSiteId = siteId;
                localStorage.setItem('selectedSiteId', siteId);
            }
            document.getElementById('siteButton').innerHTML = `${name} <span class="caret">▾</span>`;
            dropdown.classList.remove('open');
            // refresh data for selected site
            fetchRealtime();
            fetchEventCounts();
        });
    });

    // click outside to close
    document.addEventListener('click', function () {
        dropdown.classList.remove('open');
    });

    // set initial text
    const items = dropdown.querySelectorAll('.site-item');
    if (!selectedSiteId && items.length) {
        // default to first (prefer "All sites" if present)
        const first = items[0];
        const firstId = first.getAttribute('data-site-id');
        if (!firstId) {
            selectedSiteId = null;
            localStorage.removeItem('selectedSiteId');
        } else {
            selectedSiteId = firstId;
            localStorage.setItem('selectedSiteId', selectedSiteId);
        }
        const name = first.querySelector('.site-item-name')?.textContent || (selectedSiteId || 'All sites');
        document.getElementById('siteButton').innerHTML = `${name} <span class="caret">▾</span>`;
    } else if (selectedSiteId) {
        const selectedEl = dropdown.querySelector(`.site-item[data-site-id="${selectedSiteId}"]`);
        if (selectedEl) {
            const name = selectedEl.querySelector('.site-item-name')?.textContent || selectedSiteId;
            document.getElementById('siteButton').innerHTML = `${name} <span class="caret">▾</span>`;
        }
    } else if (!selectedSiteId && items.length) {
        // fallback to all sites label
        document.getElementById('siteButton').innerHTML = `All sites <span class="caret">▾</span>`;
    }
}

// Fetch event counts from server (uses selectedSiteId if set)
async function fetchEventCounts() {
    try {
        let url = '/api/event_counts?minutes=30';
        if (selectedSiteId) url += `&site_id=${encodeURIComponent(selectedSiteId)}`;
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
    initSiteSelector();
    initSidebarToggle();
    // initial load
    fetchRealtime();
    fetchEventCounts();
    // refresh every minute
    setInterval(fetchRealtime, 60000);
});

// Fetch realtime data from server (and event counts)
async function fetchRealtime() {
    try {
        let url = '/api/realtime';
        if (selectedSiteId) url += `?site_id=${encodeURIComponent(selectedSiteId)}`;
        const res = await fetch(url, { credentials: 'same-origin' });
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

// Sidebar toggle init and persistence
function initSidebarToggle() {
    const btn = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    if (!btn || !sidebar) return;

    // restore state
    const collapsed = localStorage.getItem('sidebarCollapsed') === '1';
    if (collapsed) sidebar.classList.add('collapsed');

    btn.addEventListener('click', function (e) {
        e.preventDefault();
        sidebar.classList.toggle('collapsed');
        // persist
        const isCollapsed = sidebar.classList.contains('collapsed');
        localStorage.setItem('sidebarCollapsed', isCollapsed ? '1' : '0');
    });

    // On small screens allow toggling visibility by clicking outside
    document.addEventListener('click', function (ev) {
        if (window.innerWidth > 880) return;
        if (!sidebar.classList.contains('hidden')) return; // only when hidden flag used
    });
}