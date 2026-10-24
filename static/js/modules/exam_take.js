/* Native answer fields, live progress, wall-clock countdown and one submit guard. */
(() => {
  'use strict';
  const init = () => {
    const workspace = document.querySelector('[data-exam-taking]');
    const form = document.getElementById('exam-form');
    if (!workspace || !form) return;
    const cards = [...form.querySelectorAll('[data-question-id]')];
    const links = [...workspace.querySelectorAll('[data-taking-question-link]')];
    const confirmDialog = document.getElementById('exam-submit-dialog');
    const navigation = workspace.querySelector('[data-taking-navigation]');
    const clock = workspace.querySelector('[data-taking-clock]');
    const errorBox = workspace.querySelector('[data-taking-error]');
    const startedAt = Date.now();
    const seconds = Math.max(0, Number(workspace.dataset.durationSeconds) || 0);
    const deadline = startedAt + seconds * 1000;
    const questionMilliseconds = new Map();
    const visibleSince = new Map();
    const visibleIds = new Set();
    let busy = false, expired = false, expiryHandled = false, confirmed = false, warned = false, dirty = false;
    let lastRemaining = null, returnFocus = null, leavingForResult = false;
    let totals = {complete: 0, partial: 0, blank: cards.length};
    const text = (selector, value) => { const element = workspace.querySelector(selector); if (element) element.textContent = value; };
    const stateOf = card => {
      const controls = [...card.querySelectorAll('input[type="radio"],input[type="checkbox"],textarea')].filter(input => !input.disabled);
      if (card.dataset.questionType === 'short_answer') return controls.some(input => input.value.trim()) ? 'complete' : 'blank';
      const selected = controls.filter(input => input.checked);
      if (!selected.length) return 'blank';
      if (['truefalse', 'true_false'].includes(card.dataset.questionType)) return selected.length === new Set(controls.map(input => input.name)).size ? 'complete' : 'partial';
      return 'complete';
    };
    const updateProgress = () => {
      totals = {complete: 0, partial: 0, blank: 0};
      cards.forEach(card => {
        const state = stateOf(card);
        totals[state]++;
        card.dataset.answerState = state;
        card.classList.toggle('is-complete', state === 'complete');
        card.classList.toggle('is-partial', state === 'partial');
        const selectedCount = card.querySelectorAll('input:checked').length;
        const groupsCount = new Set([...card.querySelectorAll('input[type="radio"]')].map(input => input.name)).size;
        const label = state === 'complete' ? 'Đã trả lời đầy đủ' : state === 'partial' ? `Đã trả lời ${selectedCount}/${groupsCount} ý` : 'Chưa trả lời';
        card.querySelector('[data-taking-question-status]').textContent = label;
        const link = links.find(item => item.dataset.takingQuestionLink === card.dataset.questionId);
        if (link) {
          link.classList.toggle('is-complete', state === 'complete');
          link.classList.toggle('is-partial', state === 'partial');
          link.setAttribute('aria-label', `Câu ${card.dataset.questionNumber}: ${label}`);
        }
      });
      text('[data-taking-count]', `${totals.complete}/${cards.length} câu`);
      text('[data-taking-complete]', totals.complete);
      workspace.querySelector('[data-taking-progress]').value = totals.complete;
      const partial = workspace.querySelector('[data-taking-partial]');
      partial.hidden = !totals.partial;
      partial.textContent = `${totals.partial} câu Đúng / Sai mới trả lời một phần.`;
      text('[data-taking-end-summary]', `Đã trả lời đầy đủ ${totals.complete}/${cards.length} câu${totals.partial ? `; ${totals.partial} câu còn thiếu ý` : ''}.`);
      return totals;
    };
    form.addEventListener('input', () => { dirty = true; updateProgress(); });
    form.addEventListener('change', () => { dirty = true; updateProgress(); });
    form.addEventListener('reset', () => requestAnimationFrame(updateProgress));
    updateProgress();
    const narrow = window.matchMedia('(max-width: 1023px)');
    const placeNavigation = () => {
      navigation.open = !narrow.matches;
      // Keep the single timer in the reading context on mobile and in the
      // sticky support column on desktop; no duplicate timer announcements.
      if (narrow.matches) workspace.querySelector('.taking-header').append(clock);
      else workspace.querySelector('.taking-sidebar').prepend(clock);
    };
    placeNavigation();
    narrow.addEventListener('change', placeNavigation);
    links.forEach(link => link.addEventListener('click', event => {
      const card = cards.find(item => item.dataset.questionId === link.dataset.takingQuestionLink);
      if (!card) return;
      event.preventDefault();
      if (narrow.matches) navigation.open = false;
      card.scrollIntoView({block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
      card.focus({preventScroll: true});
      history.replaceState(null, '', `#${card.id}`);
    }));
    const flushVisible = (now, restart = true) => {
      visibleSince.forEach((since, id) => {
        questionMilliseconds.set(id, (questionMilliseconds.get(id) || 0) + Math.max(0, now - since));
        if (restart) visibleSince.set(id, now);
      });
      if (!restart) visibleSince.clear();
    };
    const writeTimes = () => {
      const now = Date.now();
      flushVisible(now);
      document.getElementById('time-spent-seconds').value = Math.max(0, Math.round((now - startedAt) / 1000));
      questionMilliseconds.forEach((milliseconds, id) => {
        const input = document.getElementById(`time-q-${id}`);
        if (input) input.value = Math.max(0, Math.round(milliseconds / 1000));
      });
    };
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(entries => {
        const now = Date.now();
        entries.forEach(entry => {
          const id = entry.target.dataset.questionId;
          if (entry.isIntersecting) {
            visibleIds.add(id);
            if (!document.hidden) visibleSince.set(id, visibleSince.get(id) || now);
          } else {
            visibleIds.delete(id);
            if (visibleSince.has(id)) {
              questionMilliseconds.set(id, (questionMilliseconds.get(id) || 0) + Math.max(0, now - visibleSince.get(id)));
              visibleSince.delete(id);
            }
          }
        });
        const active = cards.find(card => visibleIds.has(card.dataset.questionId));
        links.forEach(link => {
          if (active && link.dataset.takingQuestionLink === active.dataset.questionId) link.setAttribute('aria-current', 'location');
          else link.removeAttribute('aria-current');
        });
      }, {threshold: 0.35});
      cards.forEach(card => observer.observe(card));
    }
    window.addEventListener('beforeunload', event => {
      if (leavingForResult || !dirty) return;
      event.preventDefault(); event.returnValue = '';
    });
    const displayError = message => {
      errorBox.textContent = message; errorBox.hidden = false;
      errorBox.focus({preventScroll: true}); errorBox.scrollIntoView({block: 'center'});
    };
    const setBusy = value => {
      busy = value; form.inert = value; form.setAttribute('aria-busy', String(value));
      workspace.querySelectorAll('[data-taking-submit],[data-taking-confirm-submit]').forEach(button => { button.disabled = value; });
      const status = workspace.querySelector('[data-taking-send-status]');
      status.hidden = !value;
      status.textContent = expired ? 'Đã hết thời gian. Đang gửi bài làm…' : 'Đang gửi bài làm. Vui lòng chờ…';
    };
    const closeConfirmation = () => {
      if (window.AcademyDialogs) window.AcademyDialogs.close(confirmDialog);
      else if (confirmDialog.open) confirmDialog.close();
    };
    const send = async () => {
      if (busy) return;
      if (navigator.onLine === false) {
        closeConfirmation();
        displayError(expired ? 'Đã hết thời gian nhưng thiết bị đang mất kết nối. Giữ trang này mở; bài sẽ được gửi khi có mạng trở lại.' : 'Thiết bị đang mất kết nối. Câu trả lời vẫn còn trên trang này; kiểm tra mạng rồi nộp lại.');
        return;
      }
      errorBox.hidden = true;
      writeTimes();
      // Capture the untouched native fields before making the form inert.
      const payload = new FormData(form);
      closeConfirmation(); setBusy(true);
      if (!window.fetch) { leavingForResult = true; HTMLFormElement.prototype.submit.call(form); return; }
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 30000);
      try {
        const response = await fetch(form.action || location.href, {method: 'POST', body: payload, credentials: 'same-origin', redirect: 'follow', signal: controller.signal});
        const expected = new URL(workspace.dataset.resultUrl, location.origin);
        const destination = new URL(response.url || location.href);
        if (response.ok && destination.origin === expected.origin && destination.pathname === expected.pathname) {
          leavingForResult = true;
          window.location.assign(destination.href);
          return;
        }
        let message = 'Chưa xác nhận được kết quả nộp bài. Câu trả lời vẫn còn trên trang; bạn có thể nộp lại.';
        if (response.status === 400) message = 'Phiên xác thực có thể đã hết hạn. Câu trả lời vẫn còn trên trang; hãy kiểm tra kết nối và đăng nhập trước khi thử lại.';
        else if (response.status === 403) message = 'Hiện chưa có quyền nộp bài này. Câu trả lời vẫn còn trên trang; hãy kiểm tra trạng thái bài với giáo viên.';
        else if (destination.pathname === new URL(form.action || location.href).pathname) {
          const html = await response.text();
          const parsed = new DOMParser().parseFromString(html, 'text/html');
          const flash = parsed.querySelector('.flash-danger,.flash-warning,.flash-info,.flash');
          const serverMessage = flash?.querySelector('span')?.textContent.trim();
          if (serverMessage) message = `${serverMessage} Câu trả lời vẫn còn trên trang; kiểm tra trạng thái rồi thử lại.`;
        }
        setBusy(false); displayError(message);
      } catch (_error) {
        setBusy(false);
        displayError('Chưa xác nhận được kết quả nộp bài do kết nối bị gián đoạn. Giữ trang này mở và nộp lại khi có mạng; hệ thống kiểm tra bài đã ghi nhận để tránh nộp lặp.');
      } finally { clearTimeout(timeout); }
    };
    form.addEventListener('submit', event => {
      event.preventDefault();
      if (busy) return;
      updateProgress();
      if (expired || confirmed) { confirmed = false; void send(); return; }
      returnFocus = event.submitter || document.activeElement;
      text('[data-confirm-complete]', totals.complete); text('[data-confirm-partial]', totals.partial); text('[data-confirm-blank]', totals.blank);
      text('#exam-submit-title', totals.complete === cards.length && cards.length ? 'Sẵn sàng nộp bài?' : totals.blank === cards.length ? 'Nộp bài khi chưa trả lời?' : 'Bạn còn câu chưa trả lời đầy đủ');
      text('[data-confirm-hint]', totals.complete === cards.length && cards.length ? 'Bạn đã trả lời tất cả các câu. Hãy kiểm tra lựa chọn lần cuối trước khi xác nhận.' : totals.blank === cards.length ? 'Bạn chưa nhập hoặc chọn đáp án nào. Bài vẫn được nộp nếu bạn xác nhận.' : `Còn ${totals.blank} câu chưa trả lời${totals.partial ? ` và ${totals.partial} câu Đúng / Sai còn thiếu ý` : ''}. Bạn có thể quay lại để hoàn thành.`);
      if (window.AcademyDialogs) window.AcademyDialogs.open(confirmDialog, returnFocus);
      else if (typeof confirmDialog.showModal === 'function') confirmDialog.showModal();
      else if (window.confirm('Nộp bài làm? Bạn không thể sửa câu trả lời sau khi nộp.')) { confirmed = true; form.requestSubmit(); }
    });
    workspace.querySelector('[data-taking-confirm-submit]').addEventListener('click', () => { if (!busy) { confirmed = true; form.requestSubmit(); } });
    confirmDialog.addEventListener('close', () => { if (!busy && returnFocus?.isConnected) returnFocus.focus({preventScroll: true}); });
    const tick = () => {
      if (busy) return;
      const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      if (remaining !== lastRemaining) {
        text('[data-taking-time]', `${String(Math.floor(remaining / 60)).padStart(2, '0')}:${String(remaining % 60).padStart(2, '0')}`);
        clock.classList.toggle('is-warning', remaining < 300 && remaining > 0);
        clock.classList.toggle('is-expired', remaining === 0);
        lastRemaining = remaining;
      }
      if (remaining < 300 && remaining > 0 && !warned) {
        warned = true; text('[data-taking-time-hint]', 'Còn dưới 5 phút. Hãy kiểm tra đáp án.');
        text('[data-taking-announcement]', 'Bài làm còn dưới 5 phút. Hãy kiểm tra đáp án trước khi hết thời gian.');
      }
      if (remaining === 0 && !expiryHandled) {
        expired = true; expiryHandled = true;
        text('[data-taking-time-hint]', 'Đã hết thời gian làm bài');
        text('[data-taking-announcement]', 'Đã hết thời gian. Bài làm đang được gửi.');
        form.requestSubmit();
      }
    };
    let timer = window.setInterval(tick, 250);
    document.addEventListener('visibilitychange', () => {
      flushVisible(Date.now(), false);
      if (!document.hidden) { visibleIds.forEach(id => visibleSince.set(id, Date.now())); tick(); }
    });
    window.addEventListener('online', () => { if (expired && !busy) form.requestSubmit(); });
    window.addEventListener('pagehide', () => { flushVisible(Date.now(), false); clearInterval(timer); });
    window.addEventListener('pageshow', event => {
      if (event.persisted) { leavingForResult = false; setBusy(false); visibleIds.forEach(id => visibleSince.set(id, Date.now())); tick(); timer = window.setInterval(tick, 250); }
      updateProgress();
    });
    const seenImages = new WeakSet();
    const watchImages = root => {
      const images = root.matches?.('img') ? [root] : [...root.querySelectorAll('img')];
      images.forEach(image => {
        if (seenImages.has(image) || image.closest('#exam-image-dialog') || image.classList.contains('formula-svg')) return;
        seenImages.add(image);
        const failed = () => {
          if (!image.isConnected || image.dataset.takingImageFailed) return;
          image.dataset.takingImageFailed = 'true';
          const source = image.getAttribute('src');
          const imageButton = image.closest('button');
          const notice = document.createElement('div'); notice.className = 'taking-image-error'; notice.setAttribute('role', 'status');
          const label = document.createElement('span'); label.textContent = 'Không tải được hình minh họa.';
          const retry = document.createElement('button'); retry.type = 'button'; retry.className = 'btn btn-secondary'; retry.textContent = 'Tải lại hình';
          retry.addEventListener('click', event => {
            event.stopPropagation(); retry.disabled = true; label.textContent = 'Đang tải lại hình…';
            // A failed lazy image is hidden while the retry control is shown.
            // Force this explicit user request to load even outside the viewport.
            image.loading = 'eager';
            image.addEventListener('load', () => { notice.remove(); image.hidden = false; if (imageButton) imageButton.hidden = false; delete image.dataset.takingImageFailed; }, {once: true});
            image.addEventListener('error', () => { retry.disabled = false; label.textContent = 'Chưa tải được hình. Bạn có thể thử lại.'; }, {once: true});
            image.removeAttribute('src'); requestAnimationFrame(() => { image.src = source; });
          });
          notice.append(label, retry); (imageButton || image).insertAdjacentElement('afterend', notice); image.hidden = true;
          if (imageButton) imageButton.hidden = true;
        };
        image.addEventListener('error', failed);
        if (image.complete && image.naturalWidth === 0 && image.getAttribute('src')) failed();
      });
    };
    watchImages(form);
    new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => { if (node.nodeType === Node.ELEMENT_NODE) watchImages(node); }))).observe(form, {childList: true, subtree: true});
    workspace.querySelectorAll('[data-taking-image-open]').forEach(button => button.addEventListener('click', () => {
      const source = button.querySelector('img'); if (!source || source.hidden) return;
      const dialog = document.getElementById('exam-image-dialog'), preview = dialog.querySelector('[data-taking-image-preview]');
      preview.src = source.src; preview.alt = `${source.alt} phóng to`;
      if (window.AcademyDialogs) window.AcademyDialogs.open(dialog, button); else dialog.showModal();
    }));
    tick();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
