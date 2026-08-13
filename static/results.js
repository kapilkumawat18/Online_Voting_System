// Function to toggle the sidebar visibility when the user icon or bell icon is clicked
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('show');
  }
  
  // Function to handle notification icon click (e.g., show notifications)
  function toggleNotifications() {
    // Placeholder for notifications functionality
    // You can display a notification dropdown or modal here
    alert("Notifications clicked!");
    // Example: show a dropdown or update the UI based on the click
  }  
  
  function toggleMenu() {
    const navs = document.querySelector('.navs');
    navs.classList.toggle('active');
  }