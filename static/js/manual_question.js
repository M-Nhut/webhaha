/* Native add-question dialog, upload checks and mathematical preview. */
function scheduleManualPreview(form) {
  clearTimeout(form._previewTimer);
  form._previewTimer = setTimeout(() => previewManualQuestion(form), 250);
}
function previewManualQuestion(form) {
  const area = form.querySelector('[data-manual-preview]');
  if (!area) return;
  area.replaceChildren();
  const value = name => form.elements.namedItem(name)?.value || '';
  const add = (text, tag = 'p', className = '', parent = area) => {
    if (!text) return;
    const element = document.createElement(tag);
    element.textContent = text;
    if (className) element.className = className;
    parent.appendChild(element);
    return element;
  };
  add('Bản xem trước', 'h3', 'question-label');
  add(value('context'), 'div', 'question-context question-reading');
  add(value('question_text'), 'div', 'question-reading');
  if (form._imagePreviewUrl) { URL.revokeObjectURL(form._imagePreviewUrl); form._imagePreviewUrl = null; }
  const imageFile = form.elements.namedItem('question_image')?.files?.[0];
  if (imageFile && ['image/png', 'image/jpeg', 'image/webp'].includes(imageFile.type) && imageFile.size <= 5 * 1024 * 1024) {
    const image = document.createElement('img');
    form._imagePreviewUrl = URL.createObjectURL(imageFile);
    image.src = form._imagePreviewUrl; image.alt = 'Hình minh họa của câu hỏi'; area.appendChild(image);
  }
  const type = value('question_type');
  const choices = [...form.querySelectorAll('[name="option_text"]')].filter(input => !input.closest('fieldset')?.disabled);
  choices.forEach((input, i) => {
    const label = type === 'true_false' ? 'abcd'[i] : String.fromCharCode(65 + i);
    const fieldset = input.closest('fieldset');
    const answer = type === 'true_false' ? [...fieldset.querySelectorAll('select[name="correct_option"]')][i]?.value : fieldset.querySelector('[name="correct_option"]:checked')?.value;
    const correct = type !== 'true_false' && Number(answer) === i;
    const row = document.createElement('div');
    row.className = 'question-option' + (correct ? ' is-correct' : '');
    add(label, 'span', 'question-letter', row);
    add(input.value, 'span', 'question-option-text', row);
    const flag = type === 'true_false' ? (answer === 'true' ? 'Đúng' : 'Sai') : correct ? 'Đáp án đúng' : '';
    add(flag, 'span', 'bank-answer-key', row);
    area.appendChild(row);
  });
  if (type === 'short_answer') {
    const answerBox = document.createElement('div');
    answerBox.className = 'question-answer-box';
    add('Đáp án chấp nhận', 'strong', '', answerBox);
    const answer = add(value('short_answers'), 'div', 'question-reading', answerBox);
    if (answer) answer.setAttribute('data-latex-answer', '');
    area.appendChild(answerBox);
  }
  if (value('explanation')) {
    const solution = document.createElement('section');
    solution.className = 'question-solution';
    add('Lời giải', 'h3', '', solution);
    add(value('explanation'), 'div', 'question-reading', solution);
    area.appendChild(solution);
  }
  area.hidden = false;
  const render = () => window.renderFormulas?.(area);
  if (window.MathJax?.startup?.promise) window.MathJax.startup.promise.then(render);
  else render();
}
window.scheduleManualPreview = scheduleManualPreview;
window.previewManualQuestion = previewManualQuestion;

document.addEventListener('DOMContentLoaded', () => {
  const coverage = document.querySelector('.bank-coverage');
  if (coverage) {
    const desktop = matchMedia('(min-width: 1200px)');
    coverage.open = desktop.matches;
    desktop.addEventListener('change', event => { coverage.open = event.matches; });
  }
  document.querySelectorAll('[data-delete-bank-name]').forEach(form => form.addEventListener('submit', event => {
    if (!confirm(`Xóa ngân hàng “${form.dataset.deleteBankName}”? Toàn bộ câu hỏi, đáp án và hình liên quan sẽ bị xóa.`)) event.preventDefault();
  }));
  const menus = [...document.querySelectorAll('.bank-more-actions')];
  document.addEventListener('click', event => menus.forEach(menu => { if (!menu.contains(event.target)) menu.open = false; }));
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    menus.forEach(menu => { if (menu.open) { menu.open = false; menu.querySelector('summary')?.focus(); } });
  });
  const dialog = document.getElementById('add-question-modal');
  if (!dialog) return;
  let opener = null;
  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-add-question-open]');
    if (trigger) {
      opener = trigger; dialog.showModal(); document.body.classList.add('bank-dialog-open');
      dialog.querySelector('#manual-prompt')?.focus();
    }
    if (event.target.closest('[data-add-question-close]')) dialog.close();
  });
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
  });
  dialog.addEventListener('close', () => { document.body.classList.remove('bank-dialog-open'); opener?.focus(); });
  const form = dialog.querySelector('[data-manual-question-form]');
  if (!form) return;
  form.querySelector('[data-manual-preview-button]')?.addEventListener('click', () => previewManualQuestion(form));
  const imageInput = form.elements.namedItem('question_image');
  const imageStatus = document.getElementById('manual-image-status');
  imageInput?.addEventListener('change', () => {
    const file = imageInput.files?.[0];
    let message = '';
    if (file && !['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) message = 'Chọn hình PNG, JPEG hoặc WebP.';
    else if (file && file.size > 5 * 1024 * 1024) message = 'Hình vượt quá 5 MB. Hãy chọn hình nhỏ hơn.';
    imageInput.setCustomValidity(message);
    imageInput.setAttribute('aria-invalid', message ? 'true' : 'false');
    imageStatus.textContent = message || (file ? `Đã chọn ${file.name}.` : '');
    imageStatus.classList.toggle('bank-image-error', !!message);
  });
  const submit = form.querySelector('button[type="submit"]');
  const submitStatus = form.querySelector('[data-manual-submit-status]');
  form.addEventListener('submit', event => {
    if (form.dataset.submitting === 'true') { event.preventDefault(); return; }
    form.dataset.submitting = 'true'; form.setAttribute('aria-busy', 'true');
    // Preserve all native POST controls/CSRF and only disable the unnamed button.
    submit.disabled = true; submit.textContent = 'Đang lưu…'; submitStatus.hidden = false;
  });
  window.addEventListener('pageshow', () => {
    form.dataset.submitting = 'false'; form.removeAttribute('aria-busy');
    submit.disabled = false; submit.textContent = 'Lưu câu hỏi'; submitStatus.hidden = true;
  });
  window.addEventListener('pagehide', () => {
    clearTimeout(form._previewTimer);
    if (form._imagePreviewUrl) { URL.revokeObjectURL(form._imagePreviewUrl); form._imagePreviewUrl = null; }
  });
});
