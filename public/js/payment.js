// Payment Page
document.addEventListener('DOMContentLoaded', () => {
    const cart = JSON.parse(localStorage.getItem('checkoutCart') || '[]');
    const total = localStorage.getItem('checkoutTotal') || 0;

    if (cart.length === 0) {
        window.location.href = '/cart';
        return;
    }

    // Render order summary
    const orderItems = document.getElementById('orderItems');
    orderItems.innerHTML = cart.map(item => {
        const p = item.product;
        return `<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:0.9rem;color:var(--text-secondary);">
      <span>${p.name} × ${item.quantity}</span>
      <span>${formatPrice(p.price * item.quantity)}</span>
    </div>`;
    }).join('') + '<hr style="border-color:var(--border);margin:8px 0;">';

    document.getElementById('paymentTotal').textContent = formatPrice(total);

    // File upload display
    const fileInput = document.getElementById('screenshotInput');
    const fileName = document.getElementById('fileName');
    fileInput.addEventListener('change', () => {
        if (fileInput.files[0]) {
            fileName.textContent = fileInput.files[0].name;
        }
    });

    // Submit order
    document.getElementById('paymentForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = document.getElementById('submitOrderBtn');
        btn.textContent = 'Processing...';
        btn.disabled = true;

        try {
            const formData = new FormData();
            formData.append('paymentScreenshot', fileInput.files[0]);
            formData.append('transactionId', document.getElementById('transactionId').value);
            formData.append('totalAmount', total);

            const products = cart.map(item => ({
                product: item.product._id,
                name: item.product.name,
                price: item.product.price,
                quantity: item.quantity,
                image: item.product.image
            }));
            formData.append('products', JSON.stringify(products));

            const token = getToken();
            const res = await fetch('/api/orders', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.message);

            // Clear checkout data
            localStorage.removeItem('checkoutCart');
            localStorage.removeItem('checkoutTotal');

            showToast('Order placed successfully! 🎉');

            setTimeout(() => {
                window.location.href = '/orders';
            }, 1500);
        } catch (error) {
            showToast(error.message, 'error');
        } finally {
            btn.textContent = '✅ Confirm Order';
            btn.disabled = false;
        }
    });
});
