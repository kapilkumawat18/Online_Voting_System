

/* SecureVote V2 — final ballot confirmation */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form.election').forEach(form => {
    form.addEventListener('submit', (event) => {
      const selected = form.querySelector('input[name="candidate_id"]:checked');
      if (!selected) return;
      const card = selected.closest('.sv-candidate');
      const name = card?.querySelector('.sv-candidate-info strong')?.textContent?.trim() || 'your selected candidate';
      const ok = window.confirm(`Final check:\n\nYou selected ${name}.\n\nYour vote can only be submitted once. Continue?`);
      if (!ok) event.preventDefault();
    });
  });
});
