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
        if (e.target.value.trim() === '9884746078') {
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

    // ── Admin password field ──
    const pwdGroup = document.createElement('div');
    pwdGroup.className = 'form-group';
    pwdGroup.id = 'adminPasswordGroup';
    pwdGroup.innerHTML = `
        <label for="adminPassword">Admin Password</label>
        <input type="password" id="adminPassword" placeholder="Enter admin password" required>
    `;
    form.insertBefore(pwdGroup, btn);

    // ── Change Password section ──
    const changePwdSection = document.createElement('div');
    changePwdSection.id = 'changePwdSection';
    changePwdSection.style.cssText = 'position:relative; z-index:10;';
    changePwdSection.innerHTML = `
        <button type="button" id="toggleChangePwd" style="
            background:none; border:none; cursor:pointer;
            color:#1B54B8; font-size:0.82rem; font-weight:600;
            padding:4px 0 12px; text-decoration:underline; text-underline-offset:3px;
            display:block; margin-top:4px; pointer-events:auto;
        ">🔑 Change Password</button>

        <div id="changePwdFields" style="display:none; margin-top:4px; position:relative; z-index:10;">
            <div style="margin-bottom:12px;">
                <label style="display:block; font-size:13px; font-weight:600; margin-bottom:6px; color:#2a4a6a;">New Password</label>
                <input type="password" id="newPassword" placeholder="Enter new password (min 6 chars)"
                    style="width:100%; padding:12px 14px; font-size:15px;
                    border:1.5px solid #b8d9f0; border-radius:10px;
                    background:#f0f8ff; color:#0D1B3E; font-family:inherit;
                    outline:none; pointer-events:auto; position:relative; z-index:10;
                    transition:border-color .2s, box-shadow .2s; box-sizing:border-box;">
            </div>
            <div style="margin-bottom:12px;">
                <label style="display:block; font-size:13px; font-weight:600; margin-bottom:6px; color:#2a4a6a;">Confirm New Password</label>
                <input type="password" id="confirmNewPassword" placeholder="Confirm new password"
                    style="width:100%; padding:12px 14px; font-size:15px;
                    border:1.5px solid #b8d9f0; border-radius:10px;
                    background:#f0f8ff; color:#0D1B3E; font-family:inherit;
                    outline:none; pointer-events:auto; position:relative; z-index:10;
                    transition:border-color .2s, box-shadow .2s; box-sizing:border-box;">
            </div>
            <div id="changePwdAlert" style="display:none; padding:9px 14px; border-radius:8px;
                font-size:0.82rem; font-weight:600; margin-bottom:10px;"></div>
            <button type="button" id="doChangePwdBtn" style="
                width:100%; padding:12px; border-radius:10px; border:none; cursor:pointer;
                background:#6B2B3C; color:#fff; font-weight:600;
                font-size:0.9rem; font-family:inherit; margin-bottom:10px;
                pointer-events:auto; position:relative; z-index:10;
            ">Update Password</button>
        </div>
    `;
    form.insertBefore(changePwdSection, btn);

    // Toggle expand/collapse
    document.getElementById('toggleChangePwd').addEventListener('click', () => {
        const fields = document.getElementById('changePwdFields');
        const isHidden = fields.style.display === 'none';
        fields.style.display = isHidden ? 'block' : 'none';
        document.getElementById('toggleChangePwd').textContent =
            isHidden ? '▲ Cancel' : '🔑 Change Password';
    });

    // Handle change-password submit
    document.getElementById('doChangePwdBtn').addEventListener('click', handleChangePassword);
}

async function handleChangePassword() {
    const phone = document.getElementById('loginPhone').value.trim();
    const currentPwd = document.getElementById('adminPassword').value;
    const newPwd = document.getElementById('newPassword').value;
    const confirmPwd = document.getElementById('confirmNewPassword').value;
    const alertBox = document.getElementById('changePwdAlert');
    const btn = document.getElementById('doChangePwdBtn');

    const showChangePwdMsg = (msg, isError) => {
        alertBox.style.display = 'block';
        alertBox.style.background = isError ? 'rgba(255,71,87,0.15)' : 'rgba(46,213,115,0.15)';
        alertBox.style.color = isError ? '#ff8a92' : '#7ff0b0';
        alertBox.style.border = `1px solid ${isError ? 'rgba(255,71,87,0.3)' : 'rgba(46,213,115,0.3)'}`;
        alertBox.textContent = msg;
    };

    if (!currentPwd) return showChangePwdMsg('Enter your current admin password above first.', true);
    if (!newPwd) return showChangePwdMsg('Please enter a new password.', true);
    if (newPwd.length < 6) return showChangePwdMsg('New password must be at least 6 characters.', true);
    if (newPwd !== confirmPwd) return showChangePwdMsg('Passwords do not match.', true);
    if (newPwd === currentPwd) return showChangePwdMsg('New password must be different from current.', true);

    btn.textContent = 'Updating...';
    btn.disabled = true;

    try {
        // Step 1: Login with current credentials to get token
        const loginRes = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone, password: currentPwd })
        });
        const loginData = await loginRes.json();
        if (!loginRes.ok) throw new Error(loginData.message || 'Current password is incorrect.');

        const token = loginData.token;

        // Step 2: Change password using the token
        const changeRes = await fetch('/api/admin/change-password', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ currentPassword: currentPwd, newPassword: newPwd })
        });
        const changeData = await changeRes.json();
        if (!changeRes.ok) throw new Error(changeData.message || 'Failed to change password.');

        showChangePwdMsg('✓ Password changed successfully! You can now log in.', false);
        // Clear new password fields
        document.getElementById('newPassword').value = '';
        document.getElementById('confirmNewPassword').value = '';
        document.getElementById('adminPassword').value = '';
        // Collapse the section
        setTimeout(() => {
            document.getElementById('changePwdFields').style.display = 'none';
            document.getElementById('toggleChangePwd').textContent = '🔑 Change Password';
        }, 2000);

    } catch (err) {
        showChangePwdMsg(err.message, true);
    } finally {
        btn.textContent = 'Update Password';
        btn.disabled = false;
    }
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
