# Tailor Booking System — Python Backend

This project has been migrated from a **PHP** backend to a **Python (Flask)**
backend, and later extended with five feature updates on top of that
conversion (see **"v2 Feature Updates"** below): shop-hour booking limits,
tailor service categories, a staged home-visit/final payment flow, a tailor
revenue & customer-records dashboard, and stricter registration validation.

## v2 Feature Updates

1. **Booking time limit (9 AM – 9 PM)** — Customers can only book a slot
   between 9:00 AM and 9:00 PM. Enforced both in the browser (the time
   picker rejects times outside this range) and on the server (so it can't
   be bypassed by calling the API directly).

2. **Tailor service categories (Men / Women / Kids)** — Tailors pick one or
   more categories at registration. Customers can filter the tailor list on
   the dashboard by category (`GET /backend/tailors.php?category=Men`, etc).

3. **Staged payment flow** — Replaces "pay everything up front":
   - **Home Service**: the customer pays a **₹100 home-visit charge**
     first to confirm the booking. Only after the tailor visits and marks
     the measurement as taken does the **remaining service amount**
     become payable.
   - **Shop Visit**: no payment is collected until the tailor takes the
     customer's measurements in-shop and marks it done — then the **full
     service amount** becomes payable.
   - A booking now moves through `payment_stage` values:
     `awaiting_advance → awaiting_measurement → awaiting_final_payment` (Home
     Service) or `awaiting_measurement → awaiting_payment` (Shop Visit) →
     `paid`. Each stage's payment is stored as its own row in `payments`
     (`payment_type` = `advance` / `final` / `full`), so a booking can now
     have more than one payment record.
   - Tailors mark a measurement as taken from their dashboard ("Mark
     Measured" button), which calls `tailor_orders.php` with
     `{ measurement_done: true }` and unlocks the next payment step for the
     customer.

4. **Tailor dashboard — revenue & customer records** — A new
   `GET /backend/tailor_dashboard.php` endpoint returns: total revenue,
   monthly revenue breakdown, and a customer-records table (name, **mobile
   number**, email, total bookings, total spent, last booking date) —
   filterable by `?year=`, `?month=`, and `?search=` (name or mobile).
   `GET /backend/tailor_dashboard_export.php` returns the same customer
   records as a downloadable/shareable CSV file.

5. **Stricter registration validation** — Phone numbers must be exactly 10
   digits (validated client-side as you type, and again on the server), and
   must be unique across accounts, just like email.

## v3 Feature Updates (Search, Filters, City & Ratings)

6. **Full tailor search & filter system** — The customer dashboard now has:
   - A **search box** (matches shop name, owner name, or services).
   - A **City** dropdown — populated dynamically from `GET
     /backend/filter_options.php`, which returns every distinct city a tailor
     has registered with (no hardcoded city list to keep in sync).
   - A **Rating** dropdown (Any / 4.5+ / 4.0+ / 3.0+).
   - A **Price** dropdown using fixed buckets (Under ₹500, ₹500–₹1000,
     ₹1000–₹2000, Above ₹2000) based on each tailor's `starting_price`.
   - A **Sort** dropdown (Newest, Highest Rated, Price Low→High, Price
     High→Low).
   - The existing category chips (Men/Women/Kids) still work and combine
     with every other filter.
   - All filters combine via `GET /backend/tailors.php?category=&city=&
     search=&min_rating=&price_range=&sort=` — every parameter is optional
     and AND-combined server-side with parameterised queries.

7. **Tailor sign-up changes** — Three changes to tailor registration:
   - **City** (required text field) — this is what customers filter by.
   - **Starting Price** (required number field, "Starting from ₹X") — shown
     on the tailor's card and used for the customer-side price filter.
   - **Services Offered** is now a **multi-select dropdown** (`<select
     multiple>`) from a fixed list (Shirt/Pant/Suit/Alteration/Blouse/Kurta/
     Lehenga/Sherwani Stitching, Saree Fall & Pico, Other) instead of a free
     -text box — this keeps service names consistent for search/filtering.

   New tailors start with a **default rating of 4.5** (there is no customer
   review system yet, so ratings aren't earned automatically). An admin can
   correct any tailor's rating from the Admin Dashboard's Tailors tab (a
   small number input + save button next to each approved tailor) — this
   calls `POST /backend/admin.php` with `{ action: 'update_rating',
   tailor_id, rating }`.

If you're upgrading an **existing v2 database**, run `migrate_v3.sql`
(adds `city`, `rating`, and `starting_price` to `tailors` without touching
existing rows). A fresh `database.sql` install already includes all three
columns.

If you're upgrading an **existing** database instead of starting fresh, run
`migrate_v2.sql` (documented further down) instead of re-running
`database.sql`.

## v3 Feature Updates

6. **Full tailor search & filter system** — The customer dashboard now has a complete
   filter bar: free-text search (matches shop name, owner name, or services),
   a **City** dropdown (populated live from `GET /backend/filter_options.php`,
   so it always reflects real tailors in the database), a **minimum rating**
   dropdown, a **price range** dropdown, and a **sort** dropdown (Newest,
   Highest Rated, Price Low→High, Price High→Low). All filters combine
   together and are sent as query parameters to
   `GET /backend/tailors.php?category=&city=&search=&min_rating=&price_range=&sort=`.

7. **City, rating, and starting price added to tailors** — The `tailors` table
   gained three columns: `city`, `rating` (defaults to 4.5 — there is no
   customer review system yet, so an **admin can edit a tailor's rating**
   directly from the admin dashboard), and `starting_price` (set by the
   tailor at registration, shown on their card as "Starting from ₹X" and used
   by the price-range filter).

8. **Tailor sign-up: Services Offered is now a dropdown, not free text** — The
   old free-text "Services Offered" input on `register.html` is now a
   multi-select `<select>` dropdown drawn from a fixed list (Shirt Stitching,
   Pant Stitching, Suit Stitching, Alteration, Blouse Stitching, Kurta
   Stitching, Lehenga Stitching, Sherwani Stitching, Saree Fall & Pico,
   Other). Tailor sign-up also now requires a **City** field and a
   **Starting Price** field. The booking page (`customer/booking.html`) in
   turn loads each tailor's *actual* selected services via
   `GET /backend/tailors.php?id=<tailor_id>` instead of showing a fixed
   4-option list, so customers only see services that tailor really offers.

If you're upgrading an **existing v2** database, run `migrate_v3.sql` (in
addition to the already-applied `migrate_v2.sql`) instead of re-running
`database.sql`, so existing accounts and bookings aren't lost. Tailors who
registered before this migration will have an empty `city` — update it
manually (see the comment inside `migrate_v3.sql`) or have them re-save it
once a profile-edit flow for tailors exists.

## PHP → Python Migration (v1)

Every original PHP endpoint has a matching Flask route with the **same URL
style, same HTTP methods, and the same overall business rules** (validation
messages, status codes, session handling, admin approval flow, etc).

| Original (PHP)                     | New (Python)                          |
|-------------------------------------|----------------------------------------|
| `config/database.php`               | `config.py` + helpers in `app.py`      |
| `backend/*.php`                     | Routes in `app.py` (e.g. `/backend/login.php`) |
| PDO + MySQL                         | PyMySQL + MySQL (`database.sql`)       |
| `password_hash()` / `password_verify()` (bcrypt) | Python `bcrypt` library (fully compatible — verifies existing PHP-generated hashes and vice versa) |
| PHP `$_SESSION`                     | Flask `session` (signed cookie)        |

The API routes intentionally kept their original `.php`-style names
(`/backend/login.php`, `/backend/booking.php`, etc.) so the existing
frontend JavaScript needed the smallest possible change.

## Project structure

```
app.py                  # Flask app — all backend routes/logic
config.py               # DB connection settings + secret key
requirements.txt        # Python dependencies
database.sql            # MySQL schema for a FRESH install (v2, includes all 5 features)
migrate_v2.sql          # ALTER-only script to upgrade an EXISTING v1 database to v2
migrate_v3.sql          # ALTER-only script to upgrade an EXISTING v2 database to v3
index.html, login.html, register.html
css/style.css
js/script.js             # API_BASE points to /backend
customer/*.html           # booking.html, payment.html, order_summary.html, measurement.html, profile.html, dashboard.html
tailor/dashboard.html     # order management + revenue/customer-records dashboard
admin/*.html
tailor_chatbot.py        # Standalone CLI chatbot demo (unrelated to the web backend)

```

## Setup

### 1. Install MySQL / MariaDB and create the database

```bash
mysql -u root -p < database.sql
```

This creates the `tailor_booking` database with all tables and a default
admin account:

- **Email:** `admin@tailor.com`
- **Password:** `admin123`

### 2. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure the database connection (optional)

By default the app connects to `localhost` / database `tailor_booking` /
user `root` / empty password — the same defaults the original PHP app used.
For local development, Flask generates a temporary session key each time it
starts. Set `SECRET_KEY` to a stable random value when deploying, and set
`DB_PASSWORD` if your database requires a password:

```bash
export DB_HOST=localhost
export DB_NAME=tailor_booking
export DB_USER=root
export DB_PASSWORD=yourpassword
export SECRET_KEY=some-random-secret-string
```

### 4. Run the app

```bash
python app.py
```

The site will be available at **http://localhost:5000**. Flask serves both
the frontend pages and the `/backend/*` API routes, so no separate web
server is required for local development.

For production, run it behind a real WSGI server instead of the Flask dev
server, e.g.:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## Notes / behavior preserved from the original PHP app

- Admins **cannot** log in through the regular `/backend/login.php`
  endpoint — they must use `/backend/admin_login.php` (same as before).
- New tailor registrations are created with `status = 'pending'` and only
  appear in `/backend/tailors.php` and can only access
  `/backend/tailor_orders.php` after an admin approves them from the admin
  dashboard.
- Service pricing (`Shirt Stitching`, `Pant Stitching`, `Suit Stitching`,
  `Alteration`, `+₹100` for Home Service) is identical to the original
  `backend/booking.php` price map.
- "Online Payment" always completes successfully — this was a demo
  simplification in the original PHP code and has been kept as-is.

This migration ported the existing logic as-is; it did not change any
security model or fix pre-existing issues (e.g. `payment.php` does not
verify the requesting customer owns the booking) — flag any of these if
you'd like them hardened as a follow-up.
