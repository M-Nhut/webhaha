/* Read-only evidence disclosures and native images; no scoring or answer writes. */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-result-explanation], .result-audit').forEach(disclosure => {
    disclosure.addEventListener('toggle', () => {
      if (disclosure.open) window.renderFormulas?.(disclosure, {}, {immediate: true});
    });
  });
  const printOpened = new Set();
  window.addEventListener('beforeprint', () => {
    document.querySelectorAll('[data-result-explanation]').forEach(disclosure => {
      if (!disclosure.open) { printOpened.add(disclosure); disclosure.open = true; }
    });
  });
  window.addEventListener('afterprint', () => {
    printOpened.forEach(disclosure => { disclosure.open = false; }); printOpened.clear();
  });
  const dialog = document.getElementById('result-image-dialog');
  const enlarged = dialog?.querySelector('[data-result-lightbox-image]');
  const lightboxError = dialog?.querySelector('.result-lightbox-error');
  enlarged?.addEventListener('error', () => { enlarged.hidden = true; if (lightboxError) lightboxError.hidden = false; });
  enlarged?.addEventListener('load', () => { enlarged.hidden = false; if (lightboxError) lightboxError.hidden = true; });
  document.querySelectorAll('[data-result-image]').forEach(image => {
    const figure = image.closest('.result-figure');
    const button = figure.querySelector('[data-result-image-open]');
    const error = figure.querySelector('.result-image-error');
    const caption = figure.querySelector('figcaption');
    const fail = () => { button.hidden = true; error.hidden = false; caption.hidden = true; };
    const loaded = () => { button.hidden = false; error.hidden = true; caption.hidden = false; };
    image.addEventListener('error', fail);
    image.addEventListener('load', loaded);
    if (image.complete && !image.naturalWidth) fail();
    figure.querySelector('[data-result-image-retry]')?.addEventListener('click', () => {
      const source = image.getAttribute('src'); image.loading = 'eager'; image.removeAttribute('src'); image.src = source;
    });
    button.addEventListener('click', () => {
      if (!dialog || !enlarged || !window.AcademyDialogs) return;
      enlarged.hidden = false; lightboxError.hidden = true;
      enlarged.alt = `${image.alt} · phóng to`; enlarged.src = image.currentSrc || image.src;
      window.AcademyDialogs.open(dialog, button);
    });
  });
  const decisions = [...document.querySelectorAll('[data-result-decision]')];
  let deciding = false;
  decisions.forEach(form => form.addEventListener('submit', event => {
    if (deciding) { event.preventDefault(); return; }
    deciding = true;
    decisions.forEach(item => item.querySelectorAll('button').forEach(button => { button.disabled = true; button.setAttribute('aria-busy', 'true'); }));
    const status = document.querySelector('.result-decision-status'); if (status) status.hidden = false;
  }));
  window.addEventListener('pageshow', () => {
    deciding = false;
    decisions.forEach(item => item.querySelectorAll('button').forEach(button => { button.disabled = false; button.removeAttribute('aria-busy'); }));
    const status = document.querySelector('.result-decision-status'); if (status) status.hidden = true;
  });
});
