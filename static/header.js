// CSRF token helper — the app now requires an X-CSRFToken header on every
// state-changing (POST) fetch(). The token is rendered server-side into a
// <meta name="csrf-token"> tag by header.html / login.html.
function getCSRFToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

let currentSection = '';  // To track the currently opened section

function showContent(section) {

  if (section === 'myVotes') {
    window.location.href = '/my_votes'; // Redirect to My Votes page
    return;
  }
  
  const content = document.getElementById('content');
  let html = '';

  switch (section) {
    case 'notifications':
      html = `<h1>Notifications</h1><p>Here are your notifications.</p>`;
      break;
    case 'myVotes':
      html = `<h1>My Votes</h1><p>Here are the votes you've cast.</p>`;
      break;
    case 'settings':
      if (currentSection === 'settings') {
        // If already opened, hide the settings
        html = '';
        currentSection = '';
      } else {
        // Settings content
        html = `
          <h1>Settings</h1>
          <label>
              <input type="checkbox" id="dark-mode-toggle"> Enable Dark Mode
          </label>
          <button id="save-settings">Save Settings</button>
          <h3>Change Password</h3>
          <form id="change-password-form">
            <label for="current-password">Current Password:</label><br>
            <input type="password" id="current-password" name="current-password" required><br><br>
            <label for="new-password">New Password:</label><br>
            <input type="password" id="new-password" name="new-password" required><br><br>
            <button type="submit">Change Password</button>
          </form>
          <br><br>
        `;
        currentSection = 'settings';
      }
      break;
  }

  content.innerHTML = html;

  if (section === 'settings') {
    // Add event listener for password change form submission
    document.getElementById('change-password-form').addEventListener('submit', changePassword);
  }
}

// For Opening Sidebar with Smooth Animation
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  sidebar.classList.toggle('show');
}

// Auto-close sidebar when clicking outside
document.addEventListener("click", function (event) {
  const sidebar = document.getElementById('sidebar');
  const userIcon = document.querySelector(".user-icon");

  if (sidebar && userIcon) {
    if (!sidebar.contains(event.target) && !userIcon.contains(event.target)) {
      sidebar.classList.remove("show");
    }
  }
});
function saveChanges(event) {
  event.preventDefault();

  const form = document.getElementById('profile-form');
  const formData = new FormData(form);
  const messageDiv = document.getElementById('profile-message'); // Get message div

  fetch('/update_profile', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCSRFToken() },
      body: formData,
  })
  .then(response => response.json())
  .then(data => {
      if (data.message) {
          messageDiv.innerHTML = `<div class="alert alert-success">${data.message}</div>`; // Success message

          // Update name and email instantly
          document.getElementById('name-display').textContent = formData.get('name');
          document.getElementById('email-display').textContent = `Email: ${formData.get('email')}`;

          // Update profile picture
          if (data.profile_pic) {
              document.getElementById('profile-pic').src = data.profile_pic;
          }

          document.getElementById("profile-form").style.display = "none";
      } else if (data.error) {
          messageDiv.innerHTML = `<div class="alert alert-danger">${data.error}</div>`; // Error message
      } else {
          messageDiv.innerHTML = `<div class="alert alert-danger">Failed to update profile. Please try again.</div>`;
      }
  })
  .catch(error => {
      console.error('Error:', error);
      messageDiv.innerHTML = `<div class="alert alert-danger">An error occurred while updating the profile.</div>`;
  });
}

function toggleEditProfile() {
    const form = document.getElementById("profile-form");
    form.style.display = form.style.display === "none" ? "block" : "none";
}

//Prevents email for not Change 
function showEmailRestriction() {
  document.getElementById("email-message").style.display = "flex";
}

// Change password function
function changePassword(event) {
  event.preventDefault();  // Prevent default form submission
  
  const currentPassword = document.getElementById('current-password').value;
  const newPassword = document.getElementById('new-password').value;
  const messageDiv = document.getElementById("profile-message"); // Get message div

  // Send password change request
  fetch('/change_password', {
    method: 'POST',
    headers: { 'X-CSRFToken': getCSRFToken() },
    body: new URLSearchParams({
      'current-password': currentPassword,
      'new-password': newPassword
    })
  })
  .then(response => response.json())
  .then(data => {
    messageDiv.innerHTML = `<div class="alert ${data.message === 'Password changed successfully!' ? 'alert-success' : 'alert-danger'}">
                              ${data.message}
                            </div>`;

    if (data.message === 'Password changed successfully!') {
      // Clear fields on success
      document.getElementById('current-password').value = '';
      document.getElementById('new-password').value = '';
    }

    
  })
  .catch(error => {
    console.error('Error:', error);
    messageDiv.innerHTML = `<div class="alert alert-danger">Error changing password</div>`;
  });
}

//Toggle mobile menu
function toggleMenu() {
  const navs = document.querySelector('.navs');
  navs.classList.toggle('active');
}

document.addEventListener("DOMContentLoaded", function () {
    const userId = document.getElementById("user_id")?.value;
    const notifCount = document.getElementById("notif-count");
    const notifContainer = document.getElementById("notifications-container");

    if (!userId) {
        console.error("User ID not found!");
        return;
    }

        function updateNotifications() {
        fetch(`/get_notifications?user_id=${userId}`)
            .then(response => response.json())
            .then(data => {
                notifCount.textContent = data.notifications.length || "0";
                notifContainer.innerHTML = ""; // Clear old notifications

                if (data.notifications.length === 0) {
                  notifContainer.innerHTML = `<p class="no-notifications">No new notifications</p>`;
              } else {
                data.notifications.forEach(notif => {
                    let notifItem = document.createElement("div");
                    notifItem.classList.add("notif-item");
                    notifItem.setAttribute("data-id", notif.id);
                    notifItem.innerHTML = `
                        <span>${notif.message}</span>
                        <small class="notif-time">${notif.created_at}</small>
                        <button class="notif-remove" data-id="${notif.id}">✖</button>
                    `;
                    notifContainer.appendChild(notifItem);
                });}
            })
            .catch(error => console.error("Error fetching notifications:", error));
    }
    setInterval(updateNotifications, 5000);
    updateNotifications(); // Initial call


    // Function to remove notification
    function removeNotification(id) {
        fetch(`/remove_notification/${id}`, { method: "POST", headers: { 'X-CSRFToken': getCSRFToken() } })
            .then(response => response.json())
            .then(data => {
                if (data.status === "success") {
                    let notifItem = document.querySelector(`.notif-item[data-id='${id}']`);
                    if (notifItem) {
                        notifItem.remove();
                    }

                    // Update notification count instantly
                    updateNotificationCount();
                }
            })
            .catch(error => console.error("Error removing notification:", error));
    }

    // Attach event listener to dynamically handle click events on close buttons
    notifContainer.addEventListener("click", function (event) {
        if (event.target.classList.contains("notif-remove")) {
            let notifItem = event.target.closest(".notif-item");
            if (notifItem) {
                let notifId = notifItem.getAttribute("data-id");
                removeNotification(notifId);
            }
        }
    });

    // Update count every 5 seconds
    setInterval(updateNotificationCount, 5000);

    // Initial count update
    updateNotificationCount();
});

document.addEventListener("DOMContentLoaded", function () {
  let settingsChanged = false; // Track if settings have changed

  // Function to apply dark mode if enabled
  function applyDarkMode() {
      fetch("/get_dark_mode_status")
          .then(response => response.json())
          .then(data => {
              if (data.dark_mode) {
                  document.body.classList.add("dark-mode"); // Apply dark mode
              } else {
                  document.body.classList.remove("dark-mode"); // Remove dark mode
              }
          })
          .catch(error => console.error("Error fetching dark mode status:", error));
  }

  // Apply dark mode on page load
  applyDarkMode();

  // Function to initialize settings once loaded
  function initSettings() {
      let darkModeToggle = document.getElementById("dark-mode-toggle");
      let saveSettingsBtn = document.getElementById("save-settings");

      // Fetch dark mode status and update toggle switch
      fetch("/get_dark_mode_status")
          .then(response => response.json())
          .then(data => {
              darkModeToggle.checked = data.dark_mode;
          });

      // Listen for dark mode toggle
      darkModeToggle.addEventListener("change", function () {
          settingsChanged = true;
      });

      // Save settings button
      saveSettingsBtn.addEventListener("click", function () {
          const darkModeEnabled = darkModeToggle.checked;
          settingsChanged = false; // Reset warning

          fetch("/toggle_dark_mode", {
              method: "POST",
              headers: { "Content-Type": "application/json", "X-CSRFToken": getCSRFToken() },
              body: JSON.stringify({ dark_mode: darkModeEnabled })
          })
          .then(response => response.json())
          .then(data => {
              if (data.status === "success") {
                  document.body.classList.toggle("dark-mode", darkModeEnabled);
                  alert("Settings saved successfully!");
              } else {
                  alert("Failed to update settings.");
              }
          })
          .catch(error => console.error("Error updating settings:", error));
      });

      // Warn user if they leave without saving changes
      window.addEventListener("beforeunload", function (event) {
          if (settingsChanged) {
              event.preventDefault();
              event.returnValue = "You have unsaved changes. Are you sure you want to leave?";
          }
      });
  }

  // Detect when settings section is opened
  document.addEventListener("click", function (event) {
      if (event.target.textContent === "Settings") {
          setTimeout(initSettings, 500); // Wait for settings to load
      }
  });
});


// (Duplicate "save settings" listener removed — #save-settings doesn't exist until
// the Settings panel is opened, so this ran immediately on every page load, threw a
// TypeError, and silently stopped the rest of this script from running (including
// the flash-message polling below). The equivalent listener already lives safely
// inside initSettings(), which only attaches it once the button actually exists.)

function logout() {
  fetch('/logout', { method: 'POST', headers: { 'X-CSRFToken': getCSRFToken() } })
  .then(response => response.json())
  .then(data => {
      if (data.status === 'success') {
          window.location.href = '/';
      }
  });
}

function fetchFlashMessages() {
  let flashContainer = document.getElementById("add-messages");
  if (!flashContainer) return; // Only a couple of pages have this container

  fetch('/get-flash-messages')
    .then(response => response.json())
    .then(messages => {
      messages.forEach(([category, message]) => {
        if (![...flashContainer.children].some(msg => msg.textContent.includes(message))) {
          let flashMessage = document.createElement("div");
          flashMessage.classList.add("alert", category === "add_success" ? "alert-success" : "alert-danger");
          flashMessage.innerHTML = `${message} <span class="close-btn" onclick="this.parentElement.remove();">&times;</span>`;
          flashContainer.appendChild(flashMessage);
          setTimeout(() => flashMessage.remove(), 3000);
        }
      });
    })
    .catch(error => console.error("Error fetching flash messages:", error));
}
setInterval(fetchFlashMessages, 3000);
