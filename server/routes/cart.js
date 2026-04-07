const express = require('express');
const User = require('../models/User');
const { auth } = require('../middleware/auth');

const router = express.Router();

// GET /api/cart - Get user's cart
router.get('/', auth, async (req, res) => {
    try {
        const user = await User.findById(req.user._id).populate('cart.product');
        const cart = user.cart.filter(item => item.product); // Filter out deleted products
        res.json(cart);
    } catch (error) {
        res.status(500).json({ message: 'Error fetching cart.' });
    }
});

// POST /api/cart - Add item to cart
router.post('/', auth, async (req, res) => {
    try {
        const { productId, quantity } = req.body;
        const user = await User.findById(req.user._id);

        // Check if product already in cart
        const existingItem = user.cart.find(item => item.product.toString() === productId);

        if (existingItem) {
            existingItem.quantity += (quantity || 1);
        } else {
            user.cart.push({ product: productId, quantity: quantity || 1 });
        }

        await user.save();
        const updatedUser = await User.findById(req.user._id).populate('cart.product');
        res.json({ message: 'Item added to cart!', cart: updatedUser.cart });
    } catch (error) {
        console.error('Add to cart error:', error);
        res.status(500).json({ message: 'Error adding item to cart.' });
    }
});

// PUT /api/cart/:productId - Update cart item quantity
router.put('/:productId', auth, async (req, res) => {
    try {
        const { quantity } = req.body;
        const user = await User.findById(req.user._id);

        const item = user.cart.find(item => item.product.toString() === req.params.productId);
        if (!item) {
            return res.status(404).json({ message: 'Item not found in cart.' });
        }

        if (quantity <= 0) {
            user.cart = user.cart.filter(item => item.product.toString() !== req.params.productId);
        } else {
            item.quantity = quantity;
        }

        await user.save();
        const updatedUser = await User.findById(req.user._id).populate('cart.product');
        res.json({ message: 'Cart updated!', cart: updatedUser.cart });
    } catch (error) {
        res.status(500).json({ message: 'Error updating cart.' });
    }
});

// DELETE /api/cart/:productId - Remove item from cart
router.delete('/:productId', auth, async (req, res) => {
    try {
        const user = await User.findById(req.user._id);
        user.cart = user.cart.filter(item => item.product.toString() !== req.params.productId);
        await user.save();

        const updatedUser = await User.findById(req.user._id).populate('cart.product');
        res.json({ message: 'Item removed from cart!', cart: updatedUser.cart });
    } catch (error) {
        res.status(500).json({ message: 'Error removing item from cart.' });
    }
});

// DELETE /api/cart - Clear entire cart
router.delete('/', auth, async (req, res) => {
    try {
        const user = await User.findById(req.user._id);
        user.cart = [];
        await user.save();
        res.json({ message: 'Cart cleared!', cart: [] });
    } catch (error) {
        res.status(500).json({ message: 'Error clearing cart.' });
    }
});

module.exports = router;
