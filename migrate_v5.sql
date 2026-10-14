tailor_booking--============================================
-- Migration Script — v4 → v5
-- Adds:
--   1. tailors.service_prices (JSON string / TEXT mapping service names to tailor custom prices)
--
-- Run with:  mysql -u root -p tailor_booking < migrate_v5.sql
-- ============================================

USE tailor_booking;

ALTER TABLE tailors
    ADD COLUMN IF NOT EXISTS service_prices TEXT DEFAULT NULL AFTER services;
