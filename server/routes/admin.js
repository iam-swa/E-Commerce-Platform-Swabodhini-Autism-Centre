const express = require('express');
const Product = require('../models/Product');
const Order = require('../models/Order');
const User = require('../models/User');
const { adminAuth } = require('../middleware/auth');

const router = express.Router();

// GET /api/admin/stats - Dashboard statistics
router.get('/stats', adminAuth, async (req, res) => {
    try {
        const totalProducts = await Product.countDocuments();
        const activeProducts = await Product.countDocuments({ isActive: true });
        const totalOrders = await Order.countDocuments();
        const pendingOrders = await Order.countDocuments({ status: 'Pending Verification' });
        const approvedOrders = await Order.countDocuments({ status: 'Approved' });
        const shippedOrders = await Order.countDocuments({ status: 'Shipped' });
        const deliveredOrders = await Order.countDocuments({ status: 'Delivered' });
        const rejectedOrders = await Order.countDocuments({ status: 'Rejected' });
        const totalUsers = await User.countDocuments({ role: 'user', isVerified: true });

        // Revenue calculation (from approved + shipped + delivered orders)
        const revenueOrders = await Order.find({
            status: { $in: ['Approved', 'Shipped', 'Delivered'] }
        });
        const totalRevenue = revenueOrders.reduce((sum, order) => sum + order.totalAmount, 0);

        // Low stock products (stock < 5)
        const lowStockProducts = await Product.find({ stock: { $lt: 5 }, isActive: true })
            .select('name stock')
            .sort({ stock: 1 });

        // Recent orders
        const recentOrders = await Order.find()
            .populate('user', 'name phone')
            .sort({ createdAt: -1 })
            .limit(5);

        res.json({
            totalProducts,
            activeProducts,
            totalOrders,
            pendingOrders,
            approvedOrders,
            shippedOrders,
            deliveredOrders,
            rejectedOrders,
            totalUsers,
            totalRevenue,
            lowStockProducts,
            recentOrders
        });
    } catch (error) {
        console.error('Stats error:', error);
        res.status(500).json({ message: 'Error fetching dashboard stats.' });
    }
});

// GET /api/admin/users - View all registered users
router.get('/users', adminAuth, async (req, res) => {
    try {
        const users = await User.find({ role: 'user' })
            .select('name phone isVerified createdAt')
            .sort({ createdAt: -1 });
        res.json(users);
    } catch (error) {
        console.error('Users error:', error);
        res.status(500).json({ message: 'Error fetching users.' });
    }
});

// GET /api/admin/stock - Stock management data
router.get('/stock', adminAuth, async (req, res) => {
    try {
        const products = await Product.find()
            .select('name stock isActive category price')
            .sort({ stock: 1 });
        res.json(products);
    } catch (error) {
        res.status(500).json({ message: 'Error fetching stock data.' });
    }
});

// PUT /api/admin/stock/:id - Update stock directly
router.put('/stock/:id', adminAuth, async (req, res) => {
    try {
        const { stock } = req.body;
        if (stock === undefined || stock < 0) {
            return res.status(400).json({ message: 'Valid stock quantity is required.' });
        }
        const product = await Product.findByIdAndUpdate(
            req.params.id,
            { stock: parseInt(stock) },
            { new: true }
        );
        if (!product) {
            return res.status(404).json({ message: 'Product not found.' });
        }
        res.json({ message: 'Stock updated successfully!', product });
    } catch (error) {
        res.status(500).json({ message: 'Error updating stock.' });
    }
});

module.exports = router;
