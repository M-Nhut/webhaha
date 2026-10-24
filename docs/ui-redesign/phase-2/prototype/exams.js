/* Isolated Phase 2 review prototype. All changes live in browser memory only. */
const INITIAL_ROWS = [
  { id: 'ex-1', title: 'Xác suất của biến cố', course: 'Lớp 9A1', questions: 18, minutes: 45, status: 'draft', submissions: 0 },
  { id: 'ex-2', title: 'Ôn tập không gian mẫu', course: 'Lớp 9A2', questions: 16, minutes: 40, status: 'published', submissions: 24 },
  { id: 'ex-3', title: 'Kiểm tra giữa học kỳ', course: 'Lớp 9A1', questions: 24, minutes: 45, status: 'published', submissions: 31 },
  { id: 'ex-4', title: 'Phép thử và biến cố', course: 'Lớp 9A3', questions: 12, minutes: 30, status: 'draft', submissions: 0 },
  { id: 'ex-5', title: 'Tổng hợp kiến thức xác suất', course: 'Lớp 9A2', questions: 20, minutes: 45, status: 'published', submissions: 28 },
];
const CONTEXTS = {
  standalone: { label: 'Kiểm tra lớp', back: 'Danh sách đề kiểm tra', note: 'Kết quả bổ sung bằng chứng cho giáo viên; không cập nhật hồ sơ sinh bài tự luyện.' },
  diagnostic: { label: 'Đánh giá đầu vào', back: 'Danh sách đề kiểm tra', note: 'Bài đầu vào dùng chung cho lớp. Trong web thật, chỉ học sinh được giao bài mới có thể làm.' },
  practice: { label: 'Tự luyện cá nhân', back: 'Danh sách đề kiểm tra', note: 'Bài luyện cá nhân gắn với một học sinh. Đề thật được lựa chọn từ hồ sơ năng lực và nguồn của lớp.' },
};
const QUESTIONS = [
  { id: 'single', label: 'Một lựa chọn', prompt: 'Gieo một con xúc xắc cân đối một lần. Xác suất để số chấm xuất hiện là số chẵn bằng bao nhiêu?', options: ['1/2', '1/3', '1/4', '2/3'], correct: '0', explanation: 'Không gian mẫu có 6 kết quả đồng khả năng. Có 3 kết quả chẵn là 2, 4 và 6, nên xác suất bằng 3/6 = 1/2.' },
  { id: 'truth', label: 'Đúng / Sai', prompt: 'Gieo một con xúc xắc cân đối một lần. Xác định tính đúng, sai của từng khẳng định sau.', statements: [
    { id: 'a', text: 'Biến cố xuất hiện số chẵn gồm các kết quả 2, 4 và 6.', correct: true },
    { id: 'b', text: 'Xác suất xuất hiện số lẻ bằng 1/3.', correct: false },
    { id: 'c', text: 'Xác suất xuất hiện số chấm lớn hơn 4 bằng 1/3.', correct: true },
    { id: 'd', text: 'Sáu kết quả của phép thử có khả năng xảy ra như nhau.', correct: true },
  ], explanation: 'Các kết quả 1 đến 6 đồng khả năng. Có 3 số lẻ nên xác suất số lẻ là 1/2; có 2 số lớn hơn 4 nên xác suất tương ứng là 1/3.' },
  { id: 'short', label: 'Trả lời ngắn', prompt: 'Một túi có 3 thẻ đỏ và 2 thẻ xanh cùng kích thước. Rút ngẫu nhiên một thẻ. Xác suất rút được thẻ đỏ bằng bao nhiêu?', correct: '3/5', explanation: 'Có 5 thẻ và 3 thẻ đỏ. Xác suất cần tìm là 3/5 = 0,6.' },
];
const KIND_LABELS = { single: 'Một lựa chọn', truth: 'Đúng / Sai', short: 'Trả lời ngắn' };

function model(ctx) {
  const s = ctx.state;
  if (!s.examsRows) s.examsRows = INITIAL_ROWS.map(row => ({ ...row }));
  if (!s.examAnswers) s.examAnswers = { single: '', truth: {}, short: '' };
  if (!s.examEditor) s.examEditor = makeEditor(s.examsRows[0]);
  if (!s.assessmentTab) s.assessmentTab = 'all';
  return s;
}
function makeEditor(row) {
  return { id: row.id, title: row.title, course: row.course, minutes: row.minutes, status: row.status, dirty: false,
    budgets: { single: 3, truth: 4, short: 3 }, weights: { single: 1, truth: 1, short: 1 }, prompts: Object.fromEntries(QUESTIONS.map(q => [q.id, q.prompt])) };
}
function context(ctx) { return CONTEXTS[ctx.state.examContext] || CONTEXTS.standalone; }
function escape(ctx, value) { return ctx.escapeHTML(String(value ?? '')); }
function number(value, digits = 2) { return new Intl.NumberFormat('vi-VN', { maximumFractionDigits: digits }).format(value); }
function rowButton(ctx, label, action, row, iconName = '') {
  return `<button type="button" class="btn btn-ghost" data-action="${action}" data-exam-id="${row.id}">${iconName ? ctx.icon(iconName, 16) : ''}<span>${escape(ctx, label)}</span></button>`;
}
function pageHeading(ctx, eyebrow, title, description, actions = '') {
  return `<div class="page-heading"><div class="heading-copy"><p class="text-muted text-small">${escape(ctx, eyebrow)}</p><h1>${escape(ctx, title)}</h1><p>${escape(ctx, description)}</p></div><div class="heading-actions">${actions}</div></div>`;
}
function demoNotice(ctx, text) { return `<div class="notice-info exam-demo-note">${ctx.icon('info', 18)}<span>${escape(ctx, text)}</span></div>`; }
function visibleRows(s) {
  const query = String(s.assessmentSearch || '').toLocaleLowerCase('vi');
  return s.examsRows.filter(row => (s.assessmentTab === 'all' || row.status === s.assessmentTab)
    && (!s.assessmentCourse || row.course === s.assessmentCourse)
    && `${row.title} ${row.course}`.toLocaleLowerCase('vi').includes(query));
}
function listBody(ctx, rows) {
  if (!rows.length) return `<tr><td colspan="6"><div class="empty-state"><h3>Không có đề phù hợp</h3><p>Thử tìm từ khóa khác hoặc bỏ bộ lọc lớp học.</p>${ctx.button('Xóa bộ lọc', 'reset-exam-filters', 'secondary', 'refresh-cw')}</div></td></tr>`;
  return rows.map(row => `<tr><td><strong>${escape(ctx, row.title)}</strong><span class="text-muted text-small exam-cell-note">Toán · Xác suất</span></td><td>${escape(ctx, row.course)}</td><td>${row.questions} câu<span class="text-muted text-small exam-cell-note">${row.minutes} phút · thang 10</span></td><td>${ctx.badge(row.status === 'draft' ? 'Bản nháp' : 'Đã giao', row.status === 'draft' ? 'neutral' : 'success')}</td><td>${row.status === 'published' ? `<strong>${row.submissions}</strong><span class="text-muted text-small exam-cell-note">bài nộp minh họa</span>` : '<span class="text-muted">Chưa phát hành</span>'}</td><td><div class="exam-row-actions">${row.status === 'draft' ? rowButton(ctx, 'Biên soạn', 'edit-paper', row, 'pencil') : rowButton(ctx, 'Xem kết quả', 'view-paper-results', row, 'chart-no-axes-combined')}${rowButton(ctx, 'Mẫu làm bài', 'preview-paper', row, 'eye')}</div></td></tr>`).join('');
}

export function renderAssessments(ctx) {
  const s = model(ctx);
  const draftCount = s.examsRows.filter(row => row.status === 'draft').length;
  const rows = visibleRows(s);
  return `${pageHeading(ctx, 'KIỂM TRA VÀ ĐÁNH GIÁ', 'Đề kiểm tra', 'Biên soạn, giao đề và đối chiếu kết quả học sinh trong một nơi.', ctx.button('Tạo từ ngân hàng', 'create-from-bank', 'primary', 'plus'))}
    <div class="metric-strip"><div class="metric"><span class="metric-label">Tất cả đề</span><strong class="metric-value">${s.examsRows.length}</strong></div><div class="metric"><span class="metric-label">Đang biên soạn</span><strong class="metric-value">${draftCount}</strong></div><div class="metric"><span class="metric-label">Đã giao cho lớp</span><strong class="metric-value">${s.examsRows.length - draftCount}</strong></div></div>
    <section class="panel" aria-label="Danh sách đề kiểm tra">
      <div class="panel-heading"><div class="tabs" role="tablist" aria-label="Trạng thái đề">${[['all', 'Tất cả'], ['draft', 'Bản nháp'], ['published', 'Đã giao']].map(([key, text]) => `<button type="button" class="tab" role="tab" id="assessment-tab-${key}" data-exam-tab="${key}" aria-controls="assessment-results" aria-selected="${s.assessmentTab === key}" tabindex="${s.assessmentTab === key ? 0 : -1}">${text}<span class="text-muted">${key === 'all' ? s.examsRows.length : s.examsRows.filter(row => row.status === key).length}</span></button>`).join('')}</div>${ctx.badge('Dữ liệu minh họa', 'info')}</div>
      <div id="assessment-results" role="tabpanel" aria-labelledby="assessment-tab-${s.assessmentTab}">
      <div class="toolbar"><label class="search-field">${ctx.icon('search', 18)}<input type="search" id="assessment-search" aria-label="Tìm đề kiểm tra" placeholder="Tìm tên đề hoặc lớp học" value="${escape(ctx, s.assessmentSearch || '')}"></label><label class="exam-course-filter"><span class="text-small text-muted">Lớp học</span><select id="assessment-course"><option value="">Tất cả lớp</option>${['Lớp 9A1', 'Lớp 9A2', 'Lớp 9A3'].map(course => `<option${s.assessmentCourse === course ? ' selected' : ''}>${course}</option>`).join('')}</select></label></div>
      <div class="table-wrap"><table class="data-table"><thead><tr><th scope="col">Tên đề</th><th scope="col">Lớp học</th><th scope="col">Cấu trúc</th><th scope="col">Trạng thái</th><th scope="col">Kết quả</th><th scope="col">Thao tác</th></tr></thead><tbody id="assessment-rows">${listBody(ctx, rows)}</tbody></table></div>
      <div class="pagination"><span class="text-muted text-small" id="assessment-count">${rows.length} đề minh họa · ${s.examsRows.length} đề tổng cộng</span><span class="text-small">Trang 1 / 1</span></div></div>
    </section>
    ${demoNotice(ctx, 'Bản mẫu có 5 đề minh họa. Các liên kết làm bài và kết quả mở một đề mẫu 3 câu để duyệt thiết kế.')}`;
}

export function bindAssessments(root, ctx) {
  const s = model(ctx);
  const activateTab = key => {
    s.assessmentTab = key;
    ctx.refresh();
    queueMicrotask(() => document.querySelector(`#view #assessment-tab-${key}`)?.focus());
  };
  const update = () => {
    const rows = visibleRows(s);
    root.querySelector('#assessment-rows').innerHTML = listBody(ctx, rows);
    root.querySelector('#assessment-count').textContent = `${rows.length} đề minh họa · ${s.examsRows.length} đề tổng cộng`;
  };
  root.querySelector('#assessment-search')?.addEventListener('input', event => { s.assessmentSearch = event.target.value; update(); });
  root.querySelector('#assessment-course')?.addEventListener('change', event => { s.assessmentCourse = event.target.value; update(); });
  root.addEventListener('keydown', event => {
    const tab = event.target.closest('[data-exam-tab]');
    if (!tab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const order = ['all', 'draft', 'published'];
    const current = order.indexOf(tab.dataset.examTab);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? order.length - 1
      : (current + (event.key === 'ArrowRight' ? 1 : -1) + order.length) % order.length;
    activateTab(order[next]);
  });
  root.addEventListener('click', event => {
    const tab = event.target.closest('[data-exam-tab]');
    if (tab) { activateTab(tab.dataset.examTab); return; }
    const button = event.target.closest('[data-action]');
    if (!button) return;
    const row = s.examsRows.find(item => item.id === button.dataset.examId);
    if (button.dataset.action === 'reset-exam-filters') { s.assessmentSearch = ''; s.assessmentCourse = ''; ctx.refresh(); }
    if (button.dataset.action === 'create-from-bank') { ctx.go('bank'); ctx.toast('Chọn câu trong ngân hàng minh họa để xem luồng tạo đề.'); }
    if (button.dataset.action === 'edit-paper' && row) { s.examEditor = makeEditor(row); ctx.go('editor'); }
    if (button.dataset.action === 'preview-paper' && row) { s.examPreviewTitle = row.title; ctx.go('take'); }
    if (button.dataset.action === 'view-paper-results' && row) { s.examSubmission = null; s.examPreviewTitle = row.title; ctx.go('result'); }
  });
}

function budgetTotal(editor) { return Object.values(editor.budgets).reduce((sum, value) => sum + Number(value || 0), 0); }
function editorIsValid(editor) {
  return editor.title.trim().length > 0 && editor.title.length <= 200 && Number.isInteger(Number(editor.minutes))
    && Number(editor.minutes) >= 1 && Number(editor.minutes) <= 240
    && Math.abs(budgetTotal(editor) - 10) < 0.000001
    && Object.values(editor.budgets).every(value => Number.isFinite(Number(value)) && Number(value) >= 0)
    && Object.values(editor.weights).every(value => Number.isFinite(Number(value)) && Number(value) > 0)
    && Object.values(editor.prompts).every(prompt => prompt.trim().length > 0);
}
function editorQuestion(ctx, question, index, editor) {
  return `<article class="question-card" id="editor-question-${question.id}"><div class="question-meta"><h3>Câu ${index + 1}</h3>${ctx.badge(question.label, 'neutral')}<span class="text-muted text-small" data-editor-points="${question.id}">${number(editor.budgets[question.id])} điểm</span></div>
    <label class="field"><span>Nội dung câu hỏi</span><textarea name="prompt-${question.id}" data-edit-prompt="${question.id}" rows="3" required>${escape(ctx, editor.prompts[question.id])}</textarea></label>
    <details class="exam-preview" open><summary>Xem trước nội dung</summary><p class="question-body" data-prompt-preview="${question.id}">${escape(ctx, editor.prompts[question.id])}</p>${question.id === 'single' ? `<div class="answer-grid">${question.options.map((answer, i) => `<div class="answer-option${String(i) === question.correct ? ' is-correct' : ''}"><strong>${'ABCD'[i]}.</strong> ${escape(ctx, answer)}${String(i) === question.correct ? ctx.badge('Đáp án đúng', 'success') : ''}</div>`).join('')}</div>` : question.id === 'truth' ? `<ul class="exam-key-list">${question.statements.map(item => `<li><span><strong>${item.id}.</strong> ${escape(ctx, item.text)}</span>${ctx.badge(item.correct ? 'Đúng' : 'Sai', item.correct ? 'success' : 'neutral')}</li>`).join('')}</ul>` : `<div class="notice-success">Đáp án: 3/5 hoặc 0,6 · So sánh giá trị số</div>`}</details>
    <div class="question-footer"><label class="field exam-weight-field"><span>Trọng số trong phần</span><input type="number" data-edit-weight="${question.id}" value="${editor.weights[question.id]}" min="0.0001" max="100" step="0.0001" required></label><span class="text-muted text-small">Nguồn và thứ tự câu được giữ nguyên.</span></div></article>`;
}

export function renderEditor(ctx) {
  const s = model(ctx), editor = s.examEditor;
  const locked = editor.status === 'published';
  return `${pageHeading(ctx, 'BIÊN SOẠN ĐỀ', 'Kiểm tra đề trước khi giao', 'Đối chiếu nội dung, đáp án và phân bổ điểm trong cùng một không gian.', ctx.button('Danh sách đề', 'editor-back', 'secondary', 'arrow-left'))}
    ${locked ? `<div class="notice-success">${ctx.icon('lock-keyhole', 18)}<span>Đã phát hành trong bản mẫu. Nội dung được khóa; mọi thay đổi chỉ tồn tại trong phiên duyệt này.</span></div>` : ''}
    <form id="exam-editor-form"><fieldset class="exam-editor-fieldset"${locked ? ' disabled' : ''}>
    <div class="editor-layout"><div class="content-panel">
      <section class="panel"><div class="panel-heading"><div><h2>Thông tin đề</h2><p class="text-muted text-small">Đề minh họa · 3 câu · Thang điểm 10</p></div>${ctx.badge(locked ? 'Đã giao' : 'Bản nháp', locked ? 'success' : 'neutral')}</div><div class="panel-body exam-form-grid">
        <label class="field exam-title-field"><span>Tên đề</span><input name="title" maxlength="200" required value="${escape(ctx, editor.title)}"></label>
        <label class="field"><span>Lớp nhận đề</span><select name="course">${['Lớp 9A1', 'Lớp 9A2', 'Lớp 9A3'].map(course => `<option${editor.course === course ? ' selected' : ''}>${course}</option>`).join('')}</select></label>
        <label class="field"><span>Thời gian (phút)</span><input type="number" name="minutes" min="1" max="240" step="1" required value="${editor.minutes}"></label>
      </div></section>
      <div class="section-heading"><div><h2>Nội dung và đáp án</h2><p class="text-muted">Sửa câu hỏi để kiểm tra cách hiển thị. Đáp án mẫu được giữ cố định.</p></div><span class="text-muted text-small">3 câu minh họa</span></div>
      <div class="question-list">${QUESTIONS.map((q, i) => editorQuestion(ctx, q, i, editor)).join('')}</div>
    </div><aside class="exam-summary"><section class="panel"><div class="panel-heading"><h2>Tổng quan đề</h2>${ctx.icon('clipboard-list', 19)}</div><div class="panel-body"><strong class="exam-summary-title" id="editor-summary-title">${escape(ctx, editor.title)}</strong><p class="text-muted text-small" id="editor-summary-meta">${escape(ctx, editor.course)} · ${editor.minutes} phút</p>
      <div class="exam-budget-list">${Object.entries(KIND_LABELS).map(([key, label]) => `<label class="field"><span>${label}<small class="text-muted">1 câu</small></span><input type="number" aria-label="Điểm phần ${label}" data-edit-budget="${key}" min="0" max="10" step="0.01" required value="${editor.budgets[key]}"></label>`).join('')}</div>
      <div class="exam-total"><strong>Tổng điểm</strong><strong id="editor-total">${number(budgetTotal(editor))} / 10</strong></div><p class="text-small text-muted">Mỗi phần mẫu có một câu nên trọng số không làm thay đổi điểm phần. Đề thật chia điểm theo trọng số các câu.</p>
      <nav class="exam-editor-nav" aria-label="Chuyển đến câu biên soạn">${QUESTIONS.map((q, i) => `<a href="#editor-question-${q.id}">Câu ${i + 1}<span class="text-muted">${q.label}</span></a>`).join('')}</nav>
    </div></section></aside></div>
    </fieldset><div class="sticky-actions"><p id="editor-save-status" role="status" aria-live="polite">${locked ? 'Bản mẫu đã phát hành.' : editor.dirty ? 'Có thay đổi chưa lưu trong bản mẫu.' : 'Chưa có thay đổi mới.'}</p><div class="heading-actions">${locked ? ctx.button('Xem mẫu làm bài', 'editor-preview', 'primary', 'eye') : `${ctx.button('Lưu bản nháp', 'save-draft', 'secondary', 'save')}${ctx.button('Giao đề cho lớp', 'publish-paper', 'primary', 'send')}`}</div></div></form>
    ${demoNotice(ctx, 'Thao tác lưu và giao chỉ mô phỏng trong bộ nhớ trình duyệt. Bản mẫu không tải file, lưu dữ liệu thật hoặc gửi đề cho học sinh.')}`;
}

export function bindEditor(root, ctx) {
  const s = model(ctx), editor = s.examEditor, form = root.querySelector('#exam-editor-form');
  const status = root.querySelector('#editor-save-status');
  form?.addEventListener('submit', event => event.preventDefault());
  const update = () => {
    editor.dirty = true;
    status.textContent = 'Có thay đổi chưa lưu trong bản mẫu.';
    root.querySelector('#editor-summary-title').textContent = editor.title || 'Chưa đặt tên đề';
    root.querySelector('#editor-summary-meta').textContent = `${editor.course} · ${editor.minutes || '—'} phút`;
    root.querySelector('#editor-total').textContent = `${number(budgetTotal(editor))} / 10`;
    root.querySelector('#editor-total').classList.toggle('exam-invalid', Math.abs(budgetTotal(editor) - 10) > 0.000001);
    root.querySelectorAll('[data-editor-points]').forEach(node => { node.textContent = `${number(editor.budgets[node.dataset.editorPoints])} điểm`; });
  };
  form?.addEventListener('input', event => {
    const input = event.target;
    if (input.dataset.editPrompt) { editor.prompts[input.dataset.editPrompt] = input.value; root.querySelector(`[data-prompt-preview="${input.dataset.editPrompt}"]`).textContent = input.value; }
    else if (input.dataset.editWeight) editor.weights[input.dataset.editWeight] = input.value;
    else if (input.dataset.editBudget) editor.budgets[input.dataset.editBudget] = input.value;
    else if (input.name === 'title') editor.title = input.value;
    else if (input.name === 'course') editor.course = input.value;
    else if (input.name === 'minutes') editor.minutes = input.value;
    update();
  });
  const validate = () => {
    if (!form.reportValidity()) return false;
    if (!editorIsValid(editor)) { status.textContent = 'Kiểm tra nội dung, trọng số và tổng điểm. Tổng các phần phải bằng 10.'; ctx.toast('Chưa hợp lệ: tổng các phần phải bằng 10 điểm.'); return false; }
    return true;
  };
  const saveRow = published => {
    const row = s.examsRows.find(item => item.id === editor.id);
    if (row) Object.assign(row, { title: editor.title, course: editor.course, minutes: Number(editor.minutes), questions: 3, status: published ? 'published' : 'draft', submissions: 0 });
    editor.status = published ? 'published' : 'draft'; editor.dirty = false;
    s.examPreviewTitle = editor.title;
  };
  root.addEventListener('click', event => {
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (action === 'editor-back') {
      if (!editor.dirty) { ctx.go('assessments'); return; }
      ctx.openDialog({ title: 'Rời trang biên soạn?', description: 'Nội dung đang nhập chỉ nằm trong bộ nhớ của bản mẫu. Bạn có thể quay lại để tiếp tục trong phiên này.', confirmLabel: 'Về danh sách', onConfirm: () => ctx.go('assessments') });
    }
    if (action === 'editor-preview') ctx.go('take');
    if (action === 'save-draft' && validate()) { saveRow(false); status.textContent = 'Đã lưu bản nháp trong bộ nhớ của bản mẫu.'; ctx.toast('Đã lưu bản nháp minh họa. Không có dữ liệu được ghi lên web thật.'); }
    if (action === 'publish-paper' && validate()) ctx.openDialog({ title: 'Xác nhận giao đề minh họa', description: 'Đối chiếu tên đề, lớp nhận và phân bổ điểm trước khi phát hành.', body: `<div class="exam-dialog-summary"><strong>${escape(ctx, editor.title)}</strong><p>${escape(ctx, editor.course)} · ${editor.minutes} phút · 3 câu · 10 điểm</p><p class="text-muted text-small">Trong web thật, nội dung được khóa sau khi giao. Thao tác ở đây chỉ đổi trạng thái bản mẫu.</p></div>`, confirmLabel: 'Xác nhận trong bản mẫu', onConfirm: () => { saveRow(true); ctx.toast('Đã chuyển đề mẫu sang trạng thái Đã giao.'); ctx.refresh(); } });
  });
}

function questionProgress(answers) {
  const truthCount = QUESTIONS[1].statements.filter(item => typeof answers.truth[item.id] === 'boolean').length;
  return { single: answers.single === '' ? 'empty' : 'complete', truth: truthCount === 4 ? 'complete' : truthCount ? 'partial' : 'empty', short: answers.short.trim() ? 'complete' : 'empty', truthCount };
}
function pointsFor(kind, examContext) { return examContext === 'standalone' ? { single: 3, truth: 4, short: 3 }[kind] : { single: 0.25, truth: 1, short: 0.5 }[kind]; }
function mapMarkup(ctx, answers) {
  const progress = questionProgress(answers);
  return QUESTIONS.map((q, i) => `<button type="button" class="exam-map-button is-${progress[q.id]}" data-question-target="${q.id}" aria-label="Câu ${i + 1}, ${progress[q.id] === 'complete' ? 'đã trả lời đủ' : progress[q.id] === 'partial' ? 'đã trả lời một phần' : 'chưa trả lời'}">${i + 1}</button>`).join('');
}
function takeQuestion(ctx, question, index, answers) {
  const kind = ctx.state.examContext || 'standalone';
  return `<article class="panel exam-question" id="take-question-${question.id}" aria-labelledby="take-question-heading-${question.id}"><div class="question-meta"><h2 id="take-question-heading-${question.id}" tabindex="-1">Câu ${index + 1}</h2>${ctx.badge(question.label, 'neutral')}<span class="text-muted">${number(pointsFor(question.id, kind))} điểm</span></div><p class="question-body">${escape(ctx, question.prompt)}</p>
    ${question.id === 'single' ? `<fieldset class="exam-choice-fieldset"><legend class="visually-hidden">Chọn một đáp án cho câu 1</legend><div class="answer-grid">${question.options.map((answer, i) => `<label class="choice${answers.single === String(i) ? ' is-selected' : ''}"><input type="radio" name="demo-single" value="${i}"${answers.single === String(i) ? ' checked' : ''}><span class="exam-answer-marker">${'ABCD'[i]}</span><span>${escape(ctx, answer)}</span></label>`).join('')}</div></fieldset>` : question.id === 'truth' ? `<div class="table-wrap"><table class="truth-table"><caption class="visually-hidden">Chọn Đúng hoặc Sai cho mỗi khẳng định</caption><thead><tr><th scope="col">Khẳng định</th><th scope="col">Đúng</th><th scope="col">Sai</th></tr></thead><tbody>${question.statements.map(item => `<tr><th scope="row"><strong>${item.id}.</strong> ${escape(ctx, item.text)}</th><td><label class="exam-truth-choice"><input type="radio" name="demo-truth-${item.id}" value="true"${answers.truth[item.id] === true ? ' checked' : ''}><span class="visually-hidden">Ý ${item.id}: Đúng</span></label></td><td><label class="exam-truth-choice"><input type="radio" name="demo-truth-${item.id}" value="false"${answers.truth[item.id] === false ? ' checked' : ''}><span class="visually-hidden">Ý ${item.id}: Sai</span></label></td></tr>`).join('')}</tbody></table></div><p class="text-muted text-small">${kind === 'standalone' ? 'Điểm được tính theo tỷ lệ số ý đúng. Ý bỏ trống không được tính đúng.' : 'Đúng 1 / 2 / 3 / 4 ý: 0,1 / 0,25 / 0,5 / 1 điểm.'}</p>` : `<label class="field"><span>Đáp án số hoặc phân số</span><input type="text" name="demo-short" value="${escape(ctx, answers.short)}" placeholder="Ví dụ: 1/2 hoặc 0,5" aria-describedby="short-answer-hint" inputmode="text" autocomplete="off"><small id="short-answer-hint" class="text-muted">Nhập số hoặc phân số, không kèm đơn vị. Sai số tuyệt đối: 0,0001.</small></label>`}</article>`;
}

export function renderTake(ctx) {
  const s = model(ctx), answers = s.examAnswers, progress = questionProgress(answers);
  const completeCount = QUESTIONS.filter(q => progress[q.id] === 'complete').length;
  return `<div class="exam-status"><div><span class="text-muted text-small">${escape(ctx, context(ctx).label)}</span><h1>Đề minh họa · 3 câu</h1><p class="text-muted text-small">${escape(ctx, s.examPreviewTitle || 'Xác suất của biến cố')}</p></div><div class="exam-status-right"><div class="exam-timer-demo"><span class="text-small text-muted">Đồng hồ minh họa</span><strong>40:00</strong><small class="text-muted">Không chạy đếm ngược</small></div>${ctx.button('Rời bài mẫu', 'take-back', 'ghost', 'x')}</div></div>
    <div class="exam-layout"><form id="demo-take-form" class="content-panel"><div class="question-list">${QUESTIONS.map((q, i) => takeQuestion(ctx, q, i, answers)).join('')}</div><div class="exam-take-footer"><span class="text-muted text-small">Câu trả lời chỉ được giữ trong phiên bản mẫu này.</span>${ctx.button('Nộp bài minh họa', 'submit-demo-exam', 'primary', 'send')}</div></form>
    <aside class="exam-summary"><section class="panel"><div class="panel-heading"><h2>Tiến độ làm bài</h2>${ctx.icon('list-checks', 19)}</div><div class="panel-body"><strong class="exam-progress-number" id="take-complete-count">${completeCount} / 3</strong><p class="text-muted text-small" id="take-partial-count">${progress.truth === 'partial' ? '1 câu đang trả lời một phần' : 'câu đã trả lời đủ'}</p><nav class="exam-map" aria-label="Điều hướng câu hỏi">${mapMarkup(ctx, answers)}</nav><div class="exam-map-legend"><span><i class="exam-dot is-complete" aria-hidden="true"></i>Đã trả lời đủ</span><span><i class="exam-dot is-partial" aria-hidden="true"></i>Trả lời một phần</span><span><i class="exam-dot is-empty" aria-hidden="true"></i>Chưa trả lời</span></div><details class="exam-context-note"><summary>Cách ghi nhận kết quả</summary><p>${escape(ctx, context(ctx).note)}</p></details>${ctx.button('Nộp bài minh họa', 'submit-demo-exam', 'primary', 'send')}</div></section></aside></div>`;
}

function numericAnswer(text) {
  const normalized = String(text).trim().replace(',', '.');
  if (!/^[+-]?\d+(?:\.\d+)?(?:\/[+-]?\d+(?:\.\d+)?)?$/.test(normalized) || normalized.length > 80) return NaN;
  const [numerator, denominator] = normalized.split('/').map(Number);
  return denominator === undefined ? numerator : denominator === 0 ? NaN : numerator / denominator;
}
function grade(answers, examContext) {
  const truthCorrect = QUESTIONS[1].statements.filter(item => answers.truth[item.id] === item.correct).length;
  const correct = { single: answers.single === QUESTIONS[0].correct, truth: truthCorrect === 4, short: Math.abs(numericAnswer(answers.short) - 0.6) <= 0.0001 };
  const values = { single: correct.single ? pointsFor('single', examContext) : 0,
    truth: examContext === 'standalone' ? truthCorrect : [0, 0.1, 0.25, 0.5, 1][truthCorrect],
    short: correct.short ? pointsFor('short', examContext) : 0 };
  const total = Object.values(values).reduce((sum, value) => sum + value, 0);
  const max = QUESTIONS.reduce((sum, q) => sum + pointsFor(q.id, examContext), 0);
  return { answers: { ...answers, truth: { ...answers.truth } }, examContext, values, correct, total, max, score: total * 10 / max, truthCorrect };
}

export function setExamContext(ctx, next) {
  if (!CONTEXTS[next]) return;
  const s = model(ctx);
  s.examContext = next;
  if (s.examSubmission) s.examSubmission = grade(s.examAnswers, next);
}

export function bindTake(root, ctx) {
  const s = model(ctx), answers = s.examAnswers;
  const update = () => {
    const progress = questionProgress(answers);
    root.querySelector('#take-complete-count').textContent = `${QUESTIONS.filter(q => progress[q.id] === 'complete').length} / 3`;
    root.querySelector('#take-partial-count').textContent = progress.truth === 'partial' ? `Câu 2: đã trả lời ${progress.truthCount}/4 ý` : 'câu đã trả lời đủ';
    root.querySelector('.exam-map').innerHTML = mapMarkup(ctx, answers);
    root.querySelectorAll('.choice').forEach(choice => choice.classList.toggle('is-selected', choice.querySelector('input').checked));
  };
  root.querySelector('#demo-take-form')?.addEventListener('submit', event => event.preventDefault());
  root.querySelector('#demo-take-form')?.addEventListener('input', event => {
    const input = event.target;
    if (input.name === 'demo-single') answers.single = input.value;
    if (input.name.startsWith('demo-truth-')) answers.truth[input.name.replace('demo-truth-', '')] = input.value === 'true';
    if (input.name === 'demo-short') answers.short = input.value;
    s.examInputChanged = true;
    update();
  });
  root.addEventListener('click', event => {
    const target = event.target.closest('[data-question-target]');
    if (target) { const heading = root.querySelector(`#take-question-heading-${target.dataset.questionTarget}`); heading?.scrollIntoView({ block: 'start', behavior: 'auto' }); heading?.focus({ preventScroll: true }); }
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (action === 'take-back') ctx.openDialog({ title: 'Rời bài minh họa?', description: 'Câu trả lời hiện chỉ nằm trong bộ nhớ của bản mẫu. Tải lại hoặc đóng trang sẽ xóa phần đang nhập.', confirmLabel: 'Về danh sách đề', onConfirm: () => ctx.go('assessments') });
    if (action === 'submit-demo-exam') {
      const progress = questionProgress(answers);
      const complete = QUESTIONS.filter(q => progress[q.id] === 'complete').length;
      const partial = QUESTIONS.filter(q => progress[q.id] === 'partial').length;
      ctx.openDialog({ title: 'Nộp bài minh họa?', description: 'Kiểm tra tiến độ trước khi xem kết quả mô phỏng.', body: `<div class="exam-dialog-summary"><strong>${complete}/3 câu đã trả lời đủ</strong><p>${partial ? `${partial} câu đang trả lời một phần. ` : ''}${3 - complete - partial} câu chưa trả lời.</p><p class="text-muted text-small">Điểm được tính tại trình duyệt bằng đáp án mẫu. Không tạo lượt nộp hoặc hồ sơ năng lực trên web thật.</p></div>`, confirmLabel: 'Nộp và xem kết quả', onConfirm: () => { s.examSubmission = grade(answers, s.examContext || 'standalone'); ctx.go('result'); ctx.toast('Đã tính kết quả minh họa từ câu trả lời trong phiên này.'); } });
    }
  });
}

function resultQuestion(ctx, question, index, result) {
  const state = result.correct[question.id] ? 'Đúng' : result.values[question.id] > 0 ? 'Đúng một phần' : questionProgress(result.answers)[question.id] === 'empty' ? 'Bỏ trống' : 'Chưa đúng';
  const tone = result.correct[question.id] ? 'success' : result.values[question.id] > 0 ? 'warning' : 'danger';
  const answers = result.answers;
  return `<article class="panel exam-question"><div class="question-meta"><h2>Câu ${index + 1}</h2>${ctx.badge(state, tone)}<span class="text-muted text-small">${number(result.values[question.id])} / ${number(pointsFor(question.id, result.examContext))} điểm</span></div><p class="question-body">${escape(ctx, question.prompt)}</p>
    ${question.id === 'single' ? `<div class="answer-grid">${question.options.map((answer, i) => `<div class="answer-option${String(i) === question.correct ? ' is-correct' : ''}"><strong>${'ABCD'[i]}.</strong><span>${escape(ctx, answer)}</span>${String(i) === question.correct ? ctx.badge('Đáp án đúng', 'success') : ''}${answers.single === String(i) ? ctx.badge('Đã chọn', 'info') : ''}</div>`).join('')}</div>${answers.single === '' ? '<p class="text-muted text-small">Bạn chưa chọn đáp án.</p>' : ''}` : question.id === 'truth' ? `<div class="table-wrap"><table class="data-table exam-review-table"><thead><tr><th scope="col">Khẳng định</th><th scope="col">Đã chọn</th><th scope="col">Đáp án</th></tr></thead><tbody>${question.statements.map(item => `<tr><th scope="row"><strong>${item.id}.</strong> ${escape(ctx, item.text)}</th><td>${typeof answers.truth[item.id] === 'boolean' ? ctx.badge(answers.truth[item.id] ? 'Đúng' : 'Sai', answers.truth[item.id] === item.correct ? 'success' : 'danger') : ctx.badge('Bỏ trống', 'neutral')}</td><td>${item.correct ? 'Đúng' : 'Sai'}</td></tr>`).join('')}</tbody></table></div>` : `<div class="exam-short-review"><div><span class="text-muted text-small">Câu trả lời</span><strong>${escape(ctx, answers.short.trim() || 'Bỏ trống')}</strong></div><div><span class="text-muted text-small">Đáp án</span><strong>3/5 hoặc 0,6</strong></div></div>`}
    <details class="exam-explanation"><summary>${ctx.icon('book-open', 17)}Xem lời giải</summary><p>${escape(ctx, question.explanation)}</p></details></article>`;
}

export function renderResult(ctx) {
  const s = model(ctx);
  const result = s.examSubmission || grade({ single: '0', truth: { a: true, b: false, c: false, d: true }, short: '3/5' }, s.examContext || 'standalone');
  const actualDemo = Boolean(s.examSubmission);
  const correctCount = QUESTIONS.filter(q => result.correct[q.id]).length;
  const partialCount = QUESTIONS.filter(q => !result.correct[q.id] && result.values[q.id] > 0).length;
  const resultContext = CONTEXTS[result.examContext];
  return `${pageHeading(ctx, resultContext.label.toLocaleUpperCase('vi'), 'Kết quả bài minh họa', actualDemo ? 'Đối chiếu câu trả lời vừa nhập với đáp án mẫu và lời giải.' : 'Bản mẫu kết quả có sẵn để duyệt cách trình bày. Bạn chưa nộp bài trong phiên này.', ctx.button('Danh sách đề', 'result-back', 'secondary', 'arrow-left'))}
    ${demoNotice(ctx, actualDemo ? 'Kết quả này được tính từ câu trả lời trong phiên duyệt. Không ghi điểm, lượt nộp hoặc hồ sơ năng lực vào web thật.' : 'Điểm và câu trả lời bên dưới là dữ liệu mẫu, không phải kết quả làm bài của bạn.')}
    <div class="editor-layout"><div class="content-panel"><div class="section-heading"><h2>Chi tiết bài làm</h2><span class="text-muted text-small">Đề minh họa · 3 câu</span></div><div class="question-list">${QUESTIONS.map((q, i) => resultQuestion(ctx, q, i, result)).join('')}</div></div>
    <aside class="exam-summary"><section class="panel"><div class="panel-heading"><h2>Điểm minh họa</h2>${ctx.badge('Đã tính tại trình duyệt', 'info')}</div><div class="panel-body"><div class="exam-result-score"><strong>${number(result.score)}</strong><span>/ 10</span></div><p class="text-muted text-small">Đạt ${number(result.total)} / ${number(result.max)} điểm câu hỏi · Quy đổi về thang 10.</p><div class="exam-result-stats"><div><strong>${correctCount}</strong><span>Câu đúng hoàn toàn</span></div><div><strong>${partialCount}</strong><span>Câu đúng một phần</span></div><div><strong>${3 - correctCount - partialCount}</strong><span>Câu chưa đạt điểm</span></div></div><p class="text-small text-muted">${result.examContext === 'standalone' ? 'Đúng/Sai được tính theo tỷ lệ số ý đúng. Điểm kiểm tra được dùng làm bằng chứng bổ sung cho giáo viên.' : 'Đúng/Sai: đúng 1 / 2 / 3 / 4 ý được 0,1 / 0,25 / 0,5 / 1 điểm. Bản mẫu 3 câu không đại diện một đề đầu vào hoặc tự luyện hoàn chỉnh.'}</p>${ctx.button('Thử làm lại bài mẫu', 'retry-demo-exam', 'secondary', 'refresh-cw')}</div></section>
    ${result.examContext === 'practice' ? `<section class="panel panel-body"><h3>Sau bài luyện</h3><p class="text-small text-muted">Trong web thật, Tiếp tục chỉ xuất hiện khi bài nộp và hồ sơ đã được lưu đủ, nguồn của lớp còn hợp lệ.</p>${ctx.button('Xem giải thích luồng tiếp tục', 'explain-next-practice', 'ghost', 'arrow-right')}</section>` : result.examContext === 'diagnostic' ? `<section class="panel panel-body"><h3>Hồ sơ đầu vào</h3><p class="text-small text-muted">Web thật ghi nhận hồ sơ sau khi chấm và lưu thành công. Bản mẫu này chỉ trình bày kết quả, không khởi tạo hồ sơ.</p></section>` : ''}</aside></div>`;
}

export function bindResult(root, ctx) {
  const s = model(ctx);
  root.addEventListener('click', event => {
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (action === 'result-back') ctx.go('assessments');
    if (action === 'retry-demo-exam') ctx.openDialog({ title: 'Làm lại bài minh họa?', description: 'Xóa câu trả lời và kết quả hiện có trong bộ nhớ để thử lại. Web thật có quy tắc một lần nộp trên mỗi đề; thao tác này chỉ dành cho bản mẫu.', confirmLabel: 'Bắt đầu lại bản mẫu', onConfirm: () => { s.examAnswers = { single: '', truth: {}, short: '' }; s.examSubmission = null; s.examInputChanged = false; ctx.go('take'); } });
    if (action === 'explain-next-practice') ctx.openDialog({ title: 'Tiếp tục sau bài luyện', description: 'Điều kiện từ nghiệp vụ hiện tại', body: '<ol class="exam-flow-list"><li>Bài nộp được chấm và ghi nhận cùng hồ sơ năng lực.</li><li>Phiên chuyển sang chờ học sinh chọn tiếp tục hoặc kết thúc.</li><li>Khi tiếp tục, hệ thống kiểm tra lại nguồn câu của lớp rồi tạo đề mới.</li></ol><p class="text-muted text-small">Bản mẫu không tạo thêm đề hoặc mô phỏng cập nhật hồ sơ năng lực.</p>', confirmLabel: 'Đã hiểu', cancelLabel: 'Đóng' });
  });
}
