// Simulate real-time data
let timeData = [];
let userCounts = [];
let currentUsers = 127;
let pageViewsCount = 1543;

// Initialize time data
for (let i = 30; i >= 0; i--) {
    const time = new Date(Date.now() - i * 60000);
    timeData.push(time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }));
    userCounts.push(Math.floor(Math.random() * 50) + 80);
}

// Line Chart
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

// Pie Chart
const pieCtx = document.getElementById('pieChart').getContext('2d');
const pieChart = new Chart(pieCtx, {
    type: 'doughnut',
    data: {
        labels: ['Direct', 'Organic Search', 'Social', 'Referral', 'Email'],
        datasets: [{
            data: [35, 30, 15, 12, 8],
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
const pages = [
    { url: '/home', users: 45, views: 234 },
    { url: '/products', users: 32, views: 189 },
    { url: '/blog/article-1', users: 28, views: 156 },
    { url: '/about', users: 15, views: 98 },
    { url: '/contact', users: 7, views: 45 }
];

function updateTable() {
    const tbody = document.querySelector('#pagesTable tbody');
    tbody.innerHTML = '';
    pages.forEach(page => {
        const row = tbody.insertRow();
        row.innerHTML = `
            <td>${page.url}</td>
            <td>${page.users}</td>
            <td>${page.views} <span class="bar-graph" style="width: ${page.views / 3}px"></span></td>
        `;
    });
}

// Update metrics
function updateMetrics() {
    const change = (Math.random() * 10 - 5).toFixed(1);
    currentUsers += Math.floor(Math.random() * 10 - 5);
    currentUsers = Math.max(50, Math.min(200, currentUsers));
    
    pageViewsCount += Math.floor(Math.random() * 20);
    
    document.getElementById('activeUsers').textContent = currentUsers;
    document.getElementById('pageViews').textContent = pageViewsCount.toLocaleString();
    document.getElementById('avgDuration').textContent = `${Math.floor(Math.random() * 3 + 2)}:${Math.floor(Math.random() * 60).toString().padStart(2, '0')}`;
    document.getElementById('bounceRate').textContent = `${(Math.random() * 20 + 35).toFixed(1)}%`;
    document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
    
    const userChangeEl = document.getElementById('userChange');
    userChangeEl.textContent = `${change > 0 ? '+' : ''}${change}%`;
    userChangeEl.className = `change ${change > 0 ? 'positive' : 'negative'}`;
    
    const viewChangeVal = (Math.random() * 15).toFixed(1);
    document.getElementById('viewChange').textContent = `+${viewChangeVal}%`;
    
    // Update chart
    timeData.shift();
    userCounts.shift();
    const now = new Date();
    timeData.push(now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }));
    userCounts.push(currentUsers);
    
    lineChart.data.labels = timeData;
    lineChart.data.datasets[0].data = userCounts;
    lineChart.update('none');
}

updateTable();
updateMetrics();
setInterval(updateMetrics, 3000);