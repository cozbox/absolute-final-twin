// TwinSync Spot JavaScript

// API helper
async function api(endpoint, options = {}) {
    const baseUrl = window.location.origin;
    const url = `${baseUrl}${endpoint}`;
    
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        }
    };
    
    const response = await fetch(url, { ...defaultOptions, ...options });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || 'Request failed');
    }
    
    return response.json();
}

// Toast notifications
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
    
    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease-out reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Check a spot
async function checkSpot(spotId, evt) {
    const button = evt ? evt.target : document.querySelector(`[onclick*="checkSpot(${spotId}"]`);
    if (!button) return;
    
    const originalText = button.innerHTML;
    
    button.disabled = true;
    button.innerHTML = '<span class="spinner"></span> Checking...';
    
    try {
        const result = await api(`/api/spots/${spotId}/check`, { method: 'POST' });
        showToast('Check completed!', 'success');
        
        // Reload page after a short delay
        setTimeout(() => window.location.reload(), 1000);
    } catch (error) {
        showToast(error.message, 'error');
        button.disabled = false;
        button.innerHTML = originalText;
    }
}

// Reset a spot
async function resetSpot(spotId) {
    if (!confirm('Are you sure you want to reset this spot? All check history will be deleted.')) {
        return;
    }
    
    try {
        await api(`/api/spots/${spotId}/reset`, { method: 'POST' });
        showToast('Spot reset successfully', 'success');
        setTimeout(() => window.location.reload(), 1000);
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// Snooze a spot
async function snoozeSpot(spotId, hours) {
    try {
        await api(`/api/spots/${spotId}/snooze`, {
            method: 'POST',
            body: JSON.stringify({ hours })
        });
        showToast(`Spot snoozed for ${hours} hours`, 'success');
        setTimeout(() => window.location.reload(), 1000);
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// Delete a spot
async function deleteSpot(spotId) {
    if (!confirm('Are you sure you want to delete this spot? This cannot be undone.')) {
        return;
    }
    
    try {
        await api(`/api/spots/${spotId}`, { method: 'DELETE' });
        showToast('Spot deleted', 'success');
        setTimeout(() => window.location.href = '/', 1000);
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// Check all spots
async function checkAllSpots(evt) {
    const button = evt ? evt.target : document.querySelector('[onclick*="checkAllSpots"]');
    if (!button) return;
    
    const originalText = button.innerHTML;
    
    button.disabled = true;
    button.innerHTML = '<span class="spinner"></span> Checking all...';
    
    try {
        const result = await api('/api/check-all', { method: 'POST' });
        showToast(`Checked ${result.results.length} spots`, 'success');
        setTimeout(() => window.location.reload(), 1000);
    } catch (error) {
        showToast(error.message, 'error');
        button.disabled = false;
        button.innerHTML = originalText;
    }
}

// Theme toggle
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    const toggle = document.getElementById('theme-toggle');
    if (toggle) {
        toggle.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme');
            const next = current === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
        });
    }
}

// Navigation toggle
function initNav() {
    const toggle = document.querySelector('.nav-toggle');
    const nav = document.querySelector('.nav-list');
    
    if (toggle && nav) {
        toggle.addEventListener('click', () => {
            nav.classList.toggle('active');
        });
    }
}

// Format date
function formatDate(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return date.toLocaleDateString();
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initNav();
});
