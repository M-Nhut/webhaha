/* Only a confirmed native dialog submits the existing CSRF-protected delete form. */
(() => {
  'use strict';
  const dialog = document.getElementById('diagnostic-delete-dialog');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  const confirm = document.getElementById('diagnostic-delete-confirm');
  let activeForm = null, trigger = null, submitting = false;
  document.querySelectorAll('[data-diagnostic-delete]').forEach(form => {
    const button = form.querySelector('[data-delete-open]');
    button.hidden = false;
    button.addEventListener('click', () => {
      activeForm = form;
      trigger = button;
      submitting = false;
      confirm.disabled = false;
      confirm.textContent = 'Xóa đánh giá';
      document.getElementById('diagnostic-delete-name').textContent = form.dataset.title;
      const total = Number(form.dataset.submissions) || 0;
      document.getElementById('diagnostic-delete-impact').textContent = total ? `${total} bài đã nộp có liên quan đến đánh giá này.` : 'Đánh giá này chưa có bài nộp.';
      dialog.showModal();
    });
  });
  dialog.querySelectorAll('[data-delete-cancel]').forEach(button => button.addEventListener('click', () => { if (!submitting) dialog.close(); }));
  dialog.addEventListener('cancel', event => { if (submitting) event.preventDefault(); });
  dialog.addEventListener('close', () => { trigger?.focus(); activeForm = null; });
  confirm.addEventListener('click', () => {
    if (!activeForm || submitting) return;
    submitting = true;
    confirm.disabled = true;
    confirm.textContent = 'Đang xóa…';
    activeForm.requestSubmit();
  });
  window.addEventListener('pageshow', () => {
    submitting = false;
    confirm.disabled = false;
    confirm.textContent = 'Xóa đánh giá';
    if (dialog.open) dialog.close();
  });
})();
