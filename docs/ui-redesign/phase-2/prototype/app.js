import { icon, badge, button, escapeHTML, toast, openDialog } from './ui.js';
import { renderBanks, bindBanks, renderBank, bindBank } from './bank.js';
import { renderAssessments, bindAssessments, renderEditor, bindEditor, renderTake, bindTake, renderResult, bindResult, setExamContext } from './exams.js';

const state = { role: 'teacher', bankMode: 'research', scope: 'all', scenario: 'normal', examContext: 'standalone', assessmentTab: 'all' };
const labels = { banks: 'Danh sách ngân hàng', bank: 'Chi tiết ngân hàng', assessments: 'Quản lý đề kiểm tra', editor: 'Biên soạn đề', take: 'Làm bài', result: 'Kết quả', components: 'Hệ thống thành phần', specs: 'Phạm vi thiết kế' };
let view = location.hash.slice(1) in labels ? location.hash.slice(1) : 'bank';
const ctx = { state, icon, badge, button, escapeHTML, toast, openDialog, go, refresh: () => render(false) };
const views = { banks: [renderBanks, bindBanks], bank: [renderBank, bindBank], assessments: [renderAssessments, bindAssessments], editor: [renderEditor, bindEditor], take: [renderTake, bindTake], result: [renderResult, bindResult], components: [renderComponents, bindComponents], specs: [renderSpecs, () => {}] };
const specGroups = [
  ['Tài khoản và khung chung', 'Đăng nhập, đăng ký, hồ sơ, điều hướng và trang lỗi.', 'Phase 3', ['login.html', 'register.html', 'profile.html', 'base.html', 'errors/*.html']],
  ['Ngân hàng và phân loại', 'Danh sách, tạo/sửa, câu hỏi, kiến thức và đánh giá phân loại.', 'Phase 4', ['question_banks.html', 'question_bank_form.html', 'question_bank_detail.html', 'question_bank_classification.html', 'curriculum_catalog.html', 'classification_evaluation.html']],
  ['Nhập liệu và biên soạn', 'Nhập LaTeX, đối chiếu trùng, chọn câu và biên soạn đề.', 'Phase 5', ['question_bank_import.html', 'assessment_from_bank.html', 'assessment_import.html']],
  ['Kiểm tra và kết quả', 'Danh sách đề, ma trận, làm bài và đối chiếu kết quả.', 'Phase 6', ['assessment_list.html', 'assessment_matrix.html', 'exam_take.html', 'exam_result.html']],
  ['Học tập cá nhân hóa', 'Đầu vào, tự luyện, tiến độ, theo dõi giáo viên và bản nháp.', 'Phase 7', ['diagnostic_list.html', 'diagnostic_form.html', 'practice_home.html', 'practice_progress.html', 'teacher_practice_list.html', 'teacher_practice_detail.html', 'practice_draft.html']],
  ['Quản lý và báo cáo', 'Tổng quan, lớp học, người dùng, báo cáo và cài đặt AI.', 'Phase 8', ['index.html', 'courses.html', 'course_form.html', 'course_detail.html', 'my_students.html', 'manage_users.html', 'edit_user.html', 'ai_reports.html', 'teacher_ai_settings.html']]
];
function go(next) {
  if (!(next in views)) return;
  state.scenario = 'normal';
  if (location.hash.slice(1) === next) { view = next; render(true); }
  else location.hash = next;
}
function shell(content) {
  const exam = view === 'take';
  const active = ['banks', 'bank'].includes(view) ? 'banks' : ['assessments', 'editor', 'result'].includes(view) ? 'assessments' : view;
  const link = (title, target, i) => `<a class="nav-link${active === target ? ' is-active' : ''}" href="#${target}"${active === target ? ' aria-current="page"' : ''}>${icon(i)}<span>${title}</span>${active === target ? `<span class="nav-arrow">${icon('ChevronRight', 14)}</span>` : ''}</a>`;
  return `<button class="sidebar-scrim" data-menu-close aria-label="Đóng điều hướng"></button><aside class="sidebar" id="main-nav" aria-label="Điều hướng bản mẫu"><a class="brand" href="#bank"><img src="../../../../static/images/logo-transparent.png" alt=""><span><strong>LinhEdu</strong><small>HỌC THEO NĂNG LỰC</small></span></a>
    <nav><div class="nav-group"><div class="nav-caption">Không gian giảng dạy</div>${link('Ngân hàng câu hỏi', 'banks', 'Database')}${link('Đề kiểm tra', 'assessments', 'ClipboardList')}${link('Mẫu làm bài', 'take', 'BookOpen')}</div><div class="nav-group"><div class="nav-caption">Duyệt thiết kế</div>${link('Thành phần giao diện', 'components', 'Layers')}${link('Toàn bộ màn hình', 'specs', 'LayoutDashboard')}</div></nav>
    <div class="sidebar-bottom"><div class="review-note"><strong>Modern White Academy</strong>Bản mẫu Phase 2<br>Dữ liệu minh họa, thao tác trong phiên xem.</div></div><div class="sidebar-user"><span class="avatar">${state.role === 'admin' ? 'QT' : 'LA'}</span><div><strong>${state.role === 'admin' ? 'Quản trị minh họa' : 'Giáo viên Lan Anh'}</strong><small>${state.role === 'admin' ? 'Quản trị viên' : 'Không gian giáo viên'}</small></div></div></aside>
    <div class="app-main"><header class="topbar"><div class="topbar-left"><button class="icon-btn mobile-menu" data-menu-open aria-controls="main-nav" aria-expanded="false" aria-label="Mở điều hướng">${icon('Menu')}</button>${exam ? `<a href="#assessments" class="text-small">${icon('BookOpen',20)} LinhEdu</a>` : ''}<span class="topbar-title"><span class="desktop-context">${exam ? 'Không gian học tập' : 'Không gian giảng dạy'} &nbsp; / &nbsp; </span><strong>${labels[view]}</strong></span></div><div class="topbar-right"><button type="button" class="btn btn-ghost header-help" data-help>${icon('CircleHelp',17)} Hướng dẫn xem</button><span class="header-divider"></span><span class="avatar" aria-label="${exam ? 'Học sinh minh họa' : 'Tài khoản minh họa'}">${exam ? 'HS' : state.role === 'admin' ? 'QT' : 'LA'}</span></div></header>
    <div class="reviewbar" aria-label="Điều khiển duyệt thiết kế"><span class="review-label">${icon('Monitor',14)} Bản mẫu · Phase 2</span><span class="text-muted">Dữ liệu minh họa</span><div class="review-controls"><label>Màn hình<select id="review-view">${Object.entries(labels).map(([k,v])=>`<option value="${k}"${k===view?' selected':''}>${v}</option>`).join('')}</select></label>${['take','result'].includes(view) ? `<label>Ngữ cảnh<select id="review-context"><option value="standalone"${state.examContext==='standalone'?' selected':''}>Kiểm tra</option><option value="diagnostic"${state.examContext==='diagnostic'?' selected':''}>Đầu vào</option><option value="practice"${state.examContext==='practice'?' selected':''}>Tự luyện</option></select></label>` : `<label>Vai trò<select id="review-role"><option value="teacher"${state.role==='teacher'?' selected':''}>Giáo viên</option><option value="admin"${state.role==='admin'?' selected':''}>Quản trị viên</option></select></label>`}<label>Trạng thái<select id="review-scenario"><option value="normal"${state.scenario==='normal'?' selected':''}>Có dữ liệu</option><option value="empty"${state.scenario==='empty'?' selected':''}>Trống</option><option value="loading"${state.scenario==='loading'?' selected':''}>Đang tải</option><option value="error"${state.scenario==='error'?' selected':''}>Lỗi tải</option></select></label></div></div>
    <main class="page-content" id="view" tabindex="-1" aria-label="${labels[view]}">${content}</main></div>`;
}
function scenario() {
  const head = `<div class="page-heading"><div class="heading-copy"><h1>${labels[view]}</h1><p>Trạng thái thành phần minh họa để duyệt cách trình bày.</p></div></div>`;
  if (state.scenario === 'loading') return `${head}<section class="panel loading-panel" aria-busy="true" aria-label="Đang tải dữ liệu mẫu"><p role="status">Đang tải nội dung…</p><div class="skeleton"></div><div class="skeleton large"></div><div class="skeleton large"></div><div class="skeleton"></div></section>`;
  const error = state.scenario === 'error';
  return `${head}<section class="empty-state" ${error ? 'role="alert"' : 'role="status"'}>${icon(error?'CircleAlert':'Files',36)}<h2>${error?'Chưa thể tải nội dung':'Chưa có nội dung trong phạm vi này'}</h2><p>${error?'Kết nối bị gián đoạn. Thử tải lại để tiếp tục xem bản mẫu.':'Khi có dữ liệu phù hợp, nội dung sẽ xuất hiện tại đây. Bạn có thể quay về trạng thái có dữ liệu để xem bố cục.'}</p>${button(error?'Thử lại':'Xem dữ liệu minh họa','recover','primary',error?'RefreshCw':'ArrowRight')}</section>`;
}
function renderComponents() {
  return `<div class="page-heading"><div class="heading-copy"><p class="breadcrumb">Duyệt thiết kế / Thành phần</p><h1>Một hệ thống, toàn bộ LinhEdu</h1><p>Bề mặt trắng, xanh học thuật và phân cấp rõ cho cả quản lý lẫn học tập.</p></div>${button('Xem mẫu ngân hàng','demo-bank','primary','ArrowRight')}</div>
  <section class="system-section"><div class="section-heading"><h2>Màu sắc</h2><span class="text-small text-muted">Một màu chính, trạng thái có ngữ nghĩa</span></div><div class="swatches">${[['primary','Xanh học thuật','#1D4ED8'],['surface','Bề mặt','#FFFFFF'],['canvas','Nền ứng dụng','#F5F7FB'],['text','Nội dung chính','#0F172A'],['muted','Nội dung phụ','#596579']].map(([c,t,v])=>`<div class="swatch"><div class="swatch-color swatch-${c}"></div><div class="swatch-copy"><strong>${t}</strong><span>${v}</span></div></div>`).join('')}</div></section>
  <section class="system-section panel"><div class="panel-heading"><h2>Chữ và nhịp điệu</h2><span class="text-small text-muted">Be Vietnam Pro</span></div><div class="panel-body"><p class="type-demo">Học đúng năng lực. Tiến bộ mỗi ngày.</p><p>Tiêu đề trang 26px · Nội dung quản lý 14px · Nội dung câu hỏi 18px</p><p class="text-small text-muted">Khoảng cách 4 / 8 / 12 / 16 / 24 / 32px. Bo góc 8px cho điều khiển, 12px cho vùng nội dung. Viền nhẹ, bóng dành cho hộp thoại.</p></div></section>
  <div class="system-grid system-section"><section class="panel"><div class="panel-heading"><h2>Nút và trạng thái</h2></div><div class="panel-body"><div class="component-row">${button('Lưu thay đổi','demo-save','primary','Save')}${button('Xem trước','demo-preview','secondary','Eye')}${button('Đặt lại','demo-reset','ghost')}</div><div class="component-row"><button type="button" class="btn" disabled>Chưa đủ điều kiện</button><button type="button" class="btn" disabled aria-busy="true">Đang xử lý…</button></div><div class="component-row">${badge('Đã giao','success')}${badge('Chờ xác nhận','warning')}${badge('Bản nháp')}${badge('Không hợp lệ','danger')}</div></div></section><section class="panel"><div class="panel-heading"><h2>Biểu mẫu</h2></div><form class="panel-body" id="component-form"><div class="field"><label for="sample-title">Tên đề kiểm tra</label><input id="sample-title" required placeholder="Nhập tên đề" aria-describedby="sample-title-hint"><small id="sample-title-hint">Nhãn luôn hiển thị, không phụ thuộc placeholder.</small></div><div class="field"><label for="sample-class">Lớp nhận đề</label><select id="sample-class"><option>Lớp 9A1</option><option>Lớp 9A2</option></select></div><button type="submit" class="btn btn-primary">Kiểm tra biểu mẫu</button></form></section></div>
  <section class="system-section"><div class="section-heading"><h2>Phản hồi và xác nhận</h2></div><div class="notice notice-info">${icon('Info')}<span>Ngân hàng chung chỉ đọc. Bạn vẫn có thể thêm câu riêng của mình.</span></div><div class="notice notice-warning">${icon('TriangleAlert')}<span>Còn câu hỏi chưa xác nhận nhãn kiến thức. Đối chiếu trước khi giao đề.</span></div><div class="notice notice-success">${icon('CircleCheck')}<span>Nội dung hợp lệ. Các thông báo luôn dùng cả chữ và màu.</span></div>${button('Xem hộp thoại xác nhận','demo-dialog','secondary','Trash2')}</section>`;
}
function bindComponents(root) {
  root.addEventListener('click', e => {
    const action = e.target.closest('[data-action]')?.dataset.action;
    if (action === 'demo-bank') go('bank');
    if (action === 'demo-save') toast('Đã minh họa phản hồi lưu. Web hiện tại không thay đổi.');
    if (action === 'demo-preview') go('take');
    if (action === 'demo-reset') { root.querySelector('#component-form').reset(); toast('Đã đặt lại biểu mẫu minh họa.'); }
    if (action === 'demo-dialog') openDialog({ title: 'Xóa ngân hàng minh họa?', description: 'Hộp thoại kiểm tra xác nhận, bàn phím và focus. Đây là dữ liệu mẫu.', body: '<p>Thao tác thật sẽ xóa ngân hàng và câu hỏi liên quan. Bản mẫu này chỉ hiển thị phản hồi.</p>', destructive: true, confirmLabel: 'Xóa trong bản mẫu', onConfirm: () => toast('Đã xác nhận thao tác minh họa.') });
  });
  root.querySelector('#component-form').addEventListener('submit', e => { e.preventDefault(); toast('Biểu mẫu minh họa hợp lệ.'); });
}
function renderSpecs() {
  return `<div class="page-heading"><div class="heading-copy"><p class="breadcrumb">Duyệt thiết kế / Toàn bộ màn hình</p><h1>Thiết kế lại toàn bộ giao diện</h1><p>32 template trang đang hoạt động, khung chung, component và trang lỗi đều có đặc tả chuyển đổi.</p></div><a class="btn btn-secondary" href="../../phase-2-screen-specs.md" target="_blank" rel="noopener">${icon('FileText')} Đọc đặc tả đầy đủ</a></div><div class="notice notice-info">${icon('Info')}<span>Phase 2 cung cấp hệ thống và bản mẫu để duyệt. Các phase 3–8 triển khai từng nhóm màn hình; Phase 9 dọn sạch giao diện cũ.</span></div><div class="system-grid">${specGroups.map(([title,desc,phase,files])=>`<section class="panel"><div class="panel-heading"><h2>${title}</h2>${badge(phase,'info')}</div><div class="panel-body"><p>${desc}</p><details><summary class="text-primary text-small">Các template trong phạm vi</summary><ul class="spec-file-list">${files.map(f=>`<li>${f}</li>`).join('')}</ul></details></div></section>`).join('')}</div>`;
}
function renderMath() {
  if (window.MathJax?.typesetPromise) window.MathJax.typesetPromise([document.getElementById('view')]).catch(() => {});
}
function render(focus) {
  const savedScroll = window.scrollY;
  const content = state.scenario === 'normal' ? views[view][0](ctx) : scenario();
  document.body.classList.toggle('is-exam', view === 'take');
  if (window.MathJax?.typesetClear) window.MathJax.typesetClear();
  document.getElementById('app').innerHTML = shell(content);
  document.title = `${labels[view]} · LinhEdu · Bản mẫu Phase 2`;
  const root = document.getElementById('view');
  if (state.scenario === 'normal') views[view][1](root, ctx);
  root.querySelector('[data-action="recover"]')?.addEventListener('click', () => { state.scenario = 'normal'; render(true); });
  document.getElementById('review-view').addEventListener('change', e => go(e.target.value));
  document.getElementById('review-scenario').addEventListener('change', e => { state.scenario = e.target.value; render(false); document.getElementById('review-scenario').focus(); });
  document.getElementById('review-role')?.addEventListener('change', e => { state.role = e.target.value; render(false); document.getElementById('review-role').focus(); });
  document.getElementById('review-context')?.addEventListener('change', e => { setExamContext(ctx,e.target.value); render(false); document.getElementById('review-context').focus(); });
  const side = document.querySelector('.sidebar'), scrim = document.querySelector('.sidebar-scrim'), menu = document.querySelector('[data-menu-open]');
  function toggleMenu(open) { side.classList.toggle('is-open',open); scrim.classList.toggle('is-open',open); menu.setAttribute('aria-expanded',String(open)); document.querySelector('.app-main').inert = open; if(open) { side.setAttribute('role','dialog'); side.setAttribute('aria-modal','true'); side.querySelector('a').focus(); } else { side.removeAttribute('role'); side.removeAttribute('aria-modal'); menu.focus(); } }
  menu.addEventListener('click', () => toggleMenu(true));
  document.querySelector('[data-menu-close]').addEventListener('click', () => toggleMenu(false));
  document.querySelector('[data-help]').addEventListener('click', () => openDialog({ title: 'Duyệt bản mẫu Phase 2', description: 'Modern White Academy cho LinhEdu.', body: '<p>Dùng menu hoặc bộ chọn Màn hình để chuyển trang. Đổi vai trò, loại ngân hàng, ngữ cảnh làm bài và trạng thái để kiểm tra các biến thể.</p><p>Tìm kiếm, bộ lọc, mở đáp án, soạn câu, lưu/giao/nộp đề là thao tác minh họa. Dữ liệu chỉ nằm trong bộ nhớ và mất khi tải lại trang.</p><p>Đặc tả toàn bộ màn hình nằm trong mục Toàn bộ màn hình.</p>', confirmLabel: 'Đã hiểu' }));
  if (focus) { window.scrollTo(0,0); root.focus({preventScroll:true}); } else window.scrollTo(0,savedScroll);
  renderMath();
}
document.addEventListener('keydown', e => {
  const drawer = document.querySelector('.sidebar.is-open');
  if (!drawer) return;
  if (e.key === 'Escape') document.querySelector('[data-menu-close]').click();
  if (e.key === 'Tab') {
    const items = [...drawer.querySelectorAll('a,button:not([disabled])')], first = items[0], last = items.at(-1);
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
});
window.addEventListener('hashchange', () => { const next=location.hash.slice(1); if(next in views) { view=next; state.scenario='normal'; render(true); } });
window.addEventListener('math-ready', renderMath);
render(false);
