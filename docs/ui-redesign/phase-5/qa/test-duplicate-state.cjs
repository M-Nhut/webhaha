const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let checks = 0;
const check = (value, expected) => { assert.deepEqual(value, expected); checks += 1; };
const requests = [];
const dialogs = [];
const rendered = [];
let response = {ok: true, status: 200, json: async () => ({success: true})};
let comparisonCopies = [];
const sandbox = {
  URL, Date,
  document: {getElementById(id) { return id === 'import-duplicate-dialog' ? {querySelectorAll: () => comparisonCopies} : null; }},
  window: {
    IMPORT_CSRF: 'fixture-csrf', location: {href: 'http://127.0.0.1/preview'},
    AcademyDialogs: {open: id => dialogs.push(['open', id]), close: id => dialogs.push(['close', id])},
    renderFormulas: (element, formulas) => rendered.push({element, formulas})
  },
  fetch: async (url, options) => { requests.push({url, options}); return response; }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('static/js/import_duplicates.js', 'utf8'), sandbox);
function state() {
  const value = sandbox.importDuplicateState();
  value.questions = []; value.stats = {valid: 0, warning: 0}; value.sessionId = 'fixture-session';
  value.$nextTick = callback => callback();
  return value;
}
function fixture(bankId = null, canReplace = true) {
  const match = {token: 'pair-token', reviewable: true, can_replace: canReplace, bank_question_id: bankId, question: {formulas: {shared: 'existing-formula'}}};
  const question = {import_uid: 'incoming-uid', question_text: 'Fixture question', formulas: {shared: 'incoming-formula'}, duplicate: {state: 'review', matches: [match]}};
  return {question, match};
}
(async () => {
  const wizard = state();
  let pair = fixture(7, false); wizard.questions = [pair.question];
  await wizard.decideDuplicate(pair.question, pair.match, 'incoming');
  check(requests.length, 0); check(wizard.duplicateError.includes('không cho phép'), true);
  await wizard.decideDuplicate(pair.question, pair.match, 'neither');
  check(requests.length, 0);
  await wizard.decideDuplicate(pair.question, {...pair.match, token: 'stale-token'}, 'duplicate');
  check(requests.length, 0); check(wizard.duplicateNeedsRefresh, true);
  wizard.questions[0].saved_question_id = 17;
  await wizard.decideDuplicate(pair.question, pair.match, 'duplicate');
  check(requests.length, 0);

  pair = fixture(); wizard.questions = [pair.question];
  wizard.openComparison(pair.question.import_uid);
  check(wizard.comparisonUid, 'incoming-uid'); check(dialogs.at(-1), ['open', 'import-duplicate-dialog']);
  wizard.closeComparison(); check(wizard.comparisonUid, null); check(dialogs.at(-1), ['close', 'import-duplicate-dialog']);
  wizard.editingIndex = 0;
  wizard.openComparison(pair.question.import_uid);
  await wizard.decideDuplicate(pair.question, pair.match, 'different');
  check(wizard.comparisonUid, null); check(requests.length, 0);
  wizard.editingIndex = null;
  wizard.busy = true;
  await wizard.decideDuplicate(pair.question, pair.match, 'different');
  check(requests.length, 0); wizard.busy = false;
  response = {ok: false, status: 409, json: async () => ({success: false, message: 'Revision changed'})};
  await wizard.decideDuplicate(pair.question, pair.match, 'different');
  check(requests.length, 1); check(wizard.duplicateNeedsRefresh, true); check(wizard.duplicateError, 'Revision changed'); check(wizard.savingDecision, false);
  check(JSON.parse(requests[0].options.body), {import_uid: 'incoming-uid', token: 'pair-token', decision: 'different'});
  check(requests[0].options.headers['X-CSRFToken'], 'fixture-csrf');
  response = {ok: false, status: 400, json: async () => ({success: false, message: 'Kết quả đối chiếu đã thay đổi hoặc không hợp lệ. Hãy tải lại phiên.'})};
  await wizard.decideDuplicate(pair.question, pair.match, 'different');
  check(wizard.duplicateNeedsRefresh, true); check(wizard.savingDecision, false);

  response = {ok: true, status: 200, json: async () => ({success: true, questions: [pair.question], stats: {total: 1}, duplicate_report: {eligible: 1, revision: 'new-revision'}})};
  await wizard.decideDuplicate(pair.question, pair.match, 'different');
  check(wizard.duplicateReport.revision, 'new-revision'); check(wizard.duplicateNeedsRefresh, false); check(wizard.duplicateNotice.includes('giữ cả hai'), true);
  wizard.comparisonUid = pair.question.import_uid;
  comparisonCopies = [{dataset: {comparisonCopy: 'incoming'}}, {dataset: {comparisonCopy: 'existing', matchToken: 'pair-token'}}];
  wizard.renderAllComparisonFormulas();
  check(rendered.at(-2).formulas.shared, 'incoming-formula'); check(rendered.at(-1).formulas.shared, 'existing-formula');

  const destination = state();
  destination.duplicateReport = {bank_id: 1, imported: 1}; destination.destinationDraft = '2';
  await destination.changeDestination(); check(requests.length, 3);
  destination.duplicateReport.imported = 0;
  destination.requestDestinationChange(); check(dialogs.at(-1), ['open', 'import-destination-dialog']);
  response = {ok: false, status: 403, json: async () => ({success: false, message: 'Destination revoked'})};
  await destination.changeDestination();
  check(destination.selectedBankId, undefined); check(destination.duplicateError, 'Destination revoked'); check(destination.changingDestination, false);
  response = {ok: true, status: 200, json: async () => ({success: true, bank_id: 2, questions: [], stats: {total: 0}, duplicate_report: {bank_id: 2, revision: 'rescan'}})};
  await destination.changeDestination();
  check(destination.selectedBankId, '2'); check(destination.lockedBankId, 2); check(destination.bankTarget, 'existing'); check(destination.destinationChanged, false); check(destination.duplicateReport.revision, 'rescan');

  response = {ok: true, status: 200, json: async () => { throw new SyntaxError('HTML response'); }};
  destination.destinationDraft = '3';
  await destination.changeDestination();
  check(destination.selectedBankId, '2'); check(destination.duplicateError.includes('kết quả hợp lệ'), true);
  check(wizard.getQuestionRows({question_type: 'truefalse', statements: [{answer: null, text: 'Unanswered'}]})[0].badgeText, 'Chưa có đáp án');
  check(wizard.getQuestionRows({question_type: 'single', options: [{text: 'A. Answer', is_correct: true}]})[0].text, 'Answer');
  check(wizard.duplicateLabel('imported'), 'Đã lưu');
  console.log(`Import duplicate UI: ${checks} contract assertions passed.`);
})().catch(error => { console.error(error); process.exitCode = 1; });
