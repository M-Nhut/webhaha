/* Read-only frozen questions, native media and release-form feedback. */
(() => {
  'use strict';
  const init = () => {
    document.querySelectorAll('.teacher-draft details').forEach(disclosure => disclosure.addEventListener('toggle', () => {
      if (disclosure.open) window.renderFormulas?.(disclosure, {}, {immediate: true});
    }));
    const printOpened = new Set();
    window.addEventListener('beforeprint', () => {
      document.querySelectorAll('.teacher-draft details').forEach(disclosure => {
        if (!disclosure.open) { printOpened.add(disclosure); disclosure.open = true; }
      });
    });
    window.addEventListener('afterprint', () => { printOpened.forEach(disclosure => { disclosure.open = false; }); printOpened.clear(); });
    const dialog = document.getElementById('draft-image-dialog');
    const enlarged = dialog?.querySelector('[data-draft-lightbox]');
    const lightboxError = dialog?.querySelector('[data-draft-lightbox-error]');
    enlarged?.addEventListener('error', () => { enlarged.hidden = true; lightboxError.hidden = false; });
    enlarged?.addEventListener('load', () => { enlarged.hidden = false; lightboxError.hidden = true; });
    document.querySelectorAll('[data-draft-image]').forEach(image => {
      const figure = image.closest('figure'), button = figure.querySelector('[data-draft-image-open]');
      const error = figure.querySelector('.teacher-draft-image-error'), caption = figure.querySelector('figcaption');
      const failed = () => { button.hidden = true; error.hidden = false; caption.hidden = true; };
      const loaded = () => { button.hidden = false; error.hidden = true; caption.hidden = false; };
      image.addEventListener('error', failed); image.addEventListener('load', loaded);
      if (image.complete && !image.naturalWidth) failed();
      figure.querySelector('[data-draft-image-retry]')?.addEventListener('click', () => {
        const source = image.getAttribute('src'); image.loading = 'eager'; image.removeAttribute('src'); image.src = source;
      });
      button.addEventListener('click', () => {
        if (!dialog || !enlarged || !window.AcademyDialogs) return;
        enlarged.hidden = false; lightboxError.hidden = true;
        enlarged.alt = image.alt + ' · phóng to'; enlarged.src = image.currentSrc || image.src;
        window.AcademyDialogs.open(dialog, button);
      });
    });
    const form = document.querySelector('[data-draft-release]');
    if (!form) return;
    const button = form.querySelector('[type="submit"]'), status = form.querySelector('[data-draft-release-status]');
    let busy = false;
    form.addEventListener('submit', event => {
      if (busy) { event.preventDefault(); return; }
      busy = true;
      if (button) { button.disabled = true; button.setAttribute('aria-busy', 'true'); }
      if (status) status.hidden = false;
    });
    window.addEventListener('pageshow', () => {
      busy = false;
      if (button) { button.disabled = false; button.removeAttribute('aria-busy'); }
      if (status) status.hidden = true;
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
