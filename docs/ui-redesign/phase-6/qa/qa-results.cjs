/* Read-only S13 browser review. Auth POSTs only; result actions are never submitted. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.PHASE6_URL || 'http://127.0.0.1:8768';
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const out = path.resolve('docs/ui-redesign/phase-6');
const checks = [], errors = [], assets = [], external = [];
const check = (name, value) => {assert(value, name); checks.push(name);};
(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const fixtureContext = await browser.newContext();
    const fixture = await (await fixtureContext.request.get(base + '/qa/fixture')).json();
    await fixtureContext.close();
    for (const role of ['student', 'teacher', 'admin']) {
      const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
      const page = await context.newPage();
      page.on('pageerror', error => errors.push(error.message));
      page.on('response', response => {if (response.status() >= 400 && response.url().includes('/static/')) assets.push(response.url());});
      page.on('request', request => {if (['script','font','stylesheet'].includes(request.resourceType()) && !request.url().startsWith(base)) external.push(request.url());});
      await page.goto(base + '/login');
      await page.locator('#username').fill('qa_' + role); await page.locator('#password').fill('Academy123!');
      await page.locator('#login-form [type=submit]').click(); await page.waitForURL(url => url.pathname !== '/login');
      await page.route('**/*', async route => {
        const request = route.request();
        if (request.method() !== 'GET' && !request.url().includes('/api/formulas/batch')) return route.abort();
        return route.continue();
      });
      const go = async (key, submission = true) => {
        const endpoint = ['decision','source_invalid','diagnostic_done','multi_history'].includes(key) ? 'practice' : 'assessments';
        const suffix = role !== 'student' && submission && fixture.submissions[key] ? '?submission_id=' + fixture.submissions[key] : '';
        const response = await page.goto(`${base}/${endpoint}/${fixture.exams[key]}/result${suffix}`);
        check(`${role} ${key} HTTP200`, response.status() === 200);
        await page.locator('.results-page').waitFor(); await page.evaluate(() => document.fonts.ready);
      };
      const shot = async name => {
        await page.evaluate(async () => {await window.MathJax?.startup?.promise; await window.renderFormulas?.(document.querySelector('.results-page'), {}, {immediate:true});});
        await page.evaluate(() => {document.activeElement?.blur(); window.scrollTo(0,0);});
        await page.screenshot({path:path.join(out,'screenshots', name+'.png'),fullPage:true});
      };
      await go('graded');
      check(`${role} four question reviews`, await page.locator('[data-result-question]').count() === 4);
      for (const state of ['correct','partial','blank','incorrect']) check(`${role} ${state} status labeled`, await page.locator(`.result-question.is-${state}`).count() === 1);
      check(`${role} score on ten`, (await page.locator('.result-score-value').innerText()).includes('/ 10'));
      check(`${role} no forbidden decision`, await page.locator('[data-result-decision]').count() === 0);
      const explanation = page.locator('[data-result-explanation]').first();
      await explanation.locator('summary').click();
      check(`${role} native explanation disclosure`, await explanation.getAttribute('open') !== null);
      if (role === 'student') {
        for (const width of [1440, 1024, 768, 375]) {
          await page.setViewportSize({width,height:1000});
          check(`student review no overflow ${width}`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
          if ([1440,375].includes(width)) await shot('result-graded-' + width);
        }
        if (await page.locator('[data-result-image-open]').count()) {
          const opener = page.locator('[data-result-image-open]').first(); await opener.click();
          check('Image native lightbox open', await page.locator('#result-image-dialog').getAttribute('open') !== null);
          await page.keyboard.press('Escape');
          check('Image lightbox restores focus', await opener.evaluate(el => document.activeElement === el));
        }
        await page.setViewportSize({width:1440,height:1000});
      }
      await go('history');
      check(`${role} ungraded neutral summary`, await page.locator('.result-score-unknown').innerText() === 'Chưa chấm');
      check(`${role} history excludes incorrect evidence`, await page.locator('.result-question.is-incorrect').count() === 0);
      check(`${role} history explanation warning`, (await page.locator('.result-notice').innerText()).includes('không được dùng làm bằng chứng năng lực'));
      if (role === 'student') await shot('result-history-1440');
      await go('multi_history');
      check(`${role} multiple history readable`, (await page.locator('.result-question-kind').first().innerText()).includes('Nhiều lựa chọn'));
      check(`${role} multiple choices retained`, await page.locator('.result-question').first().locator('.result-choice').count() === 4);
      if (role === 'student') {
        for (const key of ['decision','source_invalid','diagnostic_done']) {
          await go(key);
          if (key === 'decision') {check('Valid practice continue POST', await page.locator('form[action*="continue"][method="POST"]').count() === 1); check('Valid practice end POST', await page.locator('form[action*="end"][method="POST"]').count() === 1); check('Selection audit disclosure', await page.locator('.result-audit').count() === 1);}
          if (key === 'source_invalid') {check('Invalid source has no continue CTA', await page.locator('form[action*="continue"]').count() === 0); check('Invalid source reason readable', await page.locator('.result-source-warning').isVisible());}
          if (key === 'diagnostic_done') check('Diagnostic completion context', (await page.locator('.result-notice').innerText()).includes('Đã hoàn tất đánh giá đầu vào'));
          await shot('result-' + key + '-1440');
          await page.setViewportSize({width:375,height:900});
          check(key+' no mobile overflow', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
          if (key === 'source_invalid') await shot('result-source-invalid-375');
          await page.setViewportSize({width:1440,height:1000});
        }
      } else {
        await go('graded', false);
        check(role + ' submission list separate layout', await page.locator('.results-table').count() === 1 && await page.locator('.result-score').count() === 0);
        check(role + ' submission details link', await page.locator('.results-table a[href*="submission_id"]').count() >= 1);
        if (role === 'teacher') {
          await shot('result-submissions-1440'); await page.setViewportSize({width:375,height:900});
          check('Submission mobile card layout', await page.locator('.results-table tbody tr').first().evaluate(el => getComputedStyle(el).display) === 'block');
          check('Submission mobile no overflow', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
          await shot('result-submissions-375'); await page.setViewportSize({width:1440,height:1000});
        }
        await go('empty',false); check(role + ' empty list truthful', await page.locator('.results-empty').isVisible());
        if (role === 'teacher') await shot('result-submissions-empty-1440');
      }
      await context.close();
    }
    check('No result JS errors', errors.length === 0); check('No missing static assets', assets.length === 0); check('Only local script/font/styles', external.length === 0);
    fs.writeFileSync(path.join(out,'result-qa.json'), JSON.stringify({passed:checks.length,checks,errors,assets,external,readOnly:true},null,2));
    console.log(JSON.stringify({passed:checks.length,errors,assets,external}));
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode=1;});
