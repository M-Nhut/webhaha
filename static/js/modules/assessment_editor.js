/* The current form is preserved until a successful save; there is no autosave. */
document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('.assessment-editor');
  if (!form) return;
  form.noValidate = true;
  const status = document.getElementById('assessment-save-status');
  const dot = form.querySelector('[data-save-dot]');
  const summary = document.getElementById('assessment-editor-errors');
  const errorList = summary.querySelector('[data-editor-error-list]');
  const cards = [...form.querySelectorAll('[data-question-index]')];
  const budgets = [...form.querySelectorAll('[name^="budget_"]')];
  const dialog = document.getElementById('assessment-publish-dialog');
  const reviewed = form.elements.reviewed;
  let dirty = false, busy = false, editVersion = 0, publishConfirmed = false;
  const setStatus = (state, message) => {
    form.dataset.saveState = state;
    if (dot) dot.dataset.state = state;
    status.textContent = message;
  };
  const expandField = field => {
    let ancestor = field.parentElement;
    while (ancestor && ancestor !== form) {
      if (ancestor.tagName === 'DETAILS') ancestor.open = true;
      ancestor = ancestor.parentElement;
    }
  };
  const showErrors = errors => {
    errorList.replaceChildren();
    errors.forEach(({field, message}) => {
      const item = document.createElement('li');
      const link = document.createElement(field?.id ? 'a' : 'span');
      link.textContent = message;
      if (field?.id) {
        link.href = `#${field.id}`;
        link.addEventListener('click', event => { event.preventDefault(); expandField(field); field.focus(); });
        field.setAttribute('aria-invalid', 'true');
      }
      item.append(link); errorList.append(item);
    });
    summary.hidden = !errors.length;
    if (errors.length) summary.focus();
  };
  const updatePoints = () => {
    const total = budgets.reduce((sum, field) => sum + Number(field.value), 0);
    const validTotal = Number.isFinite(total) && Math.abs(total - 10) < 0.000001;
    const pointsStatus = document.getElementById('assessment-points-status');
    pointsStatus.textContent = validTotal ? 'Tổng: 10 điểm' : `Tổng: ${Number.isFinite(total) ? Number(total.toFixed(2)) : 'chưa hợp lệ'} / 10 điểm`;
    pointsStatus.classList.toggle('is-valid', validTotal);
    budgets.forEach(field => {
      const amount = Number(field.value);
      const kind = field.name.replace('budget_', '');
      const items = cards.filter(card => card.dataset.questionKind === kind);
      const weights = items.map(card => Number(card.querySelector('[name$="_weight"]').value));
      const sum = weights.reduce((a, b) => a + b, 0);
      let message = validTotal ? '' : 'Tổng điểm các phần phải bằng 10.';
      if (validTotal && Boolean(items.length) !== Boolean(amount)) message = `${field.dataset.kindLabel}: phần có câu phải có điểm; phần không có câu phải bằng 0.`;
      field.setCustomValidity(message);
      items.forEach((card, i) => {
        const validWeight = Number.isFinite(weights[i]) && weights[i] > 0 && Number.isFinite(sum) && sum > 0;
        card.querySelector('[data-item-points]').textContent = validWeight && Number.isFinite(amount) ? `Điểm phân bổ ≈ ${(amount * weights[i] / sum).toFixed(4)}` : 'Kiểm tra trọng số';
      });
    });
  };
  const answerIndicators = card => {
    const prefix = `q${card.dataset.questionIndex}_`;
    const kind = card.dataset.questionKind;
    card.querySelectorAll('[data-answer-indicator]').forEach(indicator => {
      const index = indicator.dataset.answerIndicator;
      if (kind === 'true_false') {
        const value = form.elements[`${prefix}truth${index}`]?.value;
        indicator.textContent = value === '1' ? 'Đúng' : value === '0' ? 'Sai' : 'Chưa chọn';
        indicator.dataset.answerState = value === '1' || value === '0' ? 'set' : 'missing';
        indicator.hidden = false;
      } else {
        const correct = card.querySelector(`input[name="${prefix}correct"]:checked`);
        indicator.textContent = correct?.value === index ? 'Đáp án đúng' : '';
        indicator.hidden = correct?.value !== index;
        indicator.dataset.answerState = 'set';
      }
    });
  };
  const previewTimers = new Map();
  cards.forEach(card => {
    let formulas = {};
    try { formulas = JSON.parse(card.dataset.formulas || '{}'); } catch (_) { /* Keep text available. */ }
    const render = node => window.renderFormulas?.(node, formulas);
    const renderField = (field, immediate = false) => {
      const name = field.name?.replace(`q${card.dataset.questionIndex}_`, '');
      const target = [...card.querySelectorAll('[data-preview-field]')].find(node => node.dataset.previewField === name);
      if (!target) return;
      const key = `${card.dataset.questionIndex}:${name}`;
      clearTimeout(previewTimers.get(key));
      const update = () => {
        window.MathJax?.typesetClear?.([target]);
        target.textContent = field.value;
        render(target);
        previewTimers.delete(key);
      };
      if (immediate) update();
      else previewTimers.set(key, setTimeout(update, 220));
    };
    card.querySelectorAll('.assessment-render').forEach(render);
    // A server validation rerender must show the submitted fields in its preview.
    card.querySelectorAll('textarea, input[type="text"]').forEach(field => renderField(field, true));
    card.addEventListener('input', event => { renderField(event.target); answerIndicators(card); });
    card.addEventListener('change', () => answerIndicators(card));
    answerIndicators(card);
  });
  form.querySelectorAll('[data-composer-image]').forEach(image => {
    const error = image.parentElement.querySelector('.assessment-image-error');
    const failed = () => { if (error) error.hidden = false; };
    image.addEventListener('error', failed);
    if (image.complete && !image.naturalWidth) failed();
  });
  form.addEventListener('input', () => {
    updatePoints();
    dirty = true; editVersion++;
    if (!busy) setStatus('dirty', 'Có thay đổi chưa lưu.');
  });
  const validate = publishing => {
    updatePoints();
    form.querySelectorAll('[aria-invalid="true"]').forEach(field => field.removeAttribute('aria-invalid'));
    const errors = [];
    [...form.elements].forEach(field => {
      if (!field.willValidate || field.validity.valid) return;
      const label = field.labels?.[0]?.textContent.trim() || field.name;
      errors.push({field, message: field.validity.customError ? field.validationMessage : `${label}: ${field.validationMessage}`});
    });
    if (publishing && !reviewed.checked) errors.push({field: reviewed, message: 'Xác nhận đã đối chiếu câu hỏi, hình vẽ, đáp án và cách tính điểm trước khi giao.'});
    showErrors(errors);
    return !errors.length;
  };
  form.querySelector('[data-request-publish]')?.addEventListener('click', event => {
    if (busy || !validate(true)) return;
    dialog.querySelector('[data-publish-title]').textContent = form.elements.title.value;
    dialog.querySelector('[data-publish-course]').textContent = form.elements.course_id.selectedOptions[0]?.textContent || '';
    dialog.querySelector('[data-publish-duration]').textContent = `${form.elements.duration_minutes.value} phút`;
    if (window.AcademyDialogs) window.AcademyDialogs.open(dialog, event.currentTarget);
    else dialog.showModal();
  });
  form.querySelector('[data-confirm-publish]')?.addEventListener('click', () => {
    if (busy || !validate(true)) return;
    publishConfirmed = true;
    if (window.AcademyDialogs) window.AcademyDialogs.close(dialog);
    else dialog.close();
    form.requestSubmit(form.querySelector('[data-publish-submit]'));
  });
  window.addEventListener('beforeunload', event => {
    if (dirty) { event.preventDefault(); event.returnValue = ''; }
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    const action = event.submitter?.value || 'draft';
    if (action === 'publish' && !publishConfirmed) { form.querySelector('[data-request-publish]').click(); return; }
    publishConfirmed = false;
    if (!validate(action === 'publish')) return;
    const version = editVersion;
    const data = new FormData(form);
    data.set('action', action);
    const buttons = [...form.querySelectorAll('button[name="action"], [data-request-publish], [data-confirm-publish]')];
    const previousDisabled = buttons.map(button => button.disabled);
    buttons.forEach(button => { button.disabled = true; button.setAttribute('aria-busy', 'true'); });
    busy = true;
    // Keep a publication snapshot fixed while it is sent; draft saves allow further edits.
    form.inert = action === 'publish';
    setStatus('saving', action === 'publish' ? 'Đang giao đề cho lớp…' : 'Đang lưu chỉnh sửa…');
    try {
      const response = await fetch(form.getAttribute('action') || location.href, {method: 'POST', body: data, headers: {Accept: 'application/json'}});
      if (!response.headers.get('content-type')?.includes('application/json')) {
        if (response.status === 403) throw new Error('Quyền sửa đề hoặc quyền sử dụng nguồn đã thay đổi.');
        if (response.status === 400 || response.status === 401 || response.redirected) throw new Error('Phiên đăng nhập hoặc mã bảo vệ đã hết hiệu lực. Đăng nhập lại ở tab khác rồi thử lưu.');
        throw new Error('Máy chủ chưa trả về kết quả lưu hợp lệ. Hãy thử lại.');
      }
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.message || 'Không thể lưu; kiểm tra quyền truy cập rồi thử lại.');
      dirty = version !== editVersion;
      setStatus(dirty ? 'dirty' : 'saved', dirty ? 'Đã lưu bản trước; còn chỉnh sửa mới chưa lưu.' : result.message || 'Đã lưu tất cả chỉnh sửa.');
      if (!dirty) document.querySelector('.assessment-composer-header h1').textContent = String(data.get('title') || '').trim();
      summary.hidden = true;
      const matrixLink = document.getElementById('assessment-matrix-link');
      if (matrixLink && result.matrix_url) { matrixLink.href = result.matrix_url; matrixLink.hidden = false; }
      if (result.redirect_url) { dirty = false; location.assign(result.redirect_url); }
    } catch (error) {
      dirty = true;
      const message = `${error.message || 'Mất kết nối khi lưu.'} Nội dung đang nhập vẫn được giữ trên trang.`;
      setStatus('error', 'Chưa lưu được. Nội dung đang nhập vẫn được giữ trên trang.');
      form.inert = false;
      showErrors(message.split('\n').filter(Boolean).map(text => ({message: text})));
    } finally {
      busy = false; form.inert = false;
      buttons.forEach((button, index) => { button.disabled = previousDisabled[index]; button.removeAttribute('aria-busy'); });
    }
  });
  updatePoints();
});
