// ── Page transition helper ──
function navigateTo(url) {
    document.body.classList.add('page-exit');
    setTimeout(function() { window.location.href = url; }, 340);
}

// ── Check if user is already logged in with valid token ──
(async function initAuth() {
    const token = localStorage.getItem('token');
    if (!token) return;

    try {
        const res = await fetch('/api/auth/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            if (data.user && data.user.role === 'admin') {
                navigateTo('/admin-dashboard');
            } else {
                navigateTo('/landing');
            }
        } else {
            // Token is expired or invalid on the current DB
            localStorage.clear();
        }
    } catch (e) {
        localStorage.clear();
    }
})();

const loginSection = document.getElementById('loginSection');
const signupSection = document.getElementById('signupSection');

document.getElementById('showSignup').addEventListener('click', (e) => {
    e.preventDefault();
    loginSection.style.display = 'none';
    signupSection.style.display = 'block';
});

document.getElementById('showLogin').addEventListener('click', (e) => {
    e.preventDefault();
    signupSection.style.display = 'none';
    loginSection.style.display = 'block';
});

function showAlert(elementId, message, type) {
    const alert = document.getElementById(elementId);
    if (!alert) return;
    alert.textContent = message;
    alert.className = `alert show ${type}`;
    setTimeout(() => { alert.className = 'alert'; }, 6000);
}

// Auto-detect admin phone number as user types
const loginPhoneInput = document.getElementById('loginPhone');
if (loginPhoneInput) {
    loginPhoneInput.addEventListener('input', (e) => {
        if (e.target.value.trim() === '7358665496') {
            showAdminPasswordField();
        }
    });
}

// ===== LOGIN (using phone number only, admin needs password) =====
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('loginBtn');
    btn.textContent = 'Logging in...';
    btn.disabled = true;

    const phone = document.getElementById('loginPhone').value.trim();

    try {
        // First attempt: login with just phone
        const loginData = { phone };

        // Check if admin password field exists and has value
        const adminPwdField = document.getElementById('adminPassword');
        if (adminPwdField && adminPwdField.value) {
            loginData.password = adminPwdField.value;
        }

        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(loginData)
        });
        const data = await res.json();

        // If admin requires password, show password field
        if (data.requirePassword) {
            showAdminPasswordField();
            showAlert('loginAlert', 'Admin account detected. Please enter your password.', 'error');
            btn.textContent = 'Login';
            btn.disabled = false;
            return;
        }

        if (!res.ok) throw new Error(data.message);

        localStorage.setItem('token', data.token);
        localStorage.setItem('user', JSON.stringify(data.user));

        navigateTo(data.user.role === 'admin' ? '/admin-dashboard' : '/landing');

    } catch (error) {
        showAlert('loginAlert', error.message, 'error');
    } finally {
        btn.textContent = 'Login';
        btn.disabled = false;
    }
});

function showAdminPasswordField() {
    if (document.getElementById('adminPasswordGroup')) return; // already shown
    const form = document.getElementById('loginForm');
    const btn = document.getElementById('loginBtn');
    const div = document.createElement('div');
    div.className = 'form-group';
    div.id = 'adminPasswordGroup';
    div.innerHTML = `
        <label for="adminPassword">Admin Password</label>
        <input type="password" id="adminPassword" placeholder="Enter admin password" required>
    `;
    form.insertBefore(div, btn);
}

// ===== SIGNUP (name + phone only) =====
document.getElementById('signupForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('signupBtn');
    btn.textContent = 'Creating Account...';
    btn.disabled = true;

    const name = document.getElementById('signupName').value.trim();
    const email = document.getElementById('signupEmail').value.trim();
    const phone = document.getElementById('signupPhone').value.trim();

    // Validate phone
    if (!/^\d{10}$/.test(phone)) {
        showAlert('signupAlert', 'Please enter a valid 10-digit phone number.', 'error');
        btn.textContent = 'Create Account';
        btn.disabled = false;
        return;
    }
    
    // Validate email
    if (!email || !/\S+@\S+\.\S+/.test(email)) {
        showAlert('signupAlert', 'Please enter a valid email address.', 'error');
        btn.textContent = 'Create Account';
        btn.disabled = false;
        return;
    }

    try {
        const res = await fetch('/api/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email, phone })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.message);

        localStorage.setItem('token', data.token);
        localStorage.setItem('user', JSON.stringify(data.user));

        navigateTo('/landing');

    } catch (error) {
        showAlert('signupAlert', error.message, 'error');
    } finally {
        btn.textContent = 'Create Account';
        btn.disabled = false;
    }
});
