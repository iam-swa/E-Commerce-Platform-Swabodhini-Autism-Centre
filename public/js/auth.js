// Check if user is already logged in
if (sessionStorage.getItem('token')) {
    const user = JSON.parse(sessionStorage.getItem('user') || '{}');
    if (user.role === 'admin') {
        window.location.href = '/admin-dashboard';
    } else {
        window.location.href = '/landing';
    }
}

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
    alert.textContent = message;
    alert.className = `alert alert-${type}`;
    setTimeout(() => { alert.className = 'alert'; }, 5000);
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

        sessionStorage.setItem('token', data.token);
        sessionStorage.setItem('user', JSON.stringify(data.user));

        showAlert('loginAlert', 'Login successful! Redirecting...', 'success');
        setTimeout(() => {
            window.location.href = data.user.role === 'admin' ? '/admin-dashboard' : '/landing';
        }, 500);
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
    const phone = document.getElementById('signupPhone').value.trim();

    // Validate phone
    if (!/^\d{10}$/.test(phone)) {
        showAlert('signupAlert', 'Please enter a valid 10-digit phone number.', 'error');
        btn.textContent = 'Create Account';
        btn.disabled = false;
        return;
    }

    try {
        const res = await fetch('/api/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, phone })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.message);

        sessionStorage.setItem('token', data.token);
        sessionStorage.setItem('user', JSON.stringify(data.user));

        showAlert('signupAlert', 'Account created! Redirecting...', 'success');
        setTimeout(() => { window.location.href = '/landing'; }, 500);
    } catch (error) {
        showAlert('signupAlert', error.message, 'error');
    } finally {
        btn.textContent = 'Create Account';
        btn.disabled = false;
    }
});
