/* Modern White Academy diagnostic authoring. Server revalidates the frozen review on publication. */
(() => {
  'use strict';
  const root = document.getElementById('diagnostic-wizard');
  if (!root) return;
  const config = JSON.parse(document.getElementById('dw-config').textContent);
  const get = id => document.getElementById(`dw-${id}`);
  const selected = new Map();
  const candidates = new Map();
  const storageKey = `linhedu:diagnostic-wizard:${config.userId}`;
  const levels = {nhan_biet: 'Nhận biết', thong_hieu: 'Thông hiểu', van_dung: 'Vận dụng', van_dung_cao: 'Vận dụng cao'};
  let bankId = '', step = 1, page = 1, pages = 1, revision = 0;
  let loading = false, reviewing = false, publishing = false;
  let listController, listVersion = 0, searchTimer, reviewData = null, reviewObserver = null;
  const readQuestions = new Set();

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text != null) element.textContent = String(text);
    return element;
  }

  function feedback(message = '', error = false, focus = false) {
    get('feedback').textContent = message;
    get('feedback').classList.toggle('is-error', error);
    get('feedback').setAttribute('role', error ? 'alert' : 'status');
    if (focus && message) get('feedback').focus();
  }

  function goTo(next) {
    step = next;
    root.querySelectorAll('[data-step]').forEach(section => { section.hidden = Number(section.dataset.step) !== next; });
    root.querySelectorAll('[data-progress-step]').forEach(item => {
      const current = Number(item.dataset.progressStep);
      item.classList.toggle('is-complete', current < next);
      if (current === next) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    });
    get(`heading-${next}`).focus();
    get(`heading-${next}`).scrollIntoView({block: 'start'});
  }

  function persist() {
    // Store small selections only; full answers and review payload stay in memory.
    try {
      sessionStorage.setItem(storageKey, JSON.stringify({bankId, selected: Array.from(selected.values()), savedAt: Date.now()}));
    } catch (_) { /* The wizard still works when browser storage is unavailable. */ }
  }

  function invalidateReview() {
    revision += 1;
    reviewData = null;
    reviewObserver?.disconnect();
    readQuestions.clear();
    get('confirm').disabled = true;
    get('review-digest').value = '';
    get('confirm').checked = false;
    get('publish').disabled = true;
    persist();
  }

  const counts = () => {
    const result = Object.fromEntries(Object.keys(config.quotas).map(kind => [kind, 0]));
    selected.forEach(question => { if (question.question_type in result) result[question.question_type] += 1; });
    return result;
  };
  const coverage = () => new Set(Array.from(selected.values(), question => question.skill).filter(code => config.skills.includes(code)));
  const complete = () => selected.size === config.total && Array.from(selected.values()).every(question => question.selectable !== false) && Object.entries(config.quotas).every(([kind, limit]) => counts()[kind] === limit) && coverage().size === config.skills.length;

  function updateControls() {
    const used = counts();
    get('review').disabled = loading || reviewing || !complete();
    get('back-bank').disabled = reviewing;
    ['search', 'kind', 'level', 'skill'].forEach(id => { get(id).disabled = reviewing; });
    get('prev-page').disabled = loading || reviewing || page <= 1;
    get('next-page').disabled = loading || reviewing || page >= pages;
    root.querySelectorAll('[data-remove-question]').forEach(button => { button.disabled = reviewing; });
    candidates.forEach(({question, checkbox, card, reason}) => {
      const chosen = selected.has(question.id);
      const full = selected.size >= config.total || used[question.question_type] >= config.quotas[question.question_type];
      checkbox.checked = chosen;
      checkbox.disabled = reviewing || !question.selectable || (!chosen && full);
      card.classList.toggle('is-selected', chosen);
      reason.textContent = !question.selectable ? (question.blocked_reason || 'Câu chưa đủ điều kiện tạo đề đầu vào. Hãy kiểm tra phân loại và đáp án trong ngân hàng.')
        : !chosen && full ? 'Đã đủ số câu của hình thức này hoặc đủ số câu toàn đề. Bỏ một câu đã chọn để thay bằng câu này.' : '';
      reason.hidden = !reason.textContent;
    });
  }

  function renderSelection() {
    const used = counts(), covered = coverage();
    get('selection-status').textContent = `Đã chọn ${selected.size}/${config.total} câu.`;
    root.querySelectorAll('[data-quota]').forEach(element => {
      const kind = element.dataset.quota;
      element.textContent = `${used[kind]}/${config.quotas[kind]}`;
      element.parentElement.classList.toggle('is-complete', used[kind] === config.quotas[kind]);
    });
    const missing = config.skills.filter(code => !covered.has(code)).map(code => code.split('-').pop());
    get('coverage').textContent = `Bao phủ ${covered.size}/${config.skills.length} dạng kiến thức.${missing.length ? ` Chưa chọn dạng: ${missing.join(', ')}.` : ' Đã đủ các dạng.'}`;
    get('bank-change-note').hidden = !selected.size;
    const list = get('selected');
    list.replaceChildren();
    if (!selected.size) list.append(node('li', 'dw-description', 'Chọn câu ở danh sách để thêm vào đề.'));
    let index = 0;
    selected.forEach(question => {
      const item = node('li', 'dw-selected-item');
      item.append(node('strong', '', `Câu ${++index} · #${question.id}`));
      item.append(node('p', '', `${config.labels[question.question_type]} · ${question.skill_label || question.skill}`));
      item.append(node('p', '', question.summary));
      if (question.selectable === false) item.append(node('p', 'dw-blocked', 'Câu đã thay đổi và chưa đủ điều kiện. Bỏ câu này để chọn lại.'));
      const button = node('button', 'btn btn-secondary', 'Bỏ câu');
      button.type = 'button';
      button.dataset.removeQuestion = String(question.id);
      button.setAttribute('aria-label', `Bỏ câu ${index}, mã ${question.id}`);
      button.addEventListener('click', () => {
        if (reviewing) return;
        selected.delete(question.id);
        invalidateReview();
        renderSelection();
        get('chosen-heading').focus();
      });
      item.append(button);
      list.append(item);
    });
    updateControls();
  }

  function selectionMetadata(question) {
    return {id: question.id, selectable: question.selectable !== false, question_type: question.question_type, skill: question.skill,
      skill_label: question.skill_label, summary: String(question.question_text || '').replace(/\[\[formula:[^\]]+\]\]/g, '[công thức]').slice(0, 180)};
  }

  async function jsonRequest(url, options = {}) {
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    options.signal?.addEventListener('abort', abort, {once: true});
    if (options.signal?.aborted) controller.abort();
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 30000);
    let response;
    try {
      response = await fetch(url, {...options, signal: controller.signal, credentials: 'same-origin', headers: {Accept: 'application/json'}});
    } catch (error) {
      if (timedOut) {
        const timeoutError = new Error('Yêu cầu mất quá nhiều thời gian. Bộ câu đã chọn vẫn được giữ; hãy thử lại.');
        timeoutError.uncertain = true;
        throw timeoutError;
      }
      throw error;
    } finally {
      clearTimeout(timeout);
      options.signal?.removeEventListener('abort', abort);
    }
    if (response.redirected || response.status === 401) throw new Error('Phiên đăng nhập đã hết hạn. Đăng nhập lại rồi tiếp tục với bộ câu đã chọn.');
    if (response.status === 403) throw new Error('Bạn không còn quyền thực hiện thao tác này.');
    if (!response.headers.get('content-type')?.includes('application/json')) {
      throw new Error(response.status === 400 ? 'Phiên làm việc đã hết hạn. Tải lại trang để tiếp tục với bộ câu đã chọn.' : 'Không nhận được dữ liệu hợp lệ. Bộ câu đã chọn vẫn được giữ.');
    }
    const data = await response.json();
    if (!response.ok || !data.success) {
      const error = new Error(data.message || 'Không thể xử lý yêu cầu. Hãy thử lại.');
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function formulasIn(container, assets = {}) {
    if (typeof window.renderFormulas === 'function') window.renderFormulas(container, assets);
  }

  function appendPrompt(container, question) {
    if (question.context) container.append(node('div', 'dw-context katex-render', question.context));
    container.append(node('div', 'dw-prompt katex-render', question.question_text));
    if (question.image_url) {
      try {
        const url = new URL(question.image_url, window.location.href);
        if (['http:', 'https:'].includes(url.protocol)) {
          const image = node('img', 'dw-figure');
          image.src = url.href;
          image.alt = `Hình minh họa của câu hỏi #${question.id}`;
          image.loading = 'lazy';
          image.addEventListener('error', () => {
            image.hidden = true;
            const notice = node('p', 'dw-image-error', 'Không tải được hình minh họa. ');
            const retry = node('button', 'btn btn-secondary', 'Tải lại hình');
            retry.type = 'button';
            retry.addEventListener('click', () => {
              notice.remove();
              image.hidden = false;
              image.loading = 'eager';
              image.src = url.href;
            });
            notice.append(retry);
            image.after(notice);
          });
          container.append(image);
        }
      } catch (_) { /* A malformed image URL should not hide the question text. */ }
    }
  }

  function appendBadges(container, question, points = false) {
    const badges = node('div', 'dw-badges');
    [config.labels[question.question_type] || question.question_type, levels[question.difficulty_level], question.skill_label || question.skill,
      points ? `${question.points} điểm` : ''].filter(Boolean).forEach(text => badges.append(node('span', '', text)));
    container.append(badges);
  }

  function appendAnswers(container, question) {
    const kind = question.question_type;
    (question.options || []).forEach((option, index) => {
      const correct = option.correct ?? option.is_correct;
      const text = option.text ?? option.option_text ?? '';
      const answer = node('div', `dw-answer${correct === true ? ' is-correct' : ''}`);
      const marker = kind === 'true_false' ? `Ý ${String.fromCharCode(97 + index)}` : kind === 'short_answer' ? 'Đáp án' : `${String.fromCharCode(65 + index)}.`;
      answer.append(node('strong', '', marker), node('div', 'dw-answer-text katex-render', text));
      if (kind === 'true_false') answer.append(node('span', 'dw-answer-key', correct == null ? 'Chưa có đáp án' : `Đáp án: ${correct ? 'Đúng' : 'Sai'}`));
      else if (correct === true) answer.append(node('span', 'dw-answer-key', 'Đáp án đúng'));
      container.append(answer);
    });
    if (!question.options?.length) container.append(node('p', 'dw-blocked', 'Câu hỏi chưa có đáp án.'));
    if (question.explanation) {
      container.append(node('h4', 'dw-explanation-heading', 'Lời giải / giải thích'));
      container.append(node('div', 'dw-explanation katex-render', question.explanation));
    }
  }

  function questionCard(question) {
    const card = node('article', 'dw-question');
    const label = node('label', 'dw-choice-label');
    const checkbox = node('input');
    checkbox.type = 'checkbox';
    checkbox.id = `dw-choice-${question.id}`;
    const reason = node('p', 'dw-blocked');
    reason.id = `dw-reason-${question.id}`;
    checkbox.setAttribute('aria-describedby', reason.id);
    label.append(checkbox, node('span', '', `Chọn câu #${question.id}`));
    card.append(label);
    appendBadges(card, question);
    appendPrompt(card, question);
    card.append(reason);
    candidates.set(question.id, {question, card, checkbox, reason});
    checkbox.addEventListener('change', () => {
      if (reviewing || !question.selectable) { updateControls(); return; }
      if (checkbox.checked) {
        if (selected.size >= config.total || counts()[question.question_type] >= config.quotas[question.question_type]) { updateControls(); return; }
        selected.set(question.id, selectionMetadata(question));
      } else selected.delete(question.id);
      invalidateReview();
      renderSelection();
      feedback();
    });
    const details = node('details');
    details.append(node('summary', '', 'Xem đáp án và lời giải'));
    const body = node('div');
    details.append(body);
    card.append(details);
    let fetching = false, loaded = false;
    const fetchDetail = async () => {
      if (fetching || loaded) return;
      fetching = true;
      body.setAttribute('aria-busy', 'true');
      body.replaceChildren(node('p', 'dw-description', 'Đang tải đáp án…'));
      try {
        const data = await jsonRequest(question.detail_url);
        if (!card.isConnected) return;
        body.replaceChildren();
        appendAnswers(body, data.question);
        formulasIn(body, data.question.formulas || {});
        loaded = true;
      } catch (error) {
        if (!card.isConnected) return;
        body.replaceChildren(node('p', 'dw-blocked', error.message || 'Không tải được đáp án.'));
        const retry = node('button', 'btn btn-secondary', 'Tải lại đáp án');
        retry.type = 'button';
        retry.addEventListener('click', fetchDetail);
        body.append(retry);
      } finally { fetching = false; body.setAttribute('aria-busy', 'false'); }
    };
    details.addEventListener('toggle', () => { if (details.open) fetchDetail(); });
    return card;
  }

  function cancelList() {
    clearTimeout(searchTimer);
    listVersion += 1;
    listController?.abort();
    loading = false;
    get('candidates').setAttribute('aria-busy', 'false');
  }

  async function loadQuestions(nextPage = 1) {
    cancelList();
    if (step !== 2 || !bankId) return;
    const version = listVersion;
    listController = new AbortController();
    loading = true;
    get('candidates').setAttribute('aria-busy', 'true');
    get('page-status').textContent = 'Đang tải câu hỏi…';
    candidates.clear();
    get('candidates').replaceChildren();
    updateControls();
    const url = new URL(config.choicesUrl, window.location.origin);
    url.searchParams.set('question_bank_id', bankId);
    url.searchParams.set('page', nextPage);
    [['q', 'search'], ['type', 'kind'], ['difficulty', 'level'], ['node_id', 'skill']].forEach(([key, id]) => {
      if (get(id).value.trim()) url.searchParams.set(key, get(id).value.trim());
    });
    try {
      const data = await jsonRequest(url, {signal: listController.signal});
      if (version !== listVersion || step !== 2) return;
      page = data.pagination.page;
      pages = data.pagination.pages;
      const skillValue = get('skill').value;
      get('skill').replaceChildren(new Option('Tất cả dạng kiến thức', ''));
      data.skills.forEach(skill => get('skill').append(new Option(`Dạng ${skill.category}: ${skill.category_name}`, String(skill.id))));
      get('skill').value = skillValue;
      get('page-label').textContent = `Trang ${page}/${pages}`;
      get('page-status').textContent = data.pagination.total ? `Hiển thị ${data.pagination.first}–${data.pagination.last} / ${data.pagination.total} câu. Lựa chọn được giữ khi chuyển trang.` : 'Không có câu hỏi khớp bộ lọc. Thử đổi bộ lọc hoặc ngân hàng.';
      const fragment = document.createDocumentFragment();
      let changed = false;
      data.questions.forEach(question => {
        if (selected.has(question.id)) {
          selected.set(question.id, selectionMetadata(question));
          changed = true;
        }
        fragment.append(questionCard(question));
      });
      get('candidates').append(fragment);
      if (changed) { invalidateReview(); renderSelection(); }
      data.questions.forEach(question => formulasIn(candidates.get(question.id).card, question.formulas));
    } catch (error) {
      if (error.name === 'AbortError' || version !== listVersion) return;
      get('page-status').textContent = error.message || 'Không thể tải danh sách. Bộ câu đã chọn vẫn được giữ.';
      const retry = node('button', 'btn btn-secondary', 'Tải lại danh sách');
      retry.type = 'button';
      retry.addEventListener('click', () => loadQuestions(nextPage));
      get('candidates').append(retry);
    } finally {
      if (version === listVersion) {
        loading = false;
        get('candidates').setAttribute('aria-busy', 'false');
        updateControls();
      }
    }
  }

  function selectedForm() {
    const data = new FormData();
    data.set('csrf_token', get('publish-form').elements.csrf_token.value);
    data.set('question_bank_id', bankId);
    selected.forEach(question => data.append('question_ids', question.id));
    return data;
  }

  function showReview(data) {
    reviewData = data;
    get('publish-bank').value = bankId;
    get('review-digest').value = data.review_digest;
    get('confirm').checked = false;
    get('publish-ids').replaceChildren();
    data.questions.forEach(question => {
      const input = node('input');
      input.type = 'hidden';
      input.name = 'question_ids';
      input.value = question.id;
      get('publish-ids').append(input);
    });
    const oldCourse = get('course').value;
    get('course').replaceChildren(new Option('Chọn lớp nhận đề', ''));
    data.courses.forEach(course => get('course').append(new Option(course.name, String(course.id))));
    if (data.courses.some(course => String(course.id) === oldCourse)) get('course').value = oldCourse;
    get('review-summary').replaceChildren();
    const totalPoints = data.questions.reduce((sum, question) => sum + Number(question.points), 0);
    const summary = [data.bank.name, `${data.questions.length} câu · ${config.duration} phút · ${totalPoints} điểm`,
      ...Object.entries(config.quotas).map(([kind, count]) => `${config.labels[kind]}: ${count} câu`),
      `Bao phủ ${Object.keys(data.skill_counts).length}/${config.skills.length} dạng kiến thức`,
      ...Object.entries(levels).map(([level, label]) => `${label}: ${data.level_counts[level] || 0} câu`)];
    summary.forEach(text => get('review-summary').append(node('span', '', text)));
    reviewObserver?.disconnect();
    readQuestions.clear();
    get('confirm').disabled = true;
    get('review-cards').replaceChildren();
    data.questions.forEach((question, index) => {
      const card = node('article', 'dw-question');
      card.append(node('h3', 'dw-review-number', `Câu ${index + 1}`));
      appendBadges(card, question, true);
      appendPrompt(card, question);
      appendAnswers(card, question);
      card.id = `dw-review-question-${question.id}`;
      card.tabIndex = -1;
      const end = node('span', 'dw-review-end', `Kết thúc câu ${index + 1}`);
      end.dataset.reviewEnd = String(question.id);
      card.append(end);
      get('review-cards').append(card);
    });
    feedback();
    goTo(3);
    formulasIn(get('review-cards'), data.formulas);
    if ('IntersectionObserver' in window) {
      reviewObserver = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting && step === 3) {
            readQuestions.add(Number(entry.target.dataset.reviewEnd));
            entry.target.classList.add('is-read');
            reviewObserver.unobserve(entry.target);
          }
        });
        updatePublish();
      }, {threshold: 1});
      get('review-cards').querySelectorAll('[data-review-end]').forEach(end => reviewObserver.observe(end));
    } else {
      // The explicit navigation button remains available without observer support.
      get('next-unread').textContent = 'Đọc và xác nhận từng câu';
    }
    updatePublish();
  }

  function updatePublish() {
    const allRead = !!reviewData && readQuestions.size === reviewData.questions.length;
    get('confirm').disabled = publishing || !allRead;
    if (!allRead) get('confirm').checked = false;
    get('read-status').textContent = `Đã xem ${readQuestions.size}/${reviewData?.questions.length || config.total} câu.${allRead ? ' Đã có thể xác nhận giao đề.' : ' Đọc đến cuối từng câu để mở xác nhận.'}`;
    get('next-unread').hidden = allRead;
    const course = get('course').selectedOptions[0];
    const title = get('title').value.trim() || `Đánh giá đầu vào${get('course').value ? ` · ${course.textContent}` : ''}`;
    get('publish-context').textContent = get('course').value ? `Giao “${title}” cho học sinh đang học trong lớp ${course.textContent}. Bộ đề có ${config.total} câu, ${config.duration} phút.` : 'Chọn lớp nhận đề ở đầu bước này.';
    get('publish').disabled = publishing || !allRead || !reviewData || !get('review-digest').value || !get('course').value || !get('confirm').checked;
  }

  get('bank').addEventListener('change', () => { get('start').disabled = !get('bank').value; });
  get('start').addEventListener('click', () => {
    const nextBank = get('bank').value;
    if (!nextBank) return;
    if (bankId !== nextBank) {
      bankId = nextBank;
      selected.clear();
      ['search', 'kind', 'level', 'skill'].forEach(id => { get(id).value = ''; });
      page = pages = 1;
      get('title').value = '';
      get('course').value = '';
      invalidateReview();
    }
    get('bank-name').textContent = get('bank').selectedOptions[0].textContent;
    feedback();
    renderSelection();
    goTo(2);
    loadQuestions(page);
  });
  get('back-bank').addEventListener('click', () => { cancelList(); feedback(); goTo(1); });
  get('back-questions').addEventListener('click', () => {
    feedback();
    goTo(2);
    get('confirm').checked = false;
    updatePublish();
    loadQuestions(page);
  });
  get('prev-page').addEventListener('click', () => loadQuestions(page - 1));
  get('next-page').addEventListener('click', () => loadQuestions(page + 1));
  ['kind', 'level', 'skill'].forEach(id => get(id).addEventListener('change', () => loadQuestions(1)));
  get('search').addEventListener('input', () => {
    cancelList();
    candidates.clear();
    get('candidates').replaceChildren();
    get('page-status').textContent = 'Đang tìm câu hỏi…';
    loading = true;
    updateControls();
    searchTimer = setTimeout(() => loadQuestions(1), 300);
  });
  get('review').addEventListener('click', async () => {
    if (reviewing || !complete()) return;
    const selectedRevision = revision;
    cancelList();
    reviewing = true;
    get('review').textContent = 'Đang kiểm tra bộ câu…';
    feedback('Đang tải đầy đủ nội dung và đáp án để kiểm tra đề.');
    updateControls();
    try {
      const data = await jsonRequest(config.reviewUrl, {method: 'POST', body: selectedForm()});
      if (selectedRevision === revision) showReview(data);
    } catch (error) { feedback(error.message || 'Không kiểm tra được đề. Bộ câu đã chọn vẫn được giữ.', true, true); }
    finally {
      reviewing = false;
      get('review').textContent = 'Tiếp tục: kiểm tra đề';
      updateControls();
    }
  });
  ['course', 'confirm'].forEach(id => get(id).addEventListener('change', updatePublish));
  get('title').addEventListener('input', updatePublish);
  get('next-unread').addEventListener('click', () => {
    const question = reviewData?.questions.find(item => !readQuestions.has(item.id));
    if (!question) return;
    const card = document.getElementById(`dw-review-question-${question.id}`);
    card.focus();
    card.scrollIntoView({block: 'start'});
    if (!('IntersectionObserver' in window)) {
      readQuestions.add(question.id);
      card.querySelector('[data-review-end]').classList.add('is-read');
      updatePublish();
    }
  });
  get('publish-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (publishing || !reviewData || readQuestions.size !== reviewData.questions.length || !get('confirm').checked || !get('publish-form').reportValidity()) return;
    const data = new FormData(get('publish-form'));
    publishing = true;
    ['title', 'course', 'confirm', 'back-questions'].forEach(id => { get(id).disabled = true; });
    get('publish').textContent = 'Đang tạo và giao đề…';
    feedback('Đang lưu đề và giao cho lớp đã chọn.');
    updatePublish();
    try {
      const result = await jsonRequest(get('publish-form').action, {method: 'POST', body: data});
      try { sessionStorage.removeItem(storageKey); } catch (_) { /* Storage is optional. */ }
      window.location.assign(result.redirect_url);
    } catch (error) {
      const message = error instanceof TypeError || error.uncertain ? 'Chưa nhận được xác nhận từ máy chủ. Mở Danh sách đề để kiểm tra trước khi thử tạo lại.' : error.message;
      feedback(message || 'Không tạo được đề. Thông tin và bộ câu đã chọn vẫn được giữ.', true, true);
      publishing = false;
      ['title', 'course', 'confirm', 'back-questions'].forEach(id => { get(id).disabled = false; });
      get('publish').textContent = 'Xác nhận tạo và giao đề';
      if (error.status === 400 && /thay đổi sau khi xem lại/.test(error.message)) {
        invalidateReview();
        goTo(2);
        loadQuestions(page);
        feedback('Nội dung câu đã thay đổi. Bộ câu vẫn được giữ; hãy kiểm tra đề lần nữa trước khi giao.', true, true);
      }
      updatePublish();
    }
  });
  window.addEventListener('pageshow', event => {
    if (!event.persisted) return;
    reviewing = publishing = false;
    ['title', 'course', 'confirm', 'back-questions'].forEach(id => { get(id).disabled = false; });
    get('review').textContent = 'Tiếp tục: kiểm tra đề';
    get('publish').textContent = 'Xác nhận tạo và giao đề';
    invalidateReview();
    feedback('Kiểm tra lại bộ câu trước khi tạo đề.');
    if (step === 3) goTo(2);
    updateControls();
    updatePublish();
    if (step === 2) loadQuestions(page);
  });

  get('feedback').tabIndex = -1;
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
    if (saved && Number.isFinite(saved.savedAt) && Date.now() >= saved.savedAt && Date.now() - saved.savedAt < 3600000 && Array.from(get('bank').options).some(option => option.value === saved.bankId) && Array.isArray(saved.selected)) {
      bankId = saved.bankId;
      get('bank').value = bankId;
      saved.selected.slice(0, config.total).forEach(question => {
        if (Number.isSafeInteger(question.id) && question.id > 0 && question.id <= 2147483647 && question.question_type in config.quotas && config.skills.includes(question.skill)) selected.set(question.id, selectionMetadata({ ...question, question_text: question.summary }));
      });
      get('start').disabled = !bankId;
      get('bank-name').textContent = get('bank').selectedOptions[0].textContent;
      if (bankId && selected.size) {
        renderSelection();
        goTo(2);
        feedback('Đã khôi phục lựa chọn trong vòng 1 giờ. Máy chủ sẽ kiểm tra lại quyền, nội dung và cấu trúc trước khi giao đề.');
        loadQuestions(1);
      }
    } else if (saved) {
      sessionStorage.removeItem(storageKey);
      feedback('Lựa chọn đã lưu đã hết hạn hoặc nguồn không còn phù hợp. Hãy chọn lại ngân hàng và bộ câu.');
    }
  } catch (_) {
    try { sessionStorage.removeItem(storageKey); } catch (_) { /* Storage is optional. */ }
  }
  renderSelection();
})();
