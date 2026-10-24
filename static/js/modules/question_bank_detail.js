/* Authorized question detail, inline editor and mutations. No bank-wide override. */
function bankQuestionsManager(config = {}) {
  const pendingDetails = new Map();
  const abortDetails = () => pendingDetails.forEach(request => request.controller.abort());
  return {
    questions: (config.questions || []).map(q => ({...q, detailsOpen: false,
      detailsLoaded: false, detailsLoading: false, detailsError: '',
      mutationBusy: false, mutationStatus: '', mutationError: false})),
    pageOffset: Number(config.pageOffset) || 0,
    canEdit: config.canEdit === true, canAdd: config.canAdd === true,
    editingId: null, editingForm: null, editRequestId: 0,
    editSaving: false, editError: '', editReviewed: false,
    typeLabel(type) {
      return ({single: 'Trắc nghiệm', true_false: 'Đúng / Sai', short_answer: 'Trả lời ngắn',
        multiple_choice: 'Nhiều lựa chọn · dữ liệu cũ', essay: 'Câu mở · dữ liệu cũ'})[type] || 'Dữ liệu cũ';
    },
    levelLabel(level) {
      return ({nhan_biet: 'Nhận biết', thong_hieu: 'Thông hiểu', van_dung: 'Vận dụng',
        van_dung_cao: 'Vận dụng cao'})[level] || 'Chưa xác định mức';
    },
    acceptedAnswers(q, fallback = 'Chưa có đáp án mẫu') {
      return (q?.options || []).map(o => o.option_text || o.text || '').join(' | ') || fallback;
    },
    openImage(url) { window.FormulaRenderer?.openImageLightbox(url, 'Hình minh họa phóng to'); },
    canEditQuestion(q) {
      if (!q || !['single', 'true_false', 'short_answer'].includes(q.question_type)) return false;
      return Object.prototype.hasOwnProperty.call(q, 'can_edit') ? q.can_edit === true : this.canEdit;
    },
    canDeleteQuestion(q) {
      if (!q) return false;
      return Object.prototype.hasOwnProperty.call(q, 'can_delete') ? q.can_delete === true : this.canEditQuestion(q);
    },
    init() {
      window.addEventListener('pagehide', abortDetails);
      this.$nextTick(() => {
        window.renderFormulas?.(this.$el);
        const hash = window.location?.hash || '';
        if (/^#qcard-\d+$/.test(hash)) {
          const target = this.$el?.querySelector(hash);
          if (target) {
            target.tabIndex = -1;
            target.focus({preventScroll: true});
            target.scrollIntoView({block: 'start'});
          }
        }
      });
    },
    destroy() {
      window.removeEventListener('pagehide', abortDetails);
      abortDetails(); pendingDetails.clear();
    },
    async toggleDetails(q) { q.detailsOpen = !q.detailsOpen; if (q.detailsOpen) await this.loadDetails(q); },
    async retryDetails(q) { q.detailsOpen = true; await this.loadDetails(q); },
    loadDetails(q) {
      if (q.detailsLoaded) return Promise.resolve(true);
      if (pendingDetails.has(q.id)) return pendingDetails.get(q.id).promise;
      const controller = new AbortController();
      q.detailsLoading = true; q.detailsError = '';
      const promise = (async () => {
        try {
          const response = await fetch(q.detail_url, {headers: {Accept: 'application/json'},
            credentials: 'same-origin', cache: 'no-store', signal: controller.signal});
          const data = await this.readResponse(response, 'Không tải được chi tiết câu hỏi. Vui lòng thử lại.');
          if (!data.question || data.question.id !== q.id) throw new Error('Chi tiết câu hỏi không hợp lệ. Vui lòng thử lại.');
          this.mergeQuestion(q, data.question); q.detailsLoaded = true;
          this.$nextTick(() => { window.lucide?.createIcons(); window.renderFormulas?.(this.$el); });
          return true;
        } catch (error) {
          if (error.name !== 'AbortError') q.detailsError = error.message || 'Không tải được chi tiết câu hỏi.';
          return false;
        } finally { q.detailsLoading = false; pendingDetails.delete(q.id); }
      })();
      pendingDetails.set(q.id, {controller, promise});
      return promise;
    },
    async readResponse(response, fallback) {
      if (response.redirected || response.status === 401) throw new Error('Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại rồi thử lại.');
      if (response.status === 403) throw new Error('Bạn không còn quyền thực hiện thao tác với câu hỏi này.');
      if (response.status === 404) throw new Error('Câu hỏi đã bị xóa hoặc không còn trong ngân hàng.');
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.success) throw new Error(data.message || fallback);
      return data;
    },
    mergeQuestion(q, data) { Object.assign(q, data); },
    reloadView() { window.location.reload(); },
    async startEdit(q) {
      if (!this.canEditQuestion(q) || this.editSaving) return;
      const requestId = ++this.editRequestId;
      q.detailsOpen = true;
      if (!await this.loadDetails(q) || requestId !== this.editRequestId || !this.canEditQuestion(q)) return;
      this.editingId = q.id; this.editError = ''; this.editReviewed = false;
      this.editingForm = JSON.parse(JSON.stringify(q));
      this.editingForm.options = (q.options || []).map(o => ({...o, option_text: o.option_text || o.text || ''}));
      this.editingForm.statements = (q.statements || []).map((s, i) => ({...s, id: s.id || 'abcd'[i]}));
      const formulas = q.formulas || {};
      if (window.toEditableLatex) {
        for (const key of ['context', 'question_text', 'explanation']) this.editingForm[key] = window.toEditableLatex(this.editingForm[key] || '', formulas);
        this.editingForm.options.forEach(o => o.option_text = window.toEditableLatex(o.option_text, formulas));
        this.editingForm.statements.forEach(s => s.text = window.toEditableLatex(s.text || '', formulas));
      }
      const saved = this.editingForm.learning_metadata || {};
      this.editingForm.learning_metadata = {...saved,
        statements: Array.from({length: 4}, (_, i) => ({...((saved.statements || [])[i] || {curriculum_code: '', cognitive_level: ''})})),
        short_answer: {...(saved.short_answer || {mode: '', tolerance: '0'})}};
      this.$nextTick(() => {
        this.renderEditPreviews();
        document.querySelector('.inline-edit-card textarea')?.focus();
      });
    },
    renderEditPreviews() {
      const container = document.querySelector('.inline-edit-card');
      if (container) window.renderFormulas?.(container, this.editingForm?.formulas || {});
    },
    cancelEdit() {
      if (this.editSaving) return;
      const id = this.editingId;
      this.editRequestId++; this.editingId = null; this.editingForm = null; this.editError = ''; this.editReviewed = false;
      this.$nextTick(() => document.getElementById('qcard-' + id)?.querySelector('.bank-question-actions button')?.focus());
    },
    toggleOptionCorrectInForm(index) {
      if (!this.canEditQuestion(this.editingForm) || this.editSaving) return;
      this.editingForm.options.forEach((o, i) => o.is_correct = i === index);
    },
    updateShortAnswerInForm(value) {
      if (!this.canEditQuestion(this.editingForm) || this.editSaving) return;
      this.editingForm.options = value.split('|').map(p => p.trim()).filter(Boolean)
        .map((option_text, order_index) => ({option_text, order_index, is_correct: true}));
    },
    editPreviewAnswers() {
      const q = this.editingForm;
      if (!q) return [];
      if (q.question_type === 'true_false') return (q.statements || []).map((s, i) => ({
        label: 'abcd'[i] + ') ' + (s.answer === true ? 'Đúng' : s.answer === false ? 'Sai' : 'Chưa chọn'), text: s.text || ''}));
      return (q.options || []).map((o, i) => ({label: q.question_type === 'short_answer' ? 'Đáp án' : String.fromCharCode(65 + i) + (o.is_correct ? ' · Đúng' : ''), text: o.option_text || o.text || ''}));
    },
    async mutateAnswer(q, payload) {
      if (!this.canEditQuestion(q) || q.mutationBusy) return;
      q.mutationBusy = true; q.mutationError = false; q.mutationStatus = 'Đang cập nhật đáp án…';
      // Keep the current server key visible until the request succeeds.
      try {
        const response = await fetch(`/questions/${q.id}/toggle-answer`, {
          method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': config.csrfToken}, body: JSON.stringify(payload)});
        const data = await this.readResponse(response, 'Không thể cập nhật đáp án. Vui lòng thử lại.');
        if (!data.question || data.question.id !== q.id) throw new Error('Phản hồi đáp án không hợp lệ.');
        this.mergeQuestion(q, data.question); q.mutationStatus = 'Đã cập nhật đáp án.';
        this.$nextTick(() => window.renderFormulas?.(this.$el));
      } catch (error) { q.mutationError = true; q.mutationStatus = error.message || 'Không thể cập nhật đáp án.'; }
      finally { q.mutationBusy = false; }
    },
    toggleOption(id, index, single) {
      const q = this.questions.find(item => item.id === id);
      if (!q?.options?.[index]) return;
      return this.mutateAnswer(q, {option_index: index, is_correct: single ? true : !q.options[index].is_correct});
    },
    setTrueFalseOption(id, index, answer) {
      const q = this.questions.find(item => item.id === id);
      if (!q?.options?.[index]) return;
      return this.mutateAnswer(q, {option_index: index, is_correct: answer});
    },
    setStatementAnswer(id, index, answer) { return this.setTrueFalseOption(id, index, answer); },
    async saveEdit(id) {
      const current = this.questions.find(q => q.id === id);
      if (!this.canEditQuestion(current) || !this.editingForm || this.editSaving) return;
      this.editError = '';
      if (!this.editReviewed) { this.editError = 'Vui lòng xác nhận đã kiểm tra nội dung và đáp án.'; return; }
      const payload = JSON.parse(JSON.stringify(this.editingForm));
      // Send only the answer structure and grading metadata for the active type.
      if (payload.question_type !== 'true_false') { delete payload.statements; delete payload.learning_metadata.statements; }
      else if (payload.learning_metadata.statements.every(s => !s.curriculum_code && !s.cognitive_level)) delete payload.learning_metadata.statements;
      if (payload.question_type !== 'short_answer') delete payload.learning_metadata.short_answer;
      if (payload.question_type === 'true_false') delete payload.options;
      if (payload.curriculum_mode === 'general') payload.curriculum_node_id = null;
      for (const key of ['detailsOpen', 'detailsLoaded', 'detailsLoading', 'detailsError', 'mutationBusy', 'mutationStatus', 'mutationError', 'can_edit', 'can_delete', 'detail_url']) delete payload[key];
      this.editSaving = true;
      try {
        const response = await fetch(`/questions/${id}/update`, {method: 'POST', credentials: 'same-origin',
          headers: {'Content-Type': 'application/json', 'X-CSRFToken': config.csrfToken}, body: JSON.stringify(payload)});
        const data = await this.readResponse(response, 'Không thể lưu câu hỏi. Vui lòng thử lại.');
        if (!data.question || data.question.id !== id) throw new Error('Phản hồi lưu câu hỏi không hợp lệ.');
        this.reloadView();
      } catch (error) {
        this.editError = error.message || 'Không thể lưu câu hỏi.';
        this.editSaving = false;
        this.$nextTick(() => document.querySelector('[data-edit-error]')?.focus());
      }
    },
    async deleteQuestion(id) {
      const q = this.questions.find(item => item.id === id);
      if (!this.canDeleteQuestion(q) || q.mutationBusy || !confirm('Xóa câu hỏi này khỏi ngân hàng? Đáp án và nội dung của câu sẽ bị xóa.')) return;
      q.mutationBusy = true; q.mutationError = false; q.mutationStatus = 'Đang xóa câu hỏi…';
      try {
        const response = await fetch(`/questions/${id}/delete`, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': config.csrfToken}});
        if (response.url.includes('/login')) throw new Error('Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.');
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.message || 'Không thể xóa câu hỏi. Vui lòng thử lại.');
        }
        this.reloadView();
      } catch (error) { q.mutationBusy = false; q.mutationError = true; q.mutationStatus = error.message || 'Không thể xóa câu hỏi.'; }
    }
  };
}
window.bankQuestionsManager = bankQuestionsManager;
