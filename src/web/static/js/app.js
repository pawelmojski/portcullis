// Jumphost Admin - Main JavaScript

// Auto-dismiss alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
});

// Confirm delete actions
function confirmDelete(message) {
    return confirm(message || 'Are you sure you want to delete this item?');
}

// Format date/time
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

// Policy form helpers
if (document.getElementById('policyForm')) {
    // Show/hide fields based on scope type
    const scopeType = document.getElementById('scope_type');
    const groupFields = document.getElementById('groupFields');
    const serverFields = document.getElementById('serverFields');
    const protocolField = document.getElementById('protocolField');
    
    if (scopeType) {
        scopeType.addEventListener('change', function() {
            if (this.value === 'group') {
                groupFields?.classList.remove('d-none');
                serverFields?.classList.add('d-none');
                protocolField?.querySelector('select').removeAttribute('required');
            } else if (this.value === 'server') {
                groupFields?.classList.add('d-none');
                serverFields?.classList.remove('d-none');
                protocolField?.querySelector('select').removeAttribute('required');
            } else if (this.value === 'service') {
                groupFields?.classList.add('d-none');
                serverFields?.classList.remove('d-none');
                protocolField?.querySelector('select').setAttribute('required', 'required');
            }
        });
    }
    
    // Load user source IPs when user is selected
    const userSelect = document.getElementById('user_id');
    const sourceIpSelect = document.getElementById('source_ip_id');
    
    if (userSelect && sourceIpSelect) {
        userSelect.addEventListener('change', function() {
            const userId = this.value;
            if (userId) {
                fetch(`/policies/api/user/${userId}/ips`)
                    .then(response => response.json())
                    .then(data => {
                        sourceIpSelect.innerHTML = '<option value="">All IPs</option>';
                        data.ips.forEach(ip => {
                            const option = document.createElement('option');
                            option.value = ip.id;
                            option.textContent = `${ip.ip} (${ip.label || 'No label'})`;
                            sourceIpSelect.appendChild(option);
                        });
                    })
                    .catch(error => console.error('Error loading source IPs:', error));
            } else {
                sourceIpSelect.innerHTML = '<option value="">All IPs</option>';
            }
        });
    }
}

// Dashboard stats refresh (every 30 seconds)
if (document.getElementById('dashboardStats')) {
    setInterval(() => {
        fetch('/dashboard/api/stats')
            .then(response => response.json())
            .then(data => {
                // Update stat values
                document.getElementById('todayConnections').textContent = data.today_connections;
                document.getElementById('todayDenied').textContent = data.today_denied;
                document.getElementById('successRate').textContent = data.success_rate + '%';
            })
            .catch(error => console.error('Error refreshing stats:', error));
    }, 30000);
}

// Monitoring charts
if (document.getElementById('hourlyChart')) {
    fetch('/monitoring/api/stats/hourly')
        .then(response => response.json())
        .then(data => {
            const ctx = document.getElementById('hourlyChart').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.map(d => d.hour),
                    datasets: [
                        {
                            label: 'Granted',
                            data: data.map(d => d.granted),
                            borderColor: 'rgb(25, 135, 84)',
                            backgroundColor: 'rgba(25, 135, 84, 0.1)',
                            tension: 0.4
                        },
                        {
                            label: 'Denied',
                            data: data.map(d => d.denied),
                            borderColor: 'rgb(220, 53, 69)',
                            backgroundColor: 'rgba(220, 53, 69, 0.1)',
                            tension: 0.4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                stepSize: 1
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top'
                        },
                        title: {
                            display: true,
                            text: 'Connections Last 24 Hours'
                        }
                    }
                }
            });
        })
        .catch(error => console.error('Error loading chart:', error));
}

if (document.getElementById('userChart')) {
    fetch('/monitoring/api/stats/by_user')
        .then(response => response.json())
        .then(data => {
            const ctx = document.getElementById('userChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.map(d => d.user),
                    datasets: [{
                        label: 'Connections',
                        data: data.map(d => d.total),
                        backgroundColor: 'rgba(13, 110, 253, 0.5)',
                        borderColor: 'rgb(13, 110, 253)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                stepSize: 1
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        title: {
                            display: true,
                            text: 'Top Users (Last 7 Days)'
                        }
                    }
                }
            });
        })
        .catch(error => console.error('Error loading chart:', error));
}
