const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const User = require('./models/User');
const Product = require('./models/Product');

const seedData = async () => {
    try {
        await mongoose.connect(process.env.MONGODB_URI);
        console.log('✅ Connected to MongoDB');

        // Clear existing data
        await User.deleteMany({});
        await Product.deleteMany({});
        console.log('🗑️  Cleared existing data');

        // Create admin user only (no sample users)
        const admin = new User({
            name: 'Admin',
            email: 'admin@swabodhini.com',
            password: 'admin123',
            phone: '9876543210',
            role: 'admin',
            isVerified: true
        });
        await admin.save();
        console.log('👤 Admin user created: Phone: 9876543210 / Password: admin123');

        // Create sample products
        const products = [
            {
                name: 'Hand-Painted Greeting Cards',
                price: 150,
                description: 'Beautiful hand-painted greeting cards made by the talented students of Swabodhini Autism Centre. Each card is unique and made with love, featuring vibrant watercolor designs. Perfect for birthdays, festivals, and special occasions. Set of 5 cards included.',
                image: '/images/product1.jpg',
                category: 'Art & Craft',
                stock: 50
            },
            {
                name: 'Handmade Paper Bags',
                price: 200,
                description: 'Eco-friendly handmade paper bags crafted by our students. These sturdy and stylish bags are perfect for gifting and daily use. Each bag is decorated with hand-painted designs and comes in assorted colors. Set of 10 bags.',
                image: '/images/product2.jpg',
                category: 'Eco-Friendly',
                stock: 30
            },
            {
                name: 'Clay Diyas (Set of 6)',
                price: 300,
                description: 'Beautifully sculpted and painted clay diyas, handcrafted by our students. Perfect for Diwali celebrations, home decor, and religious ceremonies. Each diya is uniquely decorated with vibrant patterns and colors.',
                image: '/images/product3.jpg',
                category: 'Festive',
                stock: 25
            },
            {
                name: 'Canvas Painting - Nature',
                price: 1200,
                description: 'Original canvas painting depicting beautiful nature scenes, created by the artists at Swabodhini. Each painting is a one-of-a-kind artwork that captures the creativity and imagination of our talented students. Size: 12x16 inches.',
                image: '/images/product4.jpg',
                category: 'Art & Craft',
                stock: 10
            },
            {
                name: 'Beaded Jewelry Set',
                price: 450,
                description: 'Handcrafted beaded jewelry set including a necklace and matching earrings. Made with colorful beads and carefully assembled by our skilled students. Each piece is unique with its own character and charm.',
                image: '/images/product5.jpg',
                category: 'Accessories',
                stock: 20
            },
            {
                name: 'Embroidered Cushion Covers',
                price: 550,
                description: 'Set of 2 hand-embroidered cushion covers with beautiful floral patterns. Made with premium cotton fabric and intricate embroidery work by our students. Size: 16x16 inches. Machine washable.',
                image: '/images/product6.jpg',
                category: 'Home Decor',
                stock: 15
            },
            {
                name: 'Organic Phenyl (1L)',
                price: 180,
                description: 'High-quality organic phenyl floor cleaner made at Swabodhini. Effective disinfectant with a pleasant pine fragrance. Safe for all types of flooring. Made with eco-friendly ingredients. 1 Litre bottle.',
                image: '/images/product7.jpg',
                category: 'Cleaning',
                stock: 100
            },
            {
                name: 'Handmade Candles (Set of 4)',
                price: 350,
                description: 'Aromatic handmade candles crafted by our students. Available in lavender, rose, jasmine, and vanilla fragrances. Perfect for home decor, gifting, and creating a peaceful ambiance. Burn time: approximately 8 hours each.',
                image: '/images/product8.jpg',
                category: 'Home Decor',
                stock: 35
            }
        ];

        await Product.insertMany(products);
        console.log(`📦 ${products.length} products created`);

        console.log('\n✅ Database seeded successfully!');
        console.log('\n📋 Login Credentials:');
        console.log('   Admin: Phone: 9876543210 / Password: admin123');
        console.log('   (No sample users - register via phone OTP)');

        process.exit(0);
    } catch (error) {
        console.error('❌ Seed error:', error);
        process.exit(1);
    }
};

seedData();
