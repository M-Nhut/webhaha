/* Real learning actions only against the isolated synthetic Phase 7 preview. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.PHASE7_URL||'http://127.0.0.1:8769';
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const out=path.resolve('docs/ui-redesign/phase-7');fs.mkdirSync(path.join(out,'screenshots'),{recursive:true});
const checks=[],errors=[],assets=[],external=[],shots=[],posts=[];
const check=(name,condition)=>{assert(condition,name);checks.push(name);};
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'vi-VN'}),page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));
  page.on('dialog',d=>d.type()==='beforeunload'?d.accept():d.dismiss());
  page.on('response',r=>{if(r.status()>=400&&r.url().includes('/static/'))assets.push(r.url());});
  page.on('request',r=>{if(r.method()==='POST')posts.push(new URL(r.url()).pathname);if(['font','script','stylesheet'].includes(r.resourceType())&&!r.url().startsWith(base))external.push(r.url());});
  const fixture=await(await context.request.get(base+'/qa/fixture')).json();
  const login=async(role)=>{
   await page.goto(base+'/logout');await page.goto(base+'/login');
   await page.locator('[name=username]').fill('qa_'+role);await page.locator('[name=password]').fill('Academy123!');
   await page.locator('[type=submit]').click();await page.waitForURL(u=>u.pathname!=='/login');
  };
  const go=async(route)=>{const r=await page.goto(base+route);check('GET '+route,r.status()===200);};
  const shot=async(name,full=false)=>{
   await page.evaluate(async()=>{scrollTo(0,0);document.activeElement?.blur();await document.fonts.ready;if(window.MathJax?.startup?.promise)await MathJax.startup.promise;if(window.MathJax?.typesetPromise)await MathJax.typesetPromise();});
   const file='screenshots/'+name+'.png';await page.screenshot({path:path.join(out,file),fullPage:full});shots.push(file);
  };
  if(process.env.PHASE7_CAPTURE_ONLY!=='1'){
   await login('start');await go('/practice');
   check('Fresh learner has single generate action',await page.locator('[data-practice-next]').getAttribute('data-practice-next')==='generate');
   await page.locator('form[action$="/practice/generate"] [type=submit]').click();await page.waitForURL('**/practice/*/take');
   const firstTake=page.url();
   check('Real student generation freezes twenty-two questions',await page.locator('[data-question-id]').count()===22);
   check('Generation keeps configured forty minutes',await page.locator('[data-exam-taking]').getAttribute('data-duration-seconds')==='2400');
   await go('/practice');check('Reopening home offers resume',await page.locator('[data-practice-next]').getAttribute('data-practice-next')==='resume');
   await page.locator('[data-practice-next] a[href$="/take"]').click();check('Resume opens the same paper',page.url()===firstTake);
   const submitBlank=async()=>{
    await page.locator('[data-taking-submit]').first().click();await page.locator('#exam-submit-dialog[open]').waitFor();
    check('Blank confirmation reports all twenty-two unanswered',await page.locator('[data-confirm-blank]').textContent()==='22');
    await page.locator('[data-taking-confirm-submit]').click();await page.waitForURL('**/practice/*/result');
    check('Blank paper is finalized honestly at zero',parseFloat(await page.locator('.result-score-value').textContent())===0);
   };
   await submitBlank();const firstResult=page.url();
   check('Finalized paper has explicit continue/end forms',await page.locator('[data-result-decision]').count()===2);
   await go('/practice');check('Home returns to pending decision',await page.locator('[data-practice-next]').getAttribute('data-practice-next')==='decision');
   await page.locator('[data-practice-next] a[href$="/result"]').click();check('Home opens the just-finalized result',page.url()===firstResult);
   await page.locator('form[action$="/continue"] [type=submit]').click();await page.waitForURL('**/practice/*/take');
   check('Continue creates a different frozen paper',page.url()!==firstTake&&await page.locator('[data-question-id]').count()===22);
   await shot('integration-continue-take-1440');await submitBlank();
   await page.locator('form[action$="/end"] [type=submit]').click();await page.waitForURL('**/practice/progress?*');
   check('End returns to real progress history',await page.locator('.student-history-table tbody tr').count()>=3);
   await shot('integration-ended-progress-1440',true);
   await login('teacher');await go(`/teacher/practice/${fixture.users.start}?course_id=${fixture.courses.teacher}`);
   await page.locator('#learning-support > summary').click();
   await page.locator(`#adaptive-practice-form [name=bank_ids][value="${fixture.wizard.bank_id}"]`).check();
   await page.locator('[data-teacher-generate]').click();await page.waitForURL('**/teacher/practice/drafts/*');
   const releaseUrl=page.url();check('Teacher generation opens unfrozen-release draft',await page.locator('.teacher-draft-question').count()===22&&await page.locator('[name=is_active]').isChecked()===false);
   await page.locator('#draft-title').fill('Nghiệm thu Phase 7 · Bài luyện đã duyệt');await page.locator('#draft-duration').fill('45');await page.locator('[name=is_active]').check();
   await page.locator('[data-draft-release] [type=submit]').click();await page.waitForLoadState('networkidle');
   check('Native publish keeps same paper and changed release fields',page.url()===releaseUrl&&await page.locator('[name=is_active]').isChecked()&&await page.locator('#draft-duration').inputValue()==='45');
   check('Publication reports server success',await page.locator('.flash-success').count()>0);
   await shot('integration-published-draft-1440');
   await login('start');await go('/practice');
   check('Teacher-issued paper appears in learner home',await page.locator('.student-assigned-list').textContent().then(s=>s.includes('Nghiệm thu Phase 7 · Bài luyện đã duyệt')));
   check('Teacher paper is the resumable next action',await page.locator('[data-practice-next]').getAttribute('data-practice-next')==='resume');
  }
  for(const width of [375,768,1024,1440]){
   await page.setViewportSize({width,height:1000});
   await login('student');
   for(const route of [`/practice?course_id=${fixture.courses.teacher}`,'/practice/progress?subject=Toán']){
    await go(route);check('No student page overflow '+route+'@'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    if(width===375||width===1440)await shot(`final-${route.includes('progress')?'progress':'home'}-${width}`,true);
   }
   await login('teacher');
   for(const [name,route] of [['teacher-list','/teacher/practice'],['teacher-detail',`/teacher/practice/${fixture.users.student}?course_id=${fixture.courses.teacher}`],['draft',`/teacher/practice/drafts/${fixture.exams.draft}`]]){
    await go(route);check('No teacher page overflow '+name+'@'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    if(width===375||width===1440)await shot(`final-${name}-${width}`,name==='teacher-list');
   }
   await login('admin');await go('/diagnostics');check('No diagnostic list overflow @'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await go('/diagnostics/new');check('No wizard source overflow @'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   if(width===375||width===1440)await shot(`final-diagnostic-source-${width}`,true);
  }
  for(const width of [375,1440]){
   await page.setViewportSize({width,height:1000});await login('resume');await go(`/practice/${fixture.exams.resume}/take`);
   await page.locator('.taking-selection').evaluate(n=>n.open=true);await page.locator('.taking-selection .learning-audit details').evaluate(n=>n.open=true);
   check('Shared take selection audit stays within viewport @'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   check('Take source tables remain keyboard scroll regions @'+width,await page.locator('.taking-selection .learning-table-scroll[tabindex="0"]').count()===2);
   await shot(`final-shared-take-audit-${width}`);
   await login('pending');await go(`/practice/${fixture.exams.pending}/result`);
   await page.locator('.result-audit').evaluate(n=>n.open=true);await page.locator('.result-audit .learning-audit details').evaluate(n=>n.open=true);
   check('Shared result selection audit stays within viewport @'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   check('Existing continue/end gates remain available @'+width,await page.locator('[data-result-decision]').count()===2);
   await shot(`final-shared-result-audit-${width}`);
  }
  check('No JavaScript exceptions',errors.length===0);check('No broken static assets',assets.length===0);check('No external script/font/style requests',external.length===0);
  const report={date:'2026-10-17',checks:checks.length,passed:checks,errors,assets,external,screenshots:shots,posts,captureOnly:process.env.PHASE7_CAPTURE_ONLY==='1'};
  fs.writeFileSync(path.join(out,report.captureOnly?'capture-qa.json':'browser-qa.json'),JSON.stringify(report,null,2));fs.rmSync(path.join(out,'integration-failure.json'),{force:true});
  console.log(JSON.stringify({checks:checks.length,errors,screenshots:shots.length}));
 }catch(e){fs.writeFileSync(path.join(out,'integration-failure.json'),JSON.stringify({error:e.stack,checks,errors,assets,posts},null,2));throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
