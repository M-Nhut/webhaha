const {chromium} = require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs');
const path=require('path');
const root=process.cwd(), base='http://127.0.0.1:8771';
const output=path.join(root,'docs/ui-redesign/phase-9');
const report={date:'2026-10-19',base,checks:[],errors:[],intercepted_mutations:[],screenshots:[],fixture_note:'All formula status data inserted only into browser DOM; retry POSTs intercepted and fulfilled synthetically. Image zoom uses actual seeded question image and actual bank click handler. No backend mutation or provider call.'};
function check(name,condition,detail){report.checks.push({name,passed:!!condition,detail});if(!condition)throw Error(name+': '+JSON.stringify(detail));}
(async()=>{
 const fixture=await (await fetch(base+'/qa/fixture')).json();
 const graph=await (await fetch(base+'/qa/media/graph.svg')).text();
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
 for(const width of [375,768,1024,1440]){
  const context=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});
  const page=await context.newPage();page.on('pageerror',e=>report.errors.push({width,message:e.message}));
  await page.route('**/static/qa-formula-review.svg',r=>r.fulfill({status:200,contentType:'image/svg+xml',body:graph}));
  await page.goto(base+'/login');await page.locator('[name=username]').fill('qa_teacher');await page.locator('[name=password]').fill('Academy123!');await page.locator('#login-form [type=submit]').click();await page.waitForURL(base+'/');
  await page.goto(base+'/question-banks/'+fixture.wizard.bank_id);
  const image=page.locator('img.bank-question-image[src*="/qa/media/graph.svg"]').first();await image.waitFor({state:'visible'});await image.scrollIntoViewIfNeeded();await image.focus();await image.press('Enter');
  const dialog=page.locator('dialog.formula-svg-lightbox');await dialog.waitFor({state:'visible'});
  check(width+' actual-bank-image-opens-native-dialog',await dialog.evaluate(d=>d.open&&d.matches(':modal')));
  check(width+' dialog-accessible-label',!!await dialog.getAttribute('aria-label'));
  await page.waitForFunction(()=>document.querySelector('.formula-lightbox-image')?.naturalWidth>0);
  check(width+' image-loaded',await dialog.locator('img').evaluate(i=>i.complete&&i.naturalWidth>0));
  check(width+' close-receives-focus',await dialog.locator('button').evaluate(b=>b===document.activeElement));
  await page.keyboard.press('Tab');await page.keyboard.press('Tab');
  check(width+' tab-contained',await page.evaluate(()=>document.querySelector('dialog.formula-svg-lightbox').contains(document.activeElement)));
  await page.keyboard.press('Shift+Tab');
  check(width+' reverse-tab-contained',await page.evaluate(()=>document.querySelector('dialog.formula-svg-lightbox').contains(document.activeElement)));
  check(width+' lightbox-fits-viewport',await dialog.evaluate(d=>{const b=d.getBoundingClientRect();return b.left>=0&&b.top>=0&&b.right<=innerWidth+1&&b.bottom<=innerHeight+1}));
  const shot='screenshots/cleanup-formula-zoom-'+width+'.png';fs.mkdirSync(path.join(output,'screenshots'),{recursive:true});await page.screenshot({path:path.join(output,shot)});report.screenshots.push(shot);
  await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});
  check(width+' escape-returns-opener-focus',await image.evaluate(i=>i===document.activeElement));
  await image.press('Space');await dialog.waitFor({state:'visible'});await dialog.locator('button').click();await dialog.waitFor({state:'detached'});
  check(width+' close-returns-opener-focus',await image.evaluate(i=>i===document.activeElement));
  await image.click();await dialog.waitFor({state:'visible'});await page.mouse.click(4,4);await dialog.waitFor({state:'detached'});
  check(width+' backdrop-closes-and-returns-focus',await image.evaluate(i=>i===document.activeElement));
  await page.goto(base+'/');
  await page.route('**/api/formulas/qa-error/retry',async route=>{
   const req=route.request();report.intercepted_mutations.push({path:new URL(req.url()).pathname,method:req.method(),csrf:!!req.headers()['x-csrftoken'],width});
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({formula:{conversion_status:'fallback_svg',source_format:'LaTeXBlock',svg_cache_key:'/static/qa-formula-review.svg'}})});
  });
  await page.route('**/api/formulas/qa-retry-failed/retry',async route=>{
   const req=route.request();report.intercepted_mutations.push({path:new URL(req.url()).pathname,method:req.method(),csrf:!!req.headers()['x-csrftoken'],width});
   await route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({message:'Lỗi thử lại tổng hợp, không gọi provider'})});
  });
  await page.evaluate(async()=>{
   const fixture=document.createElement('section');fixture.id='qa-formula-ui';
   for(const [id,uid]of[['qa-error-host','qa-error'],['qa-failed-host','qa-retry-failed'],['qa-block-host','qa-review-block'],['qa-inline-host','qa-review-inline'],['qa-math-host','qa-math'],['qa-table-host','qa-table']]){const p=document.createElement('p');p.id=id;p.textContent='[[formula:'+uid+']]';fixture.append(p)}
   document.querySelector('main').append(fixture);
   await window.renderFormulas(fixture,{
    'qa-error':{conversion_status:'failed',source_format:'LaTeXBlock',render_error:'Chi tiết lỗi tổng hợp'},
    'qa-retry-failed':{conversion_status:'failed',source_format:'LaTeXBlock'},
    'qa-review-block':{conversion_status:'fallback_svg',source_format:'LaTeXBlock',svg_cache_key:'/static/qa-formula-review.svg',verification_status:'needs_review',render_error:'Kiểm tra công thức trước khi dùng'},
    'qa-review-inline':{conversion_status:'fallback_svg',source_format:'MathType',svg_cache_key:'/static/qa-formula-review.svg',verification_status:'needs_review'},
    'qa-math':{latex:'\\frac{1}{2}+x^2',verification_status:'needs_review'},
    'qa-table':{table:{version:1,rows:[[{text:'Trái',align:'l'},{text:'Giữa',align:'c'},{text:'Phải',align:'r'}],[{text:'1',align:'l'},{text:'2',align:'c'},{text:'3',align:'r'}]]}}
   });
  });
  check(width+' error-uses-danger-token',await page.locator('#qa-error-host .formula-error').evaluate(e=>getComputedStyle(e).color==='rgb(185, 28, 28)'&&!e.hasAttribute('style')));
  check(width+' review-uses-warning-token',await page.locator('#qa-block-host .formula-needs-review').evaluate(e=>getComputedStyle(e).borderBottomColor==='rgb(146, 64, 14)'&&!e.hasAttribute('style')));
  check(width+' inline-and-block-review-retained',await page.locator('#qa-inline-host .formula-needs-review').count()===1&&await page.locator('#qa-block-host .formula-block-review').count()===1);
  check(width+' mathjax-render-retained',await page.locator('#qa-math-host mjx-container').count()>0);
  check(width+' structured-table-align-retained',await page.locator('#qa-table-host tr').first().locator('td').evaluateAll(c=>c.map(x=>x.style.textAlign).join(',')==='left,center,right'));
  check(width+' retry-control-size',await page.locator('#qa-error-host button').evaluate(b=>b.getBoundingClientRect().height>=(innerWidth<768?44:32)));
  await page.locator('#qa-error-host button').click();await page.locator('#qa-error-host img').waitFor({state:'visible'});
  check(width+' retry-replaces-error-with-rendered-image',await page.locator('#qa-error-host .formula-error').count()===0);
  await page.locator('#qa-failed-host button').click();await page.waitForFunction(()=>!document.querySelector('#qa-failed-host button').disabled);
  check(width+' retry-failure-remains-recoverable',await page.locator('#qa-failed-host .formula-retry-wrapper').getAttribute('title')==='Lỗi thử lại tổng hợp, không gọi provider');
  await page.route('**/question-banks/import/qa-session/formulas/qa-temp/retry',async route=>{
   const req=route.request();report.intercepted_mutations.push({path:new URL(req.url()).pathname,method:req.method(),csrf:!!req.headers()['x-csrftoken'],width});
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({formula:{latex:'x+1'}})});
  });
  await page.evaluate(async()=>{window.currentImportSessionId='qa-session';const p=document.createElement('p');p.id='qa-temp-host';p.textContent='[[formula:qa-temp]]';document.querySelector('main').append(p);await renderFormulas(p,{'qa-temp':{conversion_status:'failed',source_format:'LaTeXBlock'}})});
  await page.locator('#qa-temp-host button').click();await page.locator('#qa-temp-host mjx-container').waitFor({state:'visible'});
  check(width+' temporary-import-retry-preserved',await page.locator('#qa-temp-host .formula-error').count()===0);
  await page.evaluate(async()=>{delete window.currentImportSessionId;document.body.setAttribute('data-can-retry-formulas','false');const p=document.createElement('p');p.id='qa-no-permission-host';p.textContent='[[formula:qa-view-only]]';document.querySelector('main').append(p);await renderFormulas(p,{'qa-view-only':{conversion_status:'failed',source_format:'LaTeXBlock'}})});
  check(width+' student-view-cannot-retry',await page.locator('#qa-no-permission-host .formula-error').count()===1&&await page.locator('#qa-no-permission-host button').count()===0);
  check(width+' page-no-horizontal-overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await context.close();
 }
 check('all-retry-requests-keep-post-and-csrf',report.intercepted_mutations.length===12&&report.intercepted_mutations.every(r=>r.method==='POST'&&r.csrf));
 check('no-page-errors',report.errors.length===0,report.errors);
 }catch(e){report.failure=e.stack;process.exitCode=1}finally{await browser.close();report.passed=!report.failure&&report.checks.every(c=>c.passed);report.count=report.checks.length;fs.writeFileSync(path.join(output,'cleanup-formula-browser.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:report.passed,checks:report.count,errors:report.errors,failure:report.failure}))}
})().catch(e=>{console.error(e);process.exitCode=1});
