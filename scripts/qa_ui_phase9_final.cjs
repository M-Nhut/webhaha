/* Bounded shared renderer and print regression after Phase 9's final fixes. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.PHASE9_URL||'http://127.0.0.1:8771',out=path.resolve('docs/ui-redesign/phase-9');
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true}),checks=[],errors=[],assets=[];
 const check=(name,ok)=>{assert(ok,name);checks.push(name);};
 try{
  const context=await browser.newContext({locale:'vi-VN',reducedMotion:'reduce'}),page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400&&r.url().includes('/static/'))assets.push(r.url());});
  const data=await(await context.request.get(base+'/qa/fixture')).json(),c=data.courses.teacher;
  const login=async role=>{await page.goto(base+'/logout');await page.goto(base+'/login');await page.locator('[name=username]').fill('qa_'+role);await page.locator('[name=password]').fill('Academy123!');await page.locator('[type=submit]').click();await page.waitForURL(u=>u.pathname!=='/login');};
  for(const width of [375,768,1024,1440]){
   await page.setViewportSize({width,height:1000});
   for(const [role,routes] of [
    ['teacher',[`/question-banks/${data.banks.diagnostic}`,'/assessments',`/assessments/${data.exams.editor}/matrix`,`/assessments/import/${data.sessions.paper}`,`/teacher/practice/${data.users.student}?course_id=${c}`]],
    ['student',[`/assessments/${data.exams.standalone}/result`]],
    ['resume',[`/practice/${data.exams.resume}/take`]]
   ]){await login(role);for(const route of routes){
    const r=await page.goto(base+route);check(route+' GET200 @'+width,r.status()===200);
    await page.evaluate(async()=>{await document.fonts.ready;if(window.MathJax?.startup?.promise)await MathJax.startup.promise;});
    check(route+' no overflow @'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    check(route+' current renderer cache @'+width,await page.locator('script[src*="formula_renderer.js"]').getAttribute('src').then(s=>s.includes('20261019-phase9')));
   }}
  }
  await login('admin');await page.setViewportSize({width:1440,height:1000});await page.goto(base+`/assessments/${data.exams.editor}/matrix`);
  await page.emulateMedia({media:'print'});check('Print hides navigation',!await page.locator('#primary-navigation').isVisible());
  check('Print warning remains visible',await page.locator('.matrix-label-warning').isVisible());
  await page.pdf({path:path.join(out,'qa/matrix-a4.pdf'),format:'A4',printBackground:true});await page.emulateMedia({media:'screen'});
  check('No JS error after renderer migration',errors.length===0);check('No missing assets after renderer migration',assets.length===0);
  fs.writeFileSync(path.join(out,'final-browser-qa.json'),JSON.stringify({date:'2026-10-19',status:'passed',count:checks.length,checks,errors,assets,mutations:'Authentication only'},null,2));
  console.log(JSON.stringify({checks:checks.length,errors:errors.length,assets:assets.length}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
