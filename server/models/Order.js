const mongoose = require('mongoose');

const orderSchema = new mongoose.Schema({
    user: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'User',
        required: true
    },
    products: [{
        product: {
            type: mongoose.Schema.Types.ObjectId,
            ref: 'Product'
        },
        name: String,
        price: Number,
        quantity: {
            type: Number,
            default: 1
        },
        image: String
    }],
    shippingAddress: {
        fullName: { type: String, required: true },
        phone: { type: String, required: true },
        addressLine1: { type: String, required: true },
        addressLine2: { type: String, default: '' },
        city: { type: String, required: true },
        state: { type: String, required: true },
        pincode: { type: String, required: true }
    },
    totalAmount: {
        type: Number,
        required: true
    },
    paymentScreenshot: {
        type: String,
        required: true
    },
    transactionId: {
        type: String,
        required: true
    },
    status: {
        type: String,
        enum: ['Pending Verification', 'Approved', 'Rejected', 'Shipped', 'Delivered'],
        default: 'Pending Verification'
    },
    createdAt: {
        type: Date,
        default: Date.now
    }
});

module.exports = mongoose.model('Order', orderSchema);
