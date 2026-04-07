const express = require('express');
const path = require('path');
const cors = require('cors');
const fs = require('fs');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const connectDB = require('./config/db');
const authRoutes = require('./routes/auth');
const productRoutes = require('./routes/products');
const cartRoutes = require('./routes/cart');
const orderRoutes = require('./routes/orders');
const adminRoutes = require('./routes/admin');

const app = express();

// Connect to MongoDB
connectDB();

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve static files
app.use(express.static(path.join(__dirname, '..', 'public')));

// Ensure upload directories exist
const uploadDirs = [
    path.join(__dirname, '..', 'public', 'uploads', 'products'),
    path.join(__dirname, '..', 'public', 'uploads', 'payments')
];
uploadDirs.forEach(dir => {
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
});

// API Routes
app.use('/api/auth', authRoutes);
app.use('/api/products', productRoutes);
app.use('/api/cart', cartRoutes);
app.use('/api/orders', orderRoutes);
app.use('/api/admin', adminRoutes);

// Serve HTML pages
app.get('/', (req, res) => res.sendFile(path.join(__dirname, '..', 'public', 'index.html')));
app.get('/landing', (req, res) => res.sendFile(path.join(__dirname, '..', 'public', 'landing.html')));
app.get('/product', (req, res) => res.sendFile(path.join(__dirname, '..', 'public', 'product.html')));
app.get('/cart', (req, res) => res.sendFile(path.join(__dirname, '..', 'public', 'cart.html')));
app.get('/payment', (req, res) => res.sendFile(path.join(__dirname, '..', 'public', 'payment.html')));
app.get('/admin', (req, res) => res.sendFile(path.join(__dirname, '..', 'public', 'admin.html')));
app.get('/admin-dashboard', (req, res) => res.sendFile(path.join(__dirname, '..', 'public', 'admin-dashboard.html')));
app.get('/orders', (req, res) => res.sendFile(path.join(__dirname, '..', 'public', 'orders.html')));

// 404 handler
app.use((req, res) => {
    res.status(404).sendFile(path.join(__dirname, '..', 'public', 'index.html'));
});

// Error handler
app.use((err, req, res, next) => {
    console.error(err.stack);
    res.status(500).json({ message: 'Something went wrong!' });
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
    console.log(`\n🚀 Swabodhini E-Commerce Server running on http://localhost:${PORT}`);
    console.log(`📦 Environment: ${process.env.NODE_ENV || 'development'}`);
});
