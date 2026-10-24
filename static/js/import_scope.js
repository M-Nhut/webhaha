/* Restore the server-owned import scope and destination; the retired scope form is removed. */
function importScopeState() {
  return {
    scope: null,
    scopeError: '',
    lockedBankId: null,
    restoreImport(data) {
      this.questions = Array.isArray(data.questions) ? data.questions : [];
      this.stats = data.stats || {total: 0, valid: 0, warning: 0, error: 0};
      this.duplicateReport = data.duplicate_report || {};
      this.importResult = data.result || null;
      this.destinationDraft = data.bank_id ? String(data.bank_id) : '';
      this.fileName = data.filename || this.fileName;
      this.scope = data.scope || null;
      this.scopeError = data.scope_error || '';
      if (!data.bank_id) this.newBankGrade = data.scope?.grade || '';
      this.lockedBankId = data.bank_id || null;
      this.selectedBankId = data.bank_id ? String(data.bank_id) : '';
      this.bankTarget = data.bank_id ? 'existing' : 'new';
      this.reviewed = false;
      this.step = data.status === 'confirmed' ? 5 : 3;
    }
  };
}
