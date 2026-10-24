/* Credential UI never persists field contents or returns raw values to the page. */
(() => {
  const field = document.getElementById('teacher-ai-keys');
  const addForm = document.getElementById('teacher-ai-add-form');
  const count = document.getElementById('ai-key-count');
  const error = document.getElementById('ai-key-error');
  const lines = () => field.value.split(/\r?\n/).filter(line => line.trim());
  field?.addEventListener('input', () => {
    const amount = lines().length;
    count.textContent = amount ? `${amount}/20 khóa đã nhập` : '';
    error.hidden = true;
    field.removeAttribute('aria-invalid');
  });
  addForm?.addEventListener('submit', event => {
    if (lines().length > 20) {
      event.preventDefault();
      error.textContent = 'Mỗi lần chỉ thêm tối đa 20 khóa. Giảm số dòng rồi thử lại.';
      error.hidden = false;
      field.setAttribute('aria-invalid', 'true');
      field.focus();
    }
  });
  document.querySelectorAll('[data-ai-busy-form]').forEach(form => form.addEventListener('submit', event => {
    if (event.defaultPrevented) return;
    if (form.dataset.submitting === 'true') { event.preventDefault(); return; }
    form.dataset.submitting = 'true';
    const button = event.submitter || form.querySelector('[type="submit"]');
    if (button) { button.setAttribute('aria-busy', 'true'); button.textContent = 'Đang kiểm tra…'; }
  }));
  const dialog = document.getElementById('ai-key-delete-dialog');
  const mask = document.getElementById('ai-key-delete-mask');
  const confirm = document.getElementById('ai-key-delete-confirm');
  let pendingForm, opener;
  document.querySelectorAll('[data-ai-delete]').forEach(form => form.addEventListener('submit', event => {
    if (form.dataset.confirmed === 'true') return;
    event.preventDefault();
    pendingForm = form;
    opener = event.submitter;
    mask.textContent = form.dataset.maskedKey;
    dialog.showModal();
  }));
  dialog?.querySelectorAll('[data-close-delete]').forEach(button => button.addEventListener('click', () => dialog.close()));
  dialog?.addEventListener('close', () => { opener?.focus(); });
  confirm?.addEventListener('click', () => {
    if (!pendingForm) return;
    pendingForm.dataset.confirmed = 'true';
    confirm.disabled = true;
    pendingForm.requestSubmit();
    dialog.close();
  });
  window.addEventListener('pageshow', () => {
    document.querySelectorAll('[data-submitting]').forEach(form => {
      delete form.dataset.submitting;
      const button = form.querySelector('[aria-busy="true"]');
      if (button) { button.removeAttribute('aria-busy'); button.textContent = form === addForm ? 'Kiểm tra và lưu' : 'Thử lại'; }
    });
    if (confirm) confirm.disabled = false;
  });
})();
