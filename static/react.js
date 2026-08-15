function filterPolls(status) {
  const cards = document.querySelectorAll('.sv-election-card, .poll-card');
  const tabs = document.querySelectorAll('.sv-tab, .tab');
  const wanted = String(status || 'all').toLowerCase();

  tabs.forEach(tab => {
    const value = String(tab.dataset.filter || tab.textContent || '').trim().toLowerCase();
    tab.classList.toggle('active', wanted === 'all' ? value.includes('all') : value === wanted);
  });

  cards.forEach(card => {
    const cardStatus = String(card.dataset.status || '').toLowerCase();
    const show = wanted === 'all' || cardStatus === wanted;
    card.classList.toggle('hidden', !show);
    if (card.classList.contains('poll-card')) {
      card.style.display = show ? '' : 'none';
    }
  });
}

document.addEventListener('DOMContentLoaded', () => filterPolls('all'));
