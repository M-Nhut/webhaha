/* Duplicate decisions and receipts use server-authoritative reports and tokens. */
function importDuplicateState() {
  return {
    duplicateReport: {}, importResult: null, duplicateError: '', duplicateNotice: '',
    duplicateNeedsRefresh: false, savingDecision: false, refreshingDuplicates: false,
    comparisonUid: null, destinationDraft: '', changingDestination: false,
    get duplicateRows() { return (this.questions || []).filter(q => ['duplicate', 'review'].includes(q.duplicate?.state)); },
    get eligibleCount() { return this.duplicateReport.eligible ?? ((this.stats?.valid || 0) + (this.stats?.warning || 0)); },
    get canConfirmDuplicates() { return this.eligibleCount > 0 || (this.duplicateReport.duplicate > 0 && !this.duplicateReport.review); },
    get comparisonQuestion() { return (this.questions || []).find(q => q.import_uid === this.comparisonUid); },
    get duplicateBusy() { return this.savingDecision || this.changingDestination || this.refreshingDuplicates || !!this.busy || this.editingIndex != null; },
    get destinationChanged() { return String(this.destinationDraft || '') !== String(this.duplicateReport.bank_id || ''); },
    get duplicateDestinationLabel() {
      if (!this.destinationDraft) return 'Ngân hàng mới';
      const select = document.getElementById('duplicate-destination');
      return Array.from(select?.options || []).find(option => option.value === String(this.destinationDraft))?.textContent || 'Ngân hàng đã chọn';
    },
    duplicateLabel(state) { return ({new: 'Câu mới', duplicate: 'Trùng — bỏ qua', review: 'Cần đối chiếu', imported: 'Đã lưu'})[state] || ''; },
    decisionLabel(decision) { return ({incoming: 'giữ bản đang nhập', duplicate: 'giữ bản hiện có', different: 'giữ cả hai', neither: 'bỏ cả hai khỏi lần nhập'})[decision] || ''; },
    acceptDuplicateData(data) {
      if (Array.isArray(data.questions)) this.questions = data.questions;
      if (data.stats && typeof data.stats === 'object') this.stats = data.stats;
      this.duplicateReport = data.duplicate_report || {};
      if (data.result) this.importResult = data.result;
      this.duplicateNeedsRefresh = false;
    },
    clearDuplicateFeedback() { this.duplicateError = ''; this.duplicateNotice = ''; this.duplicateNeedsRefresh = false; },
    async duplicateResponse(response, fallback) {
      let data;
      try { data = await response.json(); }
      catch (_) { throw new Error('Máy chủ chưa trả về kết quả hợp lệ. Hãy thử lại.'); }
      if (response.ok === false || !data?.success) {
        // Existing routes return 400 for a stale pair token as well as 409-style conflicts.
        if ([400, 409].includes(response.status)) this.duplicateNeedsRefresh = true;
        throw new Error(data?.message || fallback);
      }
      return data;
    },
    requestDestinationChange() {
      if (this.duplicateBusy || !this.destinationChanged || this.duplicateReport.imported > 0) return;
      this.clearDuplicateFeedback();
      window.AcademyDialogs?.open('import-destination-dialog');
    },
    async changeDestination() {
      if (this.duplicateBusy || !this.sessionId || !this.destinationChanged || this.duplicateReport.imported > 0) return;
      this.clearDuplicateFeedback();
      this.changingDestination = true;
      try {
        const response = await fetch(`/question-banks/import/${encodeURIComponent(this.sessionId)}/destination`, {
          method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.IMPORT_CSRF},
          body: JSON.stringify({bank_id: this.destinationDraft || null})
        });
        const data = await this.duplicateResponse(response, 'Không đổi được ngân hàng nhận.');
        this.acceptDuplicateData(data);
        this.selectedBankId = data.bank_id ? String(data.bank_id) : '';
        this.destinationDraft = this.selectedBankId;
        this.lockedBankId = data.bank_id || null;
        this.bankTarget = data.bank_id ? 'existing' : 'new';
        this.closeComparison();
        window.AcademyDialogs?.close('import-destination-dialog');
        this.duplicateNotice = 'Đã đổi đích nhận và dò trùng lại. Hãy duyệt kết quả mới trước khi lưu.';
      } catch (error) { this.duplicateError = error.message || 'Kết nối bị gián đoạn. Hãy thử lại.'; }
      finally { this.changingDestination = false; }
    },
    async decideDuplicate(question, match, decision) {
      if (this.duplicateBusy || !this.sessionId || !question || !match) return;
      this.clearDuplicateFeedback();
      const current = (this.questions || []).find(row => row.import_uid === question.import_uid);
      const currentMatch = current?.duplicate?.matches?.find(row => row.token === match.token);
      if (!currentMatch || current.saved_question_id || current.duplicate?.state === 'imported') {
        this.duplicateError = 'Kết quả đối chiếu đã thay đổi. Tải lại phiên trước khi quyết định.';
        this.duplicateNeedsRefresh = true;
        return;
      }
      if (!currentMatch.reviewable || !['incoming', 'duplicate', 'different', 'neither'].includes(decision) ||
          (decision === 'incoming' && !currentMatch.can_replace) || (decision === 'neither' && currentMatch.bank_question_id)) {
        this.duplicateError = 'Quyền hiện tại không cho phép quyết định này.';
        return;
      }
      this.savingDecision = true;
      try {
        const response = await fetch(`/question-banks/import/${encodeURIComponent(this.sessionId)}/duplicate-decision`, {
          method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.IMPORT_CSRF},
          body: JSON.stringify({import_uid: current.import_uid, token: currentMatch.token, decision})
        });
        const data = await this.duplicateResponse(response, 'Không lưu được quyết định. Hãy thử lại.');
        this.acceptDuplicateData(data);
        this.duplicateNotice = 'Đã lưu quyết định: ' + this.decisionLabel(decision) + '.';
        this.$nextTick(() => this.renderAllComparisonFormulas());
      } catch (error) { this.duplicateError = error.message || 'Không lưu được quyết định. Hãy thử lại.'; }
      finally { this.savingDecision = false; }
    },
    async refreshDuplicateReport() {
      if (this.duplicateBusy || !this.sessionId) return;
      this.duplicateError = ''; this.duplicateNotice = '';
      this.refreshingDuplicates = true;
      try {
        const response = await fetch(`/question-banks/import/${encodeURIComponent(this.sessionId)}/preview`);
        const data = await this.duplicateResponse(response, 'Không tải lại được kết quả đối chiếu.');
        if (data.redirect_url) { window.location.assign(data.redirect_url); return; }
        if (typeof this.restoreImport === 'function') this.restoreImport(data);
        else this.acceptDuplicateData(data);
        this.duplicateNeedsRefresh = false;
        this.duplicateNotice = 'Đã tải kết quả mới nhất. Kiểm tra lại các quyết định trước khi lưu.';
        if (!this.comparisonQuestion || data.status === 'confirmed') this.closeComparison();
        else this.$nextTick(() => this.renderAllComparisonFormulas());
      } catch (error) { this.duplicateError = error.message || 'Không tải lại được kết quả. Hãy thử lại.'; }
      finally { this.refreshingDuplicates = false; }
    },
    openComparison(uid) {
      if (this.duplicateBusy || !(this.questions || []).some(q => q.import_uid === uid)) return;
      this.clearDuplicateFeedback();
      this.comparisonUid = uid;
      this.$nextTick(() => {
        window.AcademyDialogs?.open('import-duplicate-dialog');
        this.renderAllComparisonFormulas();
      });
    },
    closeComparison() {
      window.AcademyDialogs?.close('import-duplicate-dialog');
      this.comparisonUid = null;
    },
    trapComparisonFocus(event) {
      const dialog = event.currentTarget;
      const controls = Array.from(dialog.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'))
        .filter(control => control.getClientRects().length && !control.closest('[inert]'));
      const first = controls[0], last = controls.at(-1);
      if (!first) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
        event.preventDefault(); first.focus();
      }
    },
    renderAllComparisonFormulas() {
      const dialog = document.getElementById('import-duplicate-dialog');
      const question = this.comparisonQuestion;
      if (!dialog || !question || !window.renderFormulas) return;
      // Render each copy with its own map; matching token names can describe different formulas.
      dialog.querySelectorAll('[data-comparison-copy]').forEach(copy => {
        const source = copy.dataset.comparisonCopy === 'incoming' ? question :
          question.duplicate?.matches?.find(match => match.token === copy.dataset.matchToken)?.question;
        if (source) window.renderFormulas(copy, source.formulas || {});
      });
    },
    retryComparisonImage(figure) {
      const image = figure?.querySelector('img');
      if (!image?.dataset.sourceUrl) return;
      const source = new URL(image.dataset.sourceUrl, window.location.href);
      source.searchParams.set('_preview_retry', String(Date.now()));
      image.src = source.href;
    },
    getQuestionRows(question) {
      if (!question) return [];
      if (['true_false', 'truefalse'].includes(question.question_type)) {
        return (question.statements || []).map((statement, index) => ({
          label: (statement.id || String.fromCharCode(97 + index)) + ')',
          text: statement.text || statement.option_text || '',
          badgeText: statement.answer === true ? 'Đúng' : statement.answer === false ? 'Sai' : 'Chưa có đáp án',
          badgeClass: statement.answer === true ? 'answer-correct' : statement.answer === false ? 'answer-incorrect' : ''
        }));
      }
      return (question.options || []).map((option, index) => ({
        label: String.fromCharCode(65 + index) + '.',
        text: (option.text || option.option_text || '').replace(new RegExp('^\\s*' + String.fromCharCode(65 + index) + '[.)]\\s+', 'i'), ''),
        badgeText: option.is_correct ? 'Đáp án đúng' : '', badgeClass: option.is_correct ? 'answer-correct' : ''
      }));
    },
    answerText(question) {
      if (!question) return '';
      const isTrueFalse = ['true_false', 'truefalse'].includes(question.question_type);
      const rows = isTrueFalse ? question.statements || [] : question.options || [];
      const formulas = question.formulas || {};
      return rows.map((row, index) => {
        let raw = row.text || row.option_text || '';
        if (window.toEditableLatex) raw = window.toEditableLatex(raw, formulas);
        return `${String.fromCharCode(65 + index)}. ${raw} — ${isTrueFalse ? (row.answer === true ? 'Đúng' : row.answer === false ? 'Sai' : 'Chưa có đáp án') : (row.is_correct ? 'Đáp án đúng' : '')}`;
      }).join('\n');
    }
  };
}
