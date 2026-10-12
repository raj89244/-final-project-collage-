"""
Tailor Booking System — Python Backend
========================================
This Flask application is a 1:1 functional port of the original PHP
backend (config/database.php + backend/*.php). All routes, request/response
shapes, session behaviour, and business rules have been preserved so the
existing frontend (HTML/CSS/JS) keeps working with no changes other than
the API base path.

Run with:
    python app.py

See README.md for setup instructions.
"""

import csv
import html
import io
import json
import random
import re
import string
import uuid
from functools import wraps

import bcrypt
import pymysql
import pymysql.cursors
from flask import Flask, jsonify, request, session, send_from_directory, Response

import config

app = Flask(__name__, static_folder=None)
app.secret_key = config.SECRET_KEY

# Price map for services (mirrors backend/booking.php)
PRICE_MAP = {
    'Shirt Stitching': 500.00,
    'Pant Stitching': 400.00,
    'Suit Stitching': 2500.00,
    'Alteration': 200.00,
}

VALID_BOOKING_STATUSES = ['pending', 'accepted', 'in_progress', 'completed', 'cancelled']

# Shop operating hours — bookings can only be made for a time inside this
# window (feature #1: 9 AM to 9 PM slot restriction).
SHOP_OPEN_MINUTES = 9 * 60    # 09:00
SHOP_CLOSE_MINUTES = 21 * 60  # 21:00

# Home-visit charge collected as the "advance" payment before the tailor
# travels to the customer's home (feature #3).
HOME_VISIT_CHARGE = 100.00

# Allowed tailor service categories (feature #2).
VALID_CATEGORIES = ['Men', 'Women', 'Kids']

# Fixed service list shown as a dropdown at tailor registration (feature #6).
# On the frontend this list is filtered by selected category (Men/Women/Kids)
# — see CATEGORY_SERVICES in register.html — but the backend still validates
# against this full list regardless of category, since a tailor can legally
# pick any combination of categories and services. Booking price still falls
# back to ₹300 for any type not in PRICE_MAP above, so adding entries here
# does not require touching PRICE_MAP.
VALID_SERVICES = [
    'Shirt Stitching', 'Pant Stitching', 'Suit Stitching', 'Alteration',
    'Blouse Stitching', 'Kurta Stitching', 'Lehenga Stitching',
    'Sherwani Stitching', 'Saree Fall & Pico',
    'Kids Dress Stitching', 'School Uniform Stitching', 'Other',
]

# Price-range buckets offered in the customer-side price filter (feature #6).
PRICE_RANGES = {
    'under_500': (0, 499.99),
    '500_1000': (500, 1000),
    '1000_2000': (1000, 2000),
    'above_2000': (2000, None),
}


# ------------------------------------------------------------------
# Error handling — mirrors PHP's sendJson()+exit() pattern
# ------------------------------------------------------------------
class ApiAbort(Exception):
    """Raised to immediately short-circuit a request with a JSON response,
    equivalent to calling sendJson() then exit() in the PHP code."""

    def __init__(self, status, data=None, message=''):
        super().__init__(message)
        self.status = status
        self.data = data
        self.message = message


@app.errorhandler(ApiAbort)
def handle_api_abort(err):
    return build_json_response(err.status, err.data, err.message)


# ------------------------------------------------------------------
# Helpers (mirror the functions in config/database.php)
# ------------------------------------------------------------------
def build_json_response(status, data=None, message=''):
    body = {
        'success': 200 <= status < 300,
        'message': message,
    }
    if data is not None:
        body['data'] = data
    return jsonify(body), status


def send_json(status, data=None, message=''):
    """Equivalent of PHP sendJson(): raises to stop route execution."""
    raise ApiAbort(status, data, message)


def sanitize(value):
    """Equivalent of PHP sanitize(): trims whitespace and escapes HTML."""
    if value is None:
        return ''
    return html.escape(str(value).strip(), quote=True)


def get_json_input():
    """Equivalent of PHP getJsonInput()."""
    return request.get_json(silent=True) or {}


def get_db():
    """Open a fresh PyMySQL connection (DictCursor, ANSI-quoted results)."""
    return pymysql.connect(
        host=config.DB_HOST,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def require_auth(allowed_roles=None):
    """Equivalent of PHP requireAuth(): returns the current session user or aborts."""
    if 'user_id' not in session:
        send_json(401, None, 'Please login to continue.')
    if allowed_roles and session.get('role') not in allowed_roles:
        send_json(403, None, 'Access denied.')
    return {
        'user_id': session['user_id'],
        'role': session['role'],
        'full_name': session['full_name'],
    }


def json_default(value):
    """Make Decimal/date/time/datetime values from MySQL JSON-serialisable."""
    from decimal import Decimal
    import datetime

    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime.date, datetime.datetime, datetime.timedelta)):
        return str(value)
    return str(value)


app.json.default = json_default


# ------------------------------------------------------------------
# Global request/response behaviour (mirrors headers set in database.php)
# ------------------------------------------------------------------
@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS' and request.path.startswith('/backend/'):
        resp = jsonify({})
        resp.status_code = 200
        return resp


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


# ==================================================================
# backend/auth_check.php
# ==================================================================
@app.route('/backend/auth_check.php', methods=['GET', 'OPTIONS'])
def auth_check():
    if 'user_id' in session:
        return build_json_response(200, {
            'user_id': session['user_id'],
            'full_name': session['full_name'],
            'email': session['email'],
            'role': session['role'],
        }, 'Authenticated.')
    return build_json_response(200, None, 'Not authenticated.')


# ==================================================================
# backend/login.php
# ==================================================================
@app.route('/backend/login.php', methods=['POST', 'OPTIONS'])
def login():
    if request.method != 'POST':
        send_json(405, None, 'Method not allowed.')

    data = get_json_input()
    email = sanitize(data.get('email', ''))
    password = data.get('password', '')

    if not email or not password:
        send_json(400, None, 'Please enter both email and password.')

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
    finally:
        conn.close()

    if user and _verify_password(password, user['password']):
        if user['role'] == 'admin':
            send_json(403, None, 'Admins must use the dedicated Admin Login portal.')

        # Check if tailor account has been rejected — show reason instead of logging in.
        if user['role'] == 'tailor':
            conn2 = get_db()
            try:
                with conn2.cursor() as cur2:
                    cur2.execute("SELECT status, rejection_reason FROM tailors WHERE user_id = %s", (user['id'],))
                    tailor_row = cur2.fetchone()
                    if tailor_row and tailor_row['status'] == 'rejected':
                        reason = tailor_row['rejection_reason'] or 'No reason provided.'
                        send_json(403, {'rejection_reason': reason},
                                  f'Your registration was rejected by the admin. Reason: {reason}')
            finally:
                conn2.close()

        session['user_id'] = user['id']
        session['full_name'] = user['full_name']
        session['email'] = user['email']
        session['role'] = user['role']

        redirect = 'customer/dashboard.html'
        if user['role'] == 'tailor':
            redirect = 'tailor/dashboard.html'

        return build_json_response(200, {
            'user': {
                'id': user['id'],
                'full_name': user['full_name'],
                'email': user['email'],
                'role': user['role'],
            },
            'redirect': redirect,
        }, 'Login successful!')
    else:
        send_json(401, None, 'Invalid email or password.')


# ==================================================================
# backend/admin_login.php
# ==================================================================
@app.route('/backend/admin_login.php', methods=['POST', 'OPTIONS'])
def admin_login():
    if request.method != 'POST':
        send_json(405, None, 'Method not allowed.')

    data = get_json_input()
    email = sanitize(data.get('email', ''))
    password = data.get('password', '')

    if not email or not password:
        send_json(400, None, 'Please enter both email and password.')

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s AND role = 'admin'", (email,))
            user = cur.fetchone()

            if user and _verify_password(password, user['password']):
                session['user_id'] = user['id']
                session['full_name'] = user['full_name']
                session['email'] = user['email']
                session['role'] = user['role']

                return build_json_response(200, {
                    'user': {
                        'id': user['id'],
                        'full_name': user['full_name'],
                        'email': user['email'],
                        'role': user['role'],
                    },
                    'redirect': 'dashboard.html',
                }, 'Admin login successful!')
            else:
                cur.execute("SELECT role FROM users WHERE email = %s", (email,))
                existing = cur.fetchone()
                if existing and existing['role'] != 'admin':
                    send_json(403, None, 'Access denied. This login portal is for administrators only.')
                else:
                    send_json(401, None, 'Invalid admin email or password.')
    finally:
        conn.close()


# ==================================================================
# backend/logout.php
# ==================================================================
@app.route('/backend/logout.php', methods=['GET', 'POST', 'OPTIONS'])
def logout():
    session.clear()
    return build_json_response(200, None, 'Logged out successfully.')


# ==================================================================
# backend/register.php
# ==================================================================
@app.route('/backend/register.php', methods=['POST', 'OPTIONS'])
def register():
    if request.method != 'POST':
        send_json(405, None, 'Method not allowed.')

    data = get_json_input()
    role = sanitize(data.get('role', ''))
    full_name = sanitize(data.get('full_name', ''))
    email = sanitize(data.get('email', ''))
    phone = sanitize(data.get('phone', ''))
    address = sanitize(data.get('address', ''))
    password = data.get('password', '') or ''
    confirm_password = data.get('confirm_password', '') or ''

    if not all([full_name, email, phone, password, address]):
        send_json(400, None, 'All fields are required.')

    if not _is_valid_email(email):
        send_json(400, None, 'Invalid email format.')

    if not _is_valid_phone(phone):
        send_json(400, None, 'Phone number must be exactly 10 digits.')

    if len(password) < 6:
        send_json(400, None, 'Password must be at least 6 characters.')

    if password != confirm_password:
        send_json(400, None, 'Passwords do not match.')

    if role not in ('customer', 'tailor'):
        send_json(400, None, 'Invalid role selected.')

    # Feature #2: tailors must declare which customer categories they serve.
    # Feature #6: tailors must also declare their city and the services they
    # offer (now a fixed dropdown list instead of free text), plus a starting
    # price used for the customer-side price filter.
    category = ''
    city = ''
    services = ''
    starting_price = 0.0
    if role == 'tailor':
        raw_category = data.get('category', '')
        if isinstance(raw_category, list):
            selected = [sanitize(c) for c in raw_category if sanitize(c)]
        else:
            selected = [c.strip() for c in sanitize(raw_category).split(',') if c.strip()]
        selected = [c for c in selected if c in VALID_CATEGORIES]
        if not selected:
            send_json(400, None, 'Please select at least one service category (Men, Women, or Kids).')
        category = ','.join(selected)

        city = sanitize(data.get('city', ''))
        if not city:
            send_json(400, None, 'City is required so customers can find you.')

        raw_services = data.get('services', '')
        if isinstance(raw_services, list):
            selected_services = [sanitize(s) for s in raw_services if sanitize(s)]
        else:
            selected_services = [s.strip() for s in sanitize(raw_services).split(',') if s.strip()]
        selected_services = [s for s in selected_services if s in VALID_SERVICES]
        if not selected_services:
            send_json(400, None, 'Please select at least one service you offer.')
        services = ','.join(selected_services)

        starting_price = _float(data.get('starting_price', 0), 0)

        service_prices_raw = data.get('service_prices', {})
        service_prices_dict = {}
        if isinstance(service_prices_raw, dict):
            for k, v in service_prices_raw.items():
                s_name = sanitize(k)
                if s_name in selected_services:
                    p_val = _float(v, 0)
                    if p_val > 0:
                        service_prices_dict[s_name] = p_val
        service_prices_str = json.dumps(service_prices_dict) if service_prices_dict else None

        if service_prices_dict and (starting_price <= 0 or starting_price > min(service_prices_dict.values())):
            starting_price = min(service_prices_dict.values())

        if starting_price <= 0:
            send_json(400, None, 'Please enter a valid starting price.')

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                send_json(409, None, 'Email already registered. Please login.')

            # Feature #5: phone number must be a unique identity, like email.
            cur.execute("SELECT id FROM users WHERE phone = %s", (phone,))
            if cur.fetchone():
                send_json(409, None, 'This phone number is already registered.')

            hashed = _hash_password(password)

            try:
                conn.begin()
                cur.execute(
                    "INSERT INTO users (full_name, email, phone, address, password, role) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (full_name, email, phone, address, hashed, role),
                )
                user_id = cur.lastrowid

                if role == 'tailor':
                    shop_name = sanitize(data.get('shop_name', ''))
                    owner_name = sanitize(data.get('owner_name', ''))

                    if not shop_name or not owner_name:
                        raise ValueError('Shop Name and Owner Name are required for tailor registration.')

                    cur.execute(
                        "INSERT INTO tailors (user_id, shop_name, owner_name, address, city, services, "
                        "service_prices, category, starting_price, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')",
                        (user_id, shop_name, owner_name, address, city, services, service_prices_str, category, starting_price),
                    )

                conn.commit()
            except ApiAbort:
                raise
            except Exception as e:
                conn.rollback()
                send_json(500, None, f'Registration failed: {e}')

            msg = ('Registration successful! Your profile is under review. Admin will verify and approve your account.'
                   if role == 'tailor' else 'Registration successful! Please login.')
            return build_json_response(201, {'user_id': user_id}, msg)
    finally:
        conn.close()


# ==================================================================
# backend/tailors.php
# ==================================================================
@app.route('/backend/tailors.php', methods=['GET', 'OPTIONS'])
def tailors_list():
    # Feature #2: optional ?category=Men|Women|Kids filter.
    # Feature #6: full filter system — ?city=, ?min_rating=, ?price_range=,
    # ?search= (shop/owner/service name), and ?sort= (rating | price_low |
    # price_high | newest — default).
    category = sanitize(request.args.get('category', ''))
    city = sanitize(request.args.get('city', ''))
    search = sanitize(request.args.get('search', ''))
    min_rating = _float(request.args.get('min_rating', 0), 0)
    price_range = sanitize(request.args.get('price_range', ''))
    sort = sanitize(request.args.get('sort', ''))
    tailor_id = _int(request.args.get('id', 0), 0)

    where = ["t.status = 'active'"]
    params = []

    if tailor_id:
        where.append("t.id = %s")
        params.append(tailor_id)

    if category and category in VALID_CATEGORIES:
        where.append("FIND_IN_SET(%s, t.category)")
        params.append(category)

    if city:
        where.append("t.city LIKE %s")
        params.append(f"%{city}%")

    if search:
        where.append("(t.shop_name LIKE %s OR t.owner_name LIKE %s OR t.services LIKE %s)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    if min_rating > 0:
        where.append("t.rating >= %s")
        params.append(min_rating)

    if price_range in PRICE_RANGES:
        low, high = PRICE_RANGES[price_range]
        where.append("t.starting_price >= %s")
        params.append(low)
        if high is not None:
            where.append("t.starting_price <= %s")
            params.append(high)

    order_by = "t.created_at DESC"
    if sort == 'rating':
        order_by = "t.rating DESC, t.created_at DESC"
    elif sort == 'price_low':
        order_by = "t.starting_price ASC, t.created_at DESC"
    elif sort == 'price_high':
        order_by = "t.starting_price DESC, t.created_at DESC"

    sql = (
        "SELECT t.id, t.shop_name, t.owner_name, t.address, t.city, t.services, t.service_prices, t.category, "
        "t.rating, t.starting_price, u.phone, u.email FROM tailors t "
        "JOIN users u ON t.user_id = u.id WHERE " + " AND ".join(where) +
        " ORDER BY " + order_by
    )

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            tailors = cur.fetchall()
            for t in tailors:
                if t.get('service_prices'):
                    try:
                        t['service_prices'] = json.loads(t['service_prices'])
                    except Exception:
                        t['service_prices'] = {}
                else:
                    t['service_prices'] = {}
        return build_json_response(200, tailors, 'Tailors loaded.')
    finally:
        conn.close()


@app.route('/backend/filter_options.php', methods=['GET', 'OPTIONS'])
def filter_options():
    """Feature #6: distinct cities currently in use, so the customer-side
    city filter dropdown always reflects real data rather than a hardcoded
    list that could drift out of sync with what tailors actually entered."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT city FROM tailors WHERE status = 'active' AND city != '' ORDER BY city ASC"
            )
            cities = [row['city'] for row in cur.fetchall()]
        return build_json_response(200, {
            'cities': cities,
            'price_ranges': [
                {'value': 'under_500', 'label': 'Under \u20b9500'},
                {'value': '500_1000', 'label': '\u20b9500 \u2013 \u20b91000'},
                {'value': '1000_2000', 'label': '\u20b91000 \u2013 \u20b92000'},
                {'value': 'above_2000', 'label': 'Above \u20b92000'},
            ],
            'services': VALID_SERVICES,
        }, 'Filter options loaded.')
    finally:
        conn.close()


# ==================================================================
# backend/booking.php
# ==================================================================
@app.route('/backend/booking.php', methods=['GET', 'POST', 'OPTIONS'])
def booking():
    auth = require_auth(['customer'])
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if request.method == 'GET':
                cur.execute(
                    "SELECT b.*, t.shop_name, t.owner_name FROM bookings b "
                    "JOIN tailors t ON b.tailor_id = t.id "
                    "WHERE b.customer_id = %s ORDER BY b.created_at DESC",
                    (auth['user_id'],),
                )
                bookings = cur.fetchall()
                return build_json_response(200, bookings, 'Bookings loaded.')

            if request.method == 'POST':
                data = get_json_input()
                tailor_id = _int(data.get('tailor_id'))
                service_type = sanitize(data.get('service_type', ''))
                booking_date = sanitize(data.get('booking_date', ''))
                booking_time = sanitize(data.get('booking_time', ''))
                service_mode = sanitize(data.get('service_mode', ''))

                if not all([tailor_id, service_type, booking_date, booking_time, service_mode]):
                    send_json(400, None, 'All booking fields are required.')

                # Feature #1: shop hours are 9 AM – 9 PM only.
                if not _is_valid_booking_time(booking_time):
                    send_json(400, None, 'Please choose a booking time between 9:00 AM and 9:00 PM.')

                cur.execute("SELECT id, service_prices FROM tailors WHERE id = %s AND status = 'active'", (tailor_id,))
                tailor_row = cur.fetchone()
                if not tailor_row:
                    send_json(404, None, 'Tailor not found.')

                # Custom price for this tailor's service if set, else fallback to PRICE_MAP or 300.00
                service_price = PRICE_MAP.get(service_type, 300.00)
                if tailor_row.get('service_prices'):
                    try:
                        sp_map = json.loads(tailor_row['service_prices']) if isinstance(tailor_row['service_prices'], str) else (tailor_row['service_prices'] or {})
                        if service_type in sp_map and float(sp_map[service_type]) > 0:
                            service_price = float(sp_map[service_type])
                    except Exception:
                        pass

                if service_mode == 'Home Service':
                    advance_amount = HOME_VISIT_CHARGE
                    final_amount = service_price
                    payment_stage = 'awaiting_advance'
                else:
                    advance_amount = 0.00
                    final_amount = service_price
                    payment_stage = 'awaiting_measurement'

                total_price = advance_amount + final_amount

                cur.execute(
                    "INSERT INTO bookings (customer_id, tailor_id, service_type, booking_date, "
                    "booking_time, service_mode, price, advance_amount, final_amount, "
                    "measurement_status, payment_stage) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)",
                    (auth['user_id'], tailor_id, service_type, booking_date, booking_time,
                     service_mode, total_price, advance_amount, final_amount, payment_stage),
                )
                booking_id = cur.lastrowid

                return build_json_response(201, {
                    'booking_id': booking_id,
                    'price': total_price,
                    'advance_amount': advance_amount,
                    'final_amount': final_amount,
                    'payment_stage': payment_stage,
                }, 'Booking created successfully!')
    finally:
        conn.close()


# ==================================================================
# backend/measurement.php
# ==================================================================
@app.route('/backend/measurement.php', methods=['GET', 'POST', 'OPTIONS'])
def measurement():
    auth = require_auth(['customer', 'tailor'])
    conn = get_db()
    try:
        with conn.cursor() as cur:
            target_user_id = None

            if auth['role'] == 'customer':
                target_user_id = auth['user_id']
            else:  # tailor
                customer_id = _int(request.args.get('customer_id', 0))
                if request.method == 'POST' and not customer_id:
                    data = get_json_input()
                    customer_id = _int(data.get('customer_id', 0))

                if not customer_id:
                    send_json(400, None, 'Customer ID is required for tailors.')

                cur.execute(
                    "SELECT b.id FROM bookings b JOIN tailors t ON b.tailor_id = t.id "
                    "WHERE t.user_id = %s AND b.customer_id = %s",
                    (auth['user_id'], customer_id),
                )
                if not cur.fetchone():
                    send_json(403, None, "You do not have permission to view/edit this customer's measurements.")

                target_user_id = customer_id

            if request.method == 'GET':
                cur.execute("SELECT * FROM measurements WHERE user_id = %s", (target_user_id,))
                measurement_row = cur.fetchone()
                return build_json_response(200, measurement_row, 'Measurements loaded.' if measurement_row else 'No measurements found.')

            if request.method == 'POST':
                data = get_json_input()
                chest = _float(data.get('chest', 0))
                waist = _float(data.get('waist', 0))
                shoulder = _float(data.get('shoulder', 0))
                arm_length = _float(data.get('arm_length', 0))
                pant_length = _float(data.get('pant_length', 0))
                neck = _float(data.get('neck', 0))
                notes = sanitize(data.get('notes', ''))

                cur.execute("SELECT id FROM measurements WHERE user_id = %s", (target_user_id,))
                existing = cur.fetchone()

                if existing:
                    cur.execute(
                        "UPDATE measurements SET chest=%s, waist=%s, shoulder=%s, arm_length=%s, "
                        "pant_length=%s, neck=%s, notes=%s WHERE user_id=%s",
                        (chest, waist, shoulder, arm_length, pant_length, neck, notes, target_user_id),
                    )
                else:
                    cur.execute(
                        "INSERT INTO measurements (user_id, chest, waist, shoulder, arm_length, "
                        "pant_length, neck, notes) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (target_user_id, chest, waist, shoulder, arm_length, pant_length, neck, notes),
                    )

                return build_json_response(200, None, 'Measurements saved successfully!')
    finally:
        conn.close()


# ==================================================================
# backend/payment.php
# ==================================================================
@app.route('/backend/payment.php', methods=['GET', 'POST', 'OPTIONS'])
def payment():
    require_auth(['customer', 'admin'])
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if request.method == 'GET':
                booking_id = _int(request.args.get('booking_id', 0))
                if not booking_id:
                    send_json(400, None, 'Booking ID is required.')

                cur.execute(
                    "SELECT b.*, t.shop_name, t.owner_name, t.address AS shop_address, "
                    "u_customer.full_name AS customer_name, u_customer.phone AS customer_phone, "
                    "u_customer.email AS customer_email, u_customer.address AS customer_address, "
                    "u_tailor.phone AS tailor_phone "
                    "FROM bookings b "
                    "JOIN tailors t ON b.tailor_id = t.id "
                    "JOIN users u_customer ON b.customer_id = u_customer.id "
                    "JOIN users u_tailor ON t.user_id = u_tailor.id "
                    "WHERE b.id = %s",
                    (booking_id,),
                )
                booking_row = cur.fetchone()
                if not booking_row:
                    send_json(404, None, 'Booking not found.')

                # Feature #3: a booking can now have up to two payment rows
                # (advance + final), so return them as a list instead of a
                # single LEFT JOINed row.
                cur.execute(
                    "SELECT id, payment_type, amount, payment_method, payment_status, "
                    "transaction_id, paid_at FROM payments WHERE booking_id = %s ORDER BY paid_at ASC",
                    (booking_id,),
                )
                booking_row['payments'] = cur.fetchall()

                # Tell the frontend exactly what (if anything) is payable right now.
                due_amount, due_type = _amount_due_for_stage(booking_row)
                booking_row['amount_due'] = due_amount
                booking_row['payment_type_due'] = due_type

                return build_json_response(200, booking_row, 'Booking details loaded.')

            if request.method == 'POST':
                data = get_json_input()
                booking_id = _int(data.get('booking_id', 0))
                payment_method = sanitize(data.get('payment_method', ''))

                if not booking_id or not payment_method:
                    send_json(400, None, 'Booking ID and payment method are required.')

                cur.execute("SELECT * FROM bookings WHERE id = %s", (booking_id,))
                booking_row = cur.fetchone()
                if not booking_row:
                    send_json(404, None, 'Booking not found.')

                # Feature #3: figure out — from the booking's current stage —
                # whether an advance or a final/full payment is due, and how
                # much. This replaces the old "one payment per booking" rule.
                amount_due, payment_type = _amount_due_for_stage(booking_row)

                if payment_type is None:
                    if booking_row['payment_stage'] == 'paid':
                        send_json(400, None, 'Payment already completed for this booking.')
                    else:
                        send_json(
                            400, None,
                            'Please wait for the tailor to take your measurements before making this payment.',
                        )

                txn_id = 'TXN' + uuid.uuid4().hex[:13].upper() + str(random.randint(100, 999))
                payment_status = 'completed'  # demo: online payment always succeeds

                # After this payment, what stage does the booking move to?
                if payment_type == 'advance':
                    next_stage = 'awaiting_measurement'
                else:  # 'final' or 'full'
                    next_stage = 'paid'

                try:
                    conn.begin()
                    cur.execute(
                        "INSERT INTO payments (booking_id, payment_type, amount, payment_method, "
                        "payment_status, transaction_id) VALUES (%s, %s, %s, %s, %s, %s)",
                        (booking_id, payment_type, amount_due, payment_method, payment_status, txn_id),
                    )
                    payment_id = cur.lastrowid
                    cur.execute(
                        "UPDATE bookings SET payment_stage = %s WHERE id = %s",
                        (next_stage, booking_id),
                    )
                    conn.commit()
                except ApiAbort:
                    raise
                except Exception as e:
                    conn.rollback()
                    send_json(500, None, f'Payment failed: {e}')

                return build_json_response(200, {
                    'payment_id': payment_id,
                    'transaction_id': txn_id,
                    'status': payment_status,
                    'payment_type': payment_type,
                    'amount': amount_due,
                    'payment_stage': next_stage,
                }, 'Advance (home-visit charge) payment successful!' if payment_type == 'advance'
                   else 'Payment successful!')
    finally:
        conn.close()


# ==================================================================
# backend/profile.php
# ==================================================================
@app.route('/backend/profile.php', methods=['GET', 'POST', 'OPTIONS'])
def profile():
    auth = require_auth(['customer'])
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if request.method == 'GET':
                cur.execute(
                    "SELECT full_name, email, phone, address FROM users WHERE id = %s",
                    (auth['user_id'],),
                )
                return build_json_response(200, cur.fetchone(), 'Profile loaded.')

            if request.method == 'POST':
                data = get_json_input()
                full_name = sanitize(data.get('full_name', ''))
                phone = sanitize(data.get('phone', ''))
                address = sanitize(data.get('address', ''))

                if not all([full_name, phone, address]):
                    send_json(400, None, 'All fields are required.')

                cur.execute(
                    "UPDATE users SET full_name = %s, phone = %s, address = %s WHERE id = %s",
                    (full_name, phone, address, auth['user_id']),
                )

                session['full_name'] = full_name
                return build_json_response(200, None, 'Profile updated successfully!')
    finally:
        conn.close()


# ==================================================================
# backend/tailor_orders.php
# ==================================================================
@app.route('/backend/tailor_orders.php', methods=['GET', 'POST', 'OPTIONS'])
def tailor_orders():
    auth = require_auth(['tailor'])
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status FROM tailors WHERE user_id = %s", (auth['user_id'],))
            tailor = cur.fetchone()

            if not tailor:
                send_json(404, None, 'Tailor profile not found.')

            if tailor['status'] == 'pending':
                send_json(403, None, 'Your account is pending admin approval. Please wait for verification.')

            tailor_id = tailor['id']

            if request.method == 'GET':
                cur.execute(
                    "SELECT b.*, u.full_name AS customer_name, u.phone AS customer_phone, "
                    "u.email AS customer_email FROM bookings b JOIN users u ON b.customer_id = u.id "
                    "WHERE b.tailor_id = %s ORDER BY b.created_at DESC",
                    (tailor_id,),
                )
                return build_json_response(200, cur.fetchall(), 'Bookings loaded.')

            if request.method == 'POST':
                data = get_json_input()
                booking_id = _int(data.get('booking_id', 0))
                status = sanitize(data.get('status', ''))
                delivery_date = sanitize(data.get('delivery_date', ''))
                measurement_done = bool(data.get('measurement_done', False))

                if not booking_id or (not status and not measurement_done):
                    send_json(400, None, 'Booking ID and status (or measurement_done) are required.')

                cur.execute(
                    "SELECT * FROM bookings WHERE id = %s AND tailor_id = %s",
                    (booking_id, tailor_id),
                )
                booking_row = cur.fetchone()
                if not booking_row:
                    send_json(403, None, 'Booking not found or not authorized.')

                # Feature #3: tailor marks the measurement as taken (either
                # after visiting the customer's home, or in-shop for a shop
                # visit booking). This is what unlocks the payment step.
                if measurement_done:
                    if booking_row['measurement_status'] == 'done':
                        send_json(400, None, 'Measurement has already been recorded for this booking.')

                    if booking_row['payment_stage'] != 'awaiting_measurement':
                        send_json(
                            400, None,
                            'Measurement cannot be marked yet — the customer must complete the required '
                            'payment step first.',
                        )

                    next_stage = 'awaiting_final_payment' if booking_row['service_mode'] == 'Home Service' else 'awaiting_payment'
                    cur.execute(
                        "UPDATE bookings SET measurement_status = 'done', payment_stage = %s WHERE id = %s",
                        (next_stage, booking_id),
                    )

                if status:
                    if status not in VALID_BOOKING_STATUSES:
                        send_json(400, None, 'Invalid status.')

                    if delivery_date:
                        cur.execute(
                            "UPDATE bookings SET status = %s, delivery_date = %s WHERE id = %s",
                            (status, delivery_date, booking_id),
                        )
                    else:
                        cur.execute("UPDATE bookings SET status = %s WHERE id = %s", (status, booking_id))

                return build_json_response(200, None, 'Order updated successfully!')
    finally:
        conn.close()


# ==================================================================
# backend/tailor_dashboard.php  (Feature #4: revenue + customer records)
# ==================================================================
@app.route('/backend/tailor_dashboard.php', methods=['GET', 'OPTIONS'])
def tailor_dashboard():
    auth = require_auth(['tailor'])

    year = _int(request.args.get('year', 0)) or None
    month = _int(request.args.get('month', 0)) or None
    search = sanitize(request.args.get('search', ''))

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status FROM tailors WHERE user_id = %s", (auth['user_id'],))
            tailor = cur.fetchone()
            if not tailor:
                send_json(404, None, 'Tailor profile not found.')
            if tailor['status'] == 'pending':
                send_json(403, None, 'Your account is pending admin approval. Please wait for verification.')
            tailor_id = tailor['id']

            # Revenue grouped by month/year (all completed payments —
            # advance + final — for this tailor's bookings).
            cur.execute(
                "SELECT DATE_FORMAT(p.paid_at, '%%Y-%%m') AS month, "
                "SUM(p.amount) AS revenue, COUNT(DISTINCT p.booking_id) AS paid_orders "
                "FROM payments p JOIN bookings b ON p.booking_id = b.id "
                "WHERE b.tailor_id = %s AND p.payment_status = 'completed' "
                "GROUP BY month ORDER BY month DESC",
                (tailor_id,),
            )
            monthly_revenue = cur.fetchall()

            # Customer records — one row per customer who has booked with
            # this tailor, with mobile number, total bookings, and total
            # amount paid. Filterable by year, month, and name/mobile search.
            where = ["b.tailor_id = %s"]
            params = [tailor_id]
            if year:
                where.append("YEAR(b.created_at) = %s")
                params.append(year)
            if month:
                where.append("MONTH(b.created_at) = %s")
                params.append(month)
            if search:
                where.append("(u.full_name LIKE %s OR u.phone LIKE %s)")
                params.extend([f'%{search}%', f'%{search}%'])

            cur.execute(
                "SELECT u.id AS customer_id, u.full_name, u.phone, u.email, "
                "COUNT(DISTINCT b.id) AS total_bookings, "
                "COALESCE(SUM(CASE WHEN p.payment_status = 'completed' THEN p.amount ELSE 0 END), 0) AS total_spent, "
                "MAX(b.created_at) AS last_booking "
                "FROM bookings b JOIN users u ON b.customer_id = u.id "
                "LEFT JOIN payments p ON p.booking_id = b.id "
                f"WHERE {' AND '.join(where)} "
                "GROUP BY u.id, u.full_name, u.phone, u.email "
                "ORDER BY last_booking DESC",
                params,
            )
            customers = cur.fetchall()

            # Overall summary numbers for the top of the dashboard.
            cur.execute(
                "SELECT COALESCE(SUM(p.amount), 0) AS total_revenue, "
                "COUNT(DISTINCT b.customer_id) AS total_customers, "
                "COUNT(DISTINCT b.id) AS total_bookings "
                "FROM bookings b LEFT JOIN payments p ON p.booking_id = b.id AND p.payment_status = 'completed' "
                "WHERE b.tailor_id = %s",
                (tailor_id,),
            )
            summary = cur.fetchone()

            return build_json_response(200, {
                'summary': summary,
                'monthly_revenue': monthly_revenue,
                'customers': customers,
            }, 'Dashboard data loaded.')
    finally:
        conn.close()


# ==================================================================
# backend/tailor_dashboard_export.php  (Feature #4: share/export as CSV)
# ==================================================================
@app.route('/backend/tailor_dashboard_export.php', methods=['GET', 'OPTIONS'])
def tailor_dashboard_export():
    auth = require_auth(['tailor'])

    year = _int(request.args.get('year', 0)) or None
    month = _int(request.args.get('month', 0)) or None
    search = sanitize(request.args.get('search', ''))

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status FROM tailors WHERE user_id = %s", (auth['user_id'],))
            tailor = cur.fetchone()
            if not tailor:
                send_json(404, None, 'Tailor profile not found.')
            if tailor['status'] == 'pending':
                send_json(403, None, 'Your account is pending admin approval. Please wait for verification.')
            tailor_id = tailor['id']

            where = ["b.tailor_id = %s"]
            params = [tailor_id]
            if year:
                where.append("YEAR(b.created_at) = %s")
                params.append(year)
            if month:
                where.append("MONTH(b.created_at) = %s")
                params.append(month)
            if search:
                where.append("(u.full_name LIKE %s OR u.phone LIKE %s)")
                params.extend([f'%{search}%', f'%{search}%'])

            cur.execute(
                "SELECT u.full_name, u.phone, u.email, "
                "COUNT(DISTINCT b.id) AS total_bookings, "
                "COALESCE(SUM(CASE WHEN p.payment_status = 'completed' THEN p.amount ELSE 0 END), 0) AS total_spent, "
                "MAX(b.created_at) AS last_booking "
                "FROM bookings b JOIN users u ON b.customer_id = u.id "
                "LEFT JOIN payments p ON p.booking_id = b.id "
                f"WHERE {' AND '.join(where)} "
                "GROUP BY u.id, u.full_name, u.phone, u.email "
                "ORDER BY last_booking DESC",
                params,
            )
            customers = cur.fetchall()
    finally:
        conn.close()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['Customer Name', 'Mobile Number', 'Email', 'Total Bookings', 'Total Spent (₹)', 'Last Booking'])
    for c in customers:
        writer.writerow([c['full_name'], c['phone'], c['email'], c['total_bookings'], c['total_spent'], c['last_booking']])

    return Response(
        buffer.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=customer_records.csv'},
    )


# ==================================================================
# backend/review.php  (v4: customer submits star rating + comment after paid booking)
# ==================================================================
@app.route('/backend/review.php', methods=['GET', 'POST', 'OPTIONS'])
def review():
    auth = require_auth(['customer'])
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if request.method == 'GET':
                # Check if customer already reviewed a specific booking.
                booking_id = _int(request.args.get('booking_id', 0))
                if not booking_id:
                    send_json(400, None, 'booking_id is required.')
                cur.execute("SELECT * FROM reviews WHERE booking_id = %s AND customer_id = %s",
                            (booking_id, auth['user_id']))
                review_row = cur.fetchone()
                return build_json_response(200, review_row, 'Review loaded.')

            if request.method == 'POST':
                data = get_json_input()
                booking_id = _int(data.get('booking_id', 0))
                rating = _float(data.get('rating', 0))
                comment = sanitize(data.get('comment', ''))

                if not booking_id:
                    send_json(400, None, 'booking_id is required.')
                if rating < 1 or rating > 5:
                    send_json(400, None, 'Rating must be between 1 and 5.')

                # Verify the booking belongs to this customer and is fully paid.
                cur.execute(
                    "SELECT b.tailor_id, b.payment_stage FROM bookings b "
                    "WHERE b.id = %s AND b.customer_id = %s",
                    (booking_id, auth['user_id']),
                )
                booking_row = cur.fetchone()
                if not booking_row:
                    send_json(404, None, 'Booking not found.')
                if booking_row['payment_stage'] != 'paid':
                    send_json(400, None, 'You can only review a booking after full payment is completed.')

                tailor_id = booking_row['tailor_id']

                # Prevent duplicate reviews.
                cur.execute("SELECT id FROM reviews WHERE booking_id = %s", (booking_id,))
                if cur.fetchone():
                    send_json(409, None, 'You have already reviewed this booking.')

                # Save the review.
                cur.execute(
                    "INSERT INTO reviews (booking_id, customer_id, tailor_id, rating, comment) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (booking_id, auth['user_id'], tailor_id, rating, comment),
                )

                # Recalculate tailor's average rating from all reviews.
                cur.execute(
                    "SELECT AVG(rating) AS avg_rating, COUNT(*) AS total "
                    "FROM reviews WHERE tailor_id = %s",
                    (tailor_id,),
                )
                stats = cur.fetchone()
                new_avg = round(float(stats['avg_rating'] or rating), 1)
                cur.execute("UPDATE tailors SET rating = %s WHERE id = %s", (new_avg, tailor_id))

                return build_json_response(201, {'new_rating': new_avg},
                                           'Thank you for your review!')
    finally:
        conn.close()


# ==================================================================
# backend/admin.php
# ==================================================================
@app.route('/backend/admin.php', methods=['GET', 'POST', 'OPTIONS'])
def admin():
    require_auth(['admin'])
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if request.method == 'GET':
                cur.execute(
                    "SELECT id, full_name, email, phone, address, created_at FROM users "
                    "WHERE role = 'customer' ORDER BY created_at DESC"
                )
                customers = cur.fetchall()

                cur.execute(
                    "SELECT t.*, u.full_name, u.email, u.phone, u.created_at AS user_created "
                    "FROM tailors t JOIN users u ON t.user_id = u.id "
                    "WHERE t.status = 'active' ORDER BY t.created_at DESC"
                )
                active_tailors = cur.fetchall()

                cur.execute(
                    "SELECT t.*, u.full_name, u.email, u.phone, u.address AS user_address, "
                    "u.created_at AS user_created FROM tailors t JOIN users u ON t.user_id = u.id "
                    "WHERE t.status = 'pending' ORDER BY t.created_at DESC"
                )
                pending_tailors = cur.fetchall()

                # v4: also return rejected tailors so admin can permanently delete them.
                cur.execute(
                    "SELECT t.*, u.full_name, u.email, u.phone, u.address AS user_address, "
                    "u.created_at AS user_created FROM tailors t JOIN users u ON t.user_id = u.id "
                    "WHERE t.status = 'rejected' ORDER BY t.created_at DESC"
                )
                rejected_tailors = cur.fetchall()

                cur.execute(
                    "SELECT b.*, u.full_name AS customer_name, t.shop_name FROM bookings b "
                    "JOIN users u ON b.customer_id = u.id JOIN tailors t ON b.tailor_id = t.id "
                    "ORDER BY b.created_at DESC"
                )
                bookings = cur.fetchall()

                cur.execute(
                    "SELECT p.*, u.full_name AS customer_name FROM payments p "
                    "JOIN bookings b ON p.booking_id = b.id JOIN users u ON b.customer_id = u.id "
                    "ORDER BY p.paid_at DESC"
                )
                payments = cur.fetchall()

                return build_json_response(200, {
                    'customers': customers,
                    'tailors': active_tailors,
                    'pending_tailors': pending_tailors,
                    'rejected_tailors': rejected_tailors,
                    'bookings': bookings,
                    'payments': payments,
                }, 'Admin data loaded.')

            if request.method == 'POST':
                data = get_json_input()
                action = sanitize(data.get('action', ''))

                if action == 'approve_tailor':
                    tailor_id = _int(data.get('tailor_id', 0))
                    if not tailor_id:
                        send_json(400, None, 'Tailor ID is required.')

                    cur.execute("UPDATE tailors SET status = 'active' WHERE id = %s", (tailor_id,))
                    if cur.rowcount > 0:
                        return build_json_response(200, None, 'Tailor approved successfully! They will now appear on the website.')
                    else:
                        send_json(404, None, 'Tailor not found.')

                if action == 'reject_tailor':
                    # v4: Instead of deleting immediately, mark status='rejected' and
                    # save the admin's reason. The tailor sees the reason on next login.
                    tailor_id = _int(data.get('tailor_id', 0))
                    reason = sanitize(data.get('reason', '')).strip()
                    if not tailor_id:
                        send_json(400, None, 'Tailor ID is required.')
                    if not reason:
                        send_json(400, None, 'Please provide a rejection reason.')

                    cur.execute("SELECT id FROM tailors WHERE id = %s", (tailor_id,))
                    if not cur.fetchone():
                        send_json(404, None, 'Tailor not found.')

                    cur.execute(
                        "UPDATE tailors SET status = 'rejected', rejection_reason = %s WHERE id = %s",
                        (reason, tailor_id),
                    )
                    return build_json_response(200, None, 'Tailor rejected. The reason has been saved and will be shown to the tailor on their next login attempt.')

                if action == 'delete_rejected_tailor':
                    # Permanently delete a rejected tailor (separate deliberate action).
                    tailor_id = _int(data.get('tailor_id', 0))
                    if not tailor_id:
                        send_json(400, None, 'Tailor ID is required.')

                    cur.execute("SELECT user_id FROM tailors WHERE id = %s AND status = 'rejected'", (tailor_id,))
                    tailor = cur.fetchone()
                    if not tailor:
                        send_json(404, None, 'Tailor not found or not in rejected state.')

                    conn.begin()
                    cur.execute("DELETE FROM tailors WHERE id = %s", (tailor_id,))
                    cur.execute("DELETE FROM users WHERE id = %s", (tailor['user_id'],))
                    conn.commit()
                    return build_json_response(200, None, 'Rejected tailor account permanently deleted.')

                if action == 'update_rating':
                    # There is no customer review system yet, so the admin
                    # sets/corrects a tailor's star rating directly — this is
                    # what the city/rating/price filters on the customer
                    # dashboard actually filter against.
                    tailor_id = _int(data.get('tailor_id', 0))
                    rating = _float(data.get('rating', -1), -1)
                    if not tailor_id:
                        send_json(400, None, 'Tailor ID is required.')
                    if rating < 0 or rating > 5:
                        send_json(400, None, 'Rating must be between 0 and 5.')

                    cur.execute("UPDATE tailors SET rating = %s WHERE id = %s", (rating, tailor_id))
                    if cur.rowcount > 0:
                        return build_json_response(200, None, 'Tailor rating updated.')
                    else:
                        send_json(404, None, 'Tailor not found.')

                if action == 'delete_user':
                    user_id = _int(data.get('user_id', 0))
                    if not user_id:
                        send_json(400, None, 'User ID is required.')

                    cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                    user = cur.fetchone()
                    if not user:
                        send_json(404, None, 'User not found.')
                    if user['role'] == 'admin':
                        send_json(403, None, 'Cannot delete admin users.')

                    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                    return build_json_response(200, None, 'User deleted successfully.')

                send_json(400, None, 'Invalid action.')
    finally:
        conn.close()


# ==================================================================
# backend/tailor_profile.php (Tailor profile & services management)
# ==================================================================
@app.route('/backend/tailor_profile.php', methods=['GET', 'POST', 'OPTIONS'])
def tailor_profile():
    auth = require_auth(['tailor'])
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT t.*, u.full_name, u.email, u.phone FROM tailors t "
                "JOIN users u ON t.user_id = u.id WHERE t.user_id = %s",
                (auth['user_id'],)
            )
            tailor = cur.fetchone()
            if not tailor:
                send_json(404, None, 'Tailor profile not found.')

            if request.method == 'GET':
                if tailor.get('service_prices'):
                    try:
                        tailor['service_prices'] = json.loads(tailor['service_prices'])
                    except Exception:
                        tailor['service_prices'] = {}
                else:
                    tailor['service_prices'] = {}
                return build_json_response(200, tailor, 'Profile loaded.')

            if request.method == 'POST':
                data = get_json_input()
                shop_name = sanitize(data.get('shop_name', ''))
                owner_name = sanitize(data.get('owner_name', ''))
                address = sanitize(data.get('address', ''))
                city = sanitize(data.get('city', ''))
                starting_price = _float(data.get('starting_price', 0), 0)

                raw_category = data.get('category', '')
                if isinstance(raw_category, list):
                    selected_cats = [sanitize(c) for c in raw_category if sanitize(c)]
                else:
                    selected_cats = [c.strip() for c in sanitize(raw_category).split(',') if c.strip()]
                selected_cats = [c for c in selected_cats if c in VALID_CATEGORIES]
                if not selected_cats:
                    send_json(400, None, 'Please select at least one category (Men, Women, or Kids).')
                category = ','.join(selected_cats)

                raw_services = data.get('services', '')
                if isinstance(raw_services, list):
                    selected_services = [sanitize(s) for s in raw_services if sanitize(s)]
                else:
                    selected_services = [s.strip() for s in sanitize(raw_services).split(',') if s.strip()]
                selected_services = [s for s in selected_services if s in VALID_SERVICES]
                if not selected_services:
                    send_json(400, None, 'Please select at least one service.')
                services = ','.join(selected_services)

                service_prices_raw = data.get('service_prices', {})
                service_prices_dict = {}
                if isinstance(service_prices_raw, dict):
                    for k, v in service_prices_raw.items():
                        s_name = sanitize(k)
                        if s_name in selected_services:
                            p_val = _float(v, 0)
                            if p_val > 0:
                                service_prices_dict[s_name] = p_val
                service_prices_str = json.dumps(service_prices_dict) if service_prices_dict else None

                if service_prices_dict and (starting_price <= 0 or starting_price > min(service_prices_dict.values())):
                    starting_price = min(service_prices_dict.values())

                if not shop_name or not owner_name or not city:
                    send_json(400, None, 'Shop name, owner name, and city are required.')

                if starting_price <= 0:
                    send_json(400, None, 'Please enter a valid starting price.')

                cur.execute(
                    "UPDATE tailors SET shop_name = %s, owner_name = %s, address = %s, city = %s, "
                    "category = %s, services = %s, service_prices = %s, starting_price = %s WHERE id = %s",
                    (shop_name, owner_name, address, city, category, services, service_prices_str, starting_price, tailor['id']),
                )

                return build_json_response(200, None, 'Profile & services updated successfully!')
    finally:
        conn.close()


# ------------------------------------------------------------------
# Small utilities
# ------------------------------------------------------------------
def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_valid_email(email):
    return re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email) is not None


def _is_valid_phone(phone):
    """Feature #5: exactly 10 digits, numeric only."""
    return re.match(r'^\d{10}$', phone or '') is not None


def _is_valid_booking_time(time_str):
    """Feature #1: booking slots must fall between 9:00 AM and 9:00 PM."""
    m = re.match(r'^(\d{1,2}):(\d{2})', time_str or '')
    if not m:
        return False
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return False
    total_minutes = hour * 60 + minute
    return SHOP_OPEN_MINUTES <= total_minutes <= SHOP_CLOSE_MINUTES


def _amount_due_for_stage(booking_row):
    """Feature #3: given a booking's current payment_stage, return
    (amount_due, payment_type) — or (0, None) if nothing is payable right
    now (either already paid, or still waiting on a measurement)."""
    stage = booking_row['payment_stage']
    if stage == 'awaiting_advance':
        return float(booking_row['advance_amount']), 'advance'
    if stage == 'awaiting_final_payment':
        return float(booking_row['final_amount']), 'final'
    if stage == 'awaiting_payment':
        return float(booking_row['final_amount']), 'full'
    return 0.0, None


def _hash_password(plain_password):
    """Equivalent of PHP password_hash($password, PASSWORD_DEFAULT) (bcrypt)."""
    return bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _verify_password(plain_password, stored_hash):
    """Verify a password against a hash produced by PHP's password_hash()
    (bcrypt, $2y$/$2a$/$2b$) or by _hash_password() above — both use the
    same bcrypt algorithm so hashes are fully interchangeable."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), stored_hash.encode('utf-8'))
    except (ValueError, TypeError):
        return False


# ==================================================================
# Static frontend serving (index.html, css/, js/, customer/, tailor/, admin/)
# ==================================================================
FRONTEND_ROOT = config.BASE_DIR


@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_ROOT, 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(FRONTEND_ROOT, filename)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True, use_reloader=False)
