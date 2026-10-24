/* Run against preview_ui_phase3.py only; every account and upload is synthetic. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'docs/ui-redesign/phase-3');
const base = process.env.PHASE3_PREVIEW_URL || 'http://127.0.0.1:8766';
const checks = [];
const errors = [];
const external = new Set();
fs.mkdirSync(path.join(output, 'screenshots'), {recursive: true});
const check = (name, condition, detail) => {
  checks.push({name, passed: Boolean(condition), ...(detail === undefined ? {} : {detail})});
  assert.ok(condition, `${name}: ${JSON.stringify(detail)}`);
};
async function ready(page, url) {
  const response = await page.goto(base + url, {waitUntil: 'networkidle'});
  await page.evaluate(() => document.fonts.ready);
  return response;
}
async function login(page, role = 'teacher', password = 'Academy123!') {
  await ready(page, '/login?next=/profile');
  await page.locator('[name="username"]').fill('qa_' + role);
  await page.locator('[name="password"]').fill(password);
  await Promise.all([page.waitForURL('**/profile'), page.locator('[name="submit"]').click()]);
  await page.waitForLoadState('networkidle');
}
async function layout(page, name, url, width) {
  await page.setViewportSize({width, height: 1000});
  const response = await ready(page, url);
  const data = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth > innerWidth + 1,
    width: innerWidth, documentWidth: document.documentElement.scrollWidth,
    h1: document.querySelectorAll('h1').length,
    font: getComputedStyle(document.body).fontFamily,
    missingIcons: document.querySelectorAll('i[data-lucide]').length,
    brokenImages: [...document.images].filter(x => x.complete && !x.naturalWidth).map(x => x.getAttribute('src')),
    duplicatedIds: [...document.querySelectorAll('[id]')].map(x => x.id).filter((id, i, all) => all.indexOf(id) !== i),
    shell: document.body.classList.contains('academy-shell'),
    sidebar: document.querySelector('.sidebar') ? getComputedStyle(document.querySelector('.sidebar')).visibility : null,
    background: getComputedStyle(document.body).backgroundColor
  }));
  check(`${name} ${width}: HTTP`, response.status() === 200 || name.startsWith('error'), response.status());
  check(`${name} ${width}: no page overflow`, !data.overflow, data);
  check(`${name} ${width}: local typography`, data.font.includes('Be Vietnam Pro'), data.font);
  check(`${name} ${width}: icons and images`, data.missingIcons === 0 && data.brokenImages.length === 0, data);
  if (['login', 'register', 'profile', 'error404'].includes(name)) {
    check(`${name} ${width}: one H1 and unique IDs`, data.h1 === 1 && data.duplicatedIds.length === 0, data);
  }
  if (name === 'register') {
    const heights = await page.locator('input.form-control, select.form-control').evaluateAll(items => items.map(el => el.getBoundingClientRect().height));
    check(`${name} ${width}: consistent field heights`, Math.max(...heights) - Math.min(...heights) < 2, heights);
  }
  if (name === 'profile') check(`${name} ${width}: sidebar breakpoint`, data.sidebar === (width >= 1200 ? 'visible' : 'hidden'), data.sidebar);
  if (name === 'error404') check(`${name} ${width}: Vietnamese default message`, (await page.locator('.error-message').textContent()).includes('Trang hoặc tài nguyên'));
  if ([375, 1440].includes(width) && ['login', 'register', 'profile', 'error404', 'home'].includes(name)) {
    await page.screenshot({path: path.join(output, 'screenshots', `${name}-${width}.png`), fullPage: true});
  }
  return data;
}
(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}, locale: 'vi-VN'});
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (!request.url().startsWith(base) && !request.url().startsWith('data:')) external.add(request.url()); });
    for (const width of [375, 768, 1024, 1440]) {
      await layout(page, 'login', '/login', width);
      await layout(page, 'register', '/register', width);
      await layout(page, 'error404', '/qa/errors/404', width);
    }
    await ready(page, '/login?next=/profile');
    await page.locator('[name="username"]').fill('qa_teacher');
    await page.locator('[name="password"]').fill('incorrect');
    await page.locator('[data-password-toggle]').click();
    check('login reveal password', await page.locator('[name="password"]').getAttribute('type') === 'text');
    await Promise.all([page.waitForNavigation(), page.locator('[name="submit"]').click()]);
    check('login invalid credentials visible and focused', await page.locator('[data-auth-server-error]').isVisible() && await page.locator('[data-auth-server-error]').evaluate(el => document.activeElement === el));
    await login(page);
    check('login respects next and native CSRF', new URL(page.url()).pathname === '/profile');
    for (const width of [375, 768, 1024, 1440]) await layout(page, 'profile', '/profile', width);

    await page.setViewportSize({width: 375, height: 812});
    await ready(page, '/profile');
    const trigger = page.locator('[data-sidebar-toggle]');
    await trigger.click();
    check('drawer dialog semantics and background inert', await page.locator('#primary-navigation').getAttribute('role') === 'dialog' && await page.locator('.main-area').evaluate(el => el.inert));
    check('drawer moves focus to close', await page.locator('.sidebar [data-sidebar-close]').evaluate(el => document.activeElement === el));
    await page.keyboard.press('Shift+Tab');
    check('drawer backward focus wraps', await page.locator('.sidebar-footer').evaluate(el => document.activeElement === el));
    await page.keyboard.press('Tab');
    check('drawer forward focus wraps', await page.locator('.sidebar [data-sidebar-close]').evaluate(el => document.activeElement === el));
    await page.keyboard.press('Escape');
    check('drawer Escape closes and restores focus', await trigger.evaluate(el => document.activeElement === el && el.getAttribute('aria-expanded') === 'false') && !await page.locator('.main-area').evaluate(el => el.inert));
    await trigger.click();
    await page.locator('.sidebar-scrim').click({position: {x: 340, y: 200}});
    check('drawer scrim closes', await trigger.getAttribute('aria-expanded') === 'false');
    await trigger.click();
    await page.setViewportSize({width: 1440, height: 1000});
    await page.waitForFunction(() => !document.querySelector('.main-area').inert && !document.body.classList.contains('nav-open'));
    check('drawer resize releases background', !await page.locator('.main-area').evaluate(el => el.inert) && !await page.locator('body').evaluate(el => el.classList.contains('nav-open')));
    await page.setViewportSize({width: 375, height: 812});
    await trigger.click();
    await Promise.all([page.waitForURL('**/courses'), page.locator('.sidebar a[href="/courses"]').click()]);
    check('drawer links navigate', new URL(page.url()).pathname === '/courses' && !await page.locator('.main-area').evaluate(el => el.inert));

    await ready(page, '/profile');
    await page.locator('[name="avatar"]').setInputFiles({name: 'invalid.txt', mimeType: 'text/plain', buffer: Buffer.from('not an image')});
    check('avatar invalid selection feedback', (await page.locator('[data-profile-avatar-status]').textContent()).includes('Không thể xem trước'));
    await page.locator('[name="avatar"]').setInputFiles({name: 'preview.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aT1cAAAAASUVORK5CYII=', 'base64')});
    await page.waitForFunction(() => document.getElementById('avatar-preview').getAttribute('src').startsWith('data:'));
    check('avatar preview has live feedback', (await page.locator('[data-profile-avatar-status]').textContent()).includes('preview.png'));
    await page.locator('[name="avatar"]').setInputFiles([]);
    await page.locator('[name="fullname"]').fill('Nguyễn Minh Anh · QA');
    await Promise.all([page.waitForNavigation(), page.locator('[name="submit_profile"]').click()]);
    check('native profile submit retains submit_profile', (await page.locator('.flash').textContent()).includes('Cập nhật hồ sơ thành công') && await page.locator('[name="fullname"]').inputValue() === 'Nguyễn Minh Anh · QA');
    check('mobile flash close target is 44px', await page.locator('[data-flash-dismiss]').evaluate(el => el.getBoundingClientRect().height >= 44 && el.getBoundingClientRect().width >= 44));
    await page.locator('[data-flash-dismiss]').click();
    check('flash close is functional', await page.locator('.flash').count() === 0);
    await page.locator('[name="fullname"]').fill('Nguyễn Minh Anh');
    await Promise.all([page.waitForNavigation(), page.locator('[name="submit_profile"]').click()]);
    await page.locator('[name="old_password"]').fill('incorrect');
    await page.locator('[name="new_password"]').fill('Academy456!');
    await page.locator('[name="confirm_password"]').fill('mismatch');
    check('password mismatch feedback and native validity', await page.locator('[data-profile-password-match]').isVisible() && !await page.locator('[name="confirm_password"]').evaluate(el => el.checkValidity()));
    await page.locator('[name="confirm_password"]').fill('Academy456!');
    await page.locator('[data-profile-password-toggle="old_password"]').click();
    check('profile password toggle', await page.locator('[name="old_password"]').getAttribute('type') === 'text');
    await Promise.all([page.waitForNavigation(), page.locator('[name="submit_password"]').click()]);
    check('native password submit shows server failure', (await page.locator('.flash').textContent()).includes('Mật khẩu cũ không đúng'));
    await page.locator('[name="old_password"]').fill('Academy123!');
    await page.locator('[name="new_password"]').fill('Academy456!');
    await page.locator('[name="confirm_password"]').fill('Academy456!');
    await Promise.all([page.waitForNavigation(), page.locator('[name="submit_password"]').click()]);
    check('native password submit retains submit_password', (await page.locator('.flash').textContent()).includes('Đổi mật khẩu thành công'));
    await ready(page, '/logout');
    await login(page, 'teacher', 'Academy456!');
    await page.locator('[name="old_password"]').fill('Academy456!');
    await page.locator('[name="new_password"]').fill('Academy123!');
    await page.locator('[name="confirm_password"]').fill('Academy123!');
    await Promise.all([page.waitForNavigation(), page.locator('[name="submit_password"]').click()]);

    for (const [name, url] of [['home','/'], ['banks','/question-banks'], ['bank-detail','/question-banks/1'], ['courses','/courses'], ['assessments','/assessments']]) {
      for (const width of [375, 1440]) await layout(page, name, url, width);
    }
    await ready(page, '/question-banks/1');
    await page.locator('.question-prompt-text').first().scrollIntoViewIfNeeded();
    await page.waitForSelector('mjx-container');
    check('local MathJax still renders bank formula', await page.locator('mjx-container').count() > 0);
    check('bank navigation selected', await page.locator('.nav-item[aria-current="page"]').getAttribute('href') === '/question-banks');
    const teacherLinks = await page.locator('.sidebar a.nav-item').evaluateAll(items => items.map(el => el.getAttribute('href')));
    check('teacher navigation matches role', teacherLinks.includes('/teacher/ai-settings') && !teacherLinks.includes('/users/students') && !teacherLinks.includes('/practice'));

    for (const code of [400,403,404,405,429,500]) {
      const response = await ready(page, '/qa/errors/' + code);
      check(`error ${code}: status and content`, response.status() === code && (await page.locator('.error-status-code').textContent()).includes(String(code)) && await page.locator('h1').count() === 1);
    }
    const api = await context.request.get(base + '/api/does-not-exist', {headers: {'Accept':'application/json'}});
    check('API error remains JSON', api.status() === 404 && (await api.json()).status_code === 404);
    await ready(page, '/qa/errors/404');
    await page.locator('.error-technical summary').click();
    await page.evaluate(() => Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {writeText: async text => { window.qaCopied = text; }}}));
    await page.locator('[data-copy-request-id]').click();
    check('error request ID copy', await page.evaluate(() => window.qaCopied === document.getElementById('error-reference').textContent.trim()));
    await page.evaluate(() => Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {writeText: async () => { throw Error('denied'); }}}));
    await page.locator('[data-copy-request-id]').click();
    check('error copy failure has manual recovery', (await page.locator('#error-copy-feedback').textContent()).includes('Mã đã được chọn') && await page.evaluate(() => getSelection().toString() === document.getElementById('error-reference').textContent.trim()));
    const errorTab = await context.newPage();
    await ready(errorTab, '/qa/errors/404');
    await Promise.all([errorTab.waitForURL(base + '/'), errorTab.locator('[data-error-back]').click()]);
    check('error direct-entry back uses safe fallback', new URL(errorTab.url()).pathname === '/');
    await errorTab.close();

    await ready(page, '/logout');
    await login(page, 'student');
    const studentLinks = await page.locator('.sidebar a.nav-item').evaluateAll(items => items.map(el => el.getAttribute('href')));
    check('student navigation matches role', studentLinks.includes('/practice') && !studentLinks.includes('/question-banks') && !studentLinks.includes('/teacher/ai-settings'));
    await layout(page, 'practice', '/practice', 375);
    await ready(page, '/logout');
    await login(page, 'admin');
    const adminLinks = await page.locator('.sidebar a.nav-item').evaluateAll(items => items.map(el => el.getAttribute('href')));
    check('admin navigation matches role', adminLinks.includes('/users/students') && adminLinks.includes('/users/teachers') && !adminLinks.includes('/teacher/ai-settings'));

    const nojs = await browser.newContext({javaScriptEnabled: false, viewport: {width:375,height:812}});
    await nojs.addCookies(await context.cookies());
    const nojsPage = await nojs.newPage();
    await ready(nojsPage, '/profile');
    check('navigation remains available without JS', await nojsPage.locator('.sidebar').isVisible() && await nojsPage.locator('.sidebar a[href="/courses"]').isVisible());
    check('password controls stay hidden without JS', !await nojsPage.locator('[data-profile-password-toggle]').first().isVisible());
    await nojs.close();
    check('no runtime JS errors', errors.length === 0, errors);
    check('no external font or script requests', external.size === 0, [...external]);
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(output, 'browser-qa.json'), JSON.stringify({date:'2026-10-14', preview:base, checks, errors, externalRequests:[...external]}, null, 2) + '\n');
    console.log(JSON.stringify({passed:checks.filter(x => x.passed).length, total:checks.length, output}, null, 2));
  }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
