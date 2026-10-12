-- ============================================
-- Migration Script — upgrades an EXISTING tailor_booking
-- database (v2) to v3: adds city, rating, and starting_price
-- to tailors, so customers can filter by city / rating / price.
--
-- Run with:  mysql -u root -p tailor_booking < migrate_v3.sql
-- ============================================

USE tailor_booking;

ALTER TABLE tailors
    ADD COLUMN IF NOT EXISTS city VARCHAR(100) NOT NULL DEFAULT '' AFTER address,
    ADD COLUMN IF NOT EXISTS rating DECIMAL(2,1) NOT NULL DEFAULT 4.5 AFTER category,
    ADD COLUMN IF NOT EXISTS starting_price DECIMAL(10,2) NOT NULL DEFAULT 300.00 AFTER rating;

-- Existing tailors registered before this migration won't have a city set.
-- They will still show up in unfiltered searches; set their city manually
-- (or have them update it) so the new City filter picks them up, e.g.:
-- UPDATE tailors SET city = 'Rajkot' WHERE id = 1;
