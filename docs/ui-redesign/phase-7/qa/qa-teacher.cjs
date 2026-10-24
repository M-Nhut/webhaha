/* Synthetic local preview only. Generation/release POSTs are intercepted. */
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.PHASE7_URL || 'http://127.0.0.1:8769';
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const out = path.resolve('docs/ui-redesign/phase-7'), checks = [], errors = [], assets = [], external = [], shots = [];
const check = (name, valid) => { assert(valid, name); checks.push(name); };
(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}}), page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => { if(response.status() >= 400 && response.url().includes('/static/')) assets.push(response.url()); });
    page.on('request', request => { if(['font','script','stylesheet'].includes(request.resourceType()) && !request.url().startsWith(base)) external.push(request.url()); });
    const fixture = await (await context.request.get(base + '/qa/fixture')).json();
    const login = async name => { await page.goto(base + '/logout'); await page.goto(base + '/login'); await page.locator('[name=username]').fill(name); await page.locator('[name=password]').fill('Academy123!'); await page.locator('[type=submit]').click(); await page.waitForURL(url => url.pathname !== '/login'); };
    const go = async route => { const response = await page.goto(base + route); check('GET '+route, response.status() === 200); await page.locator('.teacher-workspace').waitFor(); };
    const shot = async (name, fullPage = true) => { await page.evaluate(() => { scrollTo(0,0); document.activeElement?.blur(); }); await page.evaluate(async () => { if(window.MathJax?.startup?.promise) await MathJax.startup.promise; }); const file = 'screenshots/'+name+'.png'; await page.screenshot({path:path.join(out,file),fullPage}); shots.push(file); };
    const detail = '/teacher/practice/'+fixture.users.student;
    const routes = [
      ['list','/teacher/practice?course_id='+fixture.courses.teacher],
      ['detail',detail+'?course_id='+fixture.courses.teacher],
      ['cold','/teacher/practice/'+fixture.users.cold+'?course_id='+fixture.courses.teacher],
      ['draft','/teacher/practice/drafts/'+fixture.exams.draft],
      ['draft-locked','/teacher/practice/drafts/'+fixture.exams.draft_locked],
      ['draft-invalid','/teacher/practice/drafts/'+fixture.exams.draft_invalid],
    ];
    await login('qa_teacher');
    for(const width of [375,768,1024,1440]) {
      await page.setViewportSize({width,height:1000});
      for(const [name,route] of routes) {
        await go(route);
        check(name+' no page overflow @'+width, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        check(name+' one page heading @'+width, await page.locator('main h1').count() === 1);
        check(name+' no inline event handlers @'+width, await page.locator('main [onclick],main [onchange]').count() === 0);
        if(name.startsWith('draft')) check(name+' frozen 22 questions @'+width, await page.locator('.teacher-draft-question').count() === 22);
        if(name==='draft-locked') check('Submitted draft disabled @'+width, await page.locator('.teacher-release-fields').evaluate(node => node.disabled) && await page.locator('#draft-title').isDisabled() && await page.locator('[data-draft-release] [type=submit]').count() === 0);
        if(name==='draft-invalid') check('Invalid source cannot publish @'+width, await page.locator('[name=is_active]').isDisabled() && !await page.locator('[name=is_active]').isChecked());
        if((width===375||width===1440)&&['list','detail','draft'].includes(name)) await shot('teacher-'+name+'-'+width, !name.startsWith('draft'));
        if(name === 'detail') {
          await page.locator('.teacher-profile .teacher-disclosure > summary').first().click();
          check('Knowledge matrix open does not overflow page @'+width, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
          check('Knowledge matrix preserves 8 by 4 evidence cells @'+width, await page.locator('.knowledge-matrix-table tbody tr').count() === 8 && await page.locator('.knowledge-matrix-table tbody td').count() === 32);
          if(width === 375 || width === 1440) {
            const file='screenshots/teacher-matrix-'+width+'.png'; await page.locator('.teacher-profile').first().screenshot({path:path.join(out,file)}); shots.push(file);
            await page.locator('#learning-support > summary').click();
            const support='screenshots/teacher-support-'+width+'.png'; await page.locator('#learning-support').screenshot({path:path.join(out,support)}); shots.push(support);
          }
        }
      }
    }
    await page.setViewportSize({width:1440,height:1000});
    await go('/teacher/practice?course_id='+fixture.courses.teacher);
    check('Practice and assessment columns are separate', await page.locator('.teacher-roster-table thead').textContent().then(text => text.includes('Bài tự luyện') && text.includes('Bài kiểm tra')));
    check('Missing averages stay missing', await page.locator('.teacher-roster-table .teacher-no-data').count() > 0);
    await page.locator('#course-select').selectOption(String(fixture.courses.english)); await page.getByRole('button',{name:'Xem lớp',exact:true}).click();
    check('List native GET retains class', new URL(page.url()).searchParams.get('course_id') === String(fixture.courses.english));
    await go('/teacher/practice?course_id='+fixture.courses.empty); check('Empty roster distinct from no class', await page.locator('.teacher-empty h3').textContent() === 'Lớp chưa có học sinh đang tham gia');
    await go(detail); await page.locator('#learning-support > summary').click();
    const form = page.locator('#adaptive-practice-form');
    check('Native form includes CSRF', (await form.locator('[name=csrf_token]').inputValue()).length > 0);
    check('Fixed question count is readonly', await form.locator('[name=total_questions]').getAttribute('readonly') !== null && await form.locator('[name=total_questions]').inputValue() === '22');
    await form.locator('[data-teacher-generate]').click();
    check('Missing sources give focusable summary', await form.locator('[data-teacher-form-errors]').isVisible() && await form.locator('[data-teacher-form-errors]').evaluate(node => node === document.activeElement));
    check('Missing source summary links to bank group', await form.locator('[data-teacher-form-errors] a[href="#adaptive-banks"]').count() === 1);
    const availableBank = form.locator('.adaptive-bank:not([hidden]) input').first(); await availableBank.check();
    await form.locator('#adaptive-course').selectOption(String(fixture.courses.english));
    check('Course change clears invalid checked source', !await form.locator('input[name=bank_ids]:checked').count());
    check('Course change disables all unavailable sources', await form.locator('input[name=bank_ids]:enabled').count() === 0);
    check('No available bank disables generation', await form.locator('[data-teacher-generate]').isDisabled() && await form.locator('[data-teacher-no-banks]').isVisible());
    check('Course source update announced', await form.locator('[data-teacher-source-status]').textContent().then(text => text.includes('Đã bỏ chọn')));
    await form.locator('#adaptive-course').selectOption(String(fixture.courses.teacher)); await form.locator('.adaptive-bank:not([hidden]) input').first().check();
    for(const input of await form.locator('[name=cognitive_levels]').all()) await input.uncheck();
    await form.locator('#mix-weak').fill('59'); await form.locator('[data-teacher-generate]').click();
    check('Cognitive levels and mix both validated', await form.locator('[data-teacher-form-errors] li').count() === 2);
    check('Mix invalid fields labeled', await form.locator('input[name^=mix_][aria-invalid=true]').count() === 3);
    { const file='screenshots/teacher-form-errors-1440.png'; await form.screenshot({path:path.join(out,file)}); shots.push(file); }
    await form.locator('[name=cognitive_levels]').first().check(); await form.locator('#mix-weak').fill('60');
    let generated = null;
    const generateURL = base+'/teacher/practice/'+fixture.users.student+'/generate';
    await page.route(generateURL, async route => { generated = new URLSearchParams(route.request().postData()); await route.fulfill({status:200,contentType:'text/html',body:'<p>QA generation intercepted</p>'}); });
    await form.locator('[data-teacher-generate]').click(); await page.waitForURL(generateURL);
    check('Generation sends canonical native fields', generated?.get('total_questions') === '22' && generated?.getAll('bank_ids').length > 0 && generated?.get('csrf_token') && generated?.get('mix_weak') === '60');
    await page.unroute(generateURL);
    await go('/teacher/practice/drafts/'+fixture.exams.draft);
    check('Draft shows all three answer types', await page.locator('.teacher-draft-answers:not(.is-truth)').count() === 12 && await page.locator('.teacher-draft-answers.is-truth').count() === 4 && await page.locator('.teacher-draft-short').count() === 6);
    await page.locator('#draft-duration').fill('4'); await page.locator('[data-draft-release] [type=submit]').click();
    check('Duration min native validation prevents submit', await page.locator('#draft-duration').evaluate(input => input.validity.rangeUnderflow));
    await page.locator('#draft-duration').fill('180'); await page.locator('#draft-title').fill('Bài luyện · bản duyệt mới'); await page.locator('[name=is_active]').check();
    let released = null; const draftURL = page.url();
    await page.route(draftURL, async route => { if(route.request().method() !== 'POST') return route.continue(); released = new URLSearchParams(route.request().postData()); await route.fulfill({status:200,contentType:'text/html',body:'<p>QA release intercepted</p>'}); });
    await page.locator('[data-draft-release] [type=submit]').click(); await page.getByText('QA release intercepted',{exact:true}).waitFor();
    check('Release posts title duration state and CSRF only', released?.get('title') === 'Bài luyện · bản duyệt mới' && released?.get('duration_minutes') === '180' && released?.get('is_active') === 'on' && released?.has('csrf_token') && [...released.keys()].length === 4);
    await page.unroute(draftURL);
    await go('/teacher/practice/drafts/'+fixture.exams.draft); await page.locator('.teacher-draft-explanation').first().locator('summary').focus(); await page.keyboard.press('Enter');
    check('Native explanation disclosure keyboard accessible', await page.locator('.teacher-draft-explanation').first().evaluate(node => node.open));
    await page.evaluate(() => window.dispatchEvent(new Event('beforeprint')));
    check('Print opens all frozen explanations', await page.locator('.teacher-draft-explanation:not([open])').count() === 0);
    await page.pdf({path:path.join(out,'qa/teacher-draft-a4.pdf'),format:'A4',printBackground:true,margin:{top:'12mm',bottom:'12mm',left:'12mm',right:'12mm'}});
    await page.evaluate(() => window.dispatchEvent(new Event('afterprint')));
    check('Print restores previously collapsed disclosures', await page.locator('.teacher-draft-explanation[open]').count() === 1);
    if(await page.locator('[data-draft-image]').count()) {
      await page.locator('[data-draft-image]').first().scrollIntoViewIfNeeded(); await page.locator('[data-draft-image-open]').first().click();
      check('Image opens native dialog', await page.locator('#draft-image-dialog').evaluate(node => node.open)); await page.keyboard.press('Escape');
      check('Image Escape returns focus', await page.locator('[data-draft-image-open]').first().evaluate(node => node === document.activeElement));
    }
    await page.emulateMedia({reducedMotion:'reduce'}); await go(detail+'?course_id='+fixture.courses.teacher);
    check('Reduced motion retains profile', await page.locator('.teacher-profile').count() > 0);
    const foreign = await page.goto(base+detail+'?course_id='+fixture.courses.foreign); check('Foreign teacher scope remains forbidden', foreign.status() === 403);
    await login('qa_empty_teacher'); await go('/teacher/practice'); check('No teacher classes has distinct empty state', await page.getByRole('heading',{name:'Chưa có lớp để theo dõi'}).count() === 1);
    await login('qa_admin'); await go(detail+'?course_id='+fixture.courses.foreign); check('Administrator can inspect enrolled foreign class', await page.locator('#learning-course').inputValue() === String(fixture.courses.foreign));
    check('No JavaScript exceptions', errors.length === 0); check('No broken static assets',assets.length === 0); check('No external scripts styles fonts',external.length === 0);
    fs.writeFileSync(path.join(out,'teacher-qa.json'), JSON.stringify({date:'2026-10-15',checks:checks.length,passed:checks,errors,assets,external,screenshots:shots,postWrites:'Only login; generation and release POSTs intercepted.'},null,2));
    if(fs.existsSync(path.join(out,'teacher-failure.json'))) fs.unlinkSync(path.join(out,'teacher-failure.json')); console.log(JSON.stringify({checks:checks.length,errors,screenshots:shots.length}));
  } catch(error) { fs.writeFileSync(path.join(out,'teacher-failure.json'),JSON.stringify({message:error.message,checks,errors,assets},null,2)); throw error; } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
