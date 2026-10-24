const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.PHASE7_URL||'http://127.0.0.1:8769';assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const out=path.resolve('docs/ui-redesign/phase-7'),checks=[],errors=[],shots=[];
const check=(name,value)=>{assert(value,name);checks.push(name);};
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 const fixture=await(await context.request.get(base+'/qa/fixture')).json();
 await page.goto(base+'/login');await page.locator('[name=username]').fill('qa_teacher');await page.locator('[name=password]').fill('Academy123!');await page.locator('[type=submit]').click();await page.waitForURL(u=>u.pathname!=='/login');
 const draft=base+'/teacher/practice/drafts/'+fixture.exams.draft;
 for(const width of [375,1440]){
  await page.setViewportSize({width,height:1000});await page.goto(draft);const question=page.locator('.teacher-draft-question').first();await question.scrollIntoViewIfNeeded();await question.locator('img').waitFor();await page.waitForFunction(()=>document.querySelector('[data-draft-image]')?.naturalWidth>0);
  await question.locator('summary').click();await page.evaluate(async()=>{if(window.MathJax?.startup?.promise)await MathJax.startup.promise;});
  check('Frozen context visible @'+width,await question.locator('.teacher-question-context').isVisible());check('Frozen image loaded @'+width,await question.locator('img').evaluate(i=>i.naturalWidth>0));check('Frozen explanation visible @'+width,await question.locator('details').evaluate(d=>d.open));
  const file='screenshots/teacher-draft-question-'+width+'.png';await question.screenshot({path:path.join(out,file)});shots.push(file);
  await question.locator('[data-draft-image-open]').click();check('Native image dialog @'+width,await page.locator('#draft-image-dialog').evaluate(d=>d.open));await page.keyboard.press('Escape');check('Image dialog focus restored @'+width,await question.locator('[data-draft-image-open]').evaluate(n=>n===document.activeElement));
 }
 await page.route('**/qa/media/graph.svg',r=>r.fulfill({status:404,body:'synthetic image failure'}));await page.goto(draft);await page.locator('.teacher-draft-question').first().scrollIntoViewIfNeeded();await page.locator('.teacher-draft-image-error').first().waitFor({state:'visible'});
 check('Failed image has visible recovery',await page.locator('[data-draft-image-retry]').first().isVisible());await page.unroute('**/qa/media/graph.svg');await page.locator('[data-draft-image-retry]').first().click();await page.waitForFunction(()=>document.querySelector('[data-draft-image]')?.naturalWidth>0);check('Image retry recovers source',await page.locator('[data-draft-image-open]').first().isVisible()&&!await page.locator('.teacher-draft-image-error').first().isVisible());
 await page.evaluate(()=>{document.activeElement?.blur();window.dispatchEvent(new Event('beforeprint'));});check('Print opens all explanations',await page.locator('[data-draft-explanation]:not([open])').count()===0);await page.pdf({path:path.join(out,'qa/teacher-draft-a4.pdf'),format:'A4',printBackground:true,margin:{top:'12mm',bottom:'12mm',left:'12mm',right:'12mm'}});await page.evaluate(()=>window.dispatchEvent(new Event('afterprint')));check('Print restores initial disclosure state',await page.locator('[data-draft-explanation][open]').count()===0);
 check('No JavaScript errors',errors.length===0);fs.writeFileSync(path.join(out,'teacher-media-qa.json'),JSON.stringify({date:'2026-10-15',checks:checks.length,passed:checks,errors,screenshots:shots,postWrites:'Only authentication'},null,2));console.log(JSON.stringify({checks:checks.length,errors}));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
