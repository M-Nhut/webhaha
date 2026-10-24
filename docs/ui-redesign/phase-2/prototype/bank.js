const BANKS = [
  {id: 'probability', name: 'Xác suất và không gian mẫu', subject: 'Toán', grade: 'Lớp 9', topic: 'Chương 8 · Bài 25–26', count: 248, ready: 226, scope: 'common', mode: 'research', updated: '12/10/2026', active: true},
  {id: 'algebra', name: 'Đại số và phương trình', subject: 'Toán', grade: 'Lớp 9', topic: 'Ôn tập học kỳ I', count: 168, ready: 152, scope: 'common', mode: 'general', updated: '11/10/2026', active: true},
  {id: 'functions', name: 'Hàm số bậc nhất', subject: 'Toán', grade: 'Lớp 9', topic: 'Đồ thị và ứng dụng', count: 84, ready: 76, scope: 'mine', mode: 'general', updated: '12/10/2026', active: true},
  {id: 'geometry', name: 'Hệ thức lượng trong tam giác', subject: 'Toán', grade: 'Lớp 9', topic: 'Hình học', count: 56, ready: 50, scope: 'mine', mode: 'general', updated: '10/10/2026', active: true},
  {id: 'vectors', name: 'Vectơ và các phép toán', subject: 'Toán', grade: 'Lớp 10', topic: 'Vectơ · Hàm số · Phương trình', count: 62, ready: 54, scope: 'mine', mode: 'general', updated: '09/10/2026', active: true},
  {id: 'term-one', name: 'Ôn tập học kỳ I · 2025–2026', subject: 'Toán', grade: 'Lớp 9', topic: 'Kho lưu trữ', count: 40, ready: 40, scope: 'mine', mode: 'general', updated: '02/10/2026', active: false}
];

const LEVELS = {nhan_biet: 'Nhận biết', thong_hieu: 'Thông hiểu', van_dung: 'Vận dụng', van_dung_cao: 'Vận dụng cao'};
const TYPES = {single: 'Trắc nghiệm', true_false: 'Đúng / Sai', short_answer: 'Trả lời ngắn'};
const RESEARCH_CATEGORIES = [
  ['1', 'Viết không gian mẫu'], ['2', 'Đếm không gian mẫu'], ['3', 'Đồng xu'], ['4', 'Xúc xắc'],
  ['5', 'Vòng quay'], ['6', 'Rút thẻ'], ['7', 'Viết số'], ['8', 'Chọn đối tượng']
];
const GENERAL_CATEGORIES = [['vectors', 'Phép toán vectơ'], ['functions', 'Hàm số'], ['equations', 'Phương trình']];
const GEOMETRY_CATEGORIES = [['triangle', 'Tam giác vuông'], ['ratios', 'Tỉ số lượng giác']];

const RESEARCH_QUESTIONS = [
  {id: 'r1', source: '9C8Ni-2D.014', category: '2', type: 'single', level: 'nhan_biet', scope: 'common', ready: true,
    text: 'Gieo một đồng xu và một con xúc xắc cân đối một lần. Không gian mẫu có bao nhiêu phần tử?',
    options: ['6', '8', '12', '16'], correct: 2,
    explanation: 'Đồng xu có 2 kết quả và xúc xắc có 6 kết quả. Theo quy tắc nhân, số phần tử của không gian mẫu là $2 \\times 6 = 12$.'},
  {id: 'r2', source: '9C8Hi-4T.021', category: '4', type: 'true_false', level: 'thong_hieu', scope: 'common', ready: true,
    text: 'Gieo một con xúc xắc cân đối một lần. Gọi A là biến cố “xuất hiện mặt có số chấm là số nguyên tố”. Xác định tính đúng, sai của các phát biểu.',
    statements: [
      {text: 'Không gian mẫu có 6 phần tử.', correct: true},
      {text: '$A=\\{2;3;5\\}$.', correct: true},
      {text: '$P(A)=\\frac{1}{2}$.', correct: true},
      {text: 'Xác suất của A lớn hơn xác suất biến cố đối của A.', correct: false}
    ], explanation: 'Các số nguyên tố trong tập từ 1 đến 6 là 2, 3 và 5. Vì vậy $P(A)=3/6=1/2$ và $P(\\overline{A})=1/2$.'},
  {id: 'r3', source: '9C8Vi-3S.009', category: '3', type: 'short_answer', level: 'van_dung', scope: 'common', ready: true,
    text: 'Tung hai đồng xu cân đối một lần. Tính xác suất để có ít nhất một mặt ngửa.',
    answer: '3/4 hoặc 0,75', grading: 'Chấm số · sai số 0',
    explanation: 'Có 4 kết quả đồng khả năng: NN, NS, SN, SS (N: ngửa; S: sấp). Có 3 kết quả chứa ít nhất một mặt ngửa nên xác suất bằng $\\frac{3}{4}$.'},
  {id: 'r4', source: '9C8Hi-6D.018', category: '6', type: 'single', level: 'thong_hieu', scope: 'mine', ready: true,
    text: 'Một hộp có 3 thẻ đỏ và 2 thẻ xanh, các thẻ có cùng kích thước. Rút ngẫu nhiên một thẻ. Xác suất rút được thẻ đỏ là bao nhiêu?',
    options: ['$\\frac{2}{5}$', '$\\frac{3}{5}$', '$\\frac{1}{3}$', '$\\frac{1}{2}$'], correct: 1,
    explanation: 'Có 5 thẻ đồng khả năng được chọn, trong đó 3 thẻ đỏ. Xác suất cần tìm là $3/5$.'},
  {id: 'r5', source: '9C8Ni-4S.033', category: '4', type: 'short_answer', level: 'nhan_biet', scope: 'mine', ready: false,
    text: 'Gieo một con xúc xắc cân đối một lần. Có bao nhiêu kết quả làm xuất hiện mặt có số chấm chẵn?',
    answer: '3', grading: 'Chấm số · sai số 0', explanation: 'Các kết quả thuận lợi là 2, 4, 6 nên có 3 kết quả.'}
];

const GENERAL_QUESTIONS = [
  {id: 'g1', category: 'vectors', type: 'single', level: 'nhan_biet', scope: 'common', ready: true,
    text: 'Trong mặt phẳng tọa độ Oxy, cho A(1; 2), B(4; 6). Tọa độ của vectơ $\\overrightarrow{AB}$ là:',
    options: ['(3; 4)', '(5; 8)', '(−3; −4)', '(4; 3)'], correct: 0,
    explanation: 'Lấy tọa độ điểm cuối trừ tọa độ điểm đầu: $\\overrightarrow{AB}=(4-1;6-2)=(3;4)$.'},
  {id: 'g2', category: 'functions', type: 'short_answer', level: 'thong_hieu', scope: 'common', ready: true,
    text: 'Cho hàm số $y=2x-3$. Tính giá trị của y khi $x=4$.',
    answer: '5', grading: 'Chấm số · sai số 0', explanation: 'Thay $x=4$ vào công thức, ta có $y=2\\times4-3=5$.'},
  {id: 'g3', category: 'equations', type: 'single', level: 'thong_hieu', scope: 'common', ready: true,
    text: 'Tập nghiệm của phương trình $x^2-5x+6=0$ là:',
    options: ['$\\{1;6\\}$', '$\\{-2;-3\\}$', '$\\{2;3\\}$', '$\\{-1;-6\\}$'], correct: 2,
    explanation: 'Ta có $x^2-5x+6=(x-2)(x-3)$. Vậy phương trình có nghiệm $x=2$ hoặc $x=3$.'},
  {id: 'g4', category: 'vectors', type: 'true_false', level: 'van_dung', scope: 'mine', ready: true,
    text: 'Cho hai vectơ $\\vec a=(1;2)$ và $\\vec b=(3;-1)$. Xác định tính đúng, sai của các phát biểu.',
    statements: [
      {text: '$\\vec a+\\vec b=(4;1)$.', correct: true},
      {text: '$\\vec a-\\vec b=(-2;3)$.', correct: true},
      {text: '$\\vec a\\cdot\\vec b=1$.', correct: true},
      {text: 'Hai vectơ cùng phương.', correct: false}
    ], explanation: 'Thực hiện phép toán theo từng tọa độ. Tích vô hướng bằng $1\\times3+2\\times(-1)=1$. Hai cặp tọa độ không tỉ lệ nên hai vectơ không cùng phương.'},
  {id: 'g5', category: 'equations', type: 'short_answer', level: 'nhan_biet', scope: 'mine', ready: false,
    text: 'Tìm nghiệm dương của phương trình $x^2-4=0$.',
    answer: '2', grading: 'Chấm số · sai số 0', explanation: 'Phương trình tương đương $(x-2)(x+2)=0$. Nghiệm dương là $x=2$.'}
];

const GEOMETRY_QUESTIONS = [
  {id: 'h1', category: 'triangle', type: 'single', level: 'nhan_biet', scope: 'mine', ready: true, text: 'Tam giác ABC vuông tại A có AB = 3 cm, AC = 4 cm. Độ dài BC là:', options: ['5 cm', '6 cm', '7 cm', '12 cm'], correct: 0, explanation: 'Theo định lý Pythagore, $BC=\\sqrt{3^2+4^2}=5$ cm.'},
  {id: 'h2', category: 'ratios', type: 'short_answer', level: 'nhan_biet', scope: 'mine', ready: true, text: 'Tính $\\sin 30^\\circ$.', answer: '1/2 hoặc 0,5', grading: 'Chấm số · sai số 0', explanation: 'Giá trị lượng giác đặc biệt: $\\sin30^\\circ=1/2$.'},
  {id: 'h3', category: 'triangle', type: 'short_answer', level: 'thong_hieu', scope: 'mine', ready: true, text: 'Một tam giác vuông có cạnh huyền 13 cm và một cạnh góc vuông 5 cm. Cạnh góc vuông còn lại dài bao nhiêu centimet?', answer: '12', grading: 'Chấm số · sai số 0', explanation: 'Cạnh còn lại dài $\\sqrt{13^2-5^2}=\\sqrt{144}=12$ cm.'},
  {id: 'h4', category: 'ratios', type: 'single', level: 'thong_hieu', scope: 'mine', ready: true, text: 'Cho góc nhọn $\\alpha$ có $\\sin\\alpha=3/5$. Khi đó $\\cos\\alpha$ bằng:', options: ['$3/5$', '$4/5$', '$5/3$', '$5/4$'], correct: 1, explanation: 'Do góc nhọn, cos dương. Dùng $\\sin^2\\alpha+\\cos^2\\alpha=1$ được $\\cos\\alpha=4/5$.'},
  {id: 'h5', category: 'triangle', type: 'true_false', level: 'van_dung', scope: 'mine', ready: false, text: 'Tam giác ABC vuông tại A có AB = 6 cm, AC = 8 cm. Xác định tính đúng, sai.', statements: [{text: 'BC = 10 cm.', correct: true}, {text: 'Diện tích tam giác bằng 24 cm².', correct: true}, {text: '$\\sin B=3/5$.', correct: false}, {text: '$\\cos B=3/5$.', correct: true}], explanation: 'BC = 10 cm và diện tích bằng $6\\times8/2=24$ cm². Với góc B, cạnh đối là AC nên sin B = 8/10 = 4/5, cos B = 6/10 = 3/5.'}
];

function mode(ctx) { return ctx.state.bankMode === 'general' ? 'general' : 'research'; }
function banks(ctx) {
  const overrides = ctx.state.bankRecordEdits || {};
  return [...BANKS, ...(ctx.state.bankLocalBanks || [])].map(bank => ({...bank, ...(overrides[bank.id] || {})}))
    .sort((a, b) => b.updated.split('/').reverse().join('').localeCompare(a.updated.split('/').reverse().join('')));
}
function selectedBank(ctx) {
  return banks(ctx).find(bank => bank.id === ctx.state.bankSelectedId && bank.mode === mode(ctx)) || banks(ctx).find(bank => bank.id === (mode(ctx) === 'research' ? 'probability' : 'vectors'));
}
function categories(ctx) {
  if (mode(ctx) === 'research') return RESEARCH_CATEGORIES;
  const id = selectedBank(ctx).id;
  if (id === 'geometry') return GEOMETRY_CATEGORIES;
  if (['functions', 'algebra', 'term-one'].includes(id)) return GENERAL_CATEGORIES.filter(category => category[0] !== 'vectors');
  return GENERAL_CATEGORIES;
}
function canEdit(ctx, question) { return ctx.state.role === 'admin' || question.scope === 'mine'; }
function scopeLabel(ctx, scope) {
  return scope === 'common' ? 'Dùng chung' : ctx.state.role === 'admin' ? 'Riêng tư · giáo viên sở hữu' : 'Riêng tư · chỉ bạn';
}
function questions(ctx) {
  const bank = selectedBank(ctx);
  let source = mode(ctx) === 'research' ? RESEARCH_QUESTIONS : bank.id === 'geometry' ? GEOMETRY_QUESTIONS : GENERAL_QUESTIONS;
  if (['functions', 'algebra', 'term-one'].includes(bank.id)) source = source.filter(question => question.category !== 'vectors');
  if (bank.id.startsWith('local-')) source = [];
  const overrides = ctx.state.bankQuestionEdits || {};
  return [...source.map(question => ({...question, id: `${bank.id}-${question.id}`, scope: bank.scope === 'mine' ? 'mine' : question.scope})), ...(ctx.state.bankLocalQuestions?.[bank.id] || [])]
    .filter(q => !(ctx.state.bankDeletedQuestions || []).includes(q.id))
    .map(q => ({...q, ...(overrides[q.id] || {})}));
}
function scopeQuestions(ctx) {
  return questions(ctx).filter(q => !ctx.state.scope || ctx.state.scope === 'all' || q.scope === ctx.state.scope);
}
function matchedQuestions(ctx) {
  const s = ctx.state, query = (s.bankQuery || '').trim().toLocaleLowerCase('vi');
  return scopeQuestions(ctx).filter(q =>
    (!s.bankCategory || q.category === s.bankCategory) &&
    (!s.bankType || q.type === s.bankType) && (!s.bankLevel || q.level === s.bankLevel) &&
    (!query || `${q.text} ${q.source || ''}`.toLocaleLowerCase('vi').includes(query)));
}
function optionHTML(ctx, entries, selected) {
  return entries.map(([value, label]) => `<option value="${ctx.escapeHTML(value)}"${selected === value ? ' selected' : ''}>${ctx.escapeHTML(label)}</option>`).join('');
}
function sourceBadge(ctx, scope) { return ctx.badge(scopeLabel(ctx, scope), scope === 'common' ? 'info' : 'neutral'); }
function localNotice(ctx) {
  return `<div class="prototype-context toolbar" aria-label="Điều khiển ngữ cảnh bản mẫu">
    <span class="text-small text-muted">Ngữ cảnh minh họa</span>
    <label class="prototype-mode-label" for="bank-mode">Loại ngân hàng</label>
    <select id="bank-mode" data-bank-mode>${optionHTML(ctx, [['research', 'Toán 9 · Chương 8'], ['general', 'Nhiều lớp / chủ đề']], mode(ctx))}</select>
    <span class="text-small text-muted">Dữ liệu mẫu · thao tác không lưu vào hệ thống</span>
  </div>`;
}

export function renderBanks(ctx) {
  const {state: s, icon, badge, button, escapeHTML: e} = ctx;
  const query = (s.bankListQuery || '').trim().toLocaleLowerCase('vi');
  const items = banks(ctx).filter(b => (!query || `${b.name} ${b.topic} ${b.grade}`.toLocaleLowerCase('vi').includes(query)) &&
    (!s.bankListGrade || b.grade === s.bankListGrade) && (!s.bankListScope || b.scope === s.bankListScope));
  return `<div class="page-heading"><div class="heading-copy"><p class="breadcrumb">Học liệu / Ngân hàng câu hỏi</p><h1>Ngân hàng câu hỏi</h1><p>Quản lý học liệu, kiểm tra độ phủ kiến thức và chuẩn bị câu hỏi cho bài học.</p></div>
    <div class="heading-actions">${button('Nhập từ LaTeX', 'bank-import', 'secondary', 'upload')}${button('Tạo ngân hàng', 'bank-create', 'primary', 'plus')}</div></div>
    <div class="notice notice-info">${icon('info')}<div>Ngân hàng dùng chung có thể xem và sử dụng. Câu bạn bổ sung vào ngân hàng chung thuộc phạm vi riêng tư của bạn.</div></div>
    <section class="panel" aria-label="Danh sách ngân hàng">
      <div class="toolbar"><label class="search-field">${icon('search')}<input data-bank-list-query type="search" aria-label="Tìm ngân hàng" placeholder="Tìm tên, lớp hoặc chủ đề…" value="${e(s.bankListQuery || '')}"></label>
        <select data-bank-list-grade aria-label="Lọc theo khối lớp">${optionHTML(ctx, [['', 'Tất cả khối lớp'], ['Lớp 9', 'Lớp 9'], ['Lớp 10', 'Lớp 10']], s.bankListGrade || '')}</select>
        <select data-bank-list-scope aria-label="Lọc theo phạm vi">${optionHTML(ctx, [['', 'Tất cả phạm vi'], ['common', 'Dùng chung'], ['mine', s.role === 'admin' ? 'Ngân hàng riêng' : 'Của tôi']], s.bankListScope || '')}</select>
      </div>
      <div class="panel-heading"><h2>Kho học liệu <span class="text-muted">(${items.length})</span></h2><span class="text-small text-muted">Sắp xếp theo cập nhật gần nhất</span></div>
      ${items.length ? `<div class="table-wrap"><table class="data-table bank-table"><thead><tr><th scope="col">Ngân hàng</th><th scope="col">Phạm vi</th><th scope="col">Câu hỏi</th><th scope="col">Cập nhật</th><th scope="col"><span class="sr-only">Thao tác</span></th></tr></thead>
        <tbody>${items.map(b => `<tr><td><button type="button" class="table-title" data-open-bank="${e(b.id)}">${e(b.name)}</button><div class="text-small text-muted">${e(b.subject)} · ${e(b.grade)} · ${e(b.topic)}</div>${!b.active ? `<div class="bank-row-status">${badge('Tạm ngưng dùng cho bài mới', 'warning')}</div>` : ''}</td>
          <td>${sourceBadge(ctx, b.scope)}</td><td><strong>${b.count}</strong><div class="text-small text-muted">${b.ready} sẵn sàng</div></td><td class="text-small text-muted">${b.updated}</td>
          <td><div class="table-actions"><button class="btn btn-secondary btn-sm" type="button" data-open-bank="${e(b.id)}">Mở ngân hàng ${icon('arrow-right', 16)}</button>${s.role === 'admin' || b.scope === 'mine' ? `<button class="icon-btn" type="button" data-edit-bank="${e(b.id)}" aria-label="Sửa ngân hàng ${e(b.name)}">${icon('pencil')}</button>` : ''}</div></td></tr>`).join('')}</tbody></table></div>` :
        `<div class="empty-state">${icon('search', 28)}<h3>Không tìm thấy ngân hàng</h3><p>Thử tìm bằng từ khóa khác hoặc đặt lại bộ lọc.</p>${button('Đặt lại bộ lọc', 'bank-list-reset')}</div>`}
      <div class="pagination"><span class="text-small text-muted" role="status">Hiển thị ${items.length} ngân hàng minh họa</span><span class="text-small text-muted">Phạm vi và quyền được thể hiện theo vai trò đang chọn</span></div>
    </section>`;
}

function bankForm(ctx, editing) {
  const e = ctx.escapeHTML;
  ctx.openDialog({title: editing ? 'Chỉnh sửa ngân hàng' : 'Tạo ngân hàng câu hỏi',
    description: 'Thao tác trong bản mẫu. Dữ liệu chỉ tồn tại trong phiên xem này.',
    body: `<div class="field"><label for="demo-bank-name">Tên ngân hàng <span aria-hidden="true">*</span></label><input id="demo-bank-name" name="bank_name" required value="${e(editing?.name || '')}" placeholder="Ví dụ: Ôn tập Toán 9"></div>
      <div class="form-grid-2"><div class="field"><label for="demo-bank-grade">Khối lớp</label><select id="demo-bank-grade" name="bank_grade">${optionHTML(ctx, [['Lớp 9', 'Lớp 9'], ['Lớp 10', 'Lớp 10']], editing?.grade || 'Lớp 9')}</select></div>
      <div class="field"><label for="demo-bank-subject">Môn học</label><select id="demo-bank-subject" name="bank_subject"><option>Toán</option></select></div></div>
      <div class="field"><label for="demo-bank-topic">Chủ đề / mô tả ngắn</label><input id="demo-bank-topic" name="bank_topic" value="${e(editing?.topic || '')}" placeholder="Nội dung chính của ngân hàng"></div>
      <div class="notice notice-info">${ctx.icon('lock-keyhole')}<div>${ctx.state.role === 'admin' ? 'Ngân hàng mới của quản trị viên ở phạm vi dùng chung.' : 'Ngân hàng mới của bạn ở phạm vi riêng tư.'}</div></div>`,
    confirmLabel: editing ? 'Lưu thay đổi trong bản mẫu' : 'Tạo trong bản mẫu',
    onConfirm(dialog) {
      const name = dialog.querySelector('[name=bank_name]').value.trim();
      if (!name) { ctx.toast('Vui lòng nhập tên ngân hàng.'); return false; }
      const record = {id: editing?.id || `local-${Date.now()}`, name, grade: dialog.querySelector('[name=bank_grade]').value, subject: 'Toán', topic: dialog.querySelector('[name=bank_topic]').value.trim(),
        count: editing?.count || 0, ready: editing?.ready || 0, scope: editing?.scope || (ctx.state.role === 'admin' ? 'common' : 'mine'), mode: editing?.mode || 'general', updated: '14/10/2026', active: editing?.active ?? true};
      if (editing && BANKS.some(b => b.id === editing.id)) ctx.state.bankRecordEdits = {...ctx.state.bankRecordEdits, [record.id]: record};
      else ctx.state.bankLocalBanks = (ctx.state.bankLocalBanks || []).filter(b => b.id !== record.id).concat(record);
      ctx.refresh(); ctx.toast(editing ? 'Đã cập nhật trong bản mẫu.' : 'Đã tạo ngân hàng trong bản mẫu.');
    }});
}

export function bindBanks(root, ctx) {
  const submitFilters = () => {
    ctx.state.bankListQuery = root.querySelector('[data-bank-list-query]').value;
    ctx.state.bankListGrade = root.querySelector('[data-bank-list-grade]').value;
    ctx.state.bankListScope = root.querySelector('[data-bank-list-scope]').value;
    ctx.refresh();
  };
  root.querySelector('[data-bank-list-query]')?.addEventListener('change', submitFilters);
  root.querySelectorAll('[data-bank-list-grade], [data-bank-list-scope]').forEach(el => el.addEventListener('change', submitFilters));
  root.querySelectorAll('[data-open-bank]').forEach(el => el.addEventListener('click', () => {
    const bank = banks(ctx).find(b => b.id === el.dataset.openBank);
    ctx.state.bankSelectedId = bank.id; ctx.state.bankMode = bank.mode; ctx.state.bankCategory = ''; ctx.state.bankQuery = ''; ctx.state.bankType = ''; ctx.state.bankLevel = ''; ctx.state.scope = 'all';
    ctx.go('bank');
  }));
  root.querySelectorAll('[data-edit-bank]').forEach(el => el.addEventListener('click', () => bankForm(ctx, banks(ctx).find(b => b.id === el.dataset.editBank))));
  root.querySelector('[data-action=bank-create]')?.addEventListener('click', () => bankForm(ctx));
  root.querySelector('[data-action=bank-import]')?.addEventListener('click', () => ctx.openDialog({title: 'Nhập học liệu LaTeX', description: 'Bản xem trước luồng nhập · không tải tệp lên hệ thống.',
    body: `<ol class="import-flow-list"><li><strong>Tải file .tex hoặc .latex</strong><p class="text-muted text-small">Xác định tài liệu ngân hàng hoặc đề kiểm tra.</p></li><li><strong>Kiểm tra nội dung và câu trùng</strong><p class="text-muted text-small">Xem công thức, đáp án và đối chiếu hai bản.</p></li><li><strong>Duyệt và lưu</strong><p class="text-muted text-small">Kiểm tra ngân hàng đích và các câu đủ điều kiện.</p></li></ol><div class="notice notice-info">Luồng nhập đầy đủ sẽ được thiết kế trong Phase 5.</div>`, confirmLabel: 'Đã xem luồng nhập', onConfirm() { ctx.toast('Luồng này là minh họa cho Phase 2.'); }}));
  root.querySelector('[data-action=bank-list-reset]')?.addEventListener('click', () => {
    ctx.state.bankListQuery = ''; ctx.state.bankListGrade = ''; ctx.state.bankListScope = ''; ctx.refresh();
  });
}

function renderAnswers(ctx, q) {
  const e = ctx.escapeHTML;
  if (q.type === 'single') return `<div class="answer-grid">${q.options.map((o, i) => `<div class="answer-option${i === q.correct ? ' is-correct' : ''}"><span class="answer-letter">${'ABCD'[i]}</span><span>${e(o)}</span>${i === q.correct ? ctx.badge('Đáp án đúng', 'success') : ''}</div>`).join('')}</div>`;
  if (q.type === 'true_false') return `<div class="statement-list">${q.statements.map((o, i) => `<div class="statement-row"><span class="answer-letter">${'abcd'[i]})</span><span>${e(o.text)}</span>${ctx.badge(o.correct ? 'Đúng' : 'Sai', o.correct ? 'success' : 'danger')}</div>`).join('')}</div>`;
  return `<div class="short-answer-key"><span class="text-small text-muted">Đáp án chấp nhận</span><strong>${e(q.answer)}</strong><span class="text-small text-muted">${e(q.grading || 'Chấm số · sai số 0')}</span></div>`;
}

function renderQuestion(ctx, q, index) {
  const e = ctx.escapeHTML, category = categories(ctx).find(c => c[0] === q.category)?.[1] || 'Chưa phân loại';
  return `<article class="question-card" id="demo-q-${e(q.id)}" aria-label="Câu ${index + 1}"><div class="question-meta"><strong>Câu ${index + 1}</strong>${ctx.badge(TYPES[q.type], 'neutral')}${ctx.badge(LEVELS[q.level], 'neutral')}${sourceBadge(ctx, q.scope)}${!q.ready ? ctx.badge('Chờ duyệt', 'warning') : ''}</div>
    <div class="question-body"><p>${e(q.text)}</p></div>
    <div class="question-context-line"><span>${ctx.icon('folder', 14)} ${e(category)}</span>${q.source ? `<span class="text-muted">${e(q.source)}</span>` : ''}</div>
    <details class="question-details"${ctx.state.bankExpandedQuestion === q.id ? ' open' : ''}><summary>Đáp án và lời giải ${ctx.icon('chevron-down', 16)}</summary><div class="question-details-body">${renderAnswers(ctx, q)}<div class="question-explanation"><h3>Lời giải</h3><p>${e(q.explanation)}</p></div></div></details>
    <div class="question-footer"><span class="text-small text-muted">${q.ready ? 'Đã duyệt · sẵn sàng sử dụng' : 'Kiểm tra đáp án và nhãn trước khi sử dụng'}</span><div class="question-actions">${canEdit(ctx, q) ? `<button class="btn btn-ghost btn-sm" type="button" data-edit-question="${e(q.id)}">${ctx.icon('pencil', 15)} Sửa</button><button class="icon-btn danger-icon" type="button" data-delete-question="${e(q.id)}" aria-label="Xóa câu ${index + 1}">${ctx.icon('trash-2', 16)}</button>` : `<span class="text-small text-muted">${ctx.icon('lock-keyhole', 13)} Chỉ đọc</span>`}</div></div></article>`;
}

function coverage(ctx) {
  const subset = scopeQuestions(ctx);
  return `<details class="panel bank-coverage"><summary><span>${ctx.icon('layers', 17)} Độ phủ kiến thức</span><span class="text-small text-muted">${subset.filter(q => q.ready).length}/${subset.length} câu sẵn sàng ${ctx.icon('chevron-down', 15)}</span></summary>
    <div class="coverage-body"><p class="text-small text-muted">Sẵn sàng = đã duyệt, đủ đáp án và được phép dùng trong luyện tập. Chọn ô để lọc câu.</p><div class="table-wrap"><table class="data-table coverage-table"><thead><tr><th scope="col">Mức nhận thức</th>${Object.values(TYPES).map(t => `<th scope="col">${t}</th>`).join('')}</tr></thead><tbody>${Object.entries(LEVELS).map(([level, label]) => `<tr><th scope="row">${label}</th>${Object.keys(TYPES).map(type => {
      const rows = subset.filter(q => q.level === level && q.type === type && (!ctx.state.bankCategory || q.category === ctx.state.bankCategory));
      return `<td><button class="coverage-cell${rows.length ? '' : ' is-empty'}" type="button" data-coverage-level="${level}" data-coverage-type="${type}" aria-label="${label}, ${TYPES[type]}: ${rows.length} câu, ${rows.filter(q => q.ready).length} sẵn sàng"><strong>${rows.length}</strong><span>${rows.filter(q => q.ready).length} sẵn sàng</span></button></td>`;
    }).join('')}</tr>`).join('')}</tbody></table></div></div></details>`;
}

export function renderBank(ctx) {
  const {state: s, icon, button, escapeHTML: e} = ctx;
  const research = mode(ctx) === 'research';
  const bank = selectedBank(ctx), title = bank.name;
  const canUse = bank.active;
  const all = questions(ctx), subset = scopeQuestions(ctx), items = matchedQuestions(ctx);
  const categoryList = categories(ctx);
  return `<div class="page-heading"><div class="heading-copy"><p class="breadcrumb"><button type="button" data-action="bank-back">Ngân hàng câu hỏi</button> ${icon('chevron-right', 13)} ${e(bank.subject)} · ${e(bank.grade)}</p><h1>${e(title)}</h1><p>${research ? 'Phép thử ngẫu nhiên, không gian mẫu và xác suất của biến cố.' : e(bank.topic)}</p></div>
    <div class="heading-actions">${canUse ? button('Tạo đề từ ngân hàng', 'bank-create-assessment', 'secondary', 'file-text') : `<button class="btn btn-secondary" type="button" disabled>${icon('file-text')} Tạm ngưng dùng cho bài mới</button>`}${button(s.role === 'admin' || bank.scope === 'mine' ? 'Thêm câu hỏi' : 'Thêm câu riêng', 'bank-add-question', 'primary', 'plus')}</div></div>
    ${localNotice(ctx)}
    <div class="notice notice-info">${icon(s.role === 'admin' ? 'check-circle' : bank.scope === 'mine' ? 'lock-keyhole' : 'info')}<div>${s.role === 'admin' ? '<strong>Chế độ quản trị.</strong> Bạn có thể kiểm toán và quản lý câu dùng chung cùng các đóng góp riêng của giáo viên.' : bank.scope === 'mine' ? '<strong>Ngân hàng riêng của bạn.</strong> Bạn có thể quản lý nội dung và sử dụng câu hỏi trong các hoạt động học tập.' : '<strong>Ngân hàng dùng chung.</strong> Các câu dùng chung chỉ đọc. Câu bạn thêm chỉ hiển thị và sử dụng với chính bạn.'}</div></div>
    <div class="tabs" role="tablist" aria-label="Phạm vi câu hỏi">${[['all', 'Tất cả câu được phép xem'], ['common', 'Dùng chung'], ['mine', s.role === 'admin' ? 'Đóng góp riêng' : 'Câu riêng của tôi']].map(([key, label]) => `<button type="button" class="tab" role="tab" id="bank-scope-${key}" aria-controls="bank-content" tabindex="${(s.scope || 'all') === key ? '0' : '-1'}" data-bank-scope="${key}" aria-selected="${(s.scope || 'all') === key}">${label}<span class="tab-count">${key === 'all' ? all.length : all.filter(q => q.scope === key).length}</span></button>`).join('')}</div>
    <div class="split-layout bank-workspace"><aside class="context-panel panel" aria-label="Dạng kiến thức"><div class="panel-heading"><h2>Dạng kiến thức</h2></div><nav class="context-tree" aria-label="Lọc theo dạng kiến thức"><button class="tree-item${!s.bankCategory ? ' is-active' : ''}" type="button" data-bank-category=""${!s.bankCategory ? ' aria-current="true"' : ''}><span>${icon('layers', 16)} Tất cả dạng</span><span class="tree-count">${subset.length}</span></button>${categoryList.map(([key, label]) => `<button class="tree-item${s.bankCategory === key ? ' is-active' : ''}" type="button" data-bank-category="${key}"${s.bankCategory === key ? ' aria-current="true"' : ''}><span>${research ? `<span class="category-code">D${key}</span>` : icon('folder', 15)} ${e(label)}</span><span class="tree-count">${subset.filter(q => q.category === key).length}</span></button>`).join('')}</nav><div class="context-footer"><p class="text-small text-muted">${research ? 'Toán 9 · Chương 8 · Bài kết hợp i' : 'Dạng kiến thức được đặt theo nội dung ngân hàng, không bắt buộc mã ID6.'}</p><button type="button" class="btn btn-ghost btn-sm" data-action="bank-catalog">${icon('sliders-horizontal', 15)} ${s.role === 'admin' ? 'Quản lý danh mục' : 'Xem danh mục'}</button></div></aside>
      <section class="content-panel" id="bank-content" role="tabpanel" aria-labelledby="bank-scope-${s.scope || 'all'}">${coverage(ctx)}
        <div class="panel bank-filter-panel"><div class="toolbar"><label class="search-field">${icon('search')}<input data-bank-query type="search" aria-label="Tìm nội dung hoặc mã câu hỏi" placeholder="Tìm nội dung hoặc mã câu hỏi…" value="${e(s.bankQuery || '')}"></label><select data-bank-type aria-label="Lọc hình thức câu hỏi">${optionHTML(ctx, [['', 'Tất cả hình thức'], ...Object.entries(TYPES)], s.bankType || '')}</select><select data-bank-level aria-label="Lọc mức nhận thức">${optionHTML(ctx, [['', 'Tất cả mức độ'], ...Object.entries(LEVELS)], s.bankLevel || '')}</select><button class="icon-btn" type="button" data-action="bank-reset" aria-label="Đặt lại bộ lọc">${icon('refresh-cw', 17)}</button></div></div>
        <div class="section-heading"><h2>${e(categoryList.find(c => c[0] === s.bankCategory)?.[1] || 'Danh sách câu hỏi')} <span class="text-muted">(${items.length})</span></h2><span class="text-small text-muted" role="status">${items.filter(q => q.ready).length} sẵn sàng · dữ liệu minh họa</span></div>
        <div class="question-list">${items.length ? items.map((q, i) => renderQuestion(ctx, q, i)).join('') : `<div class="panel empty-state">${icon('search', 26)}<h3>Chưa có câu phù hợp</h3><p>Thử đổi dạng kiến thức hoặc đặt lại bộ lọc.</p>${button('Đặt lại bộ lọc', 'bank-reset')}</div>`}</div>
        <div class="pagination"><span class="text-small text-muted">Hiển thị ${items.length} trên ${items.length} câu phù hợp</span><div class="pagination-controls"><button class="btn btn-secondary btn-sm" type="button" disabled aria-label="Trang trước">${icon('chevron-left', 14)}</button><button class="btn btn-secondary btn-sm" type="button" aria-current="page">1</button><button class="btn btn-secondary btn-sm" type="button" disabled aria-label="Trang sau">${icon('chevron-right', 14)}</button></div></div>
      </section></div>`;
}

function questionDialog(ctx, existing) {
  const e = ctx.escapeHTML, q = existing || {type: 'single', level: 'nhan_biet', category: ctx.state.bankCategory || categories(ctx)[0][0], text: '', options: ['', '', '', ''], correct: 0, explanation: ''};
  ctx.openDialog({title: existing ? 'Chỉnh sửa câu hỏi' : ctx.state.role === 'admin' ? 'Thêm câu hỏi' : 'Thêm câu riêng',
    description: 'Bản mẫu soạn câu · thay đổi chỉ có hiệu lực trong phiên xem này.',
    body: `<div class="notice notice-info">${ctx.icon('info')}<div>${existing ? 'Bản mẫu cho phép sửa nội dung, lời giải và nhãn. Cấu trúc đáp án được giữ nguyên.' : 'Minh họa tạo câu trắc nghiệm một đáp án. Bộ soạn đầy đủ ba hình thức sẽ được triển khai trong Phase 4.'}</div></div>
      <div class="form-grid-2"><div class="field"><label for="demo-q-category">Dạng kiến thức</label><select id="demo-q-category" name="q_category">${optionHTML(ctx, categories(ctx), q.category)}</select></div><div class="field"><label for="demo-q-level">Mức nhận thức</label><select id="demo-q-level" name="q_level">${optionHTML(ctx, Object.entries(LEVELS), q.level)}</select></div></div>
      <div class="field"><label for="demo-q-text">Nội dung câu hỏi</label><textarea id="demo-q-text" name="q_text" rows="4" required placeholder="Nhập nội dung câu hỏi, có thể dùng công thức giữa hai dấu $">${e(q.text)}</textarea></div>
      ${!existing ? `<fieldset class="question-option-fields"><legend>Phương án trả lời · chọn một đáp án đúng</legend>${'ABCD'.split('').map((label, i) => `<label class="option-editor-row"><input type="radio" name="q_correct" value="${i}"${i === 0 ? ' checked' : ''}><span>${label}</span><input name="q_option_${i}" required aria-label="Phương án ${label}" placeholder="Nội dung phương án ${label}"></label>`).join('')}</fieldset>` : ''}
      <div class="field"><label for="demo-q-explanation">Lời giải</label><textarea id="demo-q-explanation" name="q_explanation" rows="3">${e(q.explanation)}</textarea></div>
      <label class="checkbox-field"><input type="checkbox" name="q_reviewed" required><span>Tôi đã kiểm tra nội dung, đáp án và nhãn kiến thức.</span></label>`,
    confirmLabel: existing ? 'Lưu trong bản mẫu' : 'Thêm vào bản mẫu',
    onConfirm(dialog) {
      const text = dialog.querySelector('[name=q_text]').value.trim();
      if (!text || !dialog.querySelector('[name=q_reviewed]').checked) { ctx.toast('Nhập nội dung và xác nhận đã kiểm tra câu hỏi.'); return false; }
      const record = {...q, id: existing?.id || `local-q-${Date.now()}`, text, category: dialog.querySelector('[name=q_category]').value, level: dialog.querySelector('[name=q_level]').value,
        explanation: dialog.querySelector('[name=q_explanation]').value.trim(), scope: existing?.scope || (selectedBank(ctx).scope === 'mine' || ctx.state.role !== 'admin' ? 'mine' : 'common'), ready: true};
      if (existing) ctx.state.bankQuestionEdits = {...ctx.state.bankQuestionEdits, [existing.id]: record};
      else {
        record.options = [0, 1, 2, 3].map(i => dialog.querySelector(`[name=q_option_${i}]`).value.trim());
        if (record.options.some(o => !o)) { ctx.toast('Nhập đủ bốn phương án.'); return false; }
        record.correct = Number(dialog.querySelector('[name=q_correct]:checked').value);
        ctx.state.bankLocalQuestions ||= {}; const bankId = selectedBank(ctx).id;
        ctx.state.bankLocalQuestions[bankId] = [...(ctx.state.bankLocalQuestions[bankId] || []), record];
        ctx.state.scope = ctx.state.role === 'admin' ? 'all' : 'mine';
        ctx.state.bankCategory = ''; ctx.state.bankQuery = ''; ctx.state.bankType = ''; ctx.state.bankLevel = '';
      }
      ctx.refresh(); ctx.toast(existing ? 'Đã cập nhật câu trong bản mẫu.' : 'Đã thêm câu trong bản mẫu.');
    }});
}

export function bindBank(root, ctx) {
  // The shell replaces #view on refresh; never restore focus into the old root.
  const focusScope = () => document.querySelector(`#view [data-bank-scope="${ctx.state.scope || 'all'}"]`)?.focus();
  root.querySelector('[data-action=bank-back]')?.addEventListener('click', () => ctx.go('banks'));
  root.querySelector('[data-action=bank-create-assessment]')?.addEventListener('click', () => ctx.go('editor'));
  root.querySelector('[data-bank-mode]')?.addEventListener('change', event => {
    ctx.state.bankMode = event.target.value; ctx.state.bankSelectedId = ctx.state.bankMode === 'general' ? 'vectors' : 'probability';
    ctx.state.bankCategory = ''; ctx.state.bankQuery = ''; ctx.state.bankType = ''; ctx.state.bankLevel = ''; ctx.state.scope = 'all'; ctx.refresh();
  });
  root.querySelectorAll('[data-bank-scope]').forEach(el => el.addEventListener('click', () => {
    ctx.state.scope = el.dataset.bankScope; ctx.refresh(); focusScope();
  }));
  root.querySelectorAll('[data-bank-scope]').forEach(el => el.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const scopes = ['all', 'common', 'mine'], index = scopes.indexOf(ctx.state.scope || 'all');
    ctx.state.scope = event.key === 'Home' ? 'all' : event.key === 'End' ? 'mine' : scopes[(index + (event.key === 'ArrowRight' ? 1 : 2)) % 3];
    ctx.refresh(); focusScope();
  }));
  root.querySelectorAll('[data-bank-category]').forEach(el => el.addEventListener('click', () => { ctx.state.bankCategory = el.dataset.bankCategory; ctx.refresh(); }));
  const updateFilter = () => {
    ctx.state.bankQuery = root.querySelector('[data-bank-query]').value;
    ctx.state.bankType = root.querySelector('[data-bank-type]').value;
    ctx.state.bankLevel = root.querySelector('[data-bank-level]').value; ctx.refresh();
  };
  root.querySelector('[data-bank-query]')?.addEventListener('change', updateFilter);
  root.querySelectorAll('[data-bank-type], [data-bank-level]').forEach(el => el.addEventListener('change', updateFilter));
  root.querySelectorAll('[data-action=bank-reset]').forEach(el => el.addEventListener('click', () => {
    ctx.state.bankQuery = ''; ctx.state.bankType = ''; ctx.state.bankLevel = ''; ctx.state.bankCategory = ''; ctx.refresh();
  }));
  root.querySelectorAll('[data-coverage-level]').forEach(el => el.addEventListener('click', () => {
    ctx.state.bankLevel = el.dataset.coverageLevel; ctx.state.bankType = el.dataset.coverageType; ctx.refresh();
  }));
  root.querySelector('[data-action=bank-add-question]')?.addEventListener('click', () => questionDialog(ctx));
  root.querySelectorAll('[data-edit-question]').forEach(el => el.addEventListener('click', () => {
    const q = questions(ctx).find(q => q.id === el.dataset.editQuestion); if (q && canEdit(ctx, q)) questionDialog(ctx, q);
  }));
  root.querySelectorAll('[data-delete-question]').forEach(el => el.addEventListener('click', () => {
    const q = questions(ctx).find(q => q.id === el.dataset.deleteQuestion); if (!q || !canEdit(ctx, q)) return;
    ctx.openDialog({title: 'Xóa câu khỏi bản mẫu?', description: 'Câu sẽ được ẩn trong phiên xem hiện tại. Hệ thống thật không bị thay đổi.', body: `<p>${ctx.escapeHTML(q.text)}</p>`, confirmLabel: 'Xóa trong bản mẫu', destructive: true, onConfirm() {
      ctx.state.bankDeletedQuestions = [...(ctx.state.bankDeletedQuestions || []), q.id]; ctx.refresh(); ctx.toast('Đã xóa câu trong bản mẫu.');
    }});
  }));
  root.querySelectorAll('.question-details').forEach(el => el.addEventListener('toggle', () => {
    if (!el.isConnected) return;
    if (el.open) ctx.state.bankExpandedQuestion = el.closest('.question-card').id.replace('demo-q-', '');
    else if (ctx.state.bankExpandedQuestion === el.closest('.question-card').id.replace('demo-q-', '')) ctx.state.bankExpandedQuestion = '';
  }));
  root.querySelector('[data-action=bank-catalog]')?.addEventListener('click', () => ctx.openDialog({title: ctx.state.role === 'admin' ? 'Danh mục kiến thức' : 'Xem danh mục kiến thức',
    description: 'Danh mục minh họa trong bản mẫu Modern White Academy.', body: `<div class="table-wrap"><table class="data-table"><thead><tr><th scope="col">Mã / nhóm</th><th scope="col">Dạng kiến thức</th><th scope="col">Trạng thái</th></tr></thead><tbody>${categories(ctx).map(([key, label]) => `<tr><td>${mode(ctx) === 'research' ? `9C8-i-${key}` : ctx.escapeHTML(key)}</td><td>${ctx.escapeHTML(label)}</td><td>${ctx.badge('Đang dùng', 'success')}</td></tr>`).join('')}</tbody></table></div>`, confirmLabel: 'Đóng danh mục', onConfirm() {}}));
}
