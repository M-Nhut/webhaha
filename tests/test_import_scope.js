const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
let requests = [], next = {success: false, message: 'fixture error'};
const dialogs = [];
const navigations = [];
const sandbox = {
  URL, URLSearchParams, FormData,
  window: {location: {search: '', href: 'http://localhost/question-banks/import', assign: url => navigations.push(url)},
    history: {replaceState() {}}, AcademyDialogs: {open: id => dialogs.push(id), close() {}}},
  document: {},
  fetch: async (url, options = {}) => {requests.push({url, options}); return {ok: true, json: async () => next};}
};
vm.createContext(sandbox);
for (const file of ['static/js/import_scope.js', 'static/js/import_duplicates.js', 'static/js/modules/import_wizard.js']) {
  vm.runInContext(fs.readFileSync(file, 'utf8'), sandbox);
}
const make = () => {
  const state = sandbox.importWizard({csrfToken: 'fixture', uploadUrl: '/upload', bankListUrl: '/banks'});
  state.$nextTick = fn => fn(); state.$root = {querySelector: () => null};
  return state;
};
let checks = 0;
const eq = (a, b) => {assert.equal(a, b); checks++;};
(async () => {
  const state = make();
  const scope = {grade: '9', chapters: ['8'], lessons: ['8:i'], topics: ['thong_ke_xac_suat']};
  state.restoreImport({questions: [{import_uid: 'a'}], stats: {total: 1}, filename: 'resume.tex', bank_id: 7, scope});
  eq(state.step, 3); eq(state.selectedBankId, '7'); eq(state.lockedBankId, 7);
  eq(state.bankTarget, 'existing'); eq(state.questions.length, 1); eq(state.fileName, 'resume.tex');
  eq(state.scope.lessons[0], '8:i'); eq(state.reviewed, false);
  state.restoreImport({questions: [], stats: {total: 0}, scope: {mode: 'general', grade: '10'}, scope_error: 'Catalog changed'});
  eq(state.step, 3); eq(state.scopeError, 'Catalog changed'); eq(state.newBankGrade, '10');
  eq(state.bankTarget, 'new'); eq(state.selectedBankId, '');
  state.reviewed = true;
  state.restoreImport({status: 'confirmed', result: {completed: true, imported_count: 1}});
  eq(state.step, 5); eq(state.importResult.completed, true); eq(state.reviewed, false);
  const upload = make();
  await upload.uploadFile({name: 'fixture.tex', size: 100});
  eq(requests[0].url, '/upload'); eq(requests[0].options.headers['X-CSRFToken'], 'fixture');
  eq(upload.step, 1); eq(upload.errorMessage, 'fixture error'); eq(upload.requestBusy, false);
  const before = requests.length;
  await upload.uploadFile({name: 'fixture.docx', size: 100}); eq(requests.length, before);
  await upload.uploadFile({name: 'fixture.tex', size: 0}); eq(requests.length, before);
  upload.sessionId = 'fixture-session';
  upload.cancelImport(); eq(dialogs.at(-1), 'import-cancel-dialog'); eq(requests.length, before);
  next = {success: true};
  await upload.confirmCancelImport();
  eq(requests.at(-1).url, '/question-banks/import/fixture-session/cancel'); eq(navigations.at(-1), '/banks');
  console.log(`Import resume, configured upload/CSRF, validation and explicit cancellation: ${checks} assertions passed.`);
})().catch(error => {console.error(error); process.exitCode = 1;});
