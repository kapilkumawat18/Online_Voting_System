function getCSRFToken() { return document.querySelector('meta[name="csrf-token"]')?.content || ''; }
let currentSection = '';

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) sidebar.classList.toggle('show');
}
function toggleMenu() {
    const nav = document.getElementById('sv-mobile-nav');
    if (nav) nav.classList.toggle('active');
}
function closeMobileMenu() {
    const nav = document.getElementById('sv-mobile-nav');
    if (nav) nav.classList.remove('active');
}

function filterPolls(status) {
    const cards = document.querySelectorAll('.sv-election-card,.poll-card');
    const tabs = document.querySelectorAll('.sv-tab,.tab');
    const normalized = String(status || 'all').toLowerCase();
    tabs.forEach(tab => {
        const value = (tab.dataset.filter || tab.getAttribute('data-filter') || tab.textContent || '').trim().toLowerCase();
        tab.classList.toggle('active', value === normalized || (normalized === 'all' && value.includes('all')));
    });
    cards.forEach(card => {
        const value = (card.dataset.status || '').toLowerCase();
        card.style.display = (normalized === 'all' || value === normalized) ? '' : 'none';
    });
}

function showContent(section) {
    if (section === 'myVotes') { window.location.href = '/my_votes'; return; }
    const sidebar = document.getElementById('sidebar'); if (!sidebar) return;
    let panel = document.getElementById('sv-settings-panel');
    if (section !== 'settings') return;
    if (panel) { panel.remove(); currentSection = ''; return; }
    panel = document.createElement('div'); panel.id = 'sv-settings-panel'; panel.className = 'sv-settings-panel';
    panel.innerHTML = `<div class="sv-settings-head"><strong>Settings</strong><button type="button" id="closeSettings">×</button></div>
 <label class="sv-setting-row"><span>Dark mode</span><input type="checkbox" id="dark-mode-toggle"></label>
 <button type="button" class="sv-settings-save" id="save-settings">Save appearance</button>
 <div class="sv-settings-password"><strong>Change password</strong>
 <input type="password" id="current-password" placeholder="Current password">
 <input type="password" id="new-password" placeholder="New password">
 <button type="button" id="change-password-btn">Update password</button></div>
 <div id="settings-message" class="sv-settings-message"></div>`;
    sidebar.querySelector('.sv-logout-button')?.before(panel);
    currentSection = 'settings';
    fetch('/get_dark_mode_status').then(r => r.json()).then(d => { const t = document.getElementById('dark-mode-toggle'); if (t) t.checked = !!d.dark_mode; }).catch(() => { });
    document.getElementById('closeSettings').onclick = () => { panel.remove(); currentSection = ''; };
    document.getElementById('save-settings').onclick = () => {
        const dark = !!document.getElementById('dark-mode-toggle').checked;
        fetch('/toggle_dark_mode', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() }, body: JSON.stringify({ dark_mode: dark }) })
            .then(r => r.json()).then(d => { if (d.status === 'success') { document.body.classList.toggle('dark-mode', dark); document.documentElement.classList.toggle('dark-mode', dark); document.getElementById('settings-message').textContent = 'Settings saved.'; } else throw Error(); })
            .catch(() => document.getElementById('settings-message').textContent = 'Could not save settings.');
    };
    document.getElementById('change-password-btn').onclick = () => {
        fetch('/change_password', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': getCSRFToken() }, body: new URLSearchParams({ 'current-password': document.getElementById('current-password').value, 'new-password': document.getElementById('new-password').value }) })
            .then(r => r.json()).then(d => document.getElementById('settings-message').textContent = d.message || 'Request completed.').catch(() => document.getElementById('settings-message').textContent = 'Unable to change password.');
    };
}

function saveChanges(event) {
    event.preventDefault(); const form = document.getElementById('profile-form'), msg = document.getElementById('profile-message'); if (!form) return;
    fetch('/update_profile', { method: 'POST', headers: { 'X-CSRFToken': getCSRFToken() }, body: new FormData(form) })
        .then(r => r.json()).then(d => { if (msg) msg.innerHTML = `<div class="alert">${d.message || d.error || 'Update failed.'}</div>`; if (d.message) { document.getElementById('name-display').textContent = form.querySelector('[name="name"]').value; form.style.display = 'none'; } })
        .catch(() => { if (msg) msg.innerHTML = '<div class="alert">Unable to update profile.</div>'; });
}
function toggleEditProfile() { const form = document.getElementById('profile-form'); if (form) form.style.display = form.style.display === 'none' ? 'grid' : 'none'; }
function previewProfilePic(event) { const file = event.target.files?.[0]; if (file) { const img = document.getElementById('profile-pic'); const head = document.getElementById('header-profile-pic'); const url = URL.createObjectURL(file); if (img) img.src = url; if (head) head.src = url; } }
function logout() { fetch('/logout', { method: 'POST', headers: { 'X-CSRFToken': getCSRFToken() } }).then(() => window.location.href = '/'); }

document.addEventListener('click', e => {
    const sidebar = document.getElementById('sidebar'), profile = document.querySelector('.sv-profile-button'), nav = document.getElementById('sv-mobile-nav'), hamb = document.querySelector('.sv-mobile-toggle');
    if (sidebar?.classList.contains('show') && !sidebar.contains(e.target) && !(profile && profile.contains(e.target))) sidebar.classList.remove('show');
    if (nav?.classList.contains('active') && !nav.contains(e.target) && !(hamb && hamb.contains(e.target))) nav.classList.remove('active');
});
document.addEventListener('DOMContentLoaded', () => {
    const count = document.getElementById('notif-count');
    if (count) {
        const update = () => fetch('/get_notifications').then(r => r.json()).then(d => { const n = d.notifications?.length || 0; count.textContent = n > 99 ? '99+' : String(n); }).catch(() => { });
        update(); setInterval(update, 15000);
    }
    if (document.querySelector('.sv-election-card,.poll-card')) filterPolls('all');
    document.querySelectorAll('.notif-remove').forEach(button => {
        button.addEventListener('click', () => {
            const id = button.dataset.id;
            fetch('/remove_notification/' + encodeURIComponent(id), { method: 'POST', headers: { 'X-CSRFToken': getCSRFToken() } })
                .then(r => r.json()).then(d => { if (d.status === 'success') button.closest('.notif-item')?.remove(); });
        });
    });
});
