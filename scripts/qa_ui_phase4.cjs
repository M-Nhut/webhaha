/* End-to-end UI QA. Run only against preview_ui_phase4.py, with fake data. */
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const base = process.env.PHASE4_PREVIEW_URL || 'http://127.0.0.1:8766';
const captureOnly = process.env.PHASE4_CAPTURE_ONLY === '1';
const output = path.resolve(__dirname, '../docs/ui-redesign/phase-4');
const checks = [], errors = [], external = new Set();
fs.mkdirSync(path.join(output, 'screenshots'), {recursive: true});
const check = (name, condition, detail) => {
  checks.push({name, passed: !!condition, ...(detail === undefined ? {} : {detail})});
  assert.ok(condition, `${name}: ${JSON.stringify(detail)}`);
};
async function ready(page, url) {
  const response = await page.goto(base + url, {waitUntil: 'networkidle'});
  await page.evaluate(() => document.fonts.ready);
  return response;
}
async function login(page, role = 'teacher') {
  await ready(page, '/login');
  await page.locator('[name=username]').fill('qa_' + role);
  await page.locator('[name=password]').fill('Academy123!');
  await Promise.all([page.waitForNavigation(), page.locator('[name=submit]').click()]);
  check('native login ' + role, new URL(page.url()).pathname === '/');
}
async function layout(page, name, url, width) {
  await page.setViewportSize({width, height: 1000});
  const response = await ready(page, url);
  const data = await page.evaluate(() => ({
    viewport: innerWidth, documentWidth: document.documentElement.scrollWidth,
    h1: document.querySelectorAll('h1').length,
    font: getComputedStyle(document.body).fontFamily,
    icons: document.querySelectorAll('i[data-lucide]').length,
    duplicates: [...document.querySelectorAll('[id]')].map(el => el.id).filter((id, i, all) => all.indexOf(id) !== i),
    missingImages: [...document.images].filter(el => el.complete && !el.naturalWidth).map(el => el.getAttribute('src'))
  }));
  check(`${name}/${width} HTTP`, response.status() === 200, response.status());
  check(`${name}/${width} responsive`, data.documentWidth <= width + 1, data);
  check(`${name}/${width} headings and IDs`, data.h1 === 1 && !data.duplicates.length, data);
  check(`${name}/${width} local font/icons/media`, data.font.includes('Be Vietnam Pro') && !data.icons && !data.missingImages.length, data);
  if ([375,1440].includes(width)) {
    if (await page.locator('.bank-detail-page').count()) {
      await page.evaluate(async () => {
        await window.MathJax.startup.promise;
        await window.renderFormulas(document.querySelector('.bank-detail-page'), undefined, {immediate:true});
        await document.fonts.ready;
      });
    }
    await page.screenshot({path: path.join(output, 'screenshots', `${name}-${width}.png`), fullPage: true});
  }
}
async function addQuestion(page, bank, type, title, research = false) {
  await ready(page, '/question-banks/' + bank);
  await page.locator('[data-add-question-open]').click();
  const dialog = page.locator('#add-question-modal');
  await dialog.locator('#manual-prompt').fill(title);
  if (research) await dialog.locator('.id6-fields select:not([name])').selectOption('1');
  else await dialog.locator('[name=question_category]').fill('Dạng tổng quát QA');
  await dialog.locator('[name=question_type]').selectOption(type);
  if (type === 'single') {
    for (let i = 0; i < 4; i++) await dialog.locator('#manual-option-' + i).fill(String(i + 1));
  } else if (type === 'true_false') {
    for (let i = 0; i < 4; i++) await dialog.locator('#manual-statement-' + i).fill('Phát biểu kiểm thử ' + i);
  } else {
    await dialog.locator('#manual-short-answers').fill('0.5 | 1/2');
    await dialog.locator('#manual-short-mode').selectOption('numeric');
  }
  await dialog.locator('[name=reviewed]').check();
  await Promise.all([page.waitForNavigation(), dialog.locator('button[type=submit]').click()]);
  await page.waitForLoadState('networkidle');
  const flash = await page.locator('.flash').allTextContents();
  check(`native add ${type}/${research ? 'research' : 'general'}`, flash.some(text => text.includes('Đã thêm câu hỏi mới')), flash);
  const result = await ready(page, '/question-banks/' + bank + '?q=' + encodeURIComponent(title));
  check(`saved ${type} visible`, result.status() === 200 && await page.locator('.bank-question-card').count() === 1);
  await page.locator('.bank-detail-toolbar button').first().click();
  await page.waitForFunction(() => window.Alpine.$data(document.querySelector('[x-data^="bankQuestionsManager"]')).questions[0].detailsLoaded);
  const row = await page.evaluate(() => window.Alpine.$data(document.querySelector('[x-data^="bankQuestionsManager"]')).questions[0]);
  check(`saved ${type} answer structure`, row.question_type === type && row.detailsLoaded && row.can_edit && row.options.length === (type === 'short_answer' ? 2 : 4), {type:row.question_type, options:row.options.length, node:row.curriculum_node_id});
  if (!research) check(`saved ${type} human category`, row.curriculum_node_id === null && row.question_category === 'Dạng tổng quát QA', row.question_category);
  return row;
}
(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}, locale:'vi-VN'});
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (!request.url().startsWith(base) && !request.url().startsWith('data:') && !request.url().startsWith('blob:')) external.add(request.url()); });
    const fixture = await (await context.request.get(base + '/qa/fixture')).json();
    check('synthetic fixture loaded', fixture.banks.general === 2 && fixture.banks.research === 3);
    await login(page);
    for (const [name,url] of [['bank-list','/question-banks'], ['bank-form','/question-banks/new'], ['bank-general','/question-banks/2'], ['bank-research','/question-banks/3'], ['classification','/question-banks/3/classification?status=all'], ['evaluation','/question-banks/3/classification/evaluation'], ['catalog-teacher','/curriculum']]) {
      for (const width of [375,768,1024,1440]) await layout(page,name,url,width);
    }
    await layout(page,'bank-common','/question-banks/1',1440);
    await layout(page,'bank-empty','/question-banks/6',375);
    await layout(page,'classification-empty','/question-banks/3/classification?q=no-such-content',375);
    await ready(page,'/question-banks/2');
    await page.locator('.bank-question-prompt').first().scrollIntoViewIfNeeded();
    await page.waitForSelector('mjx-container');
    check('local MathJax renders question', await page.locator('mjx-container').count() > 0);
    for (const width of [375,1440]) {
      await page.setViewportSize({width,height:1000});
      await page.locator('[data-add-question-open]').click();
      await page.screenshot({path:path.join(output,'screenshots',`question-dialog-${width}.png`)});
      await page.keyboard.press('Escape');
    }
    await page.setViewportSize({width:1440,height:1000});
    if (captureOnly) {
      await ready(page,'/logout'); await login(page,'admin');
      for (const width of [375,1440]) await layout(page,'catalog-admin','/curriculum?inactive=1',width);
      check('capture has no browser JS errors', !errors.length, errors);
      check('capture has no external requests', !external.size, [...external]);
      return;
    }
    const singleId = fixture.questions['general-single'];
    await ready(page, '/question-banks/2?q=' + encodeURIComponent('Giải phương trình'));
    await page.getByRole('button',{name:'Sửa',exact:true}).first().click();
    const editor = page.locator('.bank-inline-editor');
    await editor.waitFor();
    await editor.locator('textarea[required]').first().fill('Câu đã chỉnh sửa bằng POST thật $x=2$.');
    await editor.locator('input[type=checkbox]').last().check();
    await Promise.all([page.waitForNavigation(), editor.getByRole('button',{name:'Lưu thay đổi',exact:true}).click()]);
    const edited = await (await context.request.get(base + `/api/question-banks/2/questions/${singleId}`)).json();
    check('inline edit native JSON saved', edited.success && edited.question.can_edit && edited.question.question_text.includes('Câu đã chỉnh sửa'));

    for (const type of ['single','true_false','short_answer']) await addQuestion(page,2,type,'UI Phase 4 mới ' + type);
    const overlay = await addQuestion(page,1,'single','UI Phase 4 đóng góp riêng',true);
    check('teacher shared contribution stays private', overlay.source === 'private' && overlay.can_edit && overlay.source_label.includes('chỉ bạn'));
    const researchTF = await addQuestion(page,3,'true_false','UI Phase 4 Đúng Sai nghiên cứu',true);
    check('research TF preserves four statement labels', researchTF.learning_metadata.statements.length === 4 && researchTF.learning_metadata.statements.every(row => row.curriculum_code === '9C8-i-1'));

    await ready(page, '/question-banks/3/classification?status=all');
    await page.locator(`.question-checkbox[value="${fixture.questions.unclassified}"]`).check();
    await page.locator('#classification-form .id6-fields select:not([name])').selectOption('2');
    await page.locator('#classification-form [name=difficulty_level]').selectOption('thong_hieu');
    await Promise.all([page.waitForNavigation(), page.locator('[data-manual-submit]').click()]);
    check('native bulk classification saves', (await page.locator('.flash').textContent()).includes('Đã xác nhận phân loại kiến thức'));
    await ready(page, '/question-banks/3/classification?status=suggested');
    await page.locator(`.question-checkbox[value="${fixture.questions.suggested}"]`).check();
    await Promise.all([page.waitForNavigation(), page.locator('[data-suggestion-submit]').click()]);
    check('native current suggestion confirmation', (await page.locator('.flash').textContent()).includes('Đã xác nhận 1 gợi ý'));

    await ready(page,'/question-banks/3/classification/evaluation');
    await page.locator('#labels-file').setInputFiles({name:'invalid.json',mimeType:'application/json',buffer:Buffer.from('[42]')});
    await Promise.all([page.waitForNavigation(),page.locator('[data-labels-submit]').click()]);
    check('bad JSON structure has focused UI error', await page.locator('[data-knowledge-error]').isVisible() && await page.locator('[data-knowledge-error]').evaluate(el => el === document.activeElement));
    await page.screenshot({path:path.join(output,'screenshots','evaluation-error-1440.png'),fullPage:true});
    await page.locator('#labels-file').setInputFiles({name:'labels.json',mimeType:'application/json',buffer:Buffer.from('[]')});
    await Promise.all([page.waitForNavigation(),page.locator('[data-labels-submit]').click()]);
    check('empty report does not claim readiness', (await page.locator('.knowledge-gate').textContent()).includes('Chưa đạt') && (await page.locator('.knowledge-evaluation-metrics').textContent()).includes('Chưa đủ dữ liệu'));
    await page.screenshot({path:path.join(output,'screenshots','evaluation-report-1440.png'),fullPage:true});

    await ready(page,'/question-banks/new');
    await page.locator('[name=name]').fill('UI Phase 4 · Ngân hàng tạm');
    await page.locator('[name=subject]').selectOption('Toán');
    await page.locator('[name=grade]').fill('10');
    await Promise.all([page.waitForNavigation(),page.locator('[data-bank-form-submit]').click()]);
    check('native bank metadata create', new URL(page.url()).pathname.startsWith('/question-banks/') && (await page.locator('.flash').textContent()).includes('Đã tạo ngân hàng'));
    const newBank = new URL(page.url()).pathname.split('/').at(-1);
    await ready(page,'/question-banks/' + newBank + '/edit');
    await page.locator('[name=name]').fill('UI Phase 4 · Ngân hàng đã sửa');
    await Promise.all([page.waitForNavigation(),page.locator('[data-bank-form-submit]').click()]);
    check('native bank metadata edit', (await page.locator('h1').textContent()).includes('Ngân hàng đã sửa'));
    await ready(page,'/question-banks');
    await page.locator(`form[action="/question-banks/${newBank}/delete"] [data-bank-delete-open]`).click();
    check('delete dialog names correct bank', (await page.locator('[data-bank-delete-name]').textContent()).includes('Ngân hàng đã sửa'));
    await Promise.all([page.waitForNavigation(),page.locator('[data-bank-delete-confirm]').click()]);
    check('native delete correct disposable bank', (await page.locator('.flash').textContent()).includes('Đã xóa hoàn toàn') && !await page.locator(`form[action="/question-banks/${newBank}/delete"]`).count());

    await ready(page,'/logout');
    await login(page,'admin');
    for (const width of [375,1440]) await layout(page,'catalog-admin','/curriculum?inactive=1',width);
    await page.locator('[data-catalog-edit]').first().click();
    await page.locator('#catalog-edit-name').fill('Dạng đã sửa bằng giao diện QA');
    await Promise.all([page.waitForNavigation(),page.locator('#catalog-editor button[type=submit]').click()]);
    check('native admin catalog upsert', (await page.locator('.flash').textContent()).includes('Đã cập nhật') && (await page.locator('.knowledge-catalog-results').textContent()).includes('Dạng đã sửa bằng giao diện QA'));
    await page.locator('[data-catalog-open]').click();
    const example = await page.locator('#catalog-rows-example').textContent();
    await page.locator('#catalog-rows').fill(example);
    await Promise.all([page.waitForNavigation(),page.locator('[data-catalog-bulk] button[type=submit]').click()]);
    check('native catalog bulk example accepted', (await page.locator('.flash-success').textContent()).includes('1'));
    await page.locator('.knowledge-catalog-row-actions form').first().locator('button').click();
    await page.waitForURL('**/curriculum?inactive=1');
    check('native admin catalog toggle', (await page.locator('.flash-success').textContent()).includes('ngừng sử dụng') && (await page.locator('.knowledge-catalog-table tbody tr').first().textContent()).includes('Ngừng dùng'));
    check('no browser JS errors', !errors.length, errors);
    check('no external font/script requests', !external.size, [...external]);
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(output,captureOnly ? 'capture-qa.json' : 'browser-qa.json'),JSON.stringify({date:'2026-10-14',captureOnly,checks,errors,externalRequests:[...external]},null,2)+'\n');
    console.log(JSON.stringify({passed:checks.filter(row=>row.passed).length,total:checks.length,output}));
  }
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
