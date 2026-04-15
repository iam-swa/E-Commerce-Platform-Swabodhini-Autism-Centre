// Common utilities used across pages

function checkAuth() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/';
        return null;
    }
    return token;
}

function getUser() {
    return JSON.parse(localStorage.getItem('user') || '{}');
}

function getToken() {
    return localStorage.getItem('token');
}

// API helper
async function apiCall(url, options = {}) {
    const token = getToken();
    const headers = { ...(options.headers || {}) };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }
    const res = await fetch(url, { ...options, headers });
    const data = await res.json();
    if (res.status === 401) {
        localStorage.clear();
        window.location.href = '/';
        return;
    }
    if (!res.ok) throw new Error(data.message || 'Something went wrong');
    return data;
}

// Toast notifications
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Update cart badge
async function updateCartBadge() {
    try {
        const badge = document.getElementById('cartBadge');
        if (!badge) return;
        const cart = await apiCall('/api/cart');
        const count = cart.reduce((sum, item) => sum + item.quantity, 0);
        badge.textContent = count;
        badge.style.display = count > 0 ? 'flex' : 'none';
    } catch (e) { /* ignore */ }
}

// Setup navbar
function setupNavbar() {
    const menuBtn = document.getElementById('menuBtn');
    const navLinks = document.getElementById('navLinks');
    if (menuBtn && navLinks) {
        menuBtn.addEventListener('click', () => navLinks.classList.toggle('open'));
    }
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            localStorage.clear();
            window.location.href = '/';
        });
    }
    const userName = document.getElementById('userName');
    if (userName) {
        const user = getUser();
        userName.textContent = user.name || 'Account';
    }
    window.addEventListener('scroll', () => {
        const navbar = document.getElementById('navbar');
        if (navbar) navbar.classList.toggle('scrolled', window.scrollY > 20);
    });
}

// Format price
function formatPrice(price) {
    return `₹${Number(price).toLocaleString('en-IN')}`;
}

// Product image fallback
function getProductImage(img) {
    return img && img !== '/images/placeholder.png'
        ? img
        : `https://picsum.photos/seed/${Math.random().toString(36).substr(2, 6)}/400/300`;
}

// ── Location: request once per session, send to backend ────────────────────
/**
 * Silently requests the browser's geolocation and posts it to /api/user/location.
 * Only fires if:
 *   - user is logged in
 *   - we haven't already sent it this session (sessionStorage flag)
 *   - browser supports geolocation
 */
function syncUserLocation() {
    const token = getToken();
    if (!token) return;
    if (sessionStorage.getItem('locationSynced')) return;
    if (!navigator.geolocation) return;

    navigator.geolocation.getCurrentPosition(
        async (pos) => {
            try {
                sessionStorage.setItem('locationSynced', '1');
                const { latitude, longitude } = pos.coords;

                // Optional: reverse-geocode to get city/region using browser's
                // free Nominatim (no API key needed, respects usage policy)
                let city = '', region = '';
                try {
                    const geoRes = await fetch(
                        `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`,
                        { headers: { 'Accept-Language': 'en' } }
                    );
                    const geoData = await geoRes.json();
                    city   = geoData.address?.city
                          || geoData.address?.town
                          || geoData.address?.village
                          || '';
                    region = geoData.address?.state || '';
                } catch (_) { /* reverse geocode optional */ }

                await fetch('/api/user/location', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ latitude, longitude, city, region })
                });
            } catch (_) { /* silently ignore */ }
        },
        () => { /* permission denied or error – do nothing */ },
        { enableHighAccuracy: false, timeout: 8000, maximumAge: 3600000 }
    );
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    setupNavbar();
    updateCartBadge();
    // Sync location quietly in the background
    syncUserLocation();
});
