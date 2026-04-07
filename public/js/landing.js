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

        // Stagger animation
        products.forEach((product, index) => {
            const card = document.createElement('div');
            card.className = 'product-card';
            card.style.animationDelay = `${index * 0.08}s`;
            card.innerHTML = `
        <img class="product-card-img" src="${getProductImage(product.image)}" alt="${product.name}" 
             onerror="this.src='https://picsum.photos/seed/${product._id}/400/300'">
        <div class="product-card-body">
          <div class="category">${product.category || 'General'}</div>
          <h3>${product.name}</h3>
          <div class="price">${formatPrice(product.price)}</div>
        </div>
      `;
            card.addEventListener('click', () => {
                window.location.href = `/product?id=${product._id}`;
            });
            grid.appendChild(card);
        });
    } catch (error) {
        spinner.style.display = 'none';
        grid.innerHTML = `<div class="cart-empty"><div class="icon">❌</div><h3>Error loading products</h3><p>${error.message}</p></div>`;
    }
});
