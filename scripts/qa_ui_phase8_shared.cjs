/* Read-only regression of the shared CSS used by earlier redesign phases. */
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.PHASE8_URL || 'http://127.0.0.1:8770';
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const output = path.resolve('docs/ui-redesign/phase-8');
(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  const checks = [], errors = [], brokenAssets = [], external = [];
  const check = (name, value) => {assert(value, name); checks.push(name);};
  try {
    const context = await browser.newContext({locale:'vi-VN'}), page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => {if (response.status() >= 400 && response.url().includes('/static/')) brokenAssets.push(response.url());});
    page.on('request', request => {if (['script','stylesheet','font'].includes(request.resourceType()) && !request.url().startsWith(base)) external.push(request.url());});
    const data = await (await context.request.get(base+'/qa/fixture')).json();
    const login = async role => {
      await page.goto(base+'/logout'); await page.goto(base+'/login');
      await page.locator('[name=username]').fill('qa_'+role);
      await page.locator('[name=password]').fill('Academy123!');
      await page.locator('[type=submit]').click(); await page.waitForURL(url => url.pathname !== '/login');
    };
    for (const width of [375,1440]) {
      await page.setViewportSize({width,height:1000});
      for (const [role, routes] of [
        ['teacher', ['/question-banks', `/question-banks/${data.banks.diagnostic}`, '/assessments', '/diagnostics', '/teacher/practice', `/teacher/practice/${data.users.student}?course_id=${data.courses.teacher}`, `/teacher/practice/drafts/${data.exams.draft}`]],
        ['student', ['/practice?course_id='+data.courses.teacher, '/practice/progress?subject=Toán', `/assessments/${data.exams.standalone}/result`]],
        ['resume', [`/practice/${data.exams.resume}/take`]],
      ]) {
        await login(role);
        for (const route of routes) {
          const response = await page.goto(base+route);
          check(`${role} ${route} GET @${width}`, response.status() === 200);
          await page.evaluate(async () => {await document.fonts.ready;});
          check(`${route} no page overflow @${width}`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1));
          check(`${route} shared foundation loaded @${width}`, await page.locator('head link[href*="main.css"]').count() === 1);
          if (route.includes('/take')) {
            check('Shared taking page keeps22questions @'+width, await page.locator('[data-question-id]').count()===22);
            if (width===375) await page.screenshot({path:path.join(output,'screenshots/shared-taking-375.png')});
          }
          if (route.startsWith('/teacher/practice/') && route.includes('?course_id=') && width===1440)
            await page.screenshot({path:path.join(output,'screenshots/shared-teacher-profile-1440.png')});
        }
      }
    }
    check('No JavaScript errors', errors.length===0);
    check('No missing static assets', brokenAssets.length===0);
    check('No external script/font/stylesheet', external.length===0);
    fs.writeFileSync(path.join(output,'shared-browser-qa.json'), JSON.stringify({status:'passed', checks:checks.length, passed:checks, errors, brokenAssets, external}, null, 2));
    console.log(JSON.stringify({checks:checks.length, errors:errors.length, brokenAssets:brokenAssets.length}));
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode=1;});
