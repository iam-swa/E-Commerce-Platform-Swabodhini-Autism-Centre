// Admin Dashboard
document.addEventListener('DOMContentLoaded', () => {
    const user = getUser();
    if (user.role !== 'admin') {
        window.location.href = '/landing';
        return;
    }

    // Tab switching
    const tabs = document.querySelectorAll('.admin-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('productsTab').style.display = tab.dataset.tab === 'products' ? 'block' : 'none';
            document.getElementById('ordersTab').style.display = tab.dataset.tab === 'orders' ? 'block' : 'none';
            if (tab.dataset.tab === 'orders') loadOrders();
        });
    });

    // Product Modal
    const modal = document.getElementById('productModal');
    const closeModal = document.getElementById('closeModal');
    document.getElementById('addProductBtn').addEventListener('click', () => {
        document.getElementById('modalTitle').textContent = 'Add Product';
        document.getElementById('productForm').reset();
        document.getElementById('productId').value = '';
        modal.classList.add('active');
    });
    closeModal.addEventListener('click', () => modal.classList.remove('active'));
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.remove('active'); });

    // Screenshot Modal
    const ssModal = document.getElementById('screenshotModal');
    document.getElementById('closeScreenshot').addEventListener('click', () => ssModal.classList.remove('active'));
    ssModal.addEventListener('click', (e) => { if (e.target === ssModal) ssModal.classList.remove('active'); });

    // Save Product
    document.getElementById('productForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = document.getElementById('productId').value;
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
            modal.classList.remove('active');
            loadProducts();
        } catch (error) {
            showToast(error.message, 'error');
        }
    });

    loadProducts();

    async function loadProducts() {
        const loading = document.getElementById('productsLoading');
        const body = document.getElementById('productsBody');
        loading.style.display = 'flex';
        try {
            const token = getToken();
            const res = await fetch('/api/products/all', { headers: { 'Authorization': `Bearer ${token}` } });
            const products = await res.json();
            loading.style.display = 'none';
            body.innerHTML = products.map(p => `
        <tr>
          <td><img src="${getProductImage(p.image)}" alt="${p.name}" onerror="this.src='https://picsum.photos/seed/${p._id}/100/100'"></td>
          <td><strong>${p.name}</strong></td>
          <td>${formatPrice(p.price)}</td>
          <td>${p.category}</td>
          <td>${p.stock}</td>
          <td><span class="status-badge ${p.isActive ? 'status-approved' : 'status-rejected'}">${p.isActive ? 'Active' : 'Inactive'}</span></td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick='editProduct(${JSON.stringify(p).replace(/'/g, "&#39;")})' style="margin-right:4px;">✏️</button>
            <button class="btn btn-danger btn-sm" onclick="deleteProduct('${p._id}')">🗑️</button>
          </td>
        </tr>
      `).join('');
        } catch (error) {
            loading.style.display = 'none';
            showToast('Error loading products', 'error');
        }
    }

    window.editProduct = (product) => {
        document.getElementById('modalTitle').textContent = 'Edit Product';
        document.getElementById('productId').value = product._id;
        document.getElementById('prodName').value = product.name;
        document.getElementById('prodPrice').value = product.price;
        document.getElementById('prodCategory').value = product.category;
        document.getElementById('prodStock').value = product.stock;
        document.getElementById('prodDesc').value = product.description;
        modal.classList.add('active');
    };

    window.deleteProduct = async (id) => {
        if (!confirm('Are you sure you want to delete this product?')) return;
        try {
            await apiCall(`/api/products/${id}`, { method: 'DELETE' });
            showToast('Product deleted');
            loadProducts();
        } catch (error) {
            showToast(error.message, 'error');
        }
    };

    async function loadOrders() {
        const loading = document.getElementById('ordersLoading');
        const body = document.getElementById('ordersBody');
        loading.style.display = 'flex';
        try {
            const orders = await apiCall('/api/orders');
            loading.style.display = 'none';
            body.innerHTML = orders.map(order => {
                const sc = order.status.toLowerCase().replace(/\s+/g, '-');
                const badgeClass = sc === 'pending-verification' ? 'pending' : sc;
                return `<tr>
          <td style="font-size:0.8rem;">#${order._id.slice(-8).toUpperCase()}</td>
          <td>${order.user?.name || 'N/A'}<br><small style="color:var(--text-muted);">📱 ${order.user?.phone || ''}</small></td>
          <td>${order.products.map(p => `${p.name} ×${p.quantity}`).join('<br>')}</td>
          <td><strong>${formatPrice(order.totalAmount)}</strong></td>
          <td style="font-size:0.8rem;">${order.transactionId}</td>
          <td><button class="btn btn-secondary btn-sm" onclick="viewScreenshot('${order.paymentScreenshot}')">📸 View</button></td>
          <td><span class="status-badge status-${badgeClass}">${order.status}</span></td>
          <td>
            <select onchange="updateOrderStatus('${order._id}', this.value)" style="background:var(--bg-input);color:var(--text-primary);border:1px solid var(--border);border-radius:6px;padding:6px 8px;font-size:0.8rem;">
              <option ${order.status === 'Pending Verification' ? 'selected' : ''}>Pending Verification</option>
              <option ${order.status === 'Approved' ? 'selected' : ''}>Approved</option>
              <option ${order.status === 'Rejected' ? 'selected' : ''}>Rejected</option>
              <option ${order.status === 'Shipped' ? 'selected' : ''}>Shipped</option>
              <option ${order.status === 'Delivered' ? 'selected' : ''}>Delivered</option>
            </select>
          </td>
        </tr>`;
            }).join('');
        } catch (error) {
            loading.style.display = 'none';
            showToast('Error loading orders', 'error');
        }
    }

    window.viewScreenshot = (src) => {
        document.getElementById('screenshotImage').src = src;
        ssModal.classList.add('active');
    };

    window.updateOrderStatus = async (orderId, status) => {
        try {
            await apiCall(`/api/orders/${orderId}/status`, {
                method: 'PUT',
                body: JSON.stringify({ status })
            });
            showToast(`Order status updated to "${status}"`);
            loadOrders();
        } catch (error) {
            showToast(error.message, 'error');
        }
    };
});
