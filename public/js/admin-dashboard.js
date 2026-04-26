// ===== Admin Dashboard JavaScript =====

// ===== AUTH & HELPERS =====
function getToken() { return sessionStorage.getItem('token'); }
function getUser() { return JSON.parse(sessionStorage.getItem('user') || '{}'); }

function formatPrice(price) {
    return `₹${Number(price).toLocaleString('en-IN')}`;
}

function getProductImage(img) {
    return img && img !== '/images/placeholder.png'
        ? img
        : `https://picsum.photos/seed/${Math.random().toString(36).substr(2, 6)}/400/300`;
}

async function apiCall(url, options = {}) {
    const token = getToken();
    const headers = { ...(options.headers || {}) };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }
    const res = await fetch(url, { ...options, headers });
    const data = await res.json();
    if (res.status === 401 || res.status === 403) {
        sessionStorage.removeItem('token');
        sessionStorage.removeItem('user');
        window.location.href = '/';
        return;
    }
    if (!res.ok) throw new Error(data.message || 'Something went wrong');
    return data;
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `${type === 'success' ? '✅' : '❌'} ${message}`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.35s ease reverse';
        setTimeout(() => toast.remove(), 350);
    }, 3500);
}

// ===== AUTH CHECK =====
(function () {
    const token = getToken();
    const user = getUser();
    if (!token || user.role !== 'admin') {
        window.location.href = '/';
        return;
    }
    // Set admin name
    const adminName = document.getElementById('adminName');
    const userAvatar = document.getElementById('userAvatar');
    if (adminName) adminName.textContent = user.name || 'Admin';
    if (userAvatar) userAvatar.textContent = (user.name || 'A').charAt(0).toUpperCase();
})();

// ===== SIDEBAR NAVIGATION =====
document.addEventListener('DOMContentLoaded', () => {
    const sidebarLinks = document.querySelectorAll('.sidebar-link[data-panel]');
    const panels = document.querySelectorAll('.panel');
    const pageTitle = document.getElementById('pageTitle');
    const pageSubtitle = document.getElementById('pageSubtitle');
    const addProductHeaderBtn = document.getElementById('addProductHeaderBtn');

    const titles = {
        dashboard: { title: 'Dashboard Overview', subtitle: "Welcome back! Here's what's happening today." },
        products: { title: 'Manage Products', subtitle: 'Add, edit, and manage your product catalog.' },
        orders: { title: 'Manage Orders', subtitle: 'Review and process customer orders.' },
        stock: { title: 'Stock Management', subtitle: 'Monitor inventory levels and stock status.' },
        users: { title: 'Registered Users', subtitle: 'View all registered customers and their details.' }
    };

    sidebarLinks.forEach(link => {
        link.addEventListener('click', () => {
            const panel = link.dataset.panel;

            // Update active states
            sidebarLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');

            // Switch panels
            panels.forEach(p => p.classList.remove('active'));
            const target = document.getElementById(`panel-${panel}`);
            if (target) target.classList.add('active');

            // Update header
            if (titles[panel]) {
                pageTitle.textContent = titles[panel].title;
                pageSubtitle.textContent = titles[panel].subtitle;
            }

            // Show/hide add product button
            addProductHeaderBtn.style.display = panel === 'products' ? 'inline-flex' : 'none';

            // Load data for panel
            if (panel === 'dashboard') loadDashboard();
            else if (panel === 'products') loadProducts();
            else if (panel === 'orders') loadOrders();
            else if (panel === 'stock') loadStock();
            else if (panel === 'users') loadUsers();

            // Close mobile sidebar
            document.getElementById('sidebar').classList.remove('open');
            document.getElementById('sidebarOverlay').classList.remove('active');
        });
    });

    // Mobile sidebar
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');

    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('active');
    });
    overlay.addEventListener('click', () => {
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
    });

    // Logout
    document.getElementById('logoutBtn').addEventListener('click', () => {
        sessionStorage.removeItem('token');
        sessionStorage.removeItem('user');
        window.location.href = '/';
    });

    // Add Product header button
    addProductHeaderBtn.addEventListener('click', () => openProductModal());

    // Load initial dashboard
    loadDashboard();
});

// ===== DASHBOARD =====
async function loadDashboard() {
    try {
        const stats = await apiCall('/api/admin/stats');

        // Update stat cards
        document.getElementById('statProducts').textContent = stats.totalProducts;
        document.getElementById('statActiveProducts').textContent = stats.activeProducts;
        document.getElementById('statOrders').textContent = stats.totalOrders;
        document.getElementById('statPendingOrders').textContent = stats.pendingOrders;
        document.getElementById('statRevenue').textContent = formatPrice(stats.totalRevenue);
        document.getElementById('statUsers').textContent = stats.totalUsers;

        // Update breakdown
        document.getElementById('breakdownPending').textContent = stats.pendingOrders;
        document.getElementById('breakdownApproved').textContent = stats.approvedOrders;
        document.getElementById('breakdownShipped').textContent = stats.shippedOrders;
        document.getElementById('breakdownDelivered').textContent = stats.deliveredOrders;
        document.getElementById('breakdownRejected').textContent = stats.rejectedOrders;

        // Pending badge
        const pendingBadge = document.getElementById('pendingBadge');
        if (stats.pendingOrders > 0) {
            pendingBadge.textContent = stats.pendingOrders;
            pendingBadge.style.display = 'inline-flex';
        } else {
            pendingBadge.style.display = 'none';
        }

        // Low stock badge
        const lowStockBadge = document.getElementById('lowStockBadge');
        if (stats.lowStockProducts.length > 0) {
            lowStockBadge.textContent = stats.lowStockProducts.length;
            lowStockBadge.style.display = 'inline-flex';
        } else {
            lowStockBadge.style.display = 'none';
        }

        // Low stock alerts
        const alertContainer = document.getElementById('lowStockAlerts');
        if (stats.lowStockProducts.length > 0) {
            alertContainer.innerHTML = `
                <div class="low-stock-alert">
                    <div class="alert-icon">⚠️</div>
                    <div class="alert-text">
                        <h4>Low Stock Alert</h4>
                        <p>${stats.lowStockProducts.map(p => `${p.name} (${p.stock} left)`).join(' • ')}</p>
                    </div>
                </div>
            `;
        } else {
            alertContainer.innerHTML = '';
        }

        // Recent orders
        const recentList = document.getElementById('recentOrdersList');
        if (stats.recentOrders.length === 0) {
            recentList.innerHTML = '<div class="empty-state"><p>No orders yet</p></div>';
        } else {
            recentList.innerHTML = stats.recentOrders.map(order => {
                const statusClass = getStatusClass(order.status);
                return `
                    <div class="mini-order-card">
                        <div class="mini-order-top">
                            <span class="mini-order-id">#${order._id.slice(-8).toUpperCase()}</span>
                            <span class="badge ${statusClass}">${order.status}</span>
                        </div>
                        <div class="mini-order-customer">${order.user?.name || 'Unknown'}</div>
                        <div class="mini-order-total">${formatPrice(order.totalAmount)}</div>
                    </div>
                `;
            }).join('');
        }
    } catch (error) {
        showToast('Error loading dashboard data', 'error');
    }
}

function getStatusClass(status) {
    const map = {
        'Pending Verification': 'badge-warning',
        'Approved': 'badge-success',
        'Rejected': 'badge-danger',
        'Shipped': 'badge-primary',
        'Delivered': 'badge-info'
    };
    return map[status] || 'badge-neutral';
}

// ===== PRODUCTS MANAGEMENT =====
async function loadProducts() {
    const loading = document.getElementById('productsLoading');
    const body = document.getElementById('productsBody');
    loading.style.display = 'flex';

    try {
        const token = getToken();
        const res = await fetch('/api/products/all', { headers: { 'Authorization': `Bearer ${token}` } });
        const products = await res.json();
        loading.style.display = 'none';

        if (products.length === 0) {
            body.innerHTML = '<tr><td colspan="7"><div class="empty-state"><div class="icon">📦</div><h3>No products</h3><p>Add your first product</p></div></td></tr>';
            return;
        }

        body.innerHTML = products.map(p => {
            const stockClass = p.stock < 5 ? 'stock-low' : p.stock < 15 ? 'stock-medium' : 'stock-ok';
            const rowClass = p.stock < 5 ? 'row-low-stock' : '';
            return `
                <tr class="${rowClass}">
                    <td><img src="${getProductImage(p.image)}" alt="${p.name}" onerror="this.src='https://picsum.photos/seed/${p._id}/100/100'"></td>
                    <td><strong>${p.name}</strong></td>
                    <td>${formatPrice(p.price)}</td>
                    <td><span class="badge badge-neutral">${p.category || 'General'}</span></td>
                    <td class="${stockClass}">${p.stock}${p.stock < 5 ? ' ⚠️' : ''}</td>
                    <td><span class="badge ${p.isActive ? 'badge-success' : 'badge-danger'}">${p.isActive ? '● Active' : '● Inactive'}</span></td>
                    <td>
                        <div class="action-btns">
                            <button class="btn btn-secondary btn-xs" onclick='editProduct(${JSON.stringify(p).replace(/'/g, "&#39;")})'>✏️ Edit</button>
                            <button class="btn btn-danger btn-xs" onclick="deleteProduct('${p._id}')">🗑️</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        loading.style.display = 'none';
        showToast('Error loading products', 'error');
    }
}

// Product Modal
function openProductModal(product = null) {
    const modal = document.getElementById('productModal');
    const title = document.getElementById('modalTitle');
    const form = document.getElementById('productForm');

    if (product) {
        title.textContent = 'Edit Product';
        document.getElementById('productId').value = product._id;
        document.getElementById('prodName').value = product.name;
        document.getElementById('prodPrice').value = product.price;
        document.getElementById('prodCategory').value = product.category || '';
        document.getElementById('prodStock').value = product.stock;
        document.getElementById('prodDesc').value = product.description;
        document.getElementById('imageFileName').textContent = '';
    } else {
        title.textContent = 'Add New Product';
        form.reset();
        document.getElementById('productId').value = '';
        document.getElementById('imageFileName').textContent = '';
    }

    modal.classList.add('active');
}

// Setup modal events
document.addEventListener('DOMContentLoaded', () => {
    const productModal = document.getElementById('productModal');
    const screenshotModal = document.getElementById('screenshotModal');

    // Close modals
    document.getElementById('closeProductModal').addEventListener('click', () => productModal.classList.remove('active'));
    document.getElementById('closeScreenshotModal').addEventListener('click', () => screenshotModal.classList.remove('active'));
    productModal.addEventListener('click', e => { if (e.target === productModal) productModal.classList.remove('active'); });
    screenshotModal.addEventListener('click', e => { if (e.target === screenshotModal) screenshotModal.classList.remove('active'); });

    // Add Product button (inside panel)
    document.getElementById('addProductBtn').addEventListener('click', () => openProductModal());

    // Image upload display
    document.getElementById('prodImage').addEventListener('change', (e) => {
        const fileName = e.target.files[0]?.name || '';
        document.getElementById('imageFileName').textContent = fileName;
    });

    // Save product form
    document.getElementById('productForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = document.getElementById('productId').value;
        const saveBtn = document.getElementById('saveProductBtn');
        saveBtn.textContent = '⏳ Saving...';
        saveBtn.disabled = true;

        const formData = new FormData();
        formData.append('name', document.getElementById('prodName').value);
        formData.append('price', document.getElementById('prodPrice').value);
        formData.append('category', document.getElementById('prodCategory').value);
        formData.append('stock', document.getElementById('prodStock').value);
        formData.append('description', document.getElementById('prodDesc').value);
        const imageFile = document.getElementById('prodImage').files[0];
        if (imageFile) formData.append('image', imageFile);

        try {
            const token = getToken();
            const url = id ? `/api/products/${id}` : '/api/products';
            const method = id ? 'PUT' : 'POST';
            const res = await fetch(url, { method, headers: { 'Authorization': `Bearer ${token}` }, body: formData });
            const data = await res.json();
            if (!res.ok) throw new Error(data.message);

            showToast(data.message);
            productModal.classList.remove('active');
            loadProducts();
        } catch (error) {
            showToast(error.message, 'error');
        } finally {
            saveBtn.textContent = '💾 Save Product';
            saveBtn.disabled = false;
        }
    });
});

// Global functions for inline handlers
window.editProduct = function (product) {
    openProductModal(product);
};

window.deleteProduct = async function (id) {
    if (!confirm('Are you sure you want to delete this product? This cannot be undone.')) return;
    try {
        await apiCall(`/api/products/${id}`, { method: 'DELETE' });
        showToast('Product deleted successfully');
        loadProducts();
    } catch (error) {
        showToast(error.message, 'error');
    }
};

// ===== ORDERS MANAGEMENT =====
async function loadOrders() {
    const loading = document.getElementById('ordersLoading');
    const body = document.getElementById('ordersBody');
    loading.style.display = 'flex';

    try {
        const orders = await apiCall('/api/orders');
        loading.style.display = 'none';

        if (orders.length === 0) {
            body.innerHTML = '<tr><td colspan="8"><div class="empty-state"><div class="icon">🧾</div><h3>No orders yet</h3><p>Orders will appear here when customers place them.</p></div></td></tr>';
            return;
        }

        body.innerHTML = orders.map(order => {
            const statusClass = getStatusClass(order.status);
            return `
                <tr>
                    <td><span style="font-family:monospace;font-size:0.8rem;color:var(--text-muted);">#${order._id.slice(-8).toUpperCase()}</span></td>
                    <td>
                        <strong>${order.user?.name || 'N/A'}</strong><br>
                        <small style="color:var(--text-muted);">📱 ${order.user?.phone || ''}</small>
                    </td>
                    <td>${order.products.map(p => `<div style="margin-bottom:2px;">${p.name} <span style="color:var(--text-muted);">×${p.quantity}</span></div>`).join('')}</td>
                    <td><strong style="color:var(--accent);">${formatPrice(order.totalAmount)}</strong></td>
                    <td><span style="font-family:monospace;font-size:0.82rem;">${order.transactionId}</span></td>
                    <td><button class="screenshot-btn" onclick="viewScreenshot('${order.paymentScreenshot}')">📸 View</button></td>
                    <td><span class="badge ${statusClass}">${order.status}</span></td>
                    <td>
                        <div class="action-btns" style="flex-direction:column;gap:4px;">
                            ${order.status === 'Pending Verification' ? `
                                <button class="btn btn-success btn-xs" onclick="updateOrderStatus('${order._id}', 'Approved')">✅ Approve</button>
                                <button class="btn btn-danger btn-xs" onclick="updateOrderStatus('${order._id}', 'Rejected')">❌ Reject</button>
                            ` : ''}
                            ${order.status === 'Approved' ? `
                                <button class="btn btn-primary btn-xs" onclick="updateOrderStatus('${order._id}', 'Shipped')">📦 Ship</button>
                            ` : ''}
                            ${order.status === 'Shipped' ? `
                                <button class="btn btn-xs" style="background:var(--accent);color:#fff;" onclick="updateOrderStatus('${order._id}', 'Delivered')">✔️ Delivered</button>
                            ` : ''}
                            ${order.status === 'Delivered' || order.status === 'Rejected' ? `
                                <span style="color:var(--text-muted);font-size:0.78rem;">No actions</span>
                            ` : ''}
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        loading.style.display = 'none';
        showToast('Error loading orders', 'error');
    }
}

window.viewScreenshot = function (src) {
    document.getElementById('screenshotImage').src = src;
    document.getElementById('screenshotModal').classList.add('active');
};

window.updateOrderStatus = async function (orderId, status) {
    const confirmMsg = status === 'Approved'
        ? 'Approve this order? Stock will be automatically deducted.'
        : `Change order status to "${status}"?`;

    if (!confirm(confirmMsg)) return;

    try {
        await apiCall(`/api/orders/${orderId}/status`, {
            method: 'PUT',
            body: JSON.stringify({ status })
        });
        showToast(`Order status updated to "${status}"`);
        loadOrders();
        // Refresh dashboard stats and stock
        loadDashboard();
    } catch (error) {
        showToast(error.message, 'error');
    }
};

// ===== STOCK MANAGEMENT =====
async function loadStock() {
    const loading = document.getElementById('stockLoading');
    const body = document.getElementById('stockBody');
    const alertBanner = document.getElementById('stockAlertBanner');
    loading.style.display = 'flex';

    try {
        const products = await apiCall('/api/admin/stock');
        loading.style.display = 'none';

        // Count low stock
        const lowStockItems = products.filter(p => p.stock < 5 && p.isActive);

        // Show alert banner
        if (lowStockItems.length > 0) {
            alertBanner.innerHTML = `
                <div class="low-stock-alert">
                    <div class="alert-icon">🚨</div>
                    <div class="alert-text">
                        <h4>${lowStockItems.length} product${lowStockItems.length > 1 ? 's' : ''} with critically low stock!</h4>
                        <p>Products with stock below 5 units need immediate restocking.</p>
                    </div>
                </div>
            `;
        } else {
            alertBanner.innerHTML = '';
        }

        if (products.length === 0) {
            body.innerHTML = '<tr><td colspan="6"><div class="empty-state"><div class="icon">📦</div><h3>No products</h3></div></td></tr>';
            return;
        }

        body.innerHTML = products.map(p => {
            let stockClass, statusBadge;
            if (p.stock === 0) {
                stockClass = 'stock-low';
                statusBadge = '<span class="badge badge-danger">❌ Out of Stock</span>';
            } else if (p.stock < 5) {
                stockClass = 'stock-low';
                statusBadge = '<span class="badge badge-danger">⚠️ Low Stock</span>';
            } else if (p.stock < 15) {
                stockClass = 'stock-medium';
                statusBadge = '<span class="badge badge-warning">🔶 Medium</span>';
            } else {
                stockClass = 'stock-ok';
                statusBadge = '<span class="badge badge-success">✅ In Stock</span>';
            }
            const rowClass = p.stock < 5 ? 'row-low-stock' : '';

            return `
                <tr class="${rowClass}">
                    <td><strong>${p.name}</strong></td>
                    <td><span class="badge badge-neutral">${p.category || 'General'}</span></td>
                    <td>${formatPrice(p.price)}</td>
                    <td class="${stockClass}" style="font-size:1rem;">${p.stock}</td>
                    <td>${statusBadge}</td>
                    <td>
                        <div class="action-btns">
                            <input type="number" class="stock-edit-input" id="stock-${p._id}" value="${p.stock}" min="0">
                            <button class="btn btn-success btn-xs" onclick="updateStock('${p._id}')">Update</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        loading.style.display = 'none';
        showToast('Error loading stock data', 'error');
    }
}

window.updateStock = async function (productId) {
    const input = document.getElementById(`stock-${productId}`);
    const newStock = parseInt(input.value);

    if (isNaN(newStock) || newStock < 0) {
        showToast('Please enter a valid stock quantity', 'error');
        return;
    }

    try {
        await apiCall(`/api/admin/stock/${productId}`, {
            method: 'PUT',
            body: JSON.stringify({ stock: newStock })
        });
        showToast('Stock updated successfully');
        loadStock();
    } catch (error) {
        showToast(error.message, 'error');
    }
};

// ===== USERS MANAGEMENT =====
async function loadUsers() {
    const loading = document.getElementById('usersLoading');
    const body = document.getElementById('usersBody');
    const countBadge = document.getElementById('totalUsersCount');
    loading.style.display = 'flex';

    try {
        const users = await apiCall('/api/admin/users');
        loading.style.display = 'none';

        countBadge.textContent = `${users.length} user${users.length !== 1 ? 's' : ''}`;

        if (users.length === 0) {
            body.innerHTML = '<tr><td colspan="5"><div class="empty-state"><div class="icon">👥</div><h3>No registered users</h3><p>Users will appear here when they sign up.</p></div></td></tr>';
            return;
        }

        body.innerHTML = users.map((user, idx) => {
            const date = new Date(user.createdAt);
            const formattedDate = date.toLocaleDateString('en-IN', {
                day: '2-digit', month: 'short', year: 'numeric'
            });
            const formattedTime = date.toLocaleTimeString('en-IN', {
                hour: '2-digit', minute: '2-digit'
            });
            return `
                <tr>
                    <td style="font-weight:600;color:var(--text-muted);">${idx + 1}</td>
                    <td><strong>${user.name}</strong></td>
                    <td style="font-family:monospace;font-size:0.9rem;">📱 ${user.phone}</td>
                    <td>
                        <span class="badge ${user.isVerified ? 'badge-success' : 'badge-warning'}">
                            ${user.isVerified ? '✅ Verified' : '⏳ Pending'}
                        </span>
                    </td>
                    <td>
                        <div>${formattedDate}</div>
                        <small style="color:var(--text-muted);">${formattedTime}</small>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        loading.style.display = 'none';
        showToast('Error loading users', 'error');
    }
}
