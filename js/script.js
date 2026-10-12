// =============================================
// Tailor Booking System — Global JavaScript
// =============================================

const API_BASE = '/backend';

// --- API Fetch Utility ---
async function fetchAPI(endpoint, method = 'GET', data = null) {
    const config = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    };
    if (data) {
        config.body = JSON.stringify(data);
    }
    try {
        const response = await fetch(`${API_BASE}/${endpoint}`, config);
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.message || 'Something went wrong.');
        }
        return result;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// --- Alert System ---
function showAlert(message, type = 'error', containerId = 'alert-container') {
    const container = document.getElementById(containerId);
    if (!container) return;

    const iconMap = {
        'success': 'fa-circle-check',
        'error': 'fa-triangle-exclamation',
        'info': 'fa-circle-info'
    };

    container.innerHTML = `
        <div class="alert-custom alert-${type}">
            <i class="fa-solid ${iconMap[type] || iconMap.error}"></i>
            <span>${message}</span>
        </div>
    `;

    setTimeout(() => { container.innerHTML = ''; }, 5000);
}

// --- Auth Check ---
async function checkAuth() {
    try {
        const result = await fetchAPI('auth_check.php');
        return result.data || null;
    } catch {
        return null;
    }
}

// --- Logout ---
async function logout() {
    try {
        await fetchAPI('logout.php', 'POST');
    } catch (e) { /* ignore */ }
    window.location.href = getBasePath() + 'login.html';
}

// --- Base Path Helper (handles subfolder pages) ---
function getBasePath() {
    const path = window.location.pathname;
    if (path.includes('/customer/') || path.includes('/tailor/') || path.includes('/admin/')) {
        return '../';
    }
    return '';
}

// --- Profile Dropdown Toggle ---
function toggleProfileMenu() {
    const menu = document.getElementById('profileMenu');
    if (menu) {
        menu.classList.toggle('show');
    }
}

// Close dropdown when clicking outside
document.addEventListener('click', function (e) {
    const menu = document.getElementById('profileMenu');
    const icon = document.querySelector('.profile-icon');
    if (menu && icon && !icon.contains(e.target) && !menu.contains(e.target)) {
        menu.classList.remove('show');
    }
});

// --- Navbar Scroll Effect ---
window.addEventListener('scroll', function () {
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    }
});

// --- Build Navbar ---
function buildNavbar(user = null, activePage = '') {
    const basePath = getBasePath();
    const isLoggedIn = user !== null;

    let navRight = '';
    if (isLoggedIn) {
        const initial = user.full_name ? user.full_name.charAt(0).toUpperCase() : 'U';
        let dashboardLink = basePath + 'customer/dashboard.html';
        if (user.role === 'tailor') dashboardLink = basePath + 'tailor/dashboard.html';
        if (user.role === 'admin') dashboardLink = basePath + 'admin/dashboard.html';

        let profileLinks = '';
        if (user.role === 'customer') {
            profileLinks = `
                <a href="${basePath}customer/profile.html"><i class="fa-solid fa-user"></i> Personal Details</a>
                <a href="${basePath}customer/measurement.html"><i class="fa-solid fa-ruler"></i> Measurement</a>
                <div class="divider"></div>
            `;
        }

        navRight = `
            <div class="profile-dropdown">
                <div class="profile-icon" onclick="toggleProfileMenu()" title="${user.full_name}">
                    ${initial}
                </div>
                <div class="profile-menu" id="profileMenu">
                    <div style="padding: 0.7rem 1.2rem; border-bottom: 1px solid var(--gray-lighter);">
                        <div style="font-weight: 700; font-size: 0.95rem;">${user.full_name}</div>
                        <div style="font-size: 0.8rem; color: var(--gray);">${user.email}</div>
                    </div>
                    <a href="${dashboardLink}"><i class="fa-solid fa-table-columns"></i> Dashboard</a>
                    ${profileLinks}
                    <a href="#" onclick="logout(); return false;" class="logout"><i class="fa-solid fa-right-from-bracket"></i> Logout</a>
                </div>
            </div>
        `;
    } else {
        navRight = `
            <a href="${basePath}login.html" class="btn-secondary-custom btn-sm-custom">Login</a>
            <a href="${basePath}register.html" class="btn-primary-custom btn-sm-custom">Sign Up</a>
        `;
    }

    let homeLink = basePath + 'index.html';
    if (isLoggedIn && user.role === 'customer') homeLink = basePath + 'customer/dashboard.html';
    if (isLoggedIn && user.role === 'tailor') homeLink = basePath + 'tailor/dashboard.html';
    if (isLoggedIn && user.role === 'admin') homeLink = basePath + 'admin/dashboard.html';

    return `
        <nav class="navbar">
            <div class="container flex-between">
                <a href="${homeLink}" class="navbar-brand">
                    <i class="fa-solid fa-scissors"></i> Smart Tailor
                </a>
                <div class="nav-links" style="display:flex; align-items:center; gap:1rem;">
                    <a href="${basePath}index.html" class="nav-link ${activePage === 'home' ? 'active' : ''}">Home</a>
                    <a href="${basePath}index.html#about" class="nav-link ${activePage === 'about' ? 'active' : ''}">About Us</a>
                    ${navRight}
                </div>
            </div>
        </nav>
    `;
}

// --- Build Footer ---
function buildFooter() {
    const basePath = getBasePath();
    return `
        <footer class="footer">
            <div class="container">
                <div class="grid-3" style="margin-bottom: 1.5rem;">
                    <div>
                        <h5><i class="fa-solid fa-scissors" style="color:var(--accent);margin-right:8px;"></i>Smart Tailor</h5>
                        <p style="font-size:0.9rem;">Your one-stop platform for finding expert tailors, booking stitching services, and managing orders seamlessly.</p>
                    </div>
                    <div>
                        <h5>Quick Links</h5>
                        <div style="display:flex;flex-direction:column;gap:0.4rem;">
                            <a href="${basePath}index.html">Home</a>
                            <a href="${basePath}index.html#about">About Us</a>
                            <a href="${basePath}register.html">Register</a>
                            <a href="${basePath}login.html">Login</a>
                        </div>
                    </div>
                    <div>
                        <h5>Contact</h5>
                        <p style="font-size:0.9rem;"><i class="fa-solid fa-envelope" style="margin-right:8px;"></i> support@smarttailor.com</p>
                        <p style="font-size:0.9rem;"><i class="fa-solid fa-phone" style="margin-right:8px;"></i> +91 98765 43210</p>
                        <p style="font-size:0.9rem;"><i class="fa-solid fa-location-dot" style="margin-right:8px;"></i> India</p>
                    </div>
                </div>
                <div class="footer-bottom">
                    <p>&copy; 2026 Smart Tailor. All rights reserved. | College Project</p>
                </div>
            </div>
        </footer>
    `;
}

// --- Initialize Page ---
async function initPage(activePage = '', requireLogin = false, allowedRoles = []) {
    const user = await checkAuth();

    // Insert navbar & footer
    const navbarEl = document.getElementById('navbar-container');
    if (navbarEl) navbarEl.innerHTML = buildNavbar(user, activePage);

    const footerEl = document.getElementById('footer-container');
    if (footerEl) footerEl.innerHTML = buildFooter();

    // Auth guard
    if (requireLogin && !user) {
        window.location.href = getBasePath() + 'login.html';
        return null;
    }

    if (requireLogin && allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
        window.location.href = getBasePath() + 'login.html';
        return null;
    }

    return user;
}

// --- Form Validation Helper ---
function validateForm(fields) {
    for (const [name, value] of Object.entries(fields)) {
        if (!value || value.trim() === '') {
            return `${name} is required.`;
        }
    }
    return null;
}

// --- Format Date ---
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' });
}

// --- Format Price ---
function formatPrice(amount) {
    return '₹' + parseFloat(amount || 0).toFixed(2);
}

// --- Status Badge ---
function getStatusBadge(status) {
    const map = {
        'pending': 'badge-pending',
        'accepted': 'badge-accepted',
        'in_progress': 'badge-progress',
        'completed': 'badge-completed',
        'cancelled': 'badge-cancelled'
    };
    const display = status.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
    return `<span class="badge-custom ${map[status] || 'badge-pending'}">${display}</span>`;
}
