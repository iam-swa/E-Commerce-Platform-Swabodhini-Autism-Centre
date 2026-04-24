// Landing Page - Product Grid & Smart Search
document.addEventListener('DOMContentLoaded', async () => {
    const grid = document.getElementById('productsGrid');
    const spinner = document.getElementById('loadingSpinner');
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const searchFilters = document.getElementById('searchFilters');

    // Initial load
    await loadProducts('/api/products');

    // Search event listeners
    if (searchBtn && searchInput) {
        searchBtn.addEventListener('click', () => {
            performSearch(searchInput.value);
        });

        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                performSearch(searchInput.value);
            }
        });
    }

    async function performSearch(query) {
        if (!query.trim()) {
            searchFilters.style.display = 'none';
            await loadProducts('/api/products');
            return;
        }

        spinner.style.display = 'block';
        grid.innerHTML = '';
        
        try {
            // NLP search — backend handles typo correction, price intent,
            // gift/handmade intent, category parsing. We only display results.
            const res = await apiCall(`/api/search?q=${encodeURIComponent(query)}`);
            spinner.style.display = 'none';

            // Only show a subtle hint when the backend falls back to suggestions.
            // Never show internal AI labels, intent pills, or keyword dumps.
            if (res.fallback_message) {
                searchFilters.innerHTML =
                    `<span class="search-hint">✦ ${res.fallback_message}</span>`;
                searchFilters.style.display = 'block';
            } else {
                searchFilters.style.display = 'none';
            }

            renderProducts(res.products || []);
        } catch (error) {
            spinner.style.display = 'none';
            searchFilters.style.display = 'none';
            console.error('[Search] Failed:', error);
            grid.innerHTML = `
                <div class="cart-empty">
                    <div class="icon">🔍</div>
                    <h3>Search unavailable</h3>
                    <p>We couldn't complete your search right now. Please try again in a moment.</p>
                </div>`;
        }
    }

    async function loadProducts(endpoint) {
        try {
            const products = await apiCall(endpoint);
            spinner.style.display = 'none';
            renderProducts(products);
        } catch (error) {
            spinner.style.display = 'none';
            grid.innerHTML = `<div class="cart-empty"><div class="icon">❌</div><h3>Error loading products</h3><p>${error.message}</p></div>`;
        }
    }

    function renderProducts(products) {
        if (!products || products.length === 0) {
            grid.innerHTML = '<div class="cart-empty"><div class="icon">🔍</div><h3>No products found</h3><p>Try searching for something else!</p></div>';
            return;
        }

        grid.innerHTML = '';
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
    }
});
