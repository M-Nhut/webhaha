/* Dedicated reports: observed charts and persisted API analysis share a scope. */
(() => {
  const root = document.getElementById('ai-report-workspace');
  if (!root) return;
  const el = id => document.getElementById(`ai-${id}`);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const detail = root.dataset.detail === 'true';
  const series = [{key:'correct', label:'Đúng', token:'--color-success'}, {key:'wrong', label:'Sai', token:'--color-danger'}, {key:'partial', label:'Chưa đủ ý', token:'--color-warning'}];
  const number = value => value === null || value === undefined ? '—' : escape(value);
  const canFilterSkill = code => Array.from(el('skill')?.options || []).some(option => option.value === code);
  let barChart;
  const sources = {standalone:'Đề kiểm tra', initial_diagnostic:'Đánh giá đầu vào', practice:'Tự luyện'};
  let data, sequence = 0, generating = false, pollTimer, pollUntil = 0;
  const date = value => {
    if (!value) return 'Chưa tạo';
    const parsed = new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : value + 'Z');
    return Number.isNaN(parsed.getTime()) ? 'Chưa rõ thời điểm' : parsed.toLocaleString('vi-VN');
  };
  function notice(message, error = false) {
    el('message').hidden = !message;
    el('message').textContent = message;
    el('message').classList.toggle('is-error', error);
  }
  function pageLink(studentId, mode = '') {
    const url = new URL(studentId ? root.dataset.personalUrl : root.dataset.pageUrl, location.origin);
    const current = new URL(location.href);
    for (const key of ['skill', 'source', 'question_type']) {
      const value = current.searchParams.get(key);
      if (value) url.searchParams.set(key, value);
    }
    if (studentId) url.searchParams.set('student_id', studentId);
    if (mode) url.searchParams.set('view', mode);
    return url.pathname + url.search;
  }
  function apiUrl() {
    const url = new URL(root.dataset.apiUrl, location.origin);
    if (root.dataset.studentId) url.searchParams.set('student_id', root.dataset.studentId);
    if (detail) { url.searchParams.set('analysis', '1'); url.searchParams.set('include_archive', '1'); }
    if (!detail) for (const key of ['skill', 'source', 'question_type']) {
      const value = el('filters').elements[key].value;
      if (value) url.searchParams.set(key, value);
    }
    return url;
  }
  async function request(url, payload) {
    const options = payload ? {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken':document.querySelector('meta[name="csrf-token"]').content}, body:JSON.stringify(payload)} : {};
    const response = await fetch(url, {...options, cache:'no-store'});
    let result;
    try { result = await response.json(); } catch (_) { throw new Error('Không thể đọc báo cáo. Kiểm tra phiên đăng nhập rồi thử tải lại.'); }
    if (!response.ok) throw new Error(result.error || 'Không thể tải báo cáo. Hãy thử lại.');
    return result;
  }
  function skillName(code) {
    return data.overview.by_skill.find(row => row.code === code)?.name || code || 'Chưa phân loại';
  }
  function renderKpis(overview) {
    const n = overview.counts;
    const weak = overview.by_skill.filter(row => row.total && (row.wrong || row.partial)).sort((a, b) => (b.wrong - a.wrong) || ((b.wrong + b.partial) - (a.wrong + a.partial)) || ((a.correct_percent ?? 101) - (b.correct_percent ?? 101)))[0];
    const items = [root.dataset.studentId ? ['Bài đã chấm', n.submission_count, 'trong phạm vi đang chọn'] : ['Học sinh có dữ liệu', `${overview.students_with_data}/${overview.roster_count}`, 'trong phạm vi đang chọn'],
      ['Tỷ lệ đúng', n.correct_percent == null ? '—' : `${n.correct_percent}%`, n.total ? `${n.correct}/${n.total} lượt trả lời` : 'Chưa có dữ liệu'],
      ['Dạng cần xem lại nhất', weak ? weak.name : '—', weak ? `${weak.wrong} sai · ${weak.partial} chưa đủ ý trên ${weak.total} lượt` : (n.total ? 'Chưa ghi nhận lỗi trong phạm vi này' : 'Chưa có dữ liệu'), 'is-text']];
    el('kpis').innerHTML = items.map(([label, value, note, cls]) => `<div class="ai-kpi"><span>${escape(label)}</span><strong class="${cls || ''}">${escape(value)}</strong><small>${escape(note)}</small></div>`).join('');
  }
  function renderCharts(overview) {
    barChart?.destroy();
    barChart = null;
    const rows = [...overview.by_skill].sort((a, b) => ((b.total ? 0 : 1) - (a.total ? 0 : 1)) || ((a.correct_percent ?? 101) - (b.correct_percent ?? 101)) || (b.total - a.total));
    const total = overview.counts.total;
    const style = getComputedStyle(document.documentElement);
    const color = name => style.getPropertyValue(name).trim();
    const animation = matchMedia('(prefers-reduced-motion: reduce)').matches ? false : {duration: 180};
    const chartFont = {family: color('--font-sans'), size: parseFloat(color('--size-xs')) || 14};
    const missingChart = '<p class="ai-empty">Biểu đồ chưa tải được. Các số liệu chính vẫn có ở phần KPI phía trên.</p>';
    el('bars').innerHTML = total ? '<div class="ai-chart-scroll" tabindex="0" role="region" aria-label="Biểu đồ kết quả theo dạng kiến thức, cuộn ngang để xem đủ"><div class="ai-chart-plot"><canvas id="ai-bar-canvas" role="img" aria-label="Biểu đồ cột kết quả theo dạng kiến thức, xếp từ dạng yếu nhất lên."></canvas></div></div><p class="ai-chart-scale">Đơn vị: lượt trả lời đã chấm. Số phần trăm dưới tên dạng là tỷ lệ đúng của dạng đó. Dạng chưa có dữ liệu không có cột.</p>' : '<p class="ai-empty">Chưa có câu trả lời đã chấm trong bộ lọc này.</p>';
    if (total && window.Chart) {
      try {
        barChart = new window.Chart(document.getElementById('ai-bar-canvas'), {
          type: 'bar',
          data: {labels: rows.map(row => row.name.match(/^Dạng \d+/)?.[0] || row.name), datasets: series.map(item => ({label: item.label, data: rows.map(row => row.total ? row[item.key] : null), backgroundColor: color(item.token), borderRadius: 3, maxBarThickness: 24}))},
          options: {
            responsive: true, maintainAspectRatio: false, animation,
            plugins: {legend: {display: false}, tooltip: {titleFont: {...chartFont, weight: '600'}, bodyFont: chartFont, callbacks: {title: items => rows[items[0]?.dataIndex]?.name || '', label: item => `${item.dataset.label}: ${item.formattedValue} lượt`}}},
            scales: {y: {beginAtZero: true, ticks: {precision: 0, color: color('--color-text-muted'), font: chartFont}, grid: {color: color('--color-border')}, border: {display: false}}, x: {ticks: {color: color('--color-text-muted'), font: chartFont, maxRotation: 0, callback: function (value) { const row = rows[value]; const short = row.name.match(/^Dạng \d+/)?.[0] || row.name; return row.total && row.correct_percent != null ? `${short} · ${row.correct_percent}%` : short; }}, grid: {display: false}, border: {display: false}}},
            onClick: (_event, items) => { const code = rows[items[0]?.index]?.code; if (code && canFilterSkill(code)) { el('skill').value = code; el('filters').requestSubmit(); } }
          }
        });
      } catch (_) { barChart?.destroy(); el('bars').innerHTML = missingChart; }
    } else if (total) { el('bars').innerHTML = missingChart; }
  }
  function renderStudents(overview) {
    if (!el('student-table')) return;
    el('roster-count').textContent = `${overview.students_with_data}/${overview.roster_count} học sinh có dữ liệu`;
    el('student-table').innerHTML = overview.students.length ? `<table><thead><tr><th>Học sinh</th><th>Tỷ lệ đúng</th><th>Dạng cần xem lại</th><th></th></tr></thead><tbody>${overview.students.map(student => `<tr><td><strong>${escape(student.display_name)}</strong><br><small>${number(student.submission_count)} bài đã chấm · ${number(student.total)} lượt trả lời</small></td><td>${student.correct_percent == null ? 'Chưa có dữ liệu' : student.correct_percent + '%'}</td><td>${student.focus_skill ? escape(skillName(student.focus_skill)) : student.total ? 'Chưa ghi nhận lỗi' : 'Chưa có dữ liệu'}</td><td>${student.student_id ? `<a class="btn btn-secondary btn-sm" href="${escape(pageLink(student.student_id))}">Xem cá nhân</a>` : '—'}</td></tr>`).join('')}</tbody></table>` : '<p>Chưa có học sinh trong lớp.</p>';
  }
  function evidenceItem(event, open = false) {
    let image = '';
    if (event.image_url) {
      try {
        const url = new URL(event.image_url, location.origin);
        if (['http:', 'https:'].includes(url.protocol)) image = `<img class="ai-evidence-image" src="${escape(url.href)}" alt="Hình minh họa câu hỏi" loading="lazy">`;
      } catch (_) { /* Invalid image paths do not obscure the answer evidence. */ }
    }
    const outcome = series.find(s => s.key === event.outcome)?.label || 'Chưa xác định';
    const statements = (event.statement_results || []).map(statement => `<tr><td>${escape(statement.label)}. <span class="katex-render">${escape(statement.text)}</span></td><td>${statement.actual === true ? 'Đúng' : statement.actual === false ? 'Sai' : 'Bỏ trống'}</td><td>${statement.expected === true ? 'Đúng' : statement.expected === false ? 'Sai' : 'Chưa có đáp án'}</td><td>${statement.status !== 'answered' ? 'Chưa trả lời' : statement.correct ? 'Đúng' : 'Sai'}</td></tr>`).join('');
    return `<details class="ai-evidence-item" ${open ? 'open' : ''}><summary><span>${escape(event.display_name)}</span><span>${escape(event.skill_name || skillName(event.curriculum_code))}</span><span class="badge ${event.outcome === 'correct' ? 'badge-present' : event.outcome === 'wrong' ? 'badge-absent' : 'badge-upcoming'}">${outcome}</span></summary><div class="ai-evidence-body">${event.question_context ? `<p class="katex-render">${escape(event.question_context)}</p>` : ''}${image}<div class="question-prompt"><p class="katex-render">${escape(event.question_text)}</p></div><div class="ai-evidence-answer"><strong>Học sinh trả lời:</strong> <span class="katex-render">${escape(event.actual_answer_text || 'Chưa trả lời đầy đủ')}</span></div><div class="ai-evidence-answer is-key"><strong>Đáp án chuẩn:</strong> <span class="katex-render">${escape(event.expected_answer_text || 'Xem các ý bên dưới')}</span></div>${statements ? `<div class="ai-table-scroll"><table><thead><tr><th>Ý / phát biểu</th><th>Học sinh</th><th>Đáp án</th><th>Kết quả</th></tr></thead><tbody>${statements}</tbody></table></div>` : ''}<small>${escape(sources[event.assessment_source] || 'Bài đã chấm')} · ${escape(date(event.occurred_at))} · Bài #${escape(event.submission_id)}<br>Mã bằng chứng: ${escape(event.event_ref)}</small></div></details>`;
  }
  function evidenceDetails(refs) {
    const wanted = new Set(refs || []);
    const evidence = data.evidence.filter(event => wanted.has(event.event_ref));
    return evidence.length ? `<details><summary>Đối chiếu ${evidence.length} bằng chứng</summary>${evidence.map(event => evidenceItem(event)).join('')}</details>` : '';
  }
  function analysisRows(rows, kind) {
    if (!rows?.length) {
      const name = kind === 'cause' ? 'giả thuyết nguyên nhân' : kind === 'risk' ? 'nguy cơ sai ở lần tiếp theo' : 'khuyến nghị hướng dạy';
      const hasErrors = data.evidence.some(event => event.outcome === 'wrong' || (event.statement_results || []).some(s => s.status === 'answered' && s.correct === false));
      if (data.status === 'observed') return `<p>Đang tải ${name} đã lưu…</p>`;
      if (data.status === 'processing') return `<p>AI đang phân tích ${name}…</p>`;
      if (data.status === 'completed' && !hasErrors && kind !== 'recommendation') return '<p>Chưa ghi nhận lỗi trong phạm vi này để đề xuất giả thuyết có căn cứ. Giáo viên có thể dùng bài luyện ở phần khuyến nghị để kiểm tra thêm.</p>';
      return `<p>Chưa có ${name} từ API trong bản báo cáo hiện tại. Giáo viên phụ trách có thể bấm Phân tích lại bằng AI để nhận báo cáo mới.</p>`;
    }
    return rows.map(row => {
      const fields = kind === 'recommendation' ? [
        ['learning_goal', 'Mục tiêu cần củng cố'], ['teaching_strategy', 'Cách giáo viên hướng dẫn'],
        ['teacher_question', 'Câu hỏi gợi mở'], ['practice_suggestion', 'Bài luyện gợi ý'],
        ['success_criteria', 'Tiêu chí kiểm tra tiến bộ'],
      ] : [
        ['trigger_condition', 'Khi nào có thể sai tiếp'],
        ['verification_question', kind === 'cause' ? 'Câu hỏi xác minh nguyên nhân' : 'Câu hỏi kiểm tra nguy cơ'],
        ['suggested_remediation', 'Hướng hỗ trợ ngăn lỗi lặp lại'],
      ];
      const details = fields.filter(([key]) => row[key]).map(([key, label]) => `<dt>${label}</dt><dd class="katex-render">${escape(row[key])}</dd>`).join('');
      const label = kind === 'recommendation' ? '<span class="ai-teacher-label">Hướng dạy dành cho giáo viên</span>' : `<span class="ai-hypothesis-label">${kind === 'cause' ? 'Nguyên nhân có thể có · cần kiểm chứng' : 'Nguy cơ sai tiếp · cần kiểm chứng'}</span>`;
      return `<article class="ai-analysis-item">${label}${row.skill ? `<h4>${escape(skillName(row.skill))}</h4>` : ''}<p class="katex-render">${escape(row.hypothesis || row.text || '')}</p>${details ? `<dl>${details}</dl>` : ''}${evidenceDetails(row.basis_evidence_refs)}</article>`;
    }).join('');
  }
  function renderAnalysis() {
    const analysis = data.analysis;
    const progressRows = (data.progress || []).slice(0, 3);
    if (el('progress-line')) el('progress-line').innerHTML = progressRows.length ? `<div class="ai-progress-block"><h4>Dấu hiệu tiến bộ</h4>${progressRows.map(row => `<article class="ai-analysis-item"><p><strong>${escape(skillName(row.skill))}</strong> — ${escape(row.claim)}</p>${evidenceDetails(row.evidence_refs)}</article>`).join('')}</div>` : '';
    if (el('summary')) {
      const summaryRows = detail ? (analysis?.summary || []) : (analysis?.summary || []).slice(0, 3);
      el('summary').innerHTML = summaryRows.length ? `<ul class="ai-summary-list">${summaryRows.map(row => `<li>${escape(row.text)}${evidenceDetails(row.basis_evidence_refs)}</li>`).join('')}</ul>` : !detail ? '' : data.status === 'observed' ? '<p>Đang tải tóm tắt AI đã lưu…</p>' : '<p>Chưa có tóm tắt AI trong bản báo cáo này.</p>';
    }
    if (el('highlights')) el('highlights').hidden = !(analysis?.summary?.length || progressRows.length);
    if (!detail) return;
    el('recommendation-list').innerHTML = analysisRows(analysis?.recommendations, 'recommendation');
    const hasCauses = !!analysis?.causes?.length, hasRisks = !!analysis?.risks?.length;
    el('cause-risk-list').innerHTML = (hasCauses || hasRisks)
      ? (hasCauses ? analysisRows(analysis.causes, 'cause') : '') + (hasRisks ? analysisRows(analysis.risks, 'risk') : '')
      : analysisRows(null, 'cause');
    const meta = data.metadata;
    el('meta').innerHTML = `<p class="ai-meta-line">Tạo lúc ${escape(date(meta.generated_at))} · Mô hình ${escape(meta.model_name || 'Chưa có bản AI')} · ${number(data.coverage.event_count)} lượt trả lời, ${number(data.coverage.students_with_data)}/${number(data.coverage.roster_count)} học sinh có dữ liệu${meta.review_note ? ` · Ghi chú đối chiếu: ${escape(meta.review_note)}` : ''}</p>`;
    if (el('review')) { el('review').hidden = !meta.id; el('review').disabled = data.status !== 'completed' || meta.review_status === 'confirmed'; el('review').textContent = meta.review_status === 'confirmed' ? 'Đã ghi nhận đối chiếu' : 'Ghi nhận đã đối chiếu'; }
    if (el('archive-section')) {
      el('archive-section').hidden = !data.personal_archive;
      if (data.personal_archive) {
        const archive = data.personal_archive;
        const section = archive.sections;
        const answerText = value => typeof value === 'string' ? value : JSON.stringify(value ?? 'Chưa có dữ liệu');
        el('archive').innerHTML = `<p class="ai-notice">Bản cá nhân đã lưu lúc ${escape(date(archive.generated_at))}${section.target_submission_id ? ' · Bài #' + escape(section.target_submission_id) : ''}. Đây là phạm vi của bản đã lưu; không dùng để tính biểu đồ hiện tại.</p><h4>Tóm tắt AI đã lưu</h4><p>${escape(section.summary)}</p><h4>Lỗi và giả thuyết nguyên nhân</h4>${section.errors.map(row => {
          const evidence = row.evidence;
          return `<article class="ai-analysis-item"><h4>${escape(evidence.skill_name || skillName(evidence.curriculum_code))}${row.statement_label ? ' · Ý ' + escape(row.statement_label) : ''}</h4><span class="ai-hypothesis-label">Giả thuyết cần kiểm chứng</span><p>${escape(row.hypothesis)}</p>${evidenceItem({...evidence, event_ref:evidence.evidence_ref || '', display_name:root.querySelector('.ai-scope-heading h2').textContent, outcome:'wrong', actual_answer_text:answerText(evidence.actual_answer), expected_answer_text:answerText(evidence.expected_answer)})}</article>`;
        }).join('') || '<p>Chưa có lỗi trong bản đã lưu.</p>'}<h4>Nguy cơ đã ghi nhận</h4>${section.risks.map(row => `<article class="ai-analysis-item"><p>${escape(row.hypothesis)}</p><p><strong>Điều kiện:</strong> ${escape(row.trigger_condition)}</p><p><strong>Kiểm chứng:</strong> ${escape(row.verification_question)}</p></article>`).join('') || '<p>Chưa có nguy cơ có đủ căn cứ.</p>'}<h4>Khuyến nghị đã lưu</h4>${section.recommendations.map(row => typeof row === 'string' ? `<article class="ai-analysis-item"><p>${escape(row)}</p></article>` : `<article class="ai-analysis-item"><p><strong>Câu hỏi gợi mở:</strong> ${escape(row.teacher_question)}</p><p>${escape(row.practice_suggestion)}</p></article>`).join('') || '<p>Chưa có khuyến nghị.</p>'}`;
      }
    }
  }
  function render(result) {
    if (!result.analysis && data?.analysis) result.analysis = data.analysis;
    if (!result.progress?.length && data?.progress?.length) result.progress = data.progress;
    data = result;
    root.setAttribute('aria-busy', 'false');
    el('content').hidden = false;
    const statuses = {observed:'Đang tải phân tích đã lưu', completed:'Đã có báo cáo AI', processing:'Đang phân tích', stale:'Có dữ liệu hoặc cấu hình mới', missing:'Chưa có báo cáo AI', failed:'Chưa tạo được báo cáo AI'};
    el('status').textContent = !detail ? 'Số liệu bài làm đã chấm' : data.status === 'completed' && data.metadata.review_status === 'confirmed' ? 'Đã đối chiếu báo cáo' : (statuses[data.status] || 'Chưa tải phân tích AI');
    el('updated').textContent = `Số liệu đến ${date(data.coverage.source_cutoff)}${detail && data.metadata.generated_at ? ' · AI: ' + date(data.metadata.generated_at) : ''}`;
    notice(!detail || data.status === 'completed' ? '' : data.error || (data.status === 'observed' ? 'Số liệu bài làm đã sẵn sàng. Đang tải bản phân tích AI đã lưu…' : data.status === 'processing' ? 'AI đang xử lý. Báo cáo sẽ tự cập nhật khi có kết quả.' : data.status === 'stale' ? 'Bản phân tích cần cập nhật. Bấm Phân tích lại bằng AI để nhận báo cáo mới.' : 'Chưa có báo cáo AI. Giáo viên phụ trách lớp có thể bấm Phân tích lại bằng AI.'), data.status === 'failed');
    if (!detail) { renderKpis(data.overview); renderCharts(data.overview); renderStudents(data.overview); }
    renderAnalysis();
    if (el('generate')) el('generate').disabled = generating || !data.overview.counts.total || data.status === 'processing';
    clearTimeout(pollTimer);
    if (detail && data.status === 'processing' && pollUntil > Date.now()) pollTimer = setTimeout(load, 5000);
    else if (detail && data.status === 'processing') notice('AI vẫn đang xử lý. Bấm Tải lại báo cáo để kiểm tra kết quả.');
    window.renderFormulas?.(el('content'));
  }
  async function load() {
    const current = ++sequence;
    root.setAttribute('aria-busy', 'true');
    el('reload').disabled = true;
    try { const result = await request(apiUrl()); if (current === sequence) { render(result); } return result; }
    catch (error) { if (current === sequence) { notice(error.message, true); el('status').textContent = 'Chưa tải được dữ liệu'; } }
    finally { if (current === sequence) { root.setAttribute('aria-busy', String(generating)); el('reload').disabled = generating; } }
  }
  el('reload').addEventListener('click', load);
  el('filters')?.addEventListener('submit', event => {
    event.preventDefault();
    const url = new URL(location.href);
    for (const key of ['skill', 'source', 'question_type']) {
      const value = el('filters').elements[key].value;
      value ? url.searchParams.set(key, value) : url.searchParams.delete(key);
      el('context-form').elements[key].value = value;
    }
    history.replaceState(null, '', url);
    root.querySelectorAll('.ai-view-tabs a').forEach(link => { const target = new URL(link.href); for (const key of ['skill', 'source', 'question_type']) { const value = url.searchParams.get(key); value ? target.searchParams.set(key, value) : target.searchParams.delete(key); } link.href = target; });
    load();
  });
  el('reset')?.addEventListener('click', () => { for (const key of ['skill','source','question_type']) el('filters').elements[key].value = ''; el('filters').requestSubmit(); });
  root.addEventListener('toggle', event => { if (event.target.open) window.renderFormulas?.(event.target); }, true);
  async function refreshAnalysis() {
    if (generating) return;
    if (data?.status === 'processing') { pollUntil = Date.now() + 360000; await load(); return; }
    if (!data?.overview.counts.total) { notice('Chưa có bài làm đã chấm trong phạm vi này để phân tích AI.'); return; }
    generating = true; el('generate').disabled = true;
    el('reload').disabled = true;
    root.setAttribute('aria-busy', 'true');
    el('status').textContent = 'Đang nhận phân tích mới';
    notice('Đang gửi bài làm để AI phân tích lại. Kết quả sẽ hiển thị khi API trả về.');
    for (const name of ['summary', 'cause-risk-list', 'recommendation-list']) el(name).textContent = 'Đang nhận kết quả từ AI…';
    if (el('review')) el('review').hidden = true;
    try {
      await request(root.dataset.generateUrl, {force:true});
      pollUntil = Date.now() + 360000;
      const result = await load();
      if (!result) for (const name of ['summary', 'cause-risk-list', 'recommendation-list']) el(name).textContent = 'Chưa tải được kết quả. Bấm Tải lại báo cáo để thử lại.';
    } catch (error) {
      const result = await load();
      if (!result) for (const name of ['summary', 'cause-risk-list', 'recommendation-list']) el(name).textContent = 'Chưa nhận được kết quả AI. Hãy thử lại.';
      notice(`Chưa nhận được phân tích mới: ${error.message}`, true);
    } finally {
      generating = false;
      root.setAttribute('aria-busy', 'false');
      el('reload').disabled = false;
      el('generate').disabled = !data?.overview.counts.total || data?.status === 'processing';
    }
  }
  el('generate')?.addEventListener('click', refreshAnalysis);
  el('detail-link')?.addEventListener('click', event => {
    if (detail && el('generate')) { event.preventDefault(); refreshAnalysis(); }
  });
  el('review')?.addEventListener('click', async () => {
    const id = data?.metadata.id;
    if (!id) return;
    el('review').disabled = true;
    try { await request(root.dataset.reviewUrl.replace('/0/review', `/${id}/review`), {status:'confirmed'}); await load(); }
    catch (error) { notice(error.message, true); el('review').disabled = false; }
  });
  window.addEventListener('pagehide', () => { clearTimeout(pollTimer); });
  // Facts are embedded with the page, so the overview needs no AI/network wait.
  const initial = document.getElementById('ai-initial-data');
  let initialRendered = false;
  if (initial) {
    try {
      render(JSON.parse(initial.textContent));
      initialRendered = true;
    } catch (error) {
      console.error('[AIReports] Unable to render initial report:', error);
      root.setAttribute('aria-busy', 'false');
      notice('Đang tải lại số liệu báo cáo…');
    }
  }
  if (detail) {
    const url = new URL(location.href);
    url.searchParams.delete('refresh');
    history.replaceState(null, '', url);
    if (root.dataset.refresh === 'true' && el('generate')) refreshAnalysis();
    else { pollUntil = Date.now() + 360000; load(); }
  } else if (!initialRendered) {
    load();
  }
})();
