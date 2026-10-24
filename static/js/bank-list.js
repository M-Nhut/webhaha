/* Confirmation retains the original native POST and CSRF field. */
document.addEventListener('DOMContentLoaded', () => {
  const dialog = document.getElementById('bank-delete-dialog');
  if (!dialog) return;
  const name = dialog.querySelector('[data-bank-delete-name]');
  const confirm = dialog.querySelector('[data-bank-delete-confirm]');
  let pendingForm = null;
  document.querySelectorAll('[data-bank-delete-open]').forEach((button) => {
    button.addEventListener('click', () => {
      pendingForm = button.closest('form[data-bank-delete-form]');
      name.textContent = button.dataset.bankName || '';
      confirm.disabled = false;
      confirm.removeAttribute('aria-busy');
      window.AcademyDialogs.open(dialog.id, button);
    });
  });
  dialog.addEventListener('close', () => {
    pendingForm = null;
  });
  confirm.addEventListener('click', () => {
    if (!pendingForm || confirm.disabled) return;
    confirm.disabled = true;
    confirm.setAttribute('aria-busy', 'true');
    pendingForm.requestSubmit();
  });
  window.addEventListener('pageshow', () => {
    confirm.disabled = false;
    confirm.removeAttribute('aria-busy');
    if (dialog.open) window.AcademyDialogs.close(dialog.id);
  });
});
