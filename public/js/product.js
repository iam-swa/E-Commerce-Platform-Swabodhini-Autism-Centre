// Product Detail Page  +  ML Recommendations (with view tracking)
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
        document.getElementById('productStock').textContent =
            product.stock > 0
                ? `✅ In Stock (${product.stock} available)`
                : '❌ Out of Stock';
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

        // ── Track this view (fire-and-forget, don't block UI) ────────────────
        trackProductView(productId);

        // ── Load recommendations ──────────────────────────────────────────────
        loadRecommendations(productId);

    } catch (error) {
        spinner.style.display = 'none';
        detail.innerHTML = `
            <div class="cart-empty" style="grid-column:1/-1;">
                <div class="icon">❌</div>
                <h3>Product not found</h3>
                <a href="/landing" class="btn btn-primary" style="margin-top:1rem;display:inline-flex;">
                    Back to Shop
                </a>
            </div>`;
        detail.style.display = 'grid';
    }
});


/**
 * Tell the server this user viewed this product.
 * Silent – never shows an error to the user.
 */
async function trackProductView(productId) {
    try {
        const token = localStorage.getItem('token');
        if (!token) return; // only track logged-in users
        await fetch('/api/track/view', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ productId })
        });
    } catch (e) {
        // Silently ignore tracking errors
    }
}


/**
 * Fetch ML recommendations and render the "You Might Also Like" section.
 */
async function loadRecommendations(productId) {
    const section    = document.getElementById('recommendationsSection');
    const recLoading = document.getElementById('recLoading');
    const recGrid    = document.getElementById('recGrid');

    section.style.display = 'block';

    try {
        const token = localStorage.getItem('token');
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const response = await fetch(
            `/api/products/${productId}/recommendations?n=4`,
            { headers }
        );
        if (!response.ok) throw new Error('fetch failed');

        const recommendations = await response.json();
        recLoading.style.display = 'none';

        if (!recommendations || recommendations.length === 0) {
            section.style.display = 'none';
            return;
        }

        recGrid.innerHTML = recommendations.map(p => `
            <a href="/product?id=${p._id}" class="rec-card">
                <img
                    class="rec-card-img"
                    src="${getProductImage(p.image)}"
                    alt="${escapeHtml(p.name)}"
                    onerror="this.src='https://picsum.photos/seed/${p._id}/400/300'"
                    loading="lazy"
                />
                <div class="rec-card-body">
                    <div class="rec-card-category">${escapeHtml(p.category || 'General')}</div>
                    <div class="rec-card-name">${escapeHtml(p.name)}</div>
                    <div class="rec-card-price">${formatPrice(p.price)}</div>
                </div>
            </a>
        `).join('');

        recGrid.style.display = 'grid';

    } catch (err) {
        section.style.display = 'none';
        console.warn('[Recommendations] Could not load:', err.message);
    }
}


function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
