/* Authentication interactions retain native form submission and WTForms fields. */
(() => {
  'use strict';
  const toggles = Array.from(document.querySelectorAll('[data-password-toggle]')).map(toggle => {
    const input = document.getElementById(toggle.getAttribute('aria-controls'));
    if (!input) return null;
    const label = toggle.dataset.passwordLabel || 'mật khẩu';
    const setVisible = visible => {
      input.type = visible ? 'text' : 'password';
      toggle.setAttribute('aria-pressed', String(visible));
      toggle.setAttribute('aria-label', `${visible ? 'Ẩn' : 'Hiện'} ${label}`);
      toggle.textContent = visible ? 'Ẩn' : 'Hiện';
    };
    toggle.hidden = false;
    toggle.addEventListener('click', () => setVisible(input.type === 'password'));
    return {setVisible};
  }).filter(Boolean);

  const forms = Array.from(document.querySelectorAll('[data-auth-form]'));
  const resetSubmission = form => {
    delete form.dataset.authSubmitting;
    form.removeAttribute('aria-busy');
    form.querySelectorAll('.auth-submit').forEach(button => button.removeAttribute('aria-disabled'));
    const status = form.querySelector('[data-auth-submit-status]');
    if (status) status.hidden = true;
  };
  forms.forEach(form => {
    form.addEventListener('submit', event => {
      if (form.dataset.authSubmitting === 'true') {
        event.preventDefault();
        return;
      }
      form.dataset.authSubmitting = 'true';
      form.setAttribute('aria-busy', 'true');
      // Retain submit fields in POST; the form lock blocks repeat submissions.
      form.querySelectorAll('.auth-submit').forEach(button => button.setAttribute('aria-disabled', 'true'));
      const status = form.querySelector('[data-auth-submit-status]');
      if (status) status.hidden = false;
    });
  });

  const summary = document.querySelector('[data-auth-validation-summary]') || document.querySelector('[data-auth-server-error]');
  if (summary) {
    summary.focus();
    summary.querySelectorAll('a[href^="#"]').forEach(link => {
      link.addEventListener('click', event => {
        const field = document.getElementById(link.getAttribute('href').slice(1));
        if (!field) return;
        event.preventDefault();
        field.focus({preventScroll: true});
        field.scrollIntoView({block: 'center'});
      });
    });
  }

  window.addEventListener('pagehide', () => toggles.forEach(toggle => toggle.setVisible(false)));
  window.addEventListener('pageshow', () => {
    forms.forEach(resetSubmission);
    toggles.forEach(toggle => toggle.setVisible(false));
  });
})();
