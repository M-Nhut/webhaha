/* Read-only Phase 6 assessment register/matrix QA; only authentication POSTs. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.PHASE6_BASE_URL || 'http://127.0.0.1:8768';
const output = path.resolve(__dirname, '..');
const checks = [], errors = [];
function check(name, condition, detail) { checks.push({name, passed:!!condition, detail}); assert.ok(condition, name + (detail ? ': ' + JSON.stringify(detail) : '')); }
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  try {
    const anon = await browser.newContext();
    const fixture = await (await anon.request.get(base+'/qa/fixture')).json();
    await anon.close();
    const login = async name => {
      const context = await browser.newContext({viewport:{width:1440,height:1000},locale:'vi-VN'});
      const page = await context.newPage(); page.on('pageerror',e=>errors.push(e.message));
      page.on('request',request=>{ if(request.method()==='POST' && !request.url().includes('/login')) errors.push('Unexpected data POST '+request.url()); });
      await page.goto(base+'/login?next=/assessments',{waitUntil:'networkidle'});
      await page.locator('[name=username]').fill(name); await page.locator('[name=password]').fill('Academy123!');
      await Promise.all([page.waitForURL('**/assessments'),page.locator('[name=submit]').click()]);
      await page.waitForLoadState('networkidle');
      return {context,page};
    };
    const go = async (page,url) => { const result = await page.goto(base+url,{waitUntil:'networkidle'}); await page.evaluate(()=>document.fonts.ready); check('GET '+url+' returns 200',result.status()===200,result.status()); };
    const screenshot = async (page,name,width) => { if([375,1440].includes(width)) await page.screenshot({path:path.join(output,'screenshots',name+'-'+width+'.png'),fullPage:true}); };
    const overflow = page=>page.evaluate(()=>({page:document.documentElement.scrollWidth,viewport:innerWidth}));
    for (const role of ['teacher','admin','student','empty_teacher']) {
      const {context,page}=await login('qa_'+role);
      for (const width of [375,768,1024,1440]) {
        await page.setViewportSize({width,height:1000}); await go(page,'/assessments');
        const size=await overflow(page); check(role+' list '+width+' no page overflow',size.page<=size.viewport+1,size);
        const rows=page.locator('.assessment-register-table tbody tr');
        if(role==='empty_teacher') check('empty teacher '+width+' specific empty state',await page.getByRole('heading',{name:'Chưa có đề kiểm tra',exact:true}).count()===1 && await rows.count()===0);
        else check(role+' list '+width+' nonempty rows',await rows.count()>0);
        if(width===375) {
          const heights=await page.locator('.assessment-register-row-actions a,.assessment-management-actions a').evaluateAll(es=>es.filter(e=>e.getBoundingClientRect().height>0).map(e=>({text:e.textContent,height:e.getBoundingClientRect().height})));
          check(role+' mobile links >=44px',heights.every(e=>e.height>=44),heights);
        }
        if(role==='student') {
          const hrefs=await page.locator('.assessment-register a').evaluateAll(es=>es.map(e=>new URL(e.href).pathname));
          check('student '+width+' only assigned take route',hrefs.length>0&&hrefs.every(h=>/^\/assessments\/\d+\/take$/.test(h)),hrefs);
          check('student '+width+' no invented completion state',!(await page.locator('.assessment-register').innerText()).match(/Chưa làm|Đã hoàn thành|Đang làm/));
          check('student '+width+' no draft status',await page.locator('.assessment-register').getByText('Bản nháp',{exact:true}).count()===0);
        }
        await screenshot(page,'assessment-list-'+role,width);
      }
      if(role==='teacher') {
        const draftRow=page.locator('tr').filter({has:page.locator('a[href="/assessments/'+fixture.exams.draft+'/matrix"]')});
        check('teacher draft has editor',await draftRow.locator('a[href^="/assessments/import/"]').count()===1);
      }
      if(role==='admin') check('admin list no inaccessible teacher editor',await page.locator('a[href^="/assessments/import/"]').count()===0);
      await context.close();
    }
    const {context,page}=await login('qa_teacher');
    for (const kind of ['draft','published']) {
      const id=fixture.exams[kind];
      for (const width of [375,768,1024,1440]) {
        await page.setViewportSize({width,height:1000}); await go(page,'/assessments/'+id+'/matrix');
        const size=await overflow(page); check(kind+' matrix '+width+' no page overflow',size.page<=size.viewport+1,size);
        check(kind+' matrix '+width+' two keyboard regions',await page.locator('.matrix-scroll[tabindex="0"][role=region]').count()===2);
        check(kind+' matrix '+width+' preserves question count',await page.locator('.matrix-details-table tbody tr').count()===fixture.questions_by_exam[kind].length);
        check(kind+' matrix '+width+' editor follows lock',await page.locator('.matrix-edit-context a').count()===(kind==='draft'?1:0));
        check(kind+' matrix '+width+' warning follows actual labels',await page.locator('.matrix-label-warning').count()===(kind==='draft'?1:0));
        check(kind+' matrix '+width+' 19 columns retained',await page.locator('.matrix-7991 tbody tr').first().locator('td').count()===19);
        check(kind+' matrix '+width+' export stays XLSX',(await page.getByRole('link',{name:'Tải Excel (.xlsx)'}).getAttribute('href')).endsWith('?download=xlsx'));
        const region=page.locator('.matrix-scroll').first();
        await region.focus(); await page.keyboard.press('ArrowRight'); await page.waitForTimeout(150);
        check(kind+' matrix '+width+' keyboard scrolls only region',await region.evaluate(e=>e.scrollLeft>0));
        await region.evaluate(e=>{e.scrollLeft=0;}); await page.locator('h1').click();
        await screenshot(page,'assessment-matrix-'+kind,width);
      }
      const download=await page.request.get(base+'/assessments/'+id+'/matrix?download=xlsx');
      check(kind+' download MIME',download.headers()['content-type'].includes('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'));
      const bytes=await download.body(); check(kind+' XLSX ZIP signature',bytes.subarray(0,2).toString()==='PK');
      await page.evaluate(()=>{window.__qaPrinted=false;window.print=()=>{window.__qaPrinted=true;};});
      await page.locator('[data-matrix-print]').click();check(kind+' native print action',await page.evaluate(()=>window.__qaPrinted));
      await page.emulateMedia({media:'print'});
      check(kind+' print hides management',!(await page.locator('.assessment-management-actions').isVisible()));
      check(kind+' print exposes whole table',await page.locator('.matrix-scroll').first().evaluate(e=>getComputedStyle(e).overflowX==='visible') && await page.locator('.matrix-7991').evaluate(e=>getComputedStyle(e).minWidth==='0px'));
      await page.pdf({path:path.join(output,'qa','matrix-'+kind+'-landscape.pdf'),preferCSSPageSize:true,printBackground:true});
      await page.emulateMedia({media:'screen'});
    }
    await context.close();
    check('no JavaScript errors or data POSTs',errors.length===0,errors);
    fs.writeFileSync(path.join(output,'list-matrix-qa.json'),JSON.stringify({checks,errors,readonly:true,templateChecks:54},null,2));
    console.log(checks.length+' read-only list/matrix browser checks passed.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
