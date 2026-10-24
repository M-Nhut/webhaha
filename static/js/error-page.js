/* Error recovery controls. Error handlers and response payloads remain server-owned. */
(() => {
  'use strict';

  function initErrorPage() {
    if (!document.body.classList.contains('error-page')) return;
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
      window.lucide.createIcons({ attrs: { 'aria-hidden': 'true', 'stroke-width': 1.75 } });
    }

    document.querySelector('[data-error-back]')?.addEventListener('click', event => {
      const button = event.currentTarget;
      let safeReferrer = false;
      try {
        const referrer = new URL(document.referrer);
        safeReferrer = referrer.origin === window.location.origin
          && referrer.href.split('#')[0] !== window.location.href.split('#')[0];
      } catch (_error) { /* Missing or malformed referrer uses the safe fallback. */ }
      if (safeReferrer && window.history.length > 1) {
        window.history.back();
        return;
      }
      const fallback = new URL(button.dataset.fallbackUrl || '/', window.location.origin);
      window.location.assign(fallback.origin === window.location.origin ? fallback.href : '/');
    });

    const reference = document.getElementById('error-reference');
    const copyButton = document.querySelector('[data-copy-request-id]');
    const feedback = document.getElementById('error-copy-feedback');
    copyButton?.addEventListener('click', async () => {
      const value = reference?.textContent.trim();
      if (!value || !feedback) return;
      copyButton.disabled = true;
      copyButton.setAttribute('aria-busy', 'true');
      feedback.classList.remove('is-error');
      feedback.textContent = '';
      try {
        if (!navigator.clipboard || typeof navigator.clipboard.writeText !== 'function') {
          throw new Error('Clipboard unavailable');
        }
        await navigator.clipboard.writeText(value);
        feedback.textContent = 'Đã sao chép mã tham chiếu.';
      } catch (_error) {
        const selection = window.getSelection();
        let selected = false;
        if (selection && reference) {
          const range = document.createRange();
          range.selectNodeContents(reference);
          selection.removeAllRanges();
          selection.addRange(range);
          reference.focus({ preventScroll: true });
          selected = true;
        }
        feedback.classList.add('is-error');
        feedback.textContent = selected
          ? 'Không thể sao chép tự động. Mã đã được chọn; bạn có thể dùng lệnh Sao chép trên thiết bị.'
          : 'Không thể sao chép tự động. Bạn có thể chọn mã tham chiếu và sao chép thủ công.';
      } finally {
        copyButton.disabled = false;
        copyButton.removeAttribute('aria-busy');
      }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initErrorPage);
  else initErrorPage();
})();
