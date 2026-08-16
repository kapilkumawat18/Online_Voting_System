
/* =========================================================
   SECUREVOTE HEADER JAVASCRIPT
   ========================================================= */

function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

let currentSection = '';

/* =========================================================
   PROFILE SIDEBAR
   ========================================================= */

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');

    if (!sidebar) return;

    sidebar.classList.toggle('show');

    // Prevent body scrolling while sidebar is open on mobile
    if (window.innerWidth <= 600) {
        document.body.classList.toggle(
            'sv-sidebar-open',
            sidebar.classList.contains('show')
        );
    }
}


/* =========================================================
   MOBILE NAV
   IMPORTANT:
   Bottom navigation is ALWAYS visible on mobile.
   No hamburger / no toggle required.
   ========================================================= */

function closeMobileMenu() {
    // Kept for compatibility with existing HTML/JS.
    // Bottom navigation is always visible.
}


/* =========================================================
   POLL FILTER
   ========================================================= */

function filterPolls(status) {

    const cards = document.querySelectorAll(
        '.sv-election-card, .poll-card'
    );

    const tabs = document.querySelectorAll(
        '.sv-tab, .tab'
    );

    const normalized = String(status || 'all').toLowerCase();

    tabs.forEach(tab => {

        const value = (
            tab.dataset.filter ||
            tab.getAttribute('data-filter') ||
            tab.textContent ||
            ''
        )
            .trim()
            .toLowerCase();

        tab.classList.toggle(
            'active',
            value === normalized ||
            (normalized === 'all' && value.includes('all'))
        );
    });

    cards.forEach(card => {

        const value = (
            card.dataset.status || ''
        ).toLowerCase();

        card.style.display =
            normalized === 'all' || value === normalized
                ? ''
                : 'none';
    });
}


/* =========================================================
   SETTINGS
   ========================================================= */

function showContent(section) {

    if (section === 'myVotes') {
        window.location.href = '/my_votes';
        return;
    }

    const sidebar = document.getElementById('sidebar');

    if (!sidebar) return;

    if (section !== 'settings') return;

    let panel = document.getElementById('sv-settings-panel');

    /* -----------------------------------------
       CLOSE SETTINGS IF ALREADY OPEN
       ----------------------------------------- */

    if (panel) {

        panel.remove();
        currentSection = '';

        return;
    }


    /* -----------------------------------------
       CREATE SETTINGS PANEL
       ----------------------------------------- */

    panel = document.createElement('div');

    panel.id = 'sv-settings-panel';
    panel.className = 'sv-settings-panel';

    panel.innerHTML = `

        <div class="sv-settings-head">

            <div class="sv-settings-title">
                <span class="sv-settings-icon">⚙</span>

                <div>
                    <strong>Settings</strong>
                    <small>Manage your account preferences</small>
                </div>
            </div>

            <button
                type="button"
                class="sv-settings-close"
                id="closeSettings"
                aria-label="Close settings">
                ×
            </button>

        </div>


        <!-- APPEARANCE -->

        <div class="sv-settings-section">

            <div class="sv-settings-section-title">
                <span>Appearance</span>
                <small>Customize how SecureVote looks</small>
            </div>


            <label class="sv-setting-row">

                <div class="sv-setting-info">

                    <span class="sv-setting-icon">◐</span>

                    <div>
                        <strong>Dark mode</strong>
                        <small>Use dark appearance</small>
                    </div>

                </div>

                <input
                    type="checkbox"
                    id="dark-mode-toggle"
                    class="sv-switch">

            </label>


            <button
                type="button"
                class="sv-settings-save"
                id="save-settings">

                Save appearance

            </button>

        </div>


        <!-- PASSWORD -->

        <div class="sv-settings-section sv-password-section">

            <div class="sv-settings-section-title">

                <span>Security</span>

                <small>
                    Update your account password
                </small>

            </div>


            <div class="sv-settings-password">

                <label for="current-password">
                    Current password
                </label>

                <input
                    type="password"
                    id="current-password"
                    placeholder="Enter current password"
                    autocomplete="current-password">


                <label for="new-password">
                    New password
                </label>

                <input
                    type="password"
                    id="new-password"
                    placeholder="Enter new password"
                    autocomplete="new-password">


                <button
                    type="button"
                    class="sv-password-button"
                    id="change-password-btn">

                    Update password

                </button>

            </div>

        </div>


        <div
            id="settings-message"
            class="sv-settings-message">
        </div>

    `;


    /* -----------------------------------------
       INSERT SETTINGS BEFORE LOGOUT
       ----------------------------------------- */

    const logoutButton =
        sidebar.querySelector('.sv-logout-button');

    if (logoutButton) {

        logoutButton.before(panel);

    } else {

        sidebar.appendChild(panel);

    }


    currentSection = 'settings';


    /* -----------------------------------------
       LOAD DARK MODE STATUS
       ----------------------------------------- */

    fetch('/get_dark_mode_status')

        .then(response => response.json())

        .then(data => {

            const toggle =
                document.getElementById('dark-mode-toggle');

            if (toggle) {
                toggle.checked = !!data.dark_mode;
            }

        })

        .catch(() => {
            // Ignore loading error
        });


    /* -----------------------------------------
       CLOSE SETTINGS
       ----------------------------------------- */

    const closeButton =
        document.getElementById('closeSettings');

    if (closeButton) {

        closeButton.onclick = () => {

            panel.remove();
            currentSection = '';

        };

    }


    /* -----------------------------------------
       SAVE APPEARANCE
       ----------------------------------------- */

    const saveButton =
        document.getElementById('save-settings');

    if (saveButton) {

        saveButton.onclick = () => {

            const toggle =
                document.getElementById('dark-mode-toggle');

            const dark =
                !!toggle?.checked;


            fetch('/toggle_dark_mode', {

                method: 'POST',

                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },

                body: JSON.stringify({
                    dark_mode: dark
                })

            })

                .then(response => response.json())

                .then(data => {

                    const message =
                        document.getElementById('settings-message');


                    if (data.status === 'success') {

                        document.body.classList.toggle(
                            'dark-mode',
                            dark
                        );

                        document.documentElement.classList.toggle(
                            'dark-mode',
                            dark
                        );


                        if (message) {

                            message.className =
                                'sv-settings-message success';

                            message.textContent =
                                '✓ Appearance settings saved.';

                        }

                    } else {

                        throw new Error(
                            data.message || 'Save failed'
                        );

                    }

                })

                .catch(() => {

                    const message =
                        document.getElementById('settings-message');

                    if (message) {

                        message.className =
                            'sv-settings-message error';

                        message.textContent =
                            'Could not save settings.';

                    }

                });

        };

    }


    /* -----------------------------------------
       CHANGE PASSWORD
       ----------------------------------------- */

    const passwordButton =
        document.getElementById('change-password-btn');

    if (passwordButton) {

        passwordButton.onclick = () => {

            const currentPassword =
                document.getElementById(
                    'current-password'
                )?.value || '';


            const newPassword =
                document.getElementById(
                    'new-password'
                )?.value || '';


            const message =
                document.getElementById(
                    'settings-message'
                );


            if (!currentPassword || !newPassword) {

                if (message) {

                    message.className =
                        'sv-settings-message error';

                    message.textContent =
                        'Please enter both passwords.';

                }

                return;
            }


            fetch('/change_password', {

                method: 'POST',

                headers: {
                    'Content-Type':
                        'application/x-www-form-urlencoded',

                    'X-CSRFToken':
                        getCSRFToken()
                },

                body: new URLSearchParams({

                    'current-password':
                        currentPassword,

                    'new-password':
                        newPassword

                })

            })

                .then(response => response.json())

                .then(data => {

                    if (message) {

                        message.className =
                            data.status === 'success'
                                ? 'sv-settings-message success'
                                : 'sv-settings-message error';

                        message.textContent =
                            data.message ||
                            'Request completed.';

                    }

                })

                .catch(() => {

                    if (message) {

                        message.className =
                            'sv-settings-message error';

                        message.textContent =
                            'Unable to change password.';

                    }

                });

        };

    }

}


/* =========================================================
   PROFILE UPDATE
   ========================================================= */

function saveChanges(event) {

    event.preventDefault();

    const form =
        document.getElementById('profile-form');

    const message =
        document.getElementById('profile-message');

    if (!form) return;


    fetch('/update_profile', {

        method: 'POST',

        headers: {
            'X-CSRFToken': getCSRFToken()
        },

        body: new FormData(form)

    })

        .then(response => response.json())

        .then(data => {

            if (message) {

                message.innerHTML = `
                <div class="alert">
                    ${data.message || data.error || 'Update failed.'}
                </div>
            `;

            }


            if (data.message) {

                const nameInput =
                    form.querySelector('[name="name"]');

                const nameDisplay =
                    document.getElementById('name-display');

                const headerName =
                    document.querySelector('.sv-profile-name');


                if (nameDisplay && nameInput) {
                    nameDisplay.textContent =
                        nameInput.value;
                }


                if (headerName && nameInput) {
                    headerName.textContent =
                        nameInput.value;
                }


                form.style.display = 'none';

            }

        })

        .catch(() => {

            if (message) {

                message.innerHTML =
                    '<div class="alert">Unable to update profile.</div>';

            }

        });

}


/* =========================================================
   EDIT PROFILE
   ========================================================= */

function toggleEditProfile() {

    const form =
        document.getElementById('profile-form');

    if (!form) return;


    const isHidden =
        form.style.display === 'none' ||
        getComputedStyle(form).display === 'none';


    form.style.display =
        isHidden ? 'grid' : 'none';

}


/* =========================================================
   PROFILE IMAGE PREVIEW
   ========================================================= */

function previewProfilePic(event) {

    const file =
        event.target.files?.[0];

    if (!file) return;


    const imageURL =
        URL.createObjectURL(file);


    const profileImage =
        document.getElementById('profile-pic');

    const headerImage =
        document.getElementById('header-profile-pic');


    if (profileImage) {
        profileImage.src = imageURL;
    }

    if (headerImage) {
        headerImage.src = imageURL;
    }

}


/* =========================================================
   LOGOUT
   ========================================================= */

function logout() {

    fetch('/logout', {

        method: 'POST',

        headers: {
            'X-CSRFToken': getCSRFToken()
        }

    })

        .then(() => {

            window.location.href = '/';

        })

        .catch(() => {

            window.location.href = '/';

        });

}


/* =========================================================
   CLICK OUTSIDE SIDEBAR
   ========================================================= */

document.addEventListener('click', event => {

    const sidebar =
        document.getElementById('sidebar');

    const profile =
        document.querySelector('.sv-profile-button');


    if (
        sidebar?.classList.contains('show') &&
        !sidebar.contains(event.target) &&
        !(profile && profile.contains(event.target))
    ) {

        sidebar.classList.remove('show');

        document.body.classList.remove(
            'sv-sidebar-open'
        );

    }

});


/* =========================================================
   ESC KEY
   ========================================================= */

document.addEventListener('keydown', event => {

    if (event.key !== 'Escape') return;


    const sidebar =
        document.getElementById('sidebar');


    if (sidebar?.classList.contains('show')) {

        sidebar.classList.remove('show');

        document.body.classList.remove(
            'sv-sidebar-open'
        );

    }


    const settings =
        document.getElementById('sv-settings-panel');


    if (settings) {

        settings.remove();
        currentSection = '';

    }

});


/* =========================================================
   DOM READY
   ========================================================= */

document.addEventListener('DOMContentLoaded', () => {


    /* -----------------------------------------
       NOTIFICATION COUNT
       ----------------------------------------- */

    const count =
        document.getElementById('notif-count');


    if (count) {

        const updateNotifications = () => {

            fetch('/get_notifications')

                .then(response => response.json())

                .then(data => {

                    const number =
                        data.notifications?.length || 0;


                    count.textContent =
                        number > 99
                            ? '99+'
                            : String(number);

                })

                .catch(() => { });

        };


        updateNotifications();

        setInterval(
            updateNotifications,
            15000
        );

    }


    /* -----------------------------------------
       DEFAULT POLL FILTER
       ----------------------------------------- */

    if (
        document.querySelector(
            '.sv-election-card, .poll-card'
        )
    ) {

        filterPolls('all');

    }


    /* -----------------------------------------
       REMOVE NOTIFICATIONS
       ----------------------------------------- */

    document
        .querySelectorAll('.notif-remove')
        .forEach(button => {

            button.addEventListener(
                'click',
                () => {

                    const id =
                        button.dataset.id;


                    fetch(
                        '/remove_notification/' +
                        encodeURIComponent(id),
                        {
                            method: 'POST',

                            headers: {
                                'X-CSRFToken':
                                    getCSRFToken()
                            }
                        }
                    )

                        .then(response =>
                            response.json()
                        )

                        .then(data => {

                            if (
                                data.status === 'success'
                            ) {

                                button
                                    .closest('.notif-item')
                                    ?.remove();

                            }

                        });

                }
            );

        });

});

