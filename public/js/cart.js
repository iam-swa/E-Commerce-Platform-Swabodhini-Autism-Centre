// Cart Page
document.addEventListener('DOMContentLoaded', async () => {
    const spinner = document.getElementById('loadingSpinner');
    const cartContent = document.getElementById('cartContent');
    const cartEmpty = document.getElementById('cartEmpty');

    await loadCart();

    async function loadCart() {
        try {
            spinner.style.display = 'flex';
            cartContent.style.display = 'none';
            cartEmpty.style.display = 'none';

            const cart = await apiCall('/api/cart');
            spinner.style.display = 'none';

            if (!cart || cart.length === 0) {
                cartEmpty.style.display = 'block';
                return;
            }

            cartContent.style.display = 'block';
            renderCart(cart);
        } catch (error) {
            spinner.style.display = 'none';
            showToast(error.message, 'error');
        }
    }

    function renderCart(cart) {
        const cartItems = document.getElementById('cartItems');
        const cartSummary = document.getElementById('cartSummary');
        let total = 0;

        cartItems.innerHTML = cart.map(item => {
            const product = item.product;
            if (!product) return '';
            const itemTotal = product.price * item.quantity;
            total += itemTotal;
            return `
        <div class="cart-item">
          <img class="cart-item-img" src="${getProductImage(product.image)}" alt="${product.name}"
               onerror="this.src='https://picsum.photos/seed/${product._id}/200/200'">
          <div class="cart-item-info">
            <h3>${product.name}</h3>
            <div class="price">${formatPrice(product.price)}</div>
          </div>
          <div class="cart-item-qty">
            <button onclick="updateQty('${product._id}', ${item.quantity - 1})">−</button>
            <span>${item.quantity}</span>
            <button onclick="updateQty('${product._id}', ${item.quantity + 1})">+</button>
          </div>
          <button class="cart-item-remove" onclick="removeItem('${product._id}')">🗑️</button>
        </div>
      `;
        }).join('');

        cartSummary.style.display = 'block';
        document.getElementById('cartTotal').textContent = formatPrice(total);

        document.getElementById('proceedBtn').onclick = () => {
            // Store cart data for payment page
            localStorage.setItem('checkoutCart', JSON.stringify(cart));
            localStorage.setItem('checkoutTotal', total);
            window.location.href = '/payment';
        };
    }

    // Make functions global
    window.updateQty = async (productId, qty) => {
        try {
            if (qty <= 0) {
                await apiCall(`/api/cart/${productId}`, { method: 'DELETE' });
            } else {
                await apiCall(`/api/cart/${productId}`, {
                    method: 'PUT',
                    body: JSON.stringify({ quantity: qty })
                });
            }
            await loadCart();
            updateCartBadge();
        } catch (error) {
            showToast(error.message, 'error');
        }
    };

    window.removeItem = async (productId) => {
        try {
            await apiCall(`/api/cart/${productId}`, { method: 'DELETE' });
            showToast('Item removed from cart');
            await loadCart();
            updateCartBadge();
        } catch (error) {
            showToast(error.message, 'error');
        }
    };
});
