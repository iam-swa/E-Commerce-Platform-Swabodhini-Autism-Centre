const express = require('express');
const Order = require('../models/Order');
const User = require('../models/User');
const Product = require('../models/Product');
const { auth, adminAuth } = require('../middleware/auth');
const multer = require('multer');
const path = require('path');

const router = express.Router();

// Configure multer for payment screenshots
const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, path.join(__dirname, '../../public/uploads/payments'));
    },
    filename: (req, file, cb) => {
        cb(null, `payment-${req.user._id}-${Date.now()}${path.extname(file.originalname)}`);
    }
});

const upload = multer({
    storage,
    limits: { fileSize: 5 * 1024 * 1024 },
    fileFilter: (req, file, cb) => {
        const allowedTypes = /jpeg|jpg|png|gif|webp/;
        const extname = allowedTypes.test(path.extname(file.originalname).toLowerCase());
        const mimetype = allowedTypes.test(file.mimetype);
        if (extname && mimetype) {
            cb(null, true);
        } else {
            cb(new Error('Only image files are allowed'));
        }
    }
});

// POST /api/orders - Create new order
router.post('/', auth, upload.single('paymentScreenshot'), async (req, res) => {
    try {
        const { transactionId, products, totalAmount } = req.body;

        if (!req.file) {
            return res.status(400).json({ message: 'Payment screenshot is required.' });
        }

        if (!transactionId) {
            return res.status(400).json({ message: 'Transaction ID is required.' });
        }

        const parsedProducts = JSON.parse(products);

        const order = new Order({
            user: req.user._id,
            products: parsedProducts,
            totalAmount: parseFloat(totalAmount),
            paymentScreenshot: `/uploads/payments/${req.file.filename}`,
            transactionId
        });

        await order.save();

        // Clear user's cart after order
        const user = await User.findById(req.user._id);
        user.cart = [];
        await user.save();

        res.status(201).json({ message: 'Order placed successfully!', order });
    } catch (error) {
        console.error('Create order error:', error);
        res.status(500).json({ message: 'Error placing order.' });
    }
});

// GET /api/orders/my - Get user's orders
router.get('/my', auth, async (req, res) => {
    try {
        const orders = await Order.find({ user: req.user._id })
            .populate('products.product')
            .sort({ createdAt: -1 });
        res.json(orders);
    } catch (error) {
        res.status(500).json({ message: 'Error fetching orders.' });
    }
});

// GET /api/orders - Get all orders (admin)
router.get('/', adminAuth, async (req, res) => {
    try {
        const orders = await Order.find()
            .populate('user', 'name email phone')
            .populate('products.product')
            .sort({ createdAt: -1 });
        res.json(orders);
    } catch (error) {
        res.status(500).json({ message: 'Error fetching orders.' });
    }
});

// PUT /api/orders/:id/status - Update order status (admin)
router.put('/:id/status', adminAuth, async (req, res) => {
    try {
        const { status } = req.body;
        const validStatuses = ['Pending Verification', 'Approved', 'Rejected', 'Shipped', 'Delivered'];

        if (!validStatuses.includes(status)) {
            return res.status(400).json({ message: 'Invalid status.' });
        }

        // Get the current order to check previous status
        const currentOrder = await Order.findById(req.params.id);
        if (!currentOrder) {
            return res.status(404).json({ message: 'Order not found.' });
        }

        // If changing to Approved and it wasn't already approved, deduct stock
        if (status === 'Approved' && currentOrder.status !== 'Approved') {
            for (const item of currentOrder.products) {
                if (item.product) {
                    const product = await Product.findById(item.product);
                    if (product) {
                        product.stock = Math.max(0, product.stock - (item.quantity || 1));
                        await product.save();
                    }
                }
            }
        }

        const order = await Order.findByIdAndUpdate(
            req.params.id,
            { status },
            { new: true }
        ).populate('user', 'name email phone');

        res.json({ message: 'Order status updated!', order });
    } catch (error) {
        console.error('Update order status error:', error);
        res.status(500).json({ message: 'Error updating order status.' });
    }
});

module.exports = router;
