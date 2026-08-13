// JavaScript to filter polls based on tabs
  function filterPolls(status) {
    const cards = document.querySelectorAll('.poll-card');
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => tab.classList.remove('active'));
    document.querySelector(`.tab[onclick="filterPolls('${status}')"]`).classList.add('active');
          
      cards.forEach(card => {
        if (status === 'all' || card.getAttribute('data-status') === status.toLowerCase()) {
          card.style.display = 'block';
        } else {
          card.style.display = 'none';
        }
      });
  }

// Initialize with "All" selected
filterPolls('all');
