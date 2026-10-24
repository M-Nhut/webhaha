/* Actual synthetic POSTs and responsive captures; never use a production URL. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.PHASE5_URL || 'http://127.0.0.1:8767';
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base), 'QA must use an isolated localhost preview');
const out = path.resolve('docs/ui-redesign/phase-5');
fs.mkdirSync(path.join(out, 'screenshots'), {recursive: true});
const checks = [], errors = [], assetErrors = [], external = [], images = [];
const check = (name, value) => {assert(value, name); checks.push(name);};

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(e.message));
    page.on('response', response => {if (response.status() >= 400 && response.url().includes('/static/')) assetErrors.push(response.url());});
    page.on('request', request => {if (['script', 'font', 'stylesheet'].includes(request.resourceType()) && !request.url().startsWith(base)) external.push(request.url());});
    page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
    const fixture = await (await context.request.get(base + '/qa/fixture')).json();
    const state = () => page.evaluate(() => Alpine.$data(document.querySelector('.import-workspace')));
    const settled = () => page.waitForFunction(() => {
      const root = document.querySelector('.import-workspace');
      return root && window.Alpine && Alpine.$data(root).step >= 3 && !Alpine.$data(root).busy;
    });
    const go = async url => {
      const response = await page.goto(base + url); check('GET ' + url, response.status() === 200);
      if (url.startsWith('/question-banks/import') && !url.includes('session_id=')) {
        await page.waitForFunction(() => document.querySelector('.import-steps li') && window.Alpine);
      }
    };
    const login = async role => {
      await page.goto(base + '/logout'); await page.goto(base + '/login');
      await page.locator('[name="username"]').fill('qa_' + role);
      await page.locator('[name="password"]').fill('Academy123!');
      await page.locator('[type="submit"]').click();
      await page.waitForURL(url => url.pathname !== '/login');
    };
    const shot = async name => {
      await page.evaluate(async () => {
        if (window.MathJax?.startup?.promise) await MathJax.startup.promise;
        window.FormulaRenderer?.renderFormulas(document.querySelector('main'), {}, {immediate: true});
        if (window.MathJax?.typesetPromise) await MathJax.typesetPromise();
      });
      const file = `screenshots/${name}.png`;
      await page.screenshot({path: path.join(out, file), fullPage: !name.includes('dialog') && !name.startsWith('publish-confirm')}); images.push(file);
    };
    await login('teacher');
    const selectionUrl = `/assessments/from-bank?course_id=${fixture.courses.teacher}&bank_ids=${fixture.banks.general}`;
    const cases = [
      ['import-upload', '/question-banks/import'],
      ['import-general', '/question-banks/import?session_id=' + fixture.sessions.general],
      ['import-research', '/question-banks/import?session_id=' + fixture.sessions.research],
      ['import-duplicates', '/question-banks/import?session_id=' + fixture.sessions.duplicates],
      ['bank-selection', selectionUrl],
      ['editor-latex', '/assessments/import/' + fixture.sessions.paper],
      ['editor-bank', '/assessments/import/' + fixture.sessions['bank-paper']],
    ];
    for (const width of [375, 768, 1024, 1440]) {
      await page.setViewportSize({width, height: 1000});
      for (const [name, url] of cases) {
        await go(url);
        if (url.includes('session_id=')) await settled();
        await page.locator('main h1').waitFor();
        check(`${name}@${width} viewport`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        check(`${name}@${width} heading`, await page.locator('main h1').count() === 1);
        if (width === 375 || width === 1440) await shot(`${name}-${width}`);
      }
      await go('/question-banks/import?session_id=' + fixture.sessions.duplicates); await settled();
      await page.getByRole('button', {name: 'Đối chiếu câu này'}).first().click();
      await page.locator('#import-duplicate-dialog[open]').waitFor();
      check(`duplicate modal@${width}`, await page.locator('.duplicate-pair').first().isVisible());
      check(`duplicate modal viewport@${width}`, await page.locator('#import-duplicate-dialog').evaluate(n => n.getBoundingClientRect().width <= innerWidth));
      if (width === 375 || width === 1440) await shot(`duplicate-dialog-${width}`);
      await page.keyboard.press('Escape');
      check(`duplicate Escape@${width}`, !await page.locator('#import-duplicate-dialog').evaluate(n => n.open));
    }
    await page.setViewportSize({width: 1440, height: 1000});
    const originalId = fixture.questions['common-7'];
    await go(`/question-banks/${fixture.banks.shared}?question_id=${originalId}#qcard-${originalId}`);
    await page.locator('#qcard-' + originalId).waitFor();
    check('Original question resolves beyond first bank page', await page.locator('#qcard-' + originalId).isVisible());
    check('Original question receives keyboard focus', await page.evaluate(id => document.activeElement.id === 'qcard-' + id, originalId));
    if (process.env.PHASE5_CAPTURE_ONLY !== '1') {
      await go('/question-banks/import?bank_id=' + fixture.banks.general);
      await page.locator('#import-file').setInputFiles({name: 'invalid.pdf', mimeType: 'application/pdf', buffer: Buffer.from('bad')});
      await page.locator('#import-error-summary').waitFor({state: 'visible'});
      check('Wrong upload format inline error', await page.locator('#import-error-summary').isVisible());
      await page.locator('#import-file').setInputFiles({name: 'qa-browser.tex', mimeType: 'text/plain', buffer: Buffer.from(fixture.sources.general)});
      await settled(); check('Real upload returns three types', (await state()).questions.length === 3);
      await page.locator('.import-filters select').nth(1).selectOption('true_false');
      check('Type filter uses current questions', await page.locator('.import-question').count() === 1);
      await page.getByRole('button', {name: 'Xóa bộ lọc', exact: true}).first().click();
      await page.locator('.import-question').first().getByRole('button', {name: 'Sửa câu', exact: true}).click();
      await page.locator('.import-inline-editor textarea[name="question_text"]').fill('Nội dung duyệt lại $a=1$.');
      await page.getByRole('button', {name: 'Lưu thay đổi', exact: true}).click();
      await page.waitForFunction(() => Alpine.$data(document.querySelector('.import-workspace')).editingIndex === null);
      check('Inline update saved by server', (await state()).questions[0].question_text.includes('Nội dung duyệt lại'));
      await page.getByRole('button', {name: /^Duyệt và lưu/}).first().click();
      check('Review blocks unconfirmed save', await page.getByRole('button', {name: 'Lưu vào ngân hàng', exact: true}).isDisabled());
      await page.locator('input[name="reviewed"]').check();
      await shot('import-confirm-1440');
      await page.getByRole('button', {name: 'Lưu vào ngân hàng', exact: true}).click();
      await page.waitForFunction(() => Alpine.$data(document.querySelector('.import-workspace')).step === 5);
      check('Completed receipt three saved', (await state()).importResult.imported_count === 3 && (await state()).importResult.completed);
      await shot('import-receipt-1440');
      await page.reload(); await settled();
      check('Confirmed resume goes to receipt', (await state()).step === 5);

      await go('/question-banks/import?session_id=' + fixture.sessions.incomplete); await settled();
      await page.getByRole('button', {name: /^Duyệt và lưu/}).first().click();
      await page.locator('input[name="reviewed"]').check();
      await page.getByRole('button', {name: 'Lưu vào ngân hàng', exact: true}).click();
      await page.waitForFunction(() => Alpine.$data(document.querySelector('.import-workspace')).step === 5);
      check('Partial receipt preserves pending answers', !(await state()).importResult.completed);
      check('Pending receipt row labeled unsaved', (await page.locator('.import-receipt-table').innerText()).includes('Chưa lưu'));
      await shot('import-partial-1440');
      await page.getByRole('button', {name: 'Tiếp tục kiểm tra phần còn lại'}).click(); await settled();
      check('Resume exposes strict pending error', (await state()).questions.some(q => q.status === 'error' && q.confirmation_errors?.length));
      const pendingIndex = (await state()).questions.findIndex(q => !q.saved_question_id && q.question_type === 'short_answer');
      const pending = page.locator('#qcard-' + pendingIndex);
      await pending.getByRole('button', {name: 'Sửa câu', exact: true}).click();
      await page.getByLabel('Đáp án được chấp nhận').fill('5 | năm');
      await page.getByLabel('Cách chấm').selectOption('text');
      await page.getByRole('button', {name: 'Lưu thay đổi', exact: true}).click();
      await page.waitForFunction(() => Alpine.$data(document.querySelector('.import-workspace')).editingIndex === null);
      check('Edited answer clears strict error', !(await state()).questions.some(q => q.confirmation_errors?.length));

      await go('/question-banks/import?session_id=' + fixture.sessions.duplicates); await settled();
      await page.getByRole('button', {name: 'Đối chiếu câu này'}).first().click();
      await page.locator('#import-duplicate-dialog[open]').waitFor();
      const decision = page.locator('#import-duplicate-dialog').getByRole('button', {name: 'Giữ cả hai', exact: true}).first();
      await decision.click(); await page.waitForFunction(() => !Alpine.$data(document.querySelector('.import-workspace')).savingDecision);
      check('Duplicate decision persisted', (await state()).duplicateNotice.includes('Đã lưu quyết định'));
      await page.keyboard.press('Escape');
      await page.locator('details.import-destination > summary').click();
      await page.locator('#duplicate-destination').selectOption(String(fixture.banks.empty));
      await page.getByRole('button', {name: 'Đổi đích và dò lại', exact: true}).first().click();
      await page.locator('#import-destination-dialog[open]').waitFor();
      await page.locator('#import-destination-dialog').getByRole('button', {name: 'Đổi đích và dò lại', exact: true}).click();
      await page.waitForFunction(() => !Alpine.$data(document.querySelector('.import-workspace')).changingDestination);
      check('Destination rescan applied to session', (await state()).selectedBankId === String(fixture.banks.empty));

      await go(selectionUrl);
      await page.locator('[data-create-draft]').click();
      check('Selection error summary', await page.locator('[data-selection-errors]').isVisible());
      for (const kind of ['single', 'true_false', 'short_answer']) {
        await page.locator(`[data-pool-question][data-question-kind="${kind}"] input[name="question_ids"]`).first().check();
        await page.locator(`[name="budget_${kind}"]`).fill(kind === 'short_answer' ? '2' : '4');
      }
      check('Manual counts reflect three selections', await page.locator('[data-selection-count]').textContent() === '3');
      await page.locator('[data-create-draft]').click(); await page.waitForURL('**/assessments/import/**');
      check('Manual POST creates editor', await page.locator('[data-question-index]').count() === 3);
      await go(selectionUrl); await page.locator('[name="mode"][value="auto"]').check();
      for (const kind of ['single', 'true_false', 'short_answer']) {
        await page.locator(`[name="count_${kind}"]`).fill('1');
        await page.locator(`[name="budget_${kind}"]`).fill(kind === 'short_answer' ? '2' : '4');
      }
      await page.locator('[data-create-draft]').click(); await page.waitForURL('**/assessments/import/**');
      check('Automatic POST creates editor', await page.locator('[data-question-index]').count() === 3);

      await go('/assessments/import/' + fixture.sessions.paper);
      await page.locator('[name="title"]').fill('Đề kiểm tra QA Phase 5');
      await page.locator('[name="course_id"]').selectOption(String(fixture.courses.teacher));
      await page.locator('[data-question-edit]').first().locator('summary').first().click();
      await page.locator('[name="q0_question_text"]').fill('Nội dung biên soạn $1+1=2$.');
      await page.route('**/assessments/import/' + fixture.sessions.paper, route => route.request().method() === 'POST' ? route.fulfill({status: 403, contentType: 'text/html', body: '<h1>Permission changed</h1>'}) : route.continue());
      await page.locator('button[name="action"][value="draft"]').first().click();
      await page.waitForFunction(() => document.querySelector('.assessment-editor').dataset.saveState === 'error');
      check('Failed editor request preserves DOM draft', await page.locator('[name="q0_question_text"]').inputValue() === 'Nội dung biên soạn $1+1=2$.');
      await shot('editor-save-error-1440');
      await page.unroute('**/assessments/import/' + fixture.sessions.paper);
      await page.locator('button[name="action"][value="draft"]').first().click();
      await page.waitForFunction(() => document.querySelector('.assessment-editor').dataset.saveState === 'saved');
      check('Actual draft save exposes matrix', await page.locator('#assessment-matrix-link').isVisible());
      await page.locator('[data-request-publish]').click();
      check('Publish requires review', !await page.locator('#assessment-publish-dialog').evaluate(n => n.open));
      await page.locator('#assessment-reviewed').check();
      await page.locator('[data-request-publish]').click(); await page.locator('#assessment-publish-dialog[open]').waitFor();
      check('Publish context names actual class', (await page.locator('[data-publish-course]').textContent()).includes('9A'));
      await shot('publish-confirm-1440');
      await page.setViewportSize({width: 375, height: 900});
      check('Publish dialog fits mobile viewport', await page.locator('#assessment-publish-dialog').evaluate(n => n.getBoundingClientRect().width <= innerWidth));
      await shot('publish-confirm-375');
      await page.setViewportSize({width: 1440, height: 1000});
      await page.locator('[data-confirm-publish]').click(); await page.waitForURL('**/assessments');
      check('Publish redirects to list', (await page.locator('main').textContent()).includes('Đề kiểm tra QA Phase 5'));
    }
    await login('admin'); await go('/question-banks/import');
    check('Admin import selector contains permitted foreign bank', (await page.locator('#duplicate-destination').textContent()).includes('Học liệu riêng của giáo viên khác'));
    await login('student');
    const denied = await page.goto(base + '/assessments/from-bank'); check('Student composer forbidden', denied.status() === 403);
    check('No browser JS exceptions', errors.length === 0);
    check('No missing static assets', assetErrors.length === 0);
    check('Scripts/styles/fonts local', external.length === 0);
    const report = {date: '2026-10-15', checks: checks.length, passed: checks, errors, assetErrors, external, screenshots: images};
    fs.writeFileSync(path.join(out, process.env.PHASE5_CAPTURE_ONLY === '1' ? 'capture-qa.json' : 'browser-qa.json'), JSON.stringify(report, null, 2));
    if (fs.existsSync(path.join(out, 'qa-failure.json'))) fs.unlinkSync(path.join(out, 'qa-failure.json'));
    console.log(JSON.stringify({checks: checks.length, screenshots: images.length, errors}));
  } catch (error) {
    fs.writeFileSync(path.join(out, 'qa-failure.json'), JSON.stringify({message: error.message, checks, errors, assetErrors}, null, 2));
    throw error;
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
