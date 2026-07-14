// Landing Page - Product Grid
document.addEventListener('DOMContentLoaded', async () => {
    const grid = document.getElementById('productsGrid');
    const spinner = document.getElementById('loadingSpinner');

    try {
        const products = await apiCall('/api/products');
        spinner.style.display = 'none';

        if (!products || products.length === 0) {
            grid.innerHTML = '<div class="cart-empty"><div class="icon">📦</div><h3>No products available</h3><p>Check back soon!</p></div>';
            return;
        }

        // Staggered entrance animation
        products.forEach((product, index) => {
            const card = document.createElement('div');
            card.className = 'product-card';
            if (product.stock === 0) card.classList.add('out-of-stock-card');
            card.style.animationDelay = `${index * 0.07}s`;

            const imgSrc = getProductImage(product.image, product._id);
            const stockBadge = product.stock > 0
                ? `<div class="stock-indicator in-stock">✦ In Stock (${product.stock})</div>`
                : `<div class="stock-indicator no-stock">✦ Out of Stock</div>`;
            const outOfStockOverlay = product.stock === 0
                ? `<div class="out-of-stock-overlay">Sold Out</div>`
                : '';

            card.innerHTML = `
        <div class="product-card-img-wrap">
          <img class="product-card-img"
               src="${imgSrc}"
               alt="${product.name}"
               onerror="this.src='https://picsum.photos/seed/${product._id}/300/300'">
          ${outOfStockOverlay}
        </div>
        <div class="product-card-body">
          <div class="category">${product.category || 'Handmade'}</div>
          <h3>${product.name}</h3>
          ${stockBadge}
          <div class="price">${formatPrice(product.price)}</div>
        </div>
      `;

            if (product.stock > 0) {
                card.addEventListener('click', () => {
                    navigateTo(`/product?id=${product._id}`);
                });
            }
            grid.appendChild(card);
        });
    } catch (error) {
        spinner.style.display = 'none';
        grid.innerHTML = `<div class="cart-empty"><div class="icon">❌</div><h3>Error loading products</h3><p>${error.message}</p></div>`;
    }
});

// Page-exit helper (used by card clicks)
function navigateTo(url) {
    document.body.classList.add('page-exit');
    setTimeout(() => { window.location.href = url; }, 340);
}
