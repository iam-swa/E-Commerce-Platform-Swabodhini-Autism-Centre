const express = require('express');
const Product = require('../models/Product');
const { auth, adminAuth } = require('../middleware/auth');
const multer = require('multer');
const path = require('path');

const router = express.Router();

// Configure multer for product images
const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, path.join(__dirname, '../../public/uploads/products'));
    },
    filename: (req, file, cb) => {
        cb(null, `product-${Date.now()}${path.extname(file.originalname)}`);
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

// GET /api/products - Get all products
router.get('/', async (req, res) => {
    try {
        const products = await Product.find({ isActive: true }).sort({ createdAt: -1 });
        res.json(products);
    } catch (error) {
        res.status(500).json({ message: 'Error fetching products.' });
    }
});

// GET /api/products/all - Get all products including inactive (admin)
router.get('/all', adminAuth, async (req, res) => {
    try {
        const products = await Product.find().sort({ createdAt: -1 });
        res.json(products);
    } catch (error) {
        res.status(500).json({ message: 'Error fetching products.' });
    }
});

// GET /api/products/:id - Get single product
router.get('/:id', async (req, res) => {
    try {
        const product = await Product.findById(req.params.id);
        if (!product) {
            return res.status(404).json({ message: 'Product not found.' });
        }
        res.json(product);
    } catch (error) {
        res.status(500).json({ message: 'Error fetching product.' });
    }
});

// POST /api/products - Create product (admin)
router.post('/', adminAuth, upload.single('image'), async (req, res) => {
    try {
        const { name, price, description, category, stock } = req.body;

        const product = new Product({
            name,
            price: parseFloat(price),
            description,
            category: category || 'General',
            stock: parseInt(stock) || 10,
            image: req.file ? `/uploads/products/${req.file.filename}` : '/images/placeholder.png'
        });

        await product.save();
        res.status(201).json({ message: 'Product created successfully!', product });
    } catch (error) {
        console.error('Create product error:', error);
        res.status(500).json({ message: 'Error creating product.' });
    }
});

// PUT /api/products/:id - Update product (admin)
router.put('/:id', adminAuth, upload.single('image'), async (req, res) => {
    try {
        const { name, price, description, category, stock, isActive } = req.body;

        const updateData = { name, price: parseFloat(price), description, category, stock: parseInt(stock) };
        if (isActive !== undefined) updateData.isActive = isActive === 'true' || isActive === true;
        if (req.file) updateData.image = `/uploads/products/${req.file.filename}`;

        const product = await Product.findByIdAndUpdate(req.params.id, updateData, { new: true });
        if (!product) {
            return res.status(404).json({ message: 'Product not found.' });
        }
        res.json({ message: 'Product updated successfully!', product });
    } catch (error) {
        res.status(500).json({ message: 'Error updating product.' });
    }
});

// DELETE /api/products/:id - Delete product (admin)
router.delete('/:id', adminAuth, async (req, res) => {
    try {
        const product = await Product.findByIdAndDelete(req.params.id);
        if (!product) {
            return res.status(404).json({ message: 'Product not found.' });
        }
        res.json({ message: 'Product deleted successfully!' });
    } catch (error) {
        res.status(500).json({ message: 'Error deleting product.' });
    }
});

module.exports = router;
