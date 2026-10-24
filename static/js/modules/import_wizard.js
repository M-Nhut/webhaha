/* LaTeX import workspace. Server reports remain authoritative for scope, duplicates and receipts. */
function importWizard(config = {}) {
  const emptyEditorDraft = () => ({
    question_text: '', context: '', image_url: '', explanation: '', question_type: '',
    options: [], statements: [], learning_metadata: {
      statements: [], short_answer: {mode: 'text', tolerance: '0'}
    }
  });
  const emptyShortAnswerMetadata = {mode: 'text', tolerance: '0'};
  return Object.defineProperties({
    step: 1,
    stepLabels: ['Tải file', 'Đọc tài liệu', 'Kiểm tra', 'Duyệt và lưu', 'Kết quả'],
    isDragging: false,
    isResuming: false,
    resumeFailed: false,
    fileName: '',
    documentPurpose: config.documentPurpose || 'auto',
    sessionId: null,
    questions: [],
    filterStatus: 'all',
    filterDuplicate: 'all',
    filterType: 'all',
    filterDifficulty: 'all',
    filterGrade: 'all',
    filterClassification: 'all',
    stats: {total: 0, valid: 0, warning: 0, error: 0},
    editingIndex: null,
    editingQuestion: emptyEditorDraft(),
    editingShortAnswerText: '',
    pendingRemoveIndex: null,
    bankTarget: 'existing',
    selectedBankId: '',
    newBankName: '',
    newBankSubject: 'Toán',
    newBankGrade: '',
    isSubmitting: false,
    requestBusy: false,
    reviewed: false,
    errorMessage: '',

    init() {
      const params = new URLSearchParams(window.location.search);
      this.selectedBankId = params.get('bank_id') || '';
      if (!this.selectedBankId) this.bankTarget = 'new';
      const resumeId = params.get('session_id');
      if (resumeId) {
        this.sessionId = resumeId;
        window.currentImportSessionId = resumeId;
        this.resumeImport();
      }
    },

    get editingShortAnswerMetadata() {
      // A departing short-answer subtree can finish effects after another type is opened.
      return this.editingQuestion.learning_metadata?.short_answer || emptyShortAnswerMetadata;
    },
    get busy() {
      return !!(this.requestBusy || this.isSubmitting || this.savingDecision || this.changingDestination || this.refreshingDuplicates);
    },
    get destinationLabel() {
      return this.bankTarget === 'new'
        ? (this.newBankName.trim() ? 'Ngân hàng mới · ' + this.newBankName.trim() : 'Tạo ngân hàng mới')
        : (config.bankLabels?.[this.selectedBankId] || (this.selectedBankId ? 'Ngân hàng #' + this.selectedBankId : 'Chưa chọn ngân hàng'));
    },
    get scopeLabel() {
      if (!this.scope) return this.documentPurpose === 'assessment' ? 'Tạo đề kiểm tra' : 'Tự nhận diện từ tài liệu';
      if (this.scope.mode === 'general') return [this.scope.grade || 'Nhiều lớp', this.scope.topic || 'Theo nội dung tài liệu'].join(' · ');
      return 'Toán 9 · Chương 8 · Không gian mẫu và xác suất';
    },
    get filteredQuestions() {
      return this.questions.filter(q => {
        const type = q.question_type === 'truefalse' ? 'true_false' : q.question_type;
        const classified = q.classification?.status;
        return (this.filterStatus === 'all' || q.status === this.filterStatus)
          && (this.filterType === 'all' || type === this.filterType)
          && (this.filterDifficulty === 'all' || q.difficulty_level === this.filterDifficulty)
          && (this.filterGrade === 'all' || q.grade === this.filterGrade)
          && (this.filterDuplicate === 'all' || q.duplicate?.state === this.filterDuplicate)
          && (this.filterClassification === 'all'
            || (this.filterClassification === 'suggested' && classified === 'suggested')
            || (this.filterClassification === 'needs_review' && !['confirmed', 'manual', 'suggested'].includes(classified)));
      });
    },
    get availableGrades() {
      return [...new Set(this.questions.map(q => q.grade).filter(Boolean))]
        .sort((a, b) => String(a).localeCompare(String(b), 'vi', {numeric: true}));
    },
    questionIndex(q) { return this.questions.indexOf(q); },
    contentStatusLabel(status) { return ({valid: 'Hợp lệ', warning: 'Cần kiểm tra', error: 'Có lỗi'})[status] || 'Cần kiểm tra'; },
    difficultyLabel(level) { return ({nhan_biet: 'Nhận biết', thong_hieu: 'Thông hiểu', van_dung: 'Vận dụng', van_dung_cao: 'Vận dụng cao'})[level] || 'Chưa xác định mức'; },
    typeLabel(type) { return ({single: 'Chọn một đáp án', true_false: 'Đúng/Sai', truefalse: 'Đúng/Sai', short_answer: 'Trả lời ngắn', multiple_choice: 'Nhiều đáp án · dữ liệu cũ', essay: 'Tự luận · dữ liệu cũ'})[type] || 'Chưa xác định hình thức'; },
    resetFilters() {
      if (this.editingIndex !== null) return;
      this.filterStatus = this.filterDuplicate = this.filterType = this.filterDifficulty = this.filterGrade = this.filterClassification = 'all';
    },
    setStep(step) {
      this.step = step;
      this.$nextTick(() => this.$root?.querySelector(`section[x-show="step === ${step}"] .import-step-heading`)?.focus({preventScroll: true}));
    },
    clearError() { this.errorMessage = ''; },
    showError(message) {
      this.errorMessage = message || 'Kết nối bị gián đoạn. Nội dung hiện tại được giữ lại; hãy thử lại.';
      this.$nextTick(() => this.$root?.querySelector('#import-error-summary')?.focus());
    },
    async readResponse(response) {
      let data;
      try { data = await response.json(); }
      catch (_) { throw new Error('Không đọc được phản hồi. Phiên đăng nhập có thể đã hết hạn; hãy tải lại trang và mở lại phiên nhập.'); }
      if (!data.success) throw new Error(data.message || 'Không hoàn tất được thao tác. Hãy thử lại.');
      return data;
    },
    sessionUrl(action) { return `/question-banks/import/${encodeURIComponent(this.sessionId)}/${action}`; },
    applyQuestionData(data) {
      this.questions = data.questions || this.questions;
      this.stats = data.stats || this.stats;
      this.duplicateReport = data.duplicate_report || {};
      if (data.scope !== undefined) this.scope = data.scope;
      this.reviewed = false;
      this.$nextTick(() => { if (window.renderKaTeX) window.renderKaTeX(); });
    },
    renderQuestionPart(element, question) {
      if (element && question && window.renderFormulas) window.renderFormulas(element, question.formulas || {});
    },
    openQuestionImage(url) {
      if (url && window.FormulaRenderer) window.FormulaRenderer.openImageLightbox(url, 'Hình minh họa câu hỏi');
    },

    async resumeImport() {
      if (this.busy || !this.sessionId) return;
      this.clearError();
      this.resumeFailed = false;
      this.isResuming = this.requestBusy = true;
      this.setStep(2);
      try {
        const data = await this.readResponse(await fetch(this.sessionUrl('preview')));
        if (data.redirect_url) { window.location.assign(data.redirect_url); return; }
        this.restoreImport(data);
        this.setStep(this.step);
      } catch (error) {
        this.setStep(1);
        this.resumeFailed = true;
        this.showError(error.message);
      } finally { this.isResuming = this.requestBusy = false; }
    },
    handleFileSelect(event) {
      const file = event.target.files?.[0];
      if (file) this.uploadFile(file);
      // Allow choosing the same file again after a parse or validation error.
      event.target.value = '';
    },
    handleDrop(event) {
      this.isDragging = false;
      if (!this.busy && event.dataTransfer.files?.[0]) this.uploadFile(event.dataTransfer.files[0]);
    },
    async uploadFile(file) {
      if (this.busy) return;
      this.clearError();
      if (!/\.(tex|latex)$/i.test(file.name)) { this.showError('Chỉ hỗ trợ tài liệu LaTeX có đuôi .tex hoặc .latex.'); return; }
      if (file.size > 10 * 1024 * 1024) { this.showError('File vượt quá 10 MB. Hãy giảm dung lượng tài liệu rồi thử lại.'); return; }
      if (!file.size) { this.showError('File đang rỗng. Hãy chọn tài liệu có nội dung câu hỏi.'); return; }
      this.fileName = file.name;
      this.requestBusy = true;
      this.setStep(2);
      const payload = new FormData();
      payload.append('document_purpose', this.documentPurpose);
      payload.append('file', file);
      if (this.selectedBankId) payload.append('bank_id', this.selectedBankId);
      if (config.defaults?.node_id && config.defaults.node_id !== '0') {
        payload.append('default_node_id', config.defaults.node_id);
        payload.append('default_difficulty', config.defaults.difficulty || '');
      }
      try {
        const data = await this.readResponse(await fetch(config.uploadUrl, {method: 'POST', headers: {'X-CSRFToken': config.csrfToken}, body: payload}));
        if (data.redirect_url) { window.location.assign(data.redirect_url); return; }
        this.sessionId = data.session_id;
        window.currentImportSessionId = data.session_id;
        const next = new URL(window.location.href);
        next.searchParams.set('session_id', data.session_id);
        window.history.replaceState({}, '', next);
        this.restoreImport(data);
        this.reviewed = false;
        this.resumeFailed = false;
        this.setStep(this.step);
      } catch (error) { this.setStep(1); this.showError(error.message); }
      finally { this.requestBusy = false; }
    },

    startInlineEdit(index) {
      if (this.busy || this.editingIndex !== null || !this.questions[index] || this.questions[index].saved_question_id) return;
      this.clearError();
      this.editingIndex = index;
      this.editingQuestion = JSON.parse(JSON.stringify(this.questions[index]));
      const q = this.editingQuestion;
      q.options = q.options || [];
      q.statements = q.statements || [];
      if (q.question_type === 'truefalse') q.question_type = 'true_false';
      const formulas = q.formulas || {};
      if (window.toEditableLatex) {
        ['question_text', 'context', 'explanation'].forEach(key => { q[key] = window.toEditableLatex(q[key] || '', formulas); });
        [...q.options, ...q.statements].forEach(row => { row.text = window.toEditableLatex(row.text || row.option_text || '', formulas); });
      }
      q.learning_metadata = q.learning_metadata || {};
      this.editingShortAnswerText = q.options.map(o => o.text || o.option_text || '').join(' | ');
      if (q.question_type === 'short_answer') {
        const first = q.options[0]?.text || '';
        q.learning_metadata.short_answer = q.learning_metadata.short_answer || {mode: first && !Number.isNaN(parseFloat(first.replace(',', '.'))) ? 'numeric' : 'text', tolerance: '0'};
      }
      if (q.question_type === 'true_false') {
        const inherited = `9C8-i-${q.question_category || ''}`;
        q.learning_metadata.statements = Array.from({length: 4}, (_, i) => q.learning_metadata.statements?.[i] || {curriculum_code: inherited, cognitive_level: q.difficulty_level});
      }
      this.$nextTick(() => this.$root?.querySelector('.inline-edit-container textarea')?.focus());
    },
    cancelInlineEdit() {
      if (this.busy) return;
      const index = this.editingIndex;
      // Keep x-model paths assignable through nested template teardown; clear content afterwards.
      this.editingIndex = null;
      this.$nextTick(() => {
        if (this.editingIndex !== null) return;
        this.editingQuestion = emptyEditorDraft();
        this.editingShortAnswerText = '';
        this.$root?.querySelector(`#qcard-${index} .import-question-heading button`)?.focus();
      });
    },
    addStatementToEditing() {
      const q = this.editingQuestion;
      if (!q || this.busy || q.statements.length >= 4) return;
      q.statements.push({id: 'abcd'[q.statements.length], text: '', answer: null});
    },
    removeStatementFromEditing(index) {
      const q = this.editingQuestion;
      if (!q || this.busy) return;
      q.statements.splice(index, 1);
      q.statements.forEach((statement, i) => { statement.id = 'abcd'[i]; });
      const labels = q.learning_metadata.statements;
      if (labels) { labels.splice(index, 1); labels.push({curriculum_code: `9C8-i-${q.question_category || ''}`, cognitive_level: q.difficulty_level}); }
    },
    toggleOptionCorrectInEdit(index) {
      if (!this.editingQuestion || this.busy) return;
      this.editingQuestion.options.forEach((option, i) => { option.is_correct = i === index; });
    },
    updateShortAnswerFromText(value) {
      if (!this.editingQuestion) return;
      // The raw input remains independent from normalized options so a trailing | can be typed.
      this.editingShortAnswerText = value;
      this.editingQuestion.options = value.split('|').map(v => v.trim()).filter(Boolean)
        .map((text, order_index) => ({text, is_correct: true, order_index}));
    },
    async setSingleCorrectOption(questionIndex, optionIndex) {
      if (this.busy || !this.questions[questionIndex] || this.questions[questionIndex].saved_question_id) return;
      const q = JSON.parse(JSON.stringify(this.questions[questionIndex]));
      if (q.question_type !== 'single' || !q.options?.[optionIndex]) return;
      q.options.forEach((option, i) => { option.is_correct = i === optionIndex; });
      await this.updateQuestionInServer(questionIndex, q);
    },
    async setStatementAnswer(questionIndex, statementIndex, answer) {
      if (this.busy || !this.questions[questionIndex] || this.questions[questionIndex].saved_question_id) return;
      const q = JSON.parse(JSON.stringify(this.questions[questionIndex]));
      if (!q.statements?.[statementIndex]) return;
      q.statements[statementIndex].answer = answer;
      await this.updateQuestionInServer(questionIndex, q);
    },
    async updateQuestionInServer(index, question = null) {
      if (this.busy || !this.sessionId || this.questions[index]?.saved_question_id) return false;
      this.requestBusy = true;
      this.clearError();
      try {
        const data = await this.readResponse(await fetch(this.sessionUrl('update'), {
          method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': config.csrfToken},
          body: JSON.stringify({index, question: question || this.questions[index]})
        }));
        this.applyQuestionData(data);
        return true;
      } catch (error) { this.showError(error.message); return false; }
      finally { this.requestBusy = false; }
    },
    async saveInlineEdit() {
      if (!this.editingQuestion || this.editingIndex === null || this.busy) return;
      if (!String(this.editingQuestion.question_text || '').trim()) { this.showError('Nội dung câu hỏi không được để trống.'); return; }
      const index = this.editingIndex;
      if (await this.updateQuestionInServer(index, this.editingQuestion)) this.cancelInlineEdit();
    },

    removeQuestion(index) {
      if (this.busy || this.editingIndex !== null || !this.questions[index] || this.questions[index].saved_question_id) return;
      this.pendingRemoveIndex = index;
      window.AcademyDialogs?.open('import-remove-dialog');
    },
    closeRemoveDialog() {
      this.pendingRemoveIndex = null;
      window.AcademyDialogs?.close('import-remove-dialog');
    },
    async confirmRemoveQuestion() {
      if (this.busy || this.pendingRemoveIndex === null) return;
      this.requestBusy = true;
      this.clearError();
      try {
        const data = await this.readResponse(await fetch(this.sessionUrl('remove'), {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': config.csrfToken}, body: JSON.stringify({index: this.pendingRemoveIndex})}));
        this.applyQuestionData(data);
        this.closeRemoveDialog();
      } catch (error) { this.closeRemoveDialog(); this.showError(error.message); }
      finally { this.requestBusy = false; }
    },
    async continueReview() {
      if (this.busy) return;
      this.requestBusy = true;
      this.clearError();
      try {
        const data = await this.readResponse(await fetch(this.sessionUrl('preview')));
        if (data.redirect_url) { window.location.assign(data.redirect_url); return; }
        this.restoreImport(data);
        this.reviewed = false;
        this.setStep(3);
      } catch (error) { this.showError(error.message); }
      finally { this.requestBusy = false; }
    },
    proceedToConfirm() {
      if (this.busy || !this.canConfirmDuplicates || this.editingIndex !== null) return;
      this.clearError();
      this.reviewed = false;
      this.setStep(4);
    },
    cancelImport() {
      if (!this.busy) window.AcademyDialogs?.open('import-cancel-dialog');
    },
    closeCancelDialog() { window.AcademyDialogs?.close('import-cancel-dialog'); },
    async confirmCancelImport() {
      if (this.busy) return;
      this.requestBusy = true;
      this.clearError();
      try {
        if (this.sessionId) await this.readResponse(await fetch(this.sessionUrl('cancel'), {method: 'POST', headers: {'X-CSRFToken': config.csrfToken}}));
        window.location.assign(config.bankListUrl);
      } catch (error) { this.closeCancelDialog(); this.showError(error.message); }
      finally { this.requestBusy = false; }
    },
    async confirmImport() {
      if (this.busy || !this.reviewed || !this.canConfirmDuplicates) return;
      this.clearError();
      if (this.bankTarget === 'existing' && !this.selectedBankId) { this.showError('Chưa có ngân hàng đích. Quay lại bước kiểm tra để chọn đích lưu.'); return; }
      if (this.bankTarget === 'new' && !this.newBankName.trim()) { this.showError('Nhập tên ngân hàng mới trước khi lưu.'); return; }
      this.isSubmitting = true;
      try {
        const data = await this.readResponse(await fetch(this.sessionUrl('confirm'), {
          method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': config.csrfToken},
          body: JSON.stringify({bank_id: this.bankTarget === 'existing' ? this.selectedBankId : null,
            new_bank_name: this.bankTarget === 'new' ? this.newBankName.trim() : null,
            subject: this.newBankSubject, grade: this.newBankGrade, confirmation_token: this.duplicateReport.revision})
        }));
        this.importResult = data;
        if (data.bank_id) { this.selectedBankId = String(data.bank_id); this.lockedBankId = data.bank_id; this.bankTarget = 'existing'; }
        this.setStep(5);
      } catch (error) { this.showError(error.message); }
      finally { this.isSubmitting = false; }
    }
  }, {...Object.getOwnPropertyDescriptors(importScopeState()), ...Object.getOwnPropertyDescriptors(importDuplicateState())});
}
window.importWizard = importWizard;
