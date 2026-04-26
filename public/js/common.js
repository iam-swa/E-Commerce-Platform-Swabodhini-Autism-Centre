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

    // Guard: only parse JSON when the server actually sends JSON.
    // Without this, an HTML error page (e.g. Flask 500 debug page) causes
    // "Unexpected token '<'" and the error message becomes unusable.
    const contentType = res.headers.get('content-type') || '';
    let data;
    if (contentType.includes('application/json')) {
        data = await res.json();
    } else {
        // Server returned HTML/text — surface a clean error instead of a
        // cryptic JSON parse failure.
        const text = await res.text();
        console.error(`[API] Non-JSON response from ${url} (${res.status}):`, text.slice(0, 300));
        throw new Error(`Server error (${res.status}). Please try again.`);
    }

    if (res.status === 401) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/';
        return;
    }
    if (!res.ok) throw new Error(data.message || data.error || 'Something went wrong');
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
            localStorage.removeItem('token');
            localStorage.removeItem('user');
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

// Product image fallback — uses a deterministic seed so the same product
// always shows the same fallback image (no more "random" images on reload).
function getProductImage(img) {
    if (img && img !== '/images/placeholder.png') {
        return img;
    }
    // Generate a stable seed from the image path (or 'default')
    const seed = (img || 'default').split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
    return `https://picsum.photos/seed/swa${seed}/400/300`;
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
