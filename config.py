"""
Configuration for the Tailor Booking System Python backend.
Values can be overridden with environment variables so the app can be
deployed without editing source code.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Database (matches config/database.php defaults) ---
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'tailor_booking')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '123456')

# --- Flask session secret key ---
# Use a fresh development key per process unless one is supplied explicitly.
SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32)
