-- ============================================
-- Migration Script — v3 → v4
-- Adds:
--   1. tailors.rejection_reason  (admin reject with reason)
--   2. tailors.status ENUM gets 'rejected' value
--   3. reviews table (customer star ratings + comment)
--
-- Run with:  mysql -u root -p tailor_booking < migrate_v4.sql
-- ============================================

USE tailor_booking;

-- 1. Add rejection_reason column to tailors
ALTER TABLE tailors
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT DEFAULT NULL AFTER status;

-- 2. Expand tailors.status ENUM to include 'rejected'
ALTER TABLE tailors
    MODIFY COLUMN status ENUM('pending', 'active', 'inactive', 'rejected') DEFAULT 'pending';

-- 3. Create reviews table
CREATE TABLE IF NOT EXISTS reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL UNIQUE,       -- one review per booking
    customer_id INT NOT NULL,
    tailor_id INT NOT NULL,
    rating DECIMAL(2,1) NOT NULL,         -- 1.0 – 5.0
    comment TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id)  REFERENCES bookings(id)  ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES users(id)     ON DELETE CASCADE,
    FOREIGN KEY (tailor_id)   REFERENCES tailors(id)   ON DELETE CASCADE
) ENGINE=InnoDB;
