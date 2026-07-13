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

            // Status stepper
            const steps = ['Pending Verification', 'Approved', 'Shipped', 'Delivered'];
            const isRejected = order.status === 'Rejected';
            const currentStep = isRejected ? -1 : steps.indexOf(order.status);
            const stepperHtml = `
              <div class="order-status-stepper">
                ${steps.map((step, i) => {
                    let cls = 'step-item';
                    if (isRejected) {
                        cls += ' step-inactive';
                    } else if (i < currentStep) {
                        cls += ' step-done';
                    } else if (i === currentStep) {
                        cls += ' step-active';
                    } else {
                        cls += ' step-inactive';
                    }
                    const icons = ['🕐', '✅', '📦', '🎉'];
                    return `<div class="${cls}">
                      <div class="step-icon">${icons[i]}</div>
                      <div class="step-label">${step === 'Pending Verification' ? 'Pending' : step}</div>
                    </div>${i < steps.length - 1 ? '<div class="step-line' + (i < currentStep && !isRejected ? ' step-line-done' : '') + '"></div>' : ''}`;
                }).join('')}
                ${isRejected ? `<div class="step-item step-rejected-tag"><div class="step-icon">❌</div><div class="step-label">Rejected</div></div>` : ''}
              </div>`;

            // Shipping address block
            const addr = order.shippingAddress;
            const addressHtml = addr ? `
              <div class="order-address-block">
                <div class="order-address-title">📍 Delivery Address</div>
                <div class="order-address-detail">
                  <strong>${addr.fullName}</strong> · 📱 ${addr.phone}<br>
                  ${addr.addressLine1}${addr.addressLine2 ? ', ' + addr.addressLine2 : ''}<br>
                  ${addr.city}, ${addr.state} – ${addr.pincode}
                </div>
              </div>` : '';

            return `
        <div class="order-card">
          <div class="order-card-header">
            <div>
              <strong>Order</strong>
              <span class="order-id">#${order._id.slice(-8).toUpperCase()}</span>
              <span style="color:var(--text-muted);font-size:0.85rem;margin-left:8px;">${date}</span>
            </div>
            <span class="status-badge status-${isRejected ? 'rejected' : (statusClass === 'pending-verification' ? 'pending' : statusClass)}">${order.status}</span>
          </div>
          ${stepperHtml}
          <div class="order-card-products">
            ${order.products.map(p => `
              <div class="order-product-item">
                <img src="${getProductImage(p.image, p._id)}" alt="${p.name}" onerror="this.src='https://picsum.photos/seed/${p._id}/80/80'">
                <span>${p.name} × ${p.quantity}</span>
                <span style="margin-left:auto;color:var(--accent);font-weight:600;">${formatPrice(p.price * p.quantity)}</span>
              </div>
            `).join('')}
          </div>
          ${addressHtml}
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
