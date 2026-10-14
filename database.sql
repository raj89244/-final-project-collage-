-- ============================================
-- Tailor Booking System — Database Schema (v5)
-- Run this to create all tables from scratch.
-- If you already have data you want to keep, use
-- migrate_v2.sql instead (ALTER statements only).
-- ============================================

CREATE DATABASE IF NOT EXISTS tailor_booking;
USE tailor_booking;

-- 1. Users Table (all roles)
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(10) UNIQUE NOT NULL,          -- exactly 10 digits, enforced in app.py
    address TEXT,
    password VARCHAR(255) NOT NULL,
    role ENUM('customer', 'tailor', 'admin') NOT NULL DEFAULT 'customer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 2. Tailors Table
CREATE TABLE IF NOT EXISTS tailors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    shop_name VARCHAR(150) NOT NULL,
    owner_name VARCHAR(100) NOT NULL,
    address TEXT,
    city VARCHAR(100) NOT NULL DEFAULT '',
    services VARCHAR(500) DEFAULT 'Shirt Stitching, Pant Stitching',
    service_prices TEXT DEFAULT NULL,                             -- JSON string mapping service names to custom prices e.g. {"Shirt Stitching": 600, "Pant Stitching": 400}
    category VARCHAR(100) NOT NULL DEFAULT 'Men,Women,Kids',   -- comma-separated: Men,Women,Kids
    rating DECIMAL(2,1) NOT NULL DEFAULT 4.5,    -- 0.0–5.0
    starting_price DECIMAL(10,2) NOT NULL DEFAULT 300.00,  -- "Starting from ₹X", set by tailor, used for price filter
    status ENUM('pending', 'active', 'inactive', 'rejected') DEFAULT 'pending',
    rejection_reason TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 3. Measurements Table
CREATE TABLE IF NOT EXISTS measurements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    chest DECIMAL(5,2) DEFAULT 0,
    waist DECIMAL(5,2) DEFAULT 0,
    shoulder DECIMAL(5,2) DEFAULT 0,
    arm_length DECIMAL(5,2) DEFAULT 0,
    pant_length DECIMAL(5,2) DEFAULT 0,
    neck DECIMAL(5,2) DEFAULT 0,
    notes TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 4. Bookings Table
CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    tailor_id INT NOT NULL,
    service_type VARCHAR(100) NOT NULL,
    booking_date DATE NOT NULL,
    booking_time TIME NOT NULL,                 -- must be between 09:00:00 and 21:00:00, enforced in app.py
    service_mode ENUM('Home Service', 'Visit Tailor Shop') NOT NULL DEFAULT 'Visit Tailor Shop',
    delivery_date DATE DEFAULT NULL,
    price DECIMAL(10,2) DEFAULT 0.00,            -- total price (advance_amount + final_amount)
    advance_amount DECIMAL(10,2) DEFAULT 0.00,   -- ₹100 home-visit charge (Home Service only), 0 for shop visit
    final_amount DECIMAL(10,2) DEFAULT 0.00,     -- remaining amount, payable after measurement is taken
    measurement_status ENUM('pending', 'done') DEFAULT 'pending',
    payment_stage ENUM('awaiting_advance', 'awaiting_measurement', 'awaiting_final_payment', 'awaiting_payment', 'paid')
        NOT NULL DEFAULT 'awaiting_measurement',
    status ENUM('pending', 'accepted', 'in_progress', 'completed', 'cancelled') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (tailor_id) REFERENCES tailors(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 5. Payments Table (a booking can now have TWO payment rows: advance + final)
CREATE TABLE IF NOT EXISTS payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    payment_type ENUM('advance', 'final', 'full') NOT NULL DEFAULT 'full',
    amount DECIMAL(10,2) NOT NULL,
    payment_method ENUM('Cash on Delivery', 'Online Payment') NOT NULL,
    payment_status ENUM('pending', 'completed', 'failed') DEFAULT 'pending',
    transaction_id VARCHAR(100) DEFAULT NULL,
    paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 6. Reviews Table
CREATE TABLE IF NOT EXISTS reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL UNIQUE,
    customer_id INT NOT NULL,
    tailor_id INT NOT NULL,
    rating DECIMAL(2,1) NOT NULL,
    comment TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (tailor_id) REFERENCES tailors(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================
-- Default Admin Account
-- Email: admin@tailor.com | Password: admin123
-- ============================================
INSERT INTO users (full_name, email, phone, address, password, role) VALUES 
('System Admin', 'admin@tailor.com', '9999999999', 'Admin Office', '$2y$10$Wll1StxUKi8SE/B8Axk8Fuh8tsFFyr/myk61spmjx.JCRNybRyhTO', 'admin');
