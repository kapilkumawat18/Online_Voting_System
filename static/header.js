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
    if (nav) nav.classList.toggle('active');
}

function showContent(section) {
    if (section === 'myVotes') {
        window.location.href = '/my_votes';
        return;
    }
    const content = document.getElementById('content');
    if (!content) return;

    if (section === 'settings') {
        if (currentSection === 'settings') {
            content.innerHTML = '';
            currentSection = '';
            return;
        }
        content.innerHTML = `
            <div class="sv-settings-mini">
                <h3>Settings</h3>
                <label><input type="checkbox" id="dark-mode-toggle"> Enable dark mode</label>
                <button id="save-settings" type="button">Save settings</button>
                <h4>Change password</h4>
                <form id="change-password-form">
                    <input type="password" id="current-password" placeholder="Current password" required>
                    <input type="password" id="new-password" placeholder="New password" required>
                    <button type="submit">Change password</button>
                </form>
            </div>`;
        currentSection = 'settings';
        const form = document.getElementById('change-password-form');
        if (form && typeof changePassword === 'function') form.addEventListener('submit', changePassword);
    }
}

function saveChanges(event) {
    event.preventDefault();
    const form = document.getElementById('profile-form');
    const messageDiv = document.getElementById('profile-message');
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

document.addEventListener('click', function(event) {
    const sidebar = document.getElementById('sidebar');
    const profile = document.querySelector('.sv-profile-button');
    if (sidebar && sidebar.classList.contains('show') &&
        !sidebar.contains(event.target) && !(profile && profile.contains(event.target))) {
        sidebar.classList.remove('show');
    }
});

document.addEventListener('DOMContentLoaded', function() {
    const userId = document.getElementById('user_id')?.value;
    const count = document.getElementById('notif-count');
    if (!userId || !count) return;

    function updateNotifications() {
        fetch(`/get_notifications?user_id=${encodeURIComponent(userId)}`)
            .then(response => response.json())
            .then(data => {
                const total = data.notifications ? data.notifications.length : 0;
                count.textContent = total > 99 ? '99+' : String(total);
            })
            .catch(() => {});
    }
    updateNotifications();
    setInterval(updateNotifications, 15000);
});
