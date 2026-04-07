const express = require('express');
const jwt = require('jsonwebtoken');
const User = require('../models/User');
const { auth } = require('../middleware/auth');

const router = express.Router();

// In-memory OTP store (in production, use Redis or database)
const otpStore = new Map();

// Generate 6-digit OTP
function generateOTP() {
    return Math.floor(100000 + Math.random() * 900000).toString();
}

// POST /api/auth/send-otp - Send OTP to phone number for signup
router.post('/send-otp', async (req, res) => {
    try {
        const { name, phone, password } = req.body;

        // Validation
        if (!name || !phone || !password) {
            return res.status(400).json({ message: 'All fields are required.' });
        }

        if (!/^\d{10}$/.test(phone)) {
            return res.status(400).json({ message: 'Please enter a valid 10-digit phone number.' });
        }

        if (password.length < 6) {
            return res.status(400).json({ message: 'Password must be at least 6 characters.' });
        }

        // Check if user already exists with this phone
        const existingUser = await User.findOne({ phone });
        if (existingUser && existingUser.isVerified) {
            return res.status(400).json({ message: 'An account with this phone number already exists.' });
        }

        // Generate OTP
        const otp = generateOTP();
        
        // Store OTP with expiry (5 minutes)
        otpStore.set(phone, {
            otp,
            name,
            password,
            expiresAt: Date.now() + 5 * 60 * 1000,
            attempts: 0
        });

        // In a production environment, you would send the OTP via SMS here
        // For now, we'll log it to the console for development/testing
        console.log(`\n📱 OTP for ${phone}: ${otp}\n`);

        res.json({
            message: 'OTP sent successfully!',
            // Remove this in production - only for development testing
            devOtp: otp
        });
    } catch (error) {
        console.error('Send OTP error:', error);
        res.status(500).json({ message: 'Server error. Please try again.' });
    }
});

// POST /api/auth/verify-otp - Verify OTP and create account
router.post('/verify-otp', async (req, res) => {
    try {
        const { name, phone, password, otp } = req.body;

        if (!phone || !otp) {
            return res.status(400).json({ message: 'Phone number and OTP are required.' });
        }

        // Get stored OTP data
        const otpData = otpStore.get(phone);

        if (!otpData) {
            return res.status(400).json({ message: 'OTP expired or not found. Please request a new OTP.' });
        }

        // Check expiry
        if (Date.now() > otpData.expiresAt) {
            otpStore.delete(phone);
            return res.status(400).json({ message: 'OTP has expired. Please request a new OTP.' });
        }

        // Check max attempts
        if (otpData.attempts >= 5) {
            otpStore.delete(phone);
            return res.status(400).json({ message: 'Too many failed attempts. Please request a new OTP.' });
        }

        // Verify OTP
        if (otpData.otp !== otp) {
            otpData.attempts++;
            return res.status(400).json({ message: 'Invalid OTP. Please try again.' });
        }

        // OTP verified - create user
        otpStore.delete(phone);

        // Remove any unverified user with same phone
        await User.deleteMany({ phone, isVerified: false });

        // Create new verified user
        const user = new User({
            name: otpData.name || name,
            phone,
            password: otpData.password || password,
            isVerified: true
        });
        await user.save();

        // Generate JWT
        const token = jwt.sign({ userId: user._id }, process.env.JWT_SECRET, { expiresIn: '7d' });

        res.status(201).json({
            message: 'Account created successfully!',
            token,
            user: {
                id: user._id,
                name: user.name,
                phone: user.phone,
                role: user.role
            }
        });
    } catch (error) {
        console.error('Verify OTP error:', error);
        res.status(500).json({ message: 'Server error. Please try again.' });
    }
});

// POST /api/auth/login - Login with phone and password
router.post('/login', async (req, res) => {
    try {
        const { phone, password } = req.body;

        if (!phone) {
            return res.status(400).json({ message: 'Phone number and password are required.' });
        }

        // Find user by phone
        const user = await User.findOne({ phone });
        if (!user) {
            return res.status(401).json({ message: 'Invalid phone number or password.' });
        }

        // If admin account detected and no password provided yet,
        // signal the frontend to show the password field
        if (user.role === 'admin' && !password) {
            return res.json({ requirePassword: true });
        }

        if (!password) {
            return res.status(400).json({ message: 'Phone number and password are required.' });
        }

        if (!user.isVerified && user.role !== 'admin') {
            return res.status(401).json({ message: 'Account not verified. Please sign up again.' });
        }

        // Check password
        const isMatch = await user.comparePassword(password);
        if (!isMatch) {
            return res.status(401).json({ message: 'Invalid phone number or password.' });
        }

        // Generate JWT
        const token = jwt.sign({ userId: user._id }, process.env.JWT_SECRET, { expiresIn: '7d' });

        res.json({
            message: 'Login successful!',
            token,
            user: {
                id: user._id,
                name: user.name,
                phone: user.phone,
                role: user.role
            }
        });
    } catch (error) {
        console.error('Login error:', error);
        res.status(500).json({ message: 'Server error. Please try again.' });
    }
});

// GET /api/auth/me
router.get('/me', auth, async (req, res) => {
    res.json({ user: req.user });
});

module.exports = router;
