/* Read-only regression: observed errors remain visible in class scope. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.PHASE7_URL||'http://127.0.0.1:8769';assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const out=path.resolve('docs/ui-redesign/phase-7'),checks=[],errors=[],writes=[],shots=[];
const check=(name,valid)=>{assert(valid,name);checks.push(name);};
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const context=await browser.newContext(),page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&!r.url().includes('/login'))writes.push(r.url());});
 const fixture=await(await context.request.get(base+'/qa/fixture')).json();await page.goto(base+'/login');await page.locator('[name=username]').fill('qa_teacher');await page.locator('[name=password]').fill('Academy123!');await page.locator('[type=submit]').click();await page.waitForURL(u=>u.pathname!=='/login');
 for(const width of [375,1440]){
  await page.setViewportSize({width,height:1000});const response=await page.goto(base+'/teacher/practice/'+fixture.users.student+'?course_id='+fixture.courses.teacher);check('Observed errors GET 200 @'+width,response.status()===200);
  const disclosure=page.locator('.teacher-observations').first(),summary=disclosure.locator(':scope > summary');check('Observed error disclosure exists @'+width,await disclosure.count()===1);
  await summary.focus();await page.keyboard.press('Enter');check('Keyboard opens observed errors @'+width,await disclosure.evaluate(d=>d.open));
  const count=await disclosure.locator('.teacher-observation-list > li').count();check('At most twenty genuine observations @'+width,count>0&&count<=20);
  check('Each observation has label claim and date @'+width,await disclosure.locator('.teacher-observation-heading strong').count()===count&&await disclosure.locator('.teacher-observation-claim').count()===count&&await disclosure.locator('time').count()===count);
  check('Observed errors remain read-only @'+width,await disclosure.locator('input,button,select,textarea,form').count()===0);
  check('Observed disclosure does not overflow page @'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  check('Original standalone evidence heading retained @'+width,await page.getByRole('heading',{name:'Kết quả đề kiểm tra',exact:true}).count()===1);
  const file='screenshots/teacher-observations-'+width+'.png';await disclosure.screenshot({path:path.join(out,file)});shots.push(file);
  await page.keyboard.press('Enter');check('Keyboard collapse preserves summary focus @'+width,!await disclosure.evaluate(d=>d.open)&&await summary.evaluate(n=>n===document.activeElement));
 }
 check('No profile or evidence writes during read',writes.length===0);check('No JavaScript errors',errors.length===0);fs.writeFileSync(path.join(out,'teacher-observations-qa.json'),JSON.stringify({date:'2026-10-16',checks:checks.length,passed:checks,errors,writes,screenshots:shots},null,2));console.log(JSON.stringify({checks:checks.length,errors,writes}));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
