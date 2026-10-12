-- ============================================
-- Migration Script — upgrades an EXISTING tailor_booking
-- database to v2 (adds category, staged payments, etc.)
-- without deleting any existing data.
--
-- Run with:  mysql -u root -p tailor_booking < migrate_v2.sql
-- ============================================

USE tailor_booking;

-- 1. Tailor service categories (Men / Women / Kids)
ALTER TABLE tailors
    ADD COLUMN IF NOT EXISTS category VARCHAR(100) NOT NULL DEFAULT 'Men,Women,Kids';

-- 2. Booking staged-payment / measurement tracking columns
ALTER TABLE bookings
    ADD COLUMN IF NOT EXISTS advance_amount DECIMAL(10,2) DEFAULT 0.00,
    ADD COLUMN IF NOT EXISTS final_amount DECIMAL(10,2) DEFAULT 0.00,
    ADD COLUMN IF NOT EXISTS measurement_status ENUM('pending', 'done') DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS payment_stage ENUM('awaiting_advance', 'awaiting_measurement', 'awaiting_final_payment', 'awaiting_payment', 'paid')
        NOT NULL DEFAULT 'awaiting_measurement';

-- Backfill existing bookings so old rows behave sensibly under the new flow:
-- treat any already-completed payment as fully paid, everything else as
-- "awaiting_payment" so it can be collected once under the new system.
UPDATE bookings b
SET final_amount = b.price,
    payment_stage = IF(
        EXISTS (SELECT 1 FROM payments p WHERE p.booking_id = b.id AND p.payment_status = 'completed'),
        'paid', 'awaiting_payment'
    ),
    measurement_status = 'done'
WHERE b.final_amount = 0.00;

-- 3. Payments: allow an "advance" / "final" / "full" tag per row
ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS payment_type ENUM('advance', 'final', 'full') NOT NULL DEFAULT 'full';

-- 4. Phone number: exactly 10 digits, unique (run manually if you have
-- existing phone numbers that are NOT 10 digits — clean those up first,
-- otherwise this step will fail).
-- ALTER TABLE users MODIFY phone VARCHAR(10) NOT NULL;
-- ALTER TABLE users ADD UNIQUE KEY unique_phone (phone);
