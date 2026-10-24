/* Native print uses the read-only matrix's landscape stylesheet. */
document.querySelectorAll('[data-matrix-print]').forEach((button) => {
  button.hidden = false;
  button.addEventListener('click', () => window.print());
});
