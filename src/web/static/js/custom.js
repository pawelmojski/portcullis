// Jumphost Web GUI - Custom JavaScript

// Auto-hide alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
});

// Confirmation dialogs for delete actions
function confirmDelete(entityType, entityName) {
    return confirm(`Are you sure you want to delete ${entityType} "${entityName}"?\n\nThis action cannot be undone.`);
}

// Format datetime for local timezone
function formatLocalDatetime(utcDateString) {
    const date = new Date(utcDateString);
    return date.toLocaleString();
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showToast('Copied to clipboard!', 'success');
    }, function(err) {
        showToast('Failed to copy: ' + err, 'error');
    });
}

// Show toast notification
function showToast(message, type = 'info') {
    const toastContainer = document.querySelector('.toast-container') || createToastContainer();
    
    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-bg-${type} border-0`;
    toastEl.setAttribute('role', 'alert');
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl);
    toast.show();
    
    toastEl.addEventListener('hidden.bs.toast', function() {
        toastEl.remove();
    });
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    document.body.appendChild(container);
    return container;
}

// Table row click navigation
document.addEventListener('DOMContentLoaded', function() {
    const clickableRows = document.querySelectorAll('tr[data-href]');
    clickableRows.forEach(function(row) {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function(e) {
            // Don't navigate if clicking on action buttons
            if (!e.target.closest('.table-actions')) {
                window.location.href = this.dataset.href;
            }
        });
    });
});

// Live search/filter for tables
function filterTable(inputId, tableId) {
    const input = document.getElementById(inputId);
    const table = document.getElementById(tableId);
    const rows = table.querySelectorAll('tbody tr');
    
    input.addEventListener('keyup', function() {
        const filter = this.value.toLowerCase();
        
        rows.forEach(function(row) {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(filter) ? '' : 'none';
        });
        
        // Show "no results" message if all rows hidden
        const visibleRows = Array.from(rows).filter(row => row.style.display !== 'none');
        const tbody = table.querySelector('tbody');
        const noResultsRow = tbody.querySelector('.no-results-row');
        
        if (visibleRows.length === 0 && !noResultsRow) {
            const tr = document.createElement('tr');
            tr.className = 'no-results-row';
            tr.innerHTML = `<td colspan="100" class="text-center text-muted py-4">
                <i class="bi bi-search"></i> No results found for "${filter}"
            </td>`;
            tbody.appendChild(tr);
        } else if (visibleRows.length > 0 && noResultsRow) {
            noResultsRow.remove();
        }
    });
}

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Initialize popovers
document.addEventListener('DOMContentLoaded', function() {
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});

// Real-time updates (for dashboard)
function startRealtimeUpdates(updateFunction, interval = 30000) {
    // Initial update
    updateFunction();
    
    // Set interval for updates
    const intervalId = setInterval(updateFunction, interval);
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        clearInterval(intervalId);
    });
    
    return intervalId;
}

// AJAX helper
async function fetchJSON(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Fetch error:', error);
        showToast('Network error: ' + error.message, 'danger');
        throw error;
    }
}
