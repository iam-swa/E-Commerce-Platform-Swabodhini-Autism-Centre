// Product Detail Page
document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    const productId = params.get('id');
    const spinner = document.getElementById('loadingSpinner');
    const detail = document.getElementById('productDetail');

    if (!productId) {
        window.location.href = '/landing';
        return;
    }

    try {
        const product = await apiCall(`/api/products/${productId}`);
        spinner.style.display = 'none';
        detail.style.display = 'grid';

        document.title = `${product.name} | Swabodhini`;
        document.getElementById('productImage').src = getProductImage(product.image);
        document.getElementById('productImage').onerror = function () {
            this.src = `https://picsum.photos/seed/${product._id}/600/450`;
        };
        document.getElementById('productName').textContent = product.name;
        document.getElementById('productCategory').textContent = product.category || 'General';
        document.getElementById('productPrice').textContent = formatPrice(product.price);
        document.getElementById('productStock').textContent = product.stock > 0 ? `✅ In Stock (${product.stock} available)` : '❌ Out of Stock';
        document.getElementById('productDescription').textContent = product.description;

        // Add to cart
        document.getElementById('addToCartBtn').addEventListener('click', async () => {
            try {
                await apiCall('/api/cart', {
                    method: 'POST',
                    body: JSON.stringify({ productId: product._id, quantity: 1 })
                });
                showToast('Added to cart!');
                updateCartBadge();
            } catch (error) {
                showToast(error.message, 'error');
            }
        });

        // Buy now
        document.getElementById('buyNowBtn').addEventListener('click', async () => {
            try {
                await apiCall('/api/cart', {
                    method: 'POST',
                    body: JSON.stringify({ productId: product._id, quantity: 1 })
                });
                window.location.href = '/cart';
            } catch (error) {
                showToast(error.message, 'error');
            }
        });
    } catch (error) {
        spinner.style.display = 'none';
        detail.innerHTML = `<div class="cart-empty" style="grid-column:1/-1;"><div class="icon">❌</div><h3>Product not found</h3><a href="/landing" class="btn btn-primary" style="margin-top:1rem;display:inline-flex;">Back to Shop</a></div>`;
        detail.style.display = 'grid';
    }
});
