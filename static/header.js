function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
}

let currentSection = '';

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) sidebar.classList.toggle('show');
}

function toggleMenu() {
    const nav = document.getElementById('sv-mobile-nav');
    if (nav) {
        nav.classList.toggle('active');
        nav.setAttribute('aria-hidden', nav.classList.contains('active') ? 'false' : 'true');
    }
}

function closeMobileMenu() {
    const nav = document.getElementById('sv-mobile-nav');
    if (nav) {
        nav.classList.remove('active');
        nav.setAttribute('aria-hidden', 'true');
    }
}

function showContent(section) {
    if (section === 'myVotes') {
        window.location.href = '/my_votes';
        return;
    }
    if (section !== 'settings') return;

    const modal = document.getElementById('sv-settings-modal');
    if (!modal) return;
    const opening = !modal.classList.contains('show');
    modal.classList.toggle('show', opening);
    modal.setAttribute('aria-hidden', opening ? 'false' : 'true');

    if (opening) {
        const toggle = document.getElementById('dark-mode-toggle');
        if (toggle) toggle.checked = document.body.classList.contains('dark-mode');
        const form = document.getElementById('change-password-form');
        if (form && !form.dataset.bound) {
            form.addEventListener('submit', changePassword);
            form.dataset.bound = 'true';
        }
    }
}

function saveChanges(event) {
    event.preventDefault();
    const form = document.getElementById('profile-form');
    const messageDiv = document.getElementById('settings-message') || document.getElementById('profile-message');
    if (!form) return;

    fetch('/update_profile', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCSRFToken() },
        body: new FormData(form)
    })
        .then(response => response.json())
        .then(data => {
            if (messageDiv) messageDiv.innerHTML = `<div class="alert ${data.message ? 'alert-success' : 'alert-danger'}">${data.message || data.error || 'Update failed.'}</div>`;
            if (data.message) {
                const name = document.getElementById('name-display');
                const email = document.getElementById('email-display');
                if (name) name.textContent = form.querySelector('[name="name"]').value;
                if (email) email.textContent = form.querySelector('[name="email"]').value;
                form.style.display = 'none';
            }
        })
        .catch(() => {
            if (messageDiv) messageDiv.innerHTML = '<div class="alert alert-danger">Unable to update profile.</div>';
        });
}

function toggleEditProfile() {
    const form = document.getElementById('profile-form');
    if (form) form.style.display = form.style.display === 'none' ? 'grid' : 'none';
}

function showEmailRestriction() {
    const el = document.getElementById('email-message');
    if (el) el.style.display = 'block';
}

function changePassword(event) {
    event.preventDefault();
    const messageDiv = document.getElementById('profile-message');
    fetch('/change_password', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: new URLSearchParams({
            'current-password': document.getElementById('current-password').value,
            'new-password': document.getElementById('new-password').value
        })
    })
        .then(response => response.json())
        .then(data => {
            if (messageDiv) messageDiv.innerHTML = `<div class="alert ${data.message === 'Password changed successfully!' ? 'alert-success' : 'alert-danger'}">${data.message || 'Request completed.'}</div>`;
            if (data.message === 'Password changed successfully!') event.target.reset();
        })
        .catch(() => {
            if (messageDiv) messageDiv.innerHTML = '<div class="alert alert-danger">Error changing password.</div>';
        });
}

function logout() {
    fetch('/logout', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCSRFToken() }
    }).then(() => window.location.href = '/');
}

document.addEventListener('click', function (event) {
    const sidebar = document.getElementById('sidebar');
    const profile = document.querySelector('.sv-profile-button');
    const mobileNav = document.getElementById('sv-mobile-nav');
    if (mobileNav && mobileNav.classList.contains('active') && !mobileNav.contains(event.target) && !(event.target.closest && event.target.closest('.sv-mobile-toggle'))) {
        mobileNav.classList.remove('active');
        mobileNav.setAttribute('aria-hidden', 'true');
    }
    if (sidebar && sidebar.classList.contains('show') &&
        !sidebar.contains(event.target) && !(profile && profile.contains(event.target))) {
        sidebar.classList.remove('show');
    }
});

document.addEventListener('DOMContentLoaded', function () {
    const settingsToggle = document.getElementById('dark-mode-toggle');
    const saveSettings = document.getElementById('save-settings');
    if (settingsToggle) settingsToggle.checked = document.body.classList.contains('dark-mode');
    if (saveSettings && settingsToggle) {
        saveSettings.addEventListener('click', () => {
            fetch('/toggle_dark_mode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() },
                body: JSON.stringify({ dark_mode: settingsToggle.checked })
            }).then(r => r.json()).then(data => {
                const msg = document.getElementById('settings-message');
                if (data.status === 'success') {
                    document.body.classList.toggle('dark-mode', data.dark_mode);
                    if (msg) msg.textContent = 'Settings saved.';
                } else if (msg) msg.textContent = data.message || 'Could not save settings.';
            }).catch(() => {
                const msg = document.getElementById('settings-message');
                if (msg) msg.textContent = 'Could not save settings.';
            });
        });
    }

    const userId = document.getElementById('user_id')?.value;
    const count = document.getElementById('notif-count');
    if (!userId || !count) return;

    function updateNotifications() {
        fetch('/get_notifications')
            .then(response => response.json())
            .then(data => {
                const total = data.notifications ? data.notifications.length : 0;
                count.textContent = total > 99 ? '99+' : String(total);
            })
            .catch(() => { });
    }
    updateNotifications();
    setInterval(updateNotifications, 15000);
});
