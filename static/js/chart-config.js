// Chart.js configurations

document.addEventListener('DOMContentLoaded', function() {
    // Sales Chart
    const salesChart = document.getElementById('salesChart');
    if (salesChart) {
        const ctx = salesChart.getContext('2d');
        const dates = JSON.parse(salesChart.getAttribute('data-dates') || '[]');
        const revenues = JSON.parse(salesChart.getAttribute('data-revenues') || '[]');
        
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [{
                    label: 'Daily Revenue (₹)',
                    data: revenues,
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '₹' + value;
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return '₹' + context.raw;
                            }
                        }
                    }
                }
            }
        });
    }

    // Inventory Chart
    const inventoryChart = document.getElementById('inventoryChart');
    if (inventoryChart) {
        const ctx = inventoryChart.getContext('2d');
        const items = JSON.parse(inventoryChart.getAttribute('data-items') || '[]');
        const stocks = JSON.parse(inventoryChart.getAttribute('data-stocks') || '[]');
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: items,
                datasets: [{
                    label: 'Current Stock',
                    data: stocks,
                    backgroundColor: 'rgba(54, 162, 235, 0.6)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    // Production Trend Chart
    const productionChart = document.getElementById('productionChart');
    if (productionChart) {
        const ctx = productionChart.getContext('2d');
        const dates = JSON.parse(productionChart.getAttribute('data-dates') || '[]');
        const quantities = JSON.parse(productionChart.getAttribute('data-quantities') || '[]');
        
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [{
                    label: 'Production (kg)',
                    data: quantities,
                    backgroundColor: 'rgba(255, 159, 64, 0.2)',
                    borderColor: 'rgba(255, 159, 64, 1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    // Recipe Distribution Chart
    const recipeChart = document.getElementById('recipeChart');
    if (recipeChart) {
        const ctx = recipeChart.getContext('2d');
        const recipes = JSON.parse(recipeChart.getAttribute('data-recipes') || '[]');
        const quantities = JSON.parse(recipeChart.getAttribute('data-quantities') || '[]');
        
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: recipes,
                datasets: [{
                    data: quantities,
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.6)',
                        'rgba(54, 162, 235, 0.6)',
                        'rgba(255, 206, 86, 0.6)',
                        'rgba(75, 192, 192, 0.6)',
                        'rgba(153, 102, 255, 0.6)',
                        'rgba(255, 159, 64, 0.6)'
                    ],
                    borderColor: [
                        'rgba(255, 99, 132, 1)',
                        'rgba(54, 162, 235, 1)',
                        'rgba(255, 206, 86, 1)',
                        'rgba(75, 192, 192, 1)',
                        'rgba(153, 102, 255, 1)',
                        'rgba(255, 159, 64, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right'
                    }
                }
            }
        });
    }
});
