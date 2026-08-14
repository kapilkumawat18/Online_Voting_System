// This file was referenced by templates (header.html, admin.html, home.html)
// via <script src="{{ url_for('static', filename='script.js') }}"> but did
// not exist in the repository — every page load was throwing a 404 for it in
// the browser console, and the "Change Profile Picture" file input had no
// handler at all (onchange="previewProfilePic(event)" pointed at a function
// that was never defined anywhere).

// Live-preview the selected profile picture before it's uploaded.
function previewProfilePic(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  if (!file.type.startsWith('image/')) {
    alert('Please choose an image file.');
    event.target.value = '';
    return;
  }

  const preview = document.getElementById('profile-pic');
  if (!preview) return;

  const reader = new FileReader();
  reader.onload = function (e) {
    preview.src = e.target.result;
  };
  reader.readAsDataURL(file);
}
