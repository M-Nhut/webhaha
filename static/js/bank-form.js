document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('[data-bank-form]');
  if (!form) return;
  const summary = form.querySelector('[data-form-error-summary]');
  const list = form.querySelector('[data-form-error-list]');
  const submit = form.querySelector('[data-bank-form-submit]');
  const busy = form.querySelector('[data-bank-form-busy]');
  let invalidTimer;
  let submitting = false;
  const showClientErrors = () => {
    list.replaceChildren();
    Array.from(form.elements).filter((field) => field.willValidate && !field.validity.valid).forEach((field) => {
      const label = form.querySelector(`label[for="${field.id}"]`);
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.href = `#${field.id}`;
      link.textContent = `${label ? label.textContent.replace('*', '').trim() : field.name}: ${field.validationMessage}`;
      item.append(link); list.append(item);
      field.setAttribute('aria-invalid', 'true');
    });
    summary.hidden = !list.children.length;
    if (!summary.hidden) summary.focus();
  };
  form.addEventListener('invalid', () => {
    window.clearTimeout(invalidTimer);
    invalidTimer = window.setTimeout(showClientErrors, 0);
  }, true);
  form.addEventListener('input', (event) => {
    if (event.target.willValidate && event.target.validity.valid) event.target.removeAttribute('aria-invalid');
  });
  summary.addEventListener('click', (event) => {
    const link = event.target.closest('a[href^="#"]');
    if (!link) return;
    const field = document.getElementById(link.getAttribute('href').slice(1));
    if (field) { event.preventDefault(); field.focus(); }
  });
  form.addEventListener('submit', (event) => {
    if (submitting) { event.preventDefault(); return; }
    submitting = true;
    submit.disabled = true;
    submit.setAttribute('aria-busy', 'true');
    busy.hidden = false;
  });
  window.addEventListener('pageshow', () => {
    submitting = false;
    submit.disabled = false;
    submit.removeAttribute('aria-busy');
    busy.hidden = true;
  });
  if (summary.hasAttribute('data-server-errors')) summary.focus();
});
