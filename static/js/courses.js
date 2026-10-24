/* Native form and dialog behavior for the class workspace. */
(() => {
  'use strict';
  const select = document.querySelector('[data-course-teacher]');
  const preview = document.querySelector('[data-course-teacher-preview]');
  const updateTeacher = () => {
    if (!select || !preview) return;
    const option = select.selectedOptions[0];
    preview.hidden = !option?.value;
    if (preview.hidden) return;
    for (const key of ['fullname', 'code', 'position', 'phone']) {
      preview.querySelector(`[data-teacher-${key}]`).textContent = option.dataset[key] || 'Chưa cập nhật';
    }
    preview.querySelector('[data-teacher-avatar]').src = option.dataset.avatar;
  };
  select?.addEventListener('change', updateTeacher);
  updateTeacher();

  const form = document.querySelector('[data-course-form]');
  if (form) {
    const summary = document.getElementById('course-form-errors');
    const list = summary.querySelector('[data-course-form-errors]');
    let invalidFields = [];
    let invalidScheduled = false;
    const removeError = field => {
      field.removeAttribute('aria-invalid');
      document.getElementById(`${field.id}-error`)?.remove();
      const ids = (field.getAttribute('aria-describedby') || '').split(' ').filter(id => id && id !== `${field.id}-error`);
      if (ids.length) field.setAttribute('aria-describedby', ids.join(' '));
      else field.removeAttribute('aria-describedby');
    };
    const displayErrors = () => {
      list.replaceChildren();
      for (const field of invalidFields) {
        removeError(field);
        field.setAttribute('aria-invalid', 'true');
        const label = form.querySelector(`label[for="${field.id}"]`)?.textContent.replace(' *', '') || field.name;
        const message = field.validity.valueMissing ? `Vui lòng nhập ${label.toLowerCase()}.` : field.validationMessage;
        const error = document.createElement('p');
        error.id = `${field.id}-error`;
        error.className = 'courses-inline-error';
        error.textContent = message;
        field.insertAdjacentElement('afterend', error);
        field.setAttribute('aria-describedby', [field.getAttribute('aria-describedby'), error.id].filter(Boolean).join(' '));
        const item = document.createElement('li');
        const link = document.createElement('a');
        link.href = `#${field.id}`;
        link.dataset.courseErrorFor = field.id;
        link.textContent = message;
        link.addEventListener('click', event => { event.preventDefault(); field.focus(); });
        item.append(link); list.append(item);
      }
      summary.hidden = invalidFields.length === 0;
      if (!summary.hidden) summary.focus();
      invalidFields = []; invalidScheduled = false;
    };
    form.addEventListener('invalid', event => {
      event.preventDefault();
      if (!invalidFields.includes(event.target)) invalidFields.push(event.target);
      if (!invalidScheduled) { invalidScheduled = true; requestAnimationFrame(displayErrors); }
    }, true);
    form.addEventListener('input', event => {
      if (event.target.validity?.valid) {
        removeError(event.target);
        for (const link of list.querySelectorAll('[data-course-error-for]')) {
          if (link.dataset.courseErrorFor === event.target.id) link.closest('li').remove();
        }
      }
      if (![...form.elements].some(field => field.getAttribute?.('aria-invalid') === 'true')) summary.hidden = true;
    });
  }

  const detailSummary = document.querySelector('[data-course-summary]');
  if (detailSummary && matchMedia('(max-width:767px)').matches) detailSummary.open = false;

  const dialog = document.getElementById('course-delete-dialog');
  if (!dialog) return;
  let pendingForm = null;
  let confirmed = false;
  document.querySelectorAll('[data-course-delete]').forEach(deleteForm => {
    deleteForm.addEventListener('submit', event => {
      if (confirmed && pendingForm === deleteForm) return;
      event.preventDefault();
      pendingForm = deleteForm;
      dialog.querySelector('[data-course-delete-name]').textContent = deleteForm.dataset.courseName;
      window.AcademyDialogs.open(dialog, event.submitter || document.activeElement);
    });
  });
  dialog.querySelector('[data-course-delete-confirm]').addEventListener('click', () => {
    if (!pendingForm) return;
    confirmed = true;
    pendingForm.requestSubmit();
  });
  dialog.addEventListener('close', () => { if (!confirmed) pendingForm = null; });
})();
