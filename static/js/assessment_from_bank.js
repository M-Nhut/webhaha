/* Native bank draft fields remain the source of truth for selection and budgets. */
document.addEventListener('DOMContentLoaded', () => {
  const sourceForm = document.querySelector('[data-assessment-source-form]');
  sourceForm?.querySelector('[name="course_id"]')?.addEventListener('change', () => {
    sourceForm.querySelectorAll('[name="bank_ids"]').forEach(field => { field.disabled = true; });
    sourceForm.requestSubmit();
  });
  let formulas = {};
  try { formulas = JSON.parse(document.getElementById('assessment-bank-formulas')?.textContent || '{}'); } catch (_) { /* Plain text remains readable. */ }
  document.querySelectorAll('[data-bank-preview]').forEach(node => window.renderFormulas?.(node, formulas));
  document.querySelectorAll('[data-composer-image]').forEach(image => {
    const error = image.parentElement.querySelector('.assessment-image-error');
    const failed = () => { if (error) error.hidden = false; };
    image.addEventListener('error', failed);
    if (image.complete && !image.naturalWidth) failed();
  });
  const form = document.querySelector('[data-assessment-selection-form]');
  if (!form) return;
  form.noValidate = true;
  const groups = [...form.querySelectorAll('[data-budget-kind]')];
  const cards = [...form.querySelectorAll('[data-pool-question]')];
  const summary = form.querySelector('[data-selection-errors]');
  const errorList = summary.querySelector('[data-selection-error-list]');
  const submit = form.querySelector('[data-create-draft]');
  let busy = false;
  const isAutomatic = () => form.querySelector('[name="mode"]:checked')?.value === 'auto';
  const counts = () => Object.fromEntries(groups.map(group => {
    const kind = group.dataset.budgetKind;
    return [kind, isAutomatic() ? Number(form.elements[`count_${kind}`].value) : cards.filter(card => card.dataset.questionKind === kind && card.querySelector('[name="question_ids"]').checked).length];
  }));
  const update = () => {
    const auto = isAutomatic();
    const selected = counts();
    cards.forEach(card => {
      const checkbox = card.querySelector('[name="question_ids"]');
      checkbox.disabled = auto;
      card.classList.toggle('is-selected', !auto && checkbox.checked);
    });
    form.querySelector('[data-auto-note]').hidden = !auto;
    form.querySelector('[data-mode-hint]').textContent = auto ? 'Nhập số câu cần lấy cho từng phần. Hệ thống chọn ngẫu nhiên và không lặp câu trong đề.' : 'Chọn câu trong danh sách và đặt điểm cho các phần có câu.';
    let total = 0;
    groups.forEach(group => {
      const kind = group.dataset.budgetKind;
      form.elements[`count_${kind}`].disabled = !auto;
      group.querySelector('[data-count-hint]').textContent = auto ? `Nguồn có ${group.dataset.available} câu.` : 'Chỉ sử dụng khi chọn ngẫu nhiên.';
      group.querySelector('[data-kind-selection]').textContent = `${auto ? 'Sẽ lấy' : 'Đang chọn'}: ${Number.isFinite(selected[kind]) ? selected[kind] : '—'} câu`;
      total += Number(form.elements[`budget_${kind}`].value);
    });
    const amount = form.querySelector('[data-budget-total]');
    amount.textContent = Number.isFinite(total) ? `${Number(total.toFixed(2))} / 10` : 'Chưa hợp lệ';
    amount.classList.toggle('is-valid', Number.isFinite(total) && Math.abs(total - 10) < 0.000001);
    const selectedTotal = Object.values(selected).reduce((sum, n) => sum + n, 0);
    form.querySelector('[data-selection-count]').textContent = Number.isFinite(selectedTotal) ? selectedTotal : '—';
  };
  const addError = (messages, field, message) => {
    field?.setAttribute('aria-invalid', 'true');
    messages.push({field, message});
  };
  const validate = () => {
    form.querySelectorAll('[aria-invalid="true"]').forEach(field => field.removeAttribute('aria-invalid'));
    const messages = [];
    const selected = counts();
    const totalCount = Object.values(selected).reduce((sum, n) => sum + n, 0);
    if (!Number.isInteger(totalCount) || totalCount < 1 || totalCount > 100) addError(messages, isAutomatic() ? form.elements[`count_${groups[0]?.dataset.budgetKind}`] : cards[0]?.querySelector('input'), 'Chọn từ 1 đến 100 câu để tạo đề.');
    let budgetTotal = 0;
    groups.forEach(group => {
      const kind = group.dataset.budgetKind;
      const budget = form.elements[`budget_${kind}`];
      const count = form.elements[`count_${kind}`];
      const points = Number(budget.value);
      budgetTotal += points;
      if (isAutomatic() && (!count.validity.valid || count.value === '')) addError(messages, count, `${group.dataset.kindLabel}: nhập số câu nguyên từ 0 đến 100.`);
      else if (isAutomatic() && selected[kind] > Number(group.dataset.available)) addError(messages, count, `${group.dataset.kindLabel}: nguồn chỉ có ${group.dataset.available} câu đủ điều kiện.`);
      if (!budget.validity.valid || budget.value === '') addError(messages, budget, `${group.dataset.kindLabel}: nhập điểm từ 0 đến 10, tối đa hai chữ số thập phân.`);
      else if (Boolean(selected[kind]) !== Boolean(points)) addError(messages, budget, `${group.dataset.kindLabel}: phần có câu phải có điểm; phần không có câu phải bằng 0 điểm.`);
    });
    if (!Number.isFinite(budgetTotal) || Math.abs(budgetTotal - 10) > 0.000001) addError(messages, form.elements[`budget_${groups[0]?.dataset.budgetKind}`], 'Tổng điểm các phần phải bằng 10 điểm.');
    errorList.replaceChildren();
    messages.forEach(({field, message}) => {
      const item = document.createElement('li');
      const link = document.createElement(field?.id ? 'a' : 'span');
      link.textContent = message;
      if (field?.id) link.href = `#${field.id}`;
      item.append(link); errorList.append(item);
    });
    summary.hidden = !messages.length;
    if (messages.length) summary.focus();
    return !messages.length;
  };
  form.addEventListener('input', update);
  form.addEventListener('change', update);
  form.addEventListener('submit', event => {
    if (busy || !validate()) { event.preventDefault(); return; }
    busy = true; submit.disabled = true; submit.setAttribute('aria-busy', 'true');
    form.querySelector('[data-create-status]').hidden = false;
  });
  window.addEventListener('pageshow', () => {
    busy = false; submit.disabled = !cards.length; submit.removeAttribute('aria-busy');
    form.querySelector('[data-create-status]').hidden = true;
  });
  update();
});
