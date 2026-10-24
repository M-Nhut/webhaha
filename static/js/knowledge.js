/* Native forms retain the server's selection and curriculum contracts. */
document.addEventListener('DOMContentLoaded', () => {
  const classification = document.querySelector('[data-classification-workspace]');
  if (classification) {
    const boxes = [...classification.querySelectorAll('.question-checkbox:not(:disabled)')];
    const selectAll = classification.querySelector('#select-all');
    const counter = classification.querySelector('#selection-count');
    const manual = classification.querySelector('[data-manual-classification]');
    const manualButton = classification.querySelector('[data-manual-submit]');
    const type = manual?.querySelector('[name="question_type"]');
    const typeHint = classification.querySelector('#selection-type-hint');
    const suggestion = classification.querySelector('[data-suggestion-classification]');
    const suggestionButton = classification.querySelector('[data-suggestion-submit]');
    const suggestionInputs = classification.querySelector('[data-suggestion-selection]');
    const suggestionHint = classification.querySelector('#suggestion-selection-hint');
    const displayCount = classification.querySelectorAll('.classification-question').length;
    const labels = {single: 'Trắc nghiệm', true_false: 'Đúng/Sai', short_answer: 'Trả lời ngắn'};
    let previousSingleType = '';
    const update = () => {
      const selected = boxes.filter(box => box.checked);
      const types = [...new Set(selected.map(box => box.dataset.questionType))];
      const oneSupportedType = types.length === 1 && Boolean(labels[types[0]]);
      if (counter) counter.textContent = `Đã chọn ${selected.length} / ${displayCount} câu đang hiển thị`;
      if (selectAll) {
        selectAll.checked = boxes.length > 0 && selected.length === boxes.length;
        selectAll.indeterminate = selected.length > 0 && selected.length < boxes.length;
        selectAll.disabled = boxes.length === 0;
      }
      boxes.forEach(box => box.closest('.classification-question')?.classList.toggle('is-selected', box.checked));
      const synchronizeType = oneSupportedType && type && previousSingleType !== types[0];
      previousSingleType = oneSupportedType ? types[0] : '';
      if (synchronizeType) {
        type.value = types[0];
        type.dispatchEvent(new Event('change', {bubbles: true}));
      }
      const matches = oneSupportedType && type?.value === types[0];
      if (manualButton) manualButton.disabled = !selected.length || !matches;
      if (typeHint) typeHint.textContent = !selected.length
        ? 'Chọn các câu cùng hình thức để gán dạng và mức độ. Hình thức trả lời của câu được giữ nguyên.'
        : !oneSupportedType
          ? 'Các câu đã chọn có nhiều hình thức hoặc hình thức cũ chưa hỗ trợ gán hàng loạt. Hãy chọn cùng một hình thức.'
          : !matches
            ? `Các câu đang chọn thuộc hình thức ${labels[types[0]]}. Chọn đúng hình thức này để giữ nguyên cấu trúc trả lời.`
            : `${selected.length} câu ${labels[types[0]]} sẽ dùng dạng và mức độ bạn chọn bên dưới.`;
      if (suggestionInputs) {
        suggestionInputs.replaceChildren(...selected.map(box => {
          const input = document.createElement('input');
          input.type = 'hidden'; input.name = 'question_ids'; input.value = box.value;
          return input;
        }));
      }
      const currentSuggestions = selected.filter(box => box.dataset.suggestionCurrent === 'true');
      if (suggestionButton) suggestionButton.disabled = !selected.length || currentSuggestions.length !== selected.length;
      if (suggestionHint) suggestionHint.textContent = !selected.length
        ? 'Chọn các câu có trạng thái “Gợi ý tự động” còn hiệu lực.'
        : currentSuggestions.length !== selected.length
          ? 'Lựa chọn có câu không phải gợi ý còn hiệu lực. Bỏ chọn câu đó để xác nhận gợi ý; hoặc dùng gán thủ công.'
          : `Xác nhận gợi ý riêng của ${selected.length} câu đã chọn. Server sẽ kiểm tra nội dung và danh mục trước khi lưu.`;
    };
    boxes.forEach(box => box.addEventListener('change', update));
    selectAll?.addEventListener('change', () => { boxes.forEach(box => { box.checked = selectAll.checked; }); update(); });
    type?.addEventListener('change', update);
    manual?.addEventListener('submit', event => { update(); if (manualButton?.disabled) { event.preventDefault(); type?.focus(); } });
    suggestion?.addEventListener('submit', event => { update(); if (suggestionButton?.disabled) event.preventDefault(); });
    // Alpine initializes the picker before this microtask runs.
    queueMicrotask(update);
    window.addEventListener('pageshow', update);
  }

  document.querySelectorAll('[data-knowledge-image]').forEach(button => {
    button.addEventListener('click', () => {
      window.FormulaRenderer?.openImageLightbox(button.dataset.knowledgeImage, 'Hình câu hỏi phóng to');
    });
  });
  document.querySelectorAll('.knowledge-question-disclosure').forEach(disclosure => {
    disclosure.addEventListener('toggle', () => { if (disclosure.open) window.renderFormulas?.(disclosure); });
  });
  document.querySelector('[data-knowledge-error]')?.focus();

  const upload = document.querySelector('[data-labels-upload]');
  if (upload) {
    const input = upload.querySelector('[name="labels_file"]');
    const feedback = upload.querySelector('#labels-file-feedback');
    input?.addEventListener('change', () => {
      const file = input.files?.[0];
      const error = !file ? '' : !file.name.toLowerCase().endsWith('.json') ? 'Hãy chọn file có đuôi .json.' : file.size > 5 * 1024 * 1024 ? 'File vượt quá 5 MB. Hãy chọn file nhỏ hơn.' : '';
      input.setCustomValidity(error);
      input.setAttribute('aria-invalid', error ? 'true' : 'false');
      if (feedback) {
        feedback.textContent = error || (file ? `Đã chọn ${file.name} · ${(file.size / 1024).toLocaleString('vi-VN', {maximumFractionDigits: 1})} KB` : '');
        feedback.classList.toggle('knowledge-file-error', Boolean(error));
      }
    });
  }

  const management = document.querySelector('#catalog-management');
  const editor = management?.querySelector('[data-catalog-editor]');
  if (management && editor) {
    const title = editor.querySelector('[data-catalog-editor-title]');
    const feedback = editor.querySelector('[data-catalog-edit-feedback]');
    const openEditor = () => {
      management.open = true;
      management.scrollIntoView({block: 'start', behavior: 'instant'});
    };
    document.querySelector('[data-catalog-open]')?.addEventListener('click', () => { management.open = true; });
    document.querySelectorAll('[data-catalog-edit]').forEach(button => {
      button.addEventListener('click', () => {
        const fields = {chapter_name: 'chapterName', category_code: 'categoryCode', category_name: 'categoryName'};
        Object.entries(fields).forEach(([name, key]) => { editor.elements.namedItem(name).value = button.dataset[key] || ''; });
        // The current catalog accepts one canonical scope and lesson name.
        // Older readable rows may retain a historical lesson name.
        ['grade', 'chapter_code', 'lesson_code', 'lesson_name'].forEach(name => {
          const field = editor.elements.namedItem(name);
          field.value = field.defaultValue;
        });
        const lessonNormalized = (button.dataset.lessonName || '') !== editor.elements.namedItem('lesson_name').defaultValue;
        editor.elements.namedItem('is_advanced').checked = button.dataset.advanced === 'true';
        if (title) title.textContent = `Cập nhật dạng ${button.dataset.canonical}`;
        if (feedback) feedback.textContent = `${lessonNormalized ? 'Tên bài cũ được chuẩn hóa theo bài kết hợp i đang dùng. ' : ''}Lưu sẽ cập nhật dạng theo mã hiện tại và kích hoạt lại nếu dạng đang ngừng dùng.`;
        openEditor();
        editor.elements.namedItem('category_name').focus({preventScroll: true});
      });
    });
    editor.querySelector('[data-catalog-reset]')?.addEventListener('click', () => {
      editor.reset();
      if (title) title.textContent = 'Thêm hoặc cập nhật một dạng';
      if (feedback) feedback.textContent = 'Lưu sẽ thêm mới hoặc cập nhật theo mã dạng.';
      editor.elements.namedItem('category_code').focus();
    });
  }
});
