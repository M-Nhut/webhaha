/* Repeatable read-only UI QA against the synthetic Phase 9 preview. */
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.QUESTION_UNIFIED_URL || 'http://127.0.0.1:8772';
const out = path.resolve('docs/ui-redesign/question-unified');
(async () => {
  const checks = [], errors = [], assets = [], writes = [], shots = [], detailRequests = [];
  const check = (name, value) => { assert.ok(value, name); checks.push(name); };
  fs.mkdirSync(path.join(out, 'screenshots'), {recursive:true});
  let browser;
  try {
    browser = await chromium.launch({channel:'chrome',headless:true});
    const context = await browser.newContext({locale:'vi-VN',reducedMotion:'reduce',viewport:{width:1440,height:1000}});
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
    page.on('response', response => { if (response.status() >= 400 && response.url().includes('/static/')) assets.push(response.url()); });
    page.on('request', request => {
      const url = new URL(request.url());
      if (!['GET','HEAD','OPTIONS'].includes(request.method()) && url.pathname !== '/login') writes.push({method:request.method(),path:url.pathname});
      if (request.method() === 'GET' && /\/api\/question-banks\/\d+\/questions\/\d+$/.test(url.pathname)) detailRequests.push(url.pathname);
    });
    const response = await context.request.get(base + '/qa/fixture');
    check('Synthetic fixture available',response.ok());
    const fixture = await response.json();
    await page.goto(base + '/login');
    await page.locator('[name=username]').fill('qa_teacher');
    await page.locator('[name=password]').fill('Academy123!');
    await page.locator('#login-form [type=submit]').click();
    await page.waitForURL(url => url.pathname !== '/login');
    const settle = async () => page.evaluate(async () => { await document.fonts.ready; if (window.MathJax?.startup?.promise) await MathJax.startup.promise; });
    const go = async (route, selector) => {
      const response = await page.goto(base + route);
      check('GET ' + route + ' HTTP200',response.status() === 200);
      await page.locator(selector).first().waitFor({state:'visible'});
      await settle();
    };
    const overflow = async name => check(name + ' no page overflow',await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    const surface = async (node,name) => check(name + ' shared surface28',await node.evaluate(node => getComputedStyle(node).borderRadius === '28px' && getComputedStyle(node).boxShadow !== 'none'));
    const option = async (node,name,width) => {
      check(name + ' shared option22',await node.evaluate(node => getComputedStyle(node).borderRadius === '22px' && getComputedStyle(node).boxShadow !== 'none'));
      const letter = node.locator('.question-letter').first();
      if (await letter.count()) { check(name + ' circle size',await letter.evaluate((node,size) => Math.abs(node.getBoundingClientRect().width - size) < 1,width < 768 ? 38 : 44)); check(name + ' circle label normalized',/^[A-Za-z]$/.test((await letter.innerText()).trim())); }
      const text = node.locator('.question-option-text').first();
      if (await text.count()) check(name + ' readable20',await text.evaluate(node => getComputedStyle(node).fontSize === '20px'));
    };
    const shot = async (name,node) => {
      const relative = 'screenshots/' + name + '.png';
      await node.screenshot({path:path.join(out,relative),style:'.topbar,.skip-link{visibility:hidden !important;}'});
      shots.push(relative);
    };
    for (const width of [375,768,1024,1440]) {
      await page.setViewportSize({width,height:1000});
      await go('/question-banks/' + fixture.banks.general,'.bank-question-card');
      await overflow('Bank@' + width);
      const cards = {};
      for (const [key,kind] of [['general-single','single'],['general-tf','TF'],['general-short','short']]) {
        const id = fixture.questions[key], card = page.locator('#qcard-' + id), api = '/api/question-banks/' + fixture.banks.general + '/questions/' + id;
        cards[kind] = card;
        await surface(card,'Bank ' + kind + '@' + width);
        check('Bank ' + kind + ' lazy initially closed@' + width,!await card.locator('.bank-detail-content').count());
        const before = detailRequests.filter(value => value === api).length;
        await card.getByRole('button',{name:'Xem đáp án và lời giải',exact:true}).click();
        await card.locator('.bank-detail-content').waitFor({state:'visible'});
        check('Bank ' + kind + ' lazy detail GET@' + width,detailRequests.filter(value => value === api).length === before + 1);
        if (kind !== 'short') await option(card.locator('.question-option').first(),'Bank ' + kind + '@' + width,width);
        else check('Bank short readonly box@' + width,await card.locator('.bank-short-answer.question-answer-box').isVisible());
        check('Bank ' + kind + ' solution shared@' + width,await card.locator('.bank-solution.question-solution').isVisible());
        await card.getByRole('button',{name:'Thu gọn đáp án và lời giải',exact:true}).click();
        await card.getByRole('button',{name:'Xem đáp án và lời giải',exact:true}).click();
        check('Bank ' + kind + ' cached reopening@' + width,detailRequests.filter(value => value === api).length === before + 1);
      }
      check('Bank correct answer label@' + width,(await cards.single.locator('.is-answer-selected').first().innerText()).includes('Đáp án đúng'));
      await page.waitForFunction(() => !!document.querySelector('.bank-question-card mjx-container'));
      check('Bank MathJax visible@' + width,await page.locator('.bank-question-card mjx-container').count() > 0);
      await overflow('Bank details@' + width);
      if ([375,1440].includes(width)) await shot('bank-single-' + width,cards.single);
      await cards.single.getByRole('button',{name:'Sửa',exact:true}).click();
      const editor = page.locator('.bank-inline-editor');
      await editor.waitFor({state:'visible'});
      await editor.locator('textarea[required]').first().fill('Bản xem trước chưa lưu: $x^2=4$.');
      const editPreview = editor.locator('.bank-edit-preview');
      await surface(editPreview,'Bank inline preview@' + width);
      await option(editPreview.locator('.question-option').first(),'Bank inline option@' + width,width);
      check('Bank inline draft visible@' + width,(await editPreview.innerText()).includes('Bản xem trước chưa lưu'));
      await editor.getByRole('button',{name:'Hủy chỉnh sửa',exact:true}).click();
      check('Bank cancel retains source@' + width,!(await cards.single.innerText()).includes('Bản xem trước chưa lưu'));

      await page.getByRole('button',{name:'Thêm câu hỏi',exact:true}).first().click();
      const dialog = page.locator('#add-question-modal');
      await dialog.waitFor({state:'visible'});
      await page.locator('#manual-context').fill('Dữ kiện xem trước, chưa lưu.');
      await page.locator('#manual-prompt').fill('Tính $1+1$ trong bản xem trước.');
      await page.locator('#manual-explanation').fill('Ta có $1+1=2$.');
      for (const kind of ['single','true_false','short_answer']) {
        await dialog.locator('select[name=question_type]').selectOption(kind);
        if (kind === 'single') for (let i=0;i<4;i++) await page.locator('#manual-option-' + i).fill('$x=' + (i+1) + '$');
        if (kind === 'true_false') for (let i=0;i<4;i++) await page.locator('#manual-statement-' + i).fill('Mệnh đề ' + (i+1) + ': $1<2$.');
        if (kind === 'short_answer') { await page.locator('#manual-short-answers').fill('2 | hai'); await page.locator('#manual-short-mode').selectOption('text'); }
        await dialog.locator('[data-manual-preview-button]').click();
        const preview = dialog.locator('[data-manual-preview]');
        await preview.waitFor({state:'visible'});
        await surface(preview,'Manual ' + kind + '@' + width);
        if (kind !== 'short_answer') await option(preview.locator('.question-option').first(),'Manual ' + kind + '@' + width,width);
        else check('Manual short answer text@' + width,(await preview.locator('.question-answer-box').innerText()).includes('2 | hai'));
        check('Manual shared solution@' + width,await preview.locator('.question-solution').isVisible());
        if (kind === 'single' && [375,1440].includes(width)) await shot('manual-preview-' + width,preview);
      }
      check('Manual dialog fits@' + width,await dialog.evaluate(node => node.scrollWidth <= node.clientWidth + 1));
      await page.keyboard.press('Escape');

      await go('/question-banks/' + fixture.banks.research + '/classification?status=all','.classification-question');
      await overflow('Classification@' + width);
      await surface(page.locator('.classification-question').first(),'Classification@' + width);
      check('Classification reading20@' + width,await page.locator('.knowledge-question-text').first().evaluate(node => getComputedStyle(node).fontSize === '20px'));
      if ([375,1440].includes(width)) await shot('classification-' + width,page.locator('.classification-question').first());

      await go('/question-banks/import?session_id=' + fixture.sessions.general,'.import-question');
      await overflow('Import@' + width);
      for (let i=0;i<3;i++) {
        const card = page.locator('.import-question').nth(i);
        await surface(card,'Import type' + i + '@' + width);
        check('Import reading20 type' + i + '@' + width,await card.locator('.import-question-text').evaluate(node => getComputedStyle(node).fontSize === '20px'));
        if (i < 2) await option(card.locator('.question-option').first(),'Import option' + i + '@' + width,width);
        else check('Import short shared box@' + width,await card.locator('.import-short-answer.question-answer-box').isVisible());
        const solution = card.locator('.import-solution');
        if (await solution.count()) { await solution.locator('summary').click(); check('Import solution shared@' + width,await solution.locator('.question-solution').isVisible()); }
        if ([375,1440].includes(width)) await shot('import-type' + i + '-' + width,card);
      }
      check('Import correct option labels@' + width,(await page.locator('.import-question').first().locator('.import-answer-button[aria-pressed=true]').innerText()).includes('Đáp án đúng'));
      check('Import TF four statement controls@' + width,await page.locator('.import-question').nth(1).locator('.import-statement .import-answer-button[aria-pressed=true]').count() === 4);
      await page.locator('.import-question').first().getByRole('button',{name:'Sửa câu',exact:true}).click();
      const importEditor = page.locator('.import-inline-editor');
      await importEditor.waitFor({state:'visible'});
      await importEditor.locator('textarea[name=question_text]').fill('Nội dung xem trước chưa lưu $2+2$.');
      check('Import inline shared preview@' + width,await importEditor.locator('.import-preview.question-answer-box').isVisible());
      check('Import inline preview updates@' + width,(await importEditor.locator('.import-preview.question-answer-box').innerText()).includes('Nội dung xem trước chưa lưu'));
      await importEditor.getByRole('button',{name:'Hủy sửa',exact:true}).click();
      await overflow('Import expanded@' + width);

      await go('/question-banks/import?session_id=' + fixture.sessions.duplicates,'.import-question');
      await page.getByRole('button',{name:'Đối chiếu câu này',exact:true}).first().click();
      const comparison = page.locator('#import-duplicate-dialog');
      await comparison.waitFor({state:'visible'});
      const pair = comparison.locator('.duplicate-pair').first(), copies = pair.locator('.duplicate-copy');
      check('Duplicate pair preserves two copies@' + width,await copies.count() === 2);
      for (let i=0;i<2;i++) {
        await surface(copies.nth(i),'Duplicate copy' + i + '@' + width);
        check('Duplicate question reading20@' + width,await copies.nth(i).locator('.duplicate-question').evaluate(node => getComputedStyle(node).fontSize === '20px'));
        await option(copies.nth(i).locator('.question-option').first(),'Duplicate option' + i + '@' + width,width);
      }
      check('Duplicate decision buttons retained@' + width,await comparison.getByRole('button',{name:'Giữ cả hai',exact:true}).first().isVisible());
      check('Duplicate dialog no horizontal overflow@' + width,await comparison.evaluate(node => node.scrollWidth <= node.clientWidth + 1));
      if ([375,1440].includes(width)) await shot('duplicate-comparison-' + width,comparison);
      await comparison.getByRole('button',{name:'Đóng đối chiếu',exact:true}).click();
      await overflow('Duplicate closed@' + width);
    }
    check('No unexpected business writes',writes.length === 0);
    check('No JavaScript runtime errors',errors.length === 0);
    check('No broken static assets',assets.length === 0);
    const report = {status:'passed',base,checks:checks.length,passed:checks,errors,assets,writes,screenshots:shots,syntheticOnly:true};
    fs.writeFileSync(path.join(out,'browser-bank.json'),JSON.stringify(report,null,2) + '\n');
    console.log(JSON.stringify({status:'passed',checks:checks.length,screenshots:shots.length}));
  } catch (error) {
    fs.writeFileSync(path.join(out,'browser-bank.json'),JSON.stringify({status:'failed',base,checks:checks.length,passed:checks,error:error.stack,errors,assets,writes,screenshots:shots,syntheticOnly:true},null,2) + '\n');
    console.error(error); process.exitCode = 1;
  } finally { if (browser) await browser.close(); }
})();
