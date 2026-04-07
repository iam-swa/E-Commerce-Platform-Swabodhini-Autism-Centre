// My Orders Page
document.addEventListener('DOMContentLoaded', async () => {
    const spinner = document.getElementById('loadingSpinner');
    const content = document.getElementById('ordersContent');
    const noOrders = document.getElementById('noOrders');

    try {
        const orders = await apiCall('/api/orders/my');
        spinner.style.display = 'none';

        if (!orders || orders.length === 0) {
            noOrders.style.display = 'block';
            return;
        }

        content.innerHTML = orders.map(order => {
            const statusClass = order.status.toLowerCase().replace(/\s+/g, '-');
            const date = new Date(order.createdAt).toLocaleDateString('en-IN', {
                day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
            });
            return `
        <div class="order-card">
          <div class="order-card-header">
            <div>
              <strong>Order</strong>
              <span class="order-id">#${order._id.slice(-8).toUpperCase()}</span>
              <span style="color:var(--text-muted);font-size:0.85rem;margin-left:8px;">${date}</span>
            </div>
            <span class="status-badge status-${statusClass === 'pending-verification' ? 'pending' : statusClass}">${order.status}</span>
          </div>
          <div class="order-card-products">
            ${order.products.map(p => `
              <div class="order-product-item">
                <img src="${getProductImage(p.image)}" alt="${p.name}" onerror="this.src='https://picsum.photos/80/80'">
                <span>${p.name} × ${p.quantity}</span>
                <span style="margin-left:auto;color:var(--accent);font-weight:600;">${formatPrice(p.price * p.quantity)}</span>
              </div>
            `).join('')}
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;padding-top:0.8rem;border-top:1px solid var(--border);">
            <span style="font-size:0.85rem;color:var(--text-muted);">Transaction: ${order.transactionId}</span>
            <strong style="color:var(--accent);font-size:1.1rem;">${formatPrice(order.totalAmount)}</strong>
          </div>
        </div>
      `;
        }).join('');
    } catch (error) {
        spinner.style.display = 'none';
        content.innerHTML = `<div class="cart-empty"><div class="icon">❌</div><h3>Error loading orders</h3><p>${error.message}</p></div>`;
    }
});
