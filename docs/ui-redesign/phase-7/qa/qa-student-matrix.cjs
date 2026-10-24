const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.PHASE7_URL||'http://127.0.0.1:8769';
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const out=path.resolve('docs/ui-redesign/phase-7');
const checks=[],errors=[],posts=[];
const check=(label,value)=>{assert(value,label);checks.push(label);};
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const fixture=await(await context.request.get(base+'/qa/fixture')).json();
  const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  await page.goto(base+'/login');await page.locator('#username').fill('qa_student');await page.locator('#password').fill('Academy123!');
  await page.locator('#login-form [type=submit]').click();await page.waitForURL(url=>url.pathname!=='/login');
  await page.route('**/*',route=>{const r=route.request();if(r.method()!=='GET'&&!r.url().includes('/api/formulas/batch')){posts.push(r.url());return route.abort();}return route.continue();});
  for(const mode of ['home','progress']){
   await page.goto(base+(mode==='home'?'/practice?course_id='+fixture.courses.teacher:'/practice/progress?subject='+encodeURIComponent('Toán')));
   if(mode==='home'){await page.locator('.student-evidence > summary').click();check('Home disclosure opens matrix',await page.locator('.student-evidence').getAttribute('open')!==null);}
   check(mode+' eight knowledge rows',await page.locator('.knowledge-matrix-table tbody tr').count()===8);
   check(mode+' four knowledge columns',await page.locator('.knowledge-matrix-table thead th').count()===5);
   check(mode+' matrix no inline styles',await page.locator('.knowledge-matrix [style]').count()===0);
   for(const width of [375,768,1024,1440]){
    await page.setViewportSize({width,height:1000});
    check(mode+' no page overflow '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    check(mode+' keyboard region '+width,await page.locator('.knowledge-matrix-scroll').getAttribute('tabindex')==='0');
    check(mode+' local overflow '+width,await page.locator('.knowledge-matrix-scroll').evaluate(el=>el.scrollWidth>=el.clientWidth&&getComputedStyle(el).overflowX==='auto'));
    if(width===375){const region=page.locator('.knowledge-matrix-scroll');await region.focus();await page.keyboard.press('ArrowRight');await page.waitForTimeout(200);check(mode+' keyboard scroll moves matrix',await region.evaluate(el=>el.scrollLeft>0));await region.evaluate(el=>{el.scrollLeft=0;});}
    if([375,1440].includes(width)){
     await page.evaluate(async()=>{await document.fonts.ready;document.activeElement?.blur();scrollTo(0,0);});
     await page.screenshot({path:path.join(out,'screenshots','student-'+mode+'-matrix-'+width+'.png'),fullPage:true});
    }
   }
   if(mode==='progress'){check('Default chart motion uses150ms',await page.evaluate(()=>window.Chart.getChart(document.getElementById('scoreChart')).options.animation.duration===150));check('All cognitive labels retained on mobile',await page.evaluate(()=>{const c=window.Chart.getChart(document.getElementById('accuracyChart'));return c.options.scales.x.ticks.autoSkip===false&&c.data.labels.length===4&&c.data.labels.every(label=>Array.isArray(label)&&label.length===2);}));check('Chart axes use local UI font',await page.evaluate(()=>window.Chart.getChart(document.getElementById('scoreChart')).options.scales.x.ticks.font.family.includes('Be Vietnam Pro')));}
  }
  await page.selectOption('#progress-subject','Tiếng Anh');await page.locator('.student-context-form [type=submit]').click();await page.waitForURL(url=>url.searchParams.get('subject')==='Tiếng Anh');
  check('Subject GET updates context',await page.locator('#progress-context-title').innerText()==='Tiếng Anh');
  check('Subject without evidence stays neutral',await page.locator('#scoreChart').count()===0&&(await page.locator('.student-kpis').innerText()).includes('Chưa có dữ liệu'));
  check('No JS errors',errors.length===0);check('No data POSTs',posts.length===0);
  fs.writeFileSync(path.join(out,'student-matrix-qa.json'),JSON.stringify({checks:checks.length,passed:checks,errors,posts},null,2)+'\n');
  process.stdout.write(JSON.stringify({checks:checks.length,errors,posts})+'\n');
 }finally{await browser.close();}
})();
