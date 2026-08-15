
document.addEventListener('DOMContentLoaded', function () {
  const inputs = [...document.querySelectorAll('.otp-grid input')];
  if (!inputs.length) return;
  inputs.forEach((el, i) => {
    el.inputMode = 'numeric'; el.maxLength = 1;
    el.addEventListener('input', () => { el.value = el.value.replace(/\D/g, ''); if (el.value && inputs[i + 1]) inputs[i + 1].focus(); });
    el.addEventListener('keydown', e => {
      if (e.key === 'Backspace' && !el.value && inputs[i - 1]) inputs[i - 1].focus();
      if (e.key === 'ArrowLeft' && inputs[i - 1]) inputs[i - 1].focus();
      if (e.key === 'ArrowRight' && inputs[i + 1]) inputs[i + 1].focus();
    });
  });
});
