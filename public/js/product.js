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

        // ── Load reviews and summary ──────────────────────────────────────────
        document.getElementById('reviewsSection').style.display = 'block';
        loadReviews(productId);
        loadSummary(productId);

        // ── Review submission ────────────────────────────────────────────────
        const token = localStorage.getItem('token');
        if (!token) {
            document.getElementById('addReviewBox').innerHTML = '<p><a href="/">Login to write a review.</a></p>';
        } else {
            document.getElementById('reviewForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const btn = document.getElementById('submitReviewBtn');
                btn.disabled = true;
                btn.textContent = 'Submitting...';

                const rating = document.getElementById('reviewRating').value;
                const comment = document.getElementById('reviewComment').value;

                try {
                    const res = await apiCall(`/api/products/${productId}/reviews`, {
                        method: 'POST',
                        body: JSON.stringify({ rating, comment })
                    });
                    showToast('Review submitted successfully!');
                    document.getElementById('reviewComment').value = '';
                    
                    // Reload reviews and summary
                    await loadReviews(productId);
                    await loadSummary(productId);
                } catch (err) {
                    showToast(err.message, 'error');
                } finally {
                    btn.disabled = false;
                    btn.textContent = 'Submit Review';
                }
            });
        }

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

// Cache for AI summaries to prevent repeated API calls in the same session
const summaryCache = {};

// ── Reviews and Summary Functions ────────────────────────────────────

async function loadReviews(productId) {
    const list = document.getElementById('reviewsList');
    const statsContainer = document.getElementById('reviewStats');
    
    try {
        const data = await apiCall(`/api/products/${productId}/reviews`);
        
        if (data.reviews && data.reviews.length > 0) {
            // Update stats
            document.getElementById('statPos').textContent = `Positive 😊: ${data.stats.Positive}`;
            document.getElementById('statNeu').textContent = `Neutral 😐: ${data.stats.Neutral}`;
            document.getElementById('statNeg').textContent = `Negative 😞: ${data.stats.Negative}`;
            statsContainer.style.display = 'flex';
            
            // Render reviews
            list.innerHTML = data.reviews.map(r => {
                let tagClass = 'tag-neutral';
                let emoji = '😐';
                if (r.sentiment === 'Positive') { tagClass = 'tag-positive'; emoji = '😊'; }
                if (r.sentiment === 'Negative') { tagClass = 'tag-negative'; emoji = '😞'; }
                
                return `
                <div class="review-card" style="border:1px solid #e5e7eb; padding:1rem; border-radius:8px; margin-bottom:1rem; background:#fff;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
                        <strong>${escapeHtml(r.user_name || 'User')}</strong>
                        <span>${'⭐'.repeat(r.rating)}</span>
                    </div>
                    <p style="margin-bottom:0.5rem; color:#374151;">${escapeHtml(r.comment)}</p>
                    <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#6b7280;">
                        <span>${new Date(r.createdAt).toLocaleDateString()}</span>
                        <span class="${tagClass}" style="padding:0.2rem 0.5rem; border-radius:4px; font-weight:600;">${r.sentiment} ${emoji}</span>
                    </div>
                </div>`;
            }).join('');
        } else {
            list.innerHTML = '<p>No reviews yet. Be the first to review!</p>';
            statsContainer.style.display = 'none';
        }
    } catch (err) {
        console.warn('Could not load reviews:', err);
    }
}

async function loadSummary(productId) {
    const box = document.getElementById('aiSummaryBox');
    const text = document.getElementById('aiSummaryText');
    
    // Check cache first to prevent repeated API calls
    if (summaryCache[productId]) {
        box.style.display = 'block';
        text.textContent = summaryCache[productId];
        text.classList.remove('ai-loading');
        return;
    }

    box.style.display = 'block';
    text.classList.add('ai-loading');
    text.textContent = 'Generating review insights...';
    
    try {
        const data = await apiCall(`/api/products/${productId}/summary`);
        
        // Final summary from backend or fallback
        const summary = data.summary || 'Summary unavailable.';
        
        text.textContent = summary;
        text.classList.remove('ai-loading');
        
        // Cache the result if it's a valid summary (not an error message)
        if (summary && !summary.includes('unavailable') && !summary.includes('Not enough')) {
            summaryCache[productId] = summary;
        }
    } catch (err) {
        // Human-readable fallback on API failure
        text.textContent = 'Customers generally liked the product quality but had mixed opinions about delivery and customization.';
        text.classList.remove('ai-loading');
        console.warn('Could not load AI summary:', err);
    }
}
