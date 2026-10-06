// Global Chart defaults for Dark Theme
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';

// State
let token = null;

// DOM Elements
const els = {
    loading: document.getElementById('loading-overlay'),
    kpiRevenue: document.getElementById('kpi-revenue'),
    kpiOrders: document.getElementById('kpi-orders'),
    kpiGrowth: document.getElementById('kpi-growth'),
    kpiCategory: document.getElementById('kpi-category'),
    kpiProduct: document.getElementById('kpi-product'),
    topProductsList: document.getElementById('top-products-list'),
    slowProductsList: document.getElementById('slow-products-list')
};

// Formatting helpers
const formatCurrency = (val) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);
const formatNumber = (val) => new Intl.NumberFormat('en-US').format(val);

// 1. Authenticate with demo account
async function authenticate() {
    try {
        const formData = new URLSearchParams();
        formData.append('username', 'demo');
        formData.append('password', 'demo1234');

        const res = await fetch('/auth/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });
        
        if (!res.ok) throw new Error("Auth failed");
        const data = await res.json();
        token = data.access_token;
    } catch (err) {
        console.error("Authentication Error:", err);
        els.loading.innerHTML = "<p style='color:#ef4444'>Authentication Failed. Is the demo user seeded?</p>";
    }
}

// 2. Fetch Helper
async function apiGet(endpoint) {
    const res = await fetch(endpoint, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    if (!res.ok) throw new Error(`API Error: ${endpoint}`);
    return res.json();
}

// 3. Render KPIs
function renderKPIs(kpiData) {
    els.kpiRevenue.textContent = formatCurrency(kpiData.total_revenue);
    els.kpiOrders.textContent = formatNumber(kpiData.total_orders);
    
    // Growth
    const g = kpiData.revenue_growth_pct;
    els.kpiGrowth.textContent = `${g > 0 ? '↑' : '↓'} ${Math.abs(g)}%`;
    els.kpiGrowth.className = `kpi-trend ${g > 0 ? 'trend-up' : 'trend-down'}`;

    els.kpiProduct.textContent = kpiData.top_product || 'N/A';
    els.kpiCategory.textContent = kpiData.top_region || 'N/A'; // Using region slot for visual variation
}

// 4. Render Lists
function renderProductList(container, products, isDanger = false) {
    container.innerHTML = '';
    if (!products || products.length === 0) {
        container.innerHTML = '<li class="list-item"><span class="item-name" style="color:var(--text-secondary)">No products found</span></li>';
        return;
    }

    products.forEach(p => {
        const li = document.createElement('li');
        li.className = 'list-item';
        
        const color = isDanger ? 'var(--danger)' : 'var(--accent-blue)';
        
        li.innerHTML = `
            <div class="item-info">
                <span class="item-name">${p.product_name}</span>
                <span class="item-category">${p.category}</span>
            </div>
            <div class="item-stats">
                <div class="item-revenue" style="color:${color}">${formatCurrency(p.total_revenue)}</div>
                <div class="item-quantity">${p.total_quantity} sold</div>
            </div>
        `;
        container.appendChild(li);
    });
}

// 5. Render Charts
function renderCharts(trendData, categoryData) {
    // Trend Chart
    const trendCtx = document.getElementById('revenueChart').getContext('2d');
    
    // Gradient for line chart
    const gradient = trendCtx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.4)');
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0.0)');

    new Chart(trendCtx, {
        type: 'line',
        data: {
            labels: trendData.map(d => d.date),
            datasets: [{
                label: 'Revenue',
                data: trendData.map(d => d.revenue),
                borderColor: '#3b82f6',
                backgroundColor: gradient,
                borderWidth: 2,
                pointBackgroundColor: '#0b0f19',
                pointBorderColor: '#3b82f6',
                pointBorderWidth: 2,
                pointRadius: trendData.map(d => d.anomaly ? 6 : 0),
                pointHoverRadius: 6,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(22, 28, 45, 0.9)',
                    titleFont: { size: 13, family: "'Inter', sans-serif" },
                    bodyFont: { size: 14, family: "'Inter', sans-serif", weight: 'bold' },
                    padding: 10,
                    cornerRadius: 8,
                    displayColors: false,
                    callbacks: {
                        label: (ctx) => formatCurrency(ctx.raw)
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { callback: (val) => '$' + (val / 1000) + 'k' }
                },
                x: {
                    grid: { display: false },
                    ticks: { maxTicksLimit: 10 }
                }
            }
        }
    });

    // Category Donut Chart
    const catCtx = document.getElementById('categoryChart').getContext('2d');
    new Chart(catCtx, {
        type: 'doughnut',
        data: {
            labels: categoryData.map(c => c.category),
            datasets: [{
                data: categoryData.map(c => c.percentage),
                backgroundColor: [
                    '#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899', '#06b6d4'
                ],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '75%',
            plugins: {
                legend: {
                    position: 'right',
                    labels: { boxWidth: 12, usePointStyle: true, padding: 15 }
                },
                tooltip: {
                    backgroundColor: 'rgba(22, 28, 45, 0.9)',
                    callbacks: {
                        label: (ctx) => ` ${ctx.raw}%`
                    }
                }
            }
        }
    });
}

// Main Boot Sequence
async function boot() {
    await authenticate();
    if (!token) return;

    try {
        // Fetch all data in parallel for speed
        const [kpi, topProd, slowProd, trend, cats] = await Promise.all([
            apiGet('/analytics/kpi-summary?days=30'),
            apiGet('/analytics/top-products?days=30&limit=5'),
            apiGet('/analytics/slow-moving-products?days=60&threshold=5'),
            apiGet('/analytics/revenue-trend?days=60&flag_anomalies=true'),
            apiGet('/analytics/category-breakdown?days=30')
        ]);

        renderKPIs(kpi);
        renderProductList(els.topProductsList, topProd);
        renderProductList(els.slowProductsList, slowProd, true);
        renderCharts(trend, cats);

        // Hide loader
        els.loading.style.opacity = '0';
        setTimeout(() => els.loading.style.display = 'none', 500);

    } catch (err) {
        console.error("Dashboard Load Error:", err);
        els.loading.innerHTML = "<p style='color:#ef4444'>Failed to load analytics data.</p>";
    }
}

// Start
document.addEventListener('DOMContentLoaded', boot);
