/* Full current UI acceptance on the disposable localhost Phase 9 preview. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.PHASE9_URL||'http://127.0.0.1:8771';
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const out=path.resolve('docs/ui-redesign/phase-9');
fs.mkdirSync(path.join(out,'screenshots'),{recursive:true});fs.mkdirSync(path.join(out,'qa'),{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const checks=[],errors=[],assets=[],external=[],apiFailures=[],pages=[],shots=[];
 const check=(name,ok,details)=>{assert(ok,name+(details?' '+JSON.stringify(details):''));checks.push(name);};
 try{
  const context=await browser.newContext({locale:'vi-VN',reducedMotion:'reduce'}),page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{const u=new URL(r.url());if(r.status()>=400&&u.pathname.startsWith('/static/'))assets.push({path:u.pathname,status:r.status()});if(r.status()>=400&&u.pathname.startsWith('/api/'))apiFailures.push({path:u.pathname,status:r.status()});});
  page.on('request',r=>{if(['script','font','stylesheet'].includes(r.resourceType())&&!r.url().startsWith(base))external.push(r.url());});
  const fixture=await(await context.request.get(base+'/qa/fixture')).json(),c=fixture.courses.teacher,s=fixture.users.student,b=fixture.banks.diagnostic;
  const login=async(role)=>{await page.goto(base+'/logout');if(!role)return;await page.goto(base+'/login');await page.locator('[name=username]').fill('qa_'+role);await page.locator('[name=password]').fill('Academy123!');await page.locator('[type=submit]').click();await page.waitForURL(u=>u.pathname!=='/login');};
  const sets=[
   [null,[['login','/login'],['register','/register']]],
   ['teacher',[
    ['dashboard','/'],['profile','/profile'],['banks','/question-banks'],['bank-form','/question-banks/new?mode=general'],['bank-detail',`/question-banks/${b}`],
    ['bank-classification',`/question-banks/${b}/classification`],['classification-evaluation',`/question-banks/${b}/classification/evaluation`],['curriculum','/curriculum'],
    ['import',`/question-banks/import?session_id=${fixture.sessions.duplicates}`],['assessment-from-bank',`/assessments/from-bank?course_id=${c}&bank_ids=${fixture.banks.general}`],
    ['assessment-editor',`/assessments/import/${fixture.sessions.paper}`],['assessments','/assessments'],['matrix',`/assessments/${fixture.exams.editor}/matrix`],
    ['diagnostics','/diagnostics'],['teacher-list','/teacher/practice'],['teacher-detail',`/teacher/practice/${s}?course_id=${c}`],['practice-draft',`/teacher/practice/drafts/${fixture.exams.draft}`],
    ['courses','/courses'],['course-detail',`/courses/${c}`],['my-students','/my-students'],['ai-class-overview',`/ai-reports/class?course_id=${c}`],
    ['ai-individual-overview',`/ai-reports/individual?course_id=${c}&student_id=${s}`],['ai-class-detail',`/ai-reports/class?course_id=${c}&view=detail`],
    ['ai-individual-detail',`/ai-reports/individual?course_id=${c}&student_id=${s}&view=detail`],['ai-settings','/teacher/ai-settings']
   ]],
   ['admin',[['diagnostic-form','/diagnostics/new'],['course-form','/courses/new'],['users','/users/students'],['edit-user',`/users/${s}/edit`]]],
   ['student',[['practice',`/practice?course_id=${c}`],['progress','/practice/progress?subject=Toán'],['result',`/assessments/${fixture.exams.standalone}/result`]]],
   ['resume',[['take',`/practice/${fixture.exams.resume}/take`]]]
  ];
  for(const width of [375,768,1024,1440]){
   await page.setViewportSize({width,height:1000});
   for(const [role,routes] of sets){await login(role);for(const [name,route] of routes){
    const response=await page.goto(base+route);check(name+' GET200 @'+width,response.status()===200,{status:response.status(),url:page.url()});
    await page.evaluate(async()=>{await document.fonts.ready;if(window.MathJax?.startup?.promise)await MathJax.startup.promise;});
    if(name.startsWith('ai-')&&name!=='ai-settings')await page.waitForFunction(()=>document.getElementById('ai-content')&&!document.getElementById('ai-content').hidden);
    if(name==='import')await page.waitForFunction(()=>window.Alpine&&Alpine.$data(document.querySelector('.import-workspace')).step===3);
    check(name+' no page overflow @'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    check(name+' one main heading @'+width,await page.locator('main h1').count()===1);
    check(name+' local Be Vietnam Pro @'+width,await page.locator('body').evaluate(el=>getComputedStyle(el).fontFamily.includes('Be Vietnam Pro')));
    const unnamed=await page.locator('main button').evaluateAll(nodes=>nodes.filter(n=>n.getClientRects().length&&!n.disabled&&!n.textContent.trim()&&!n.getAttribute('aria-label')&&!n.getAttribute('aria-labelledby')&&!n.getAttribute('title')).map(n=>n.outerHTML.slice(0,160)));
    check(name+' visible buttons named @'+width,unnamed.length===0,unnamed);
    if(name==='take')check('Take keeps22question contract @'+width,await page.locator('[data-question-id]').count()===22);
    if(name==='ai-class-overview')check('AI charts initialized @'+width,await page.locator('#ai-bar-canvas').count()===1);
    if((width===375||width===1440)&&!['ai-individual-overview','ai-individual-detail'].includes(name)){const file=`screenshots/${name}-${width}.png`;await page.screenshot({path:path.join(out,file)});shots.push(file);}
    pages.push({name,role,width,route});
   }}
  }
  await login('teacher');await page.setViewportSize({width:375,height:667});await page.goto(base+'/');
  const toggle=page.locator('[data-sidebar-toggle]');await toggle.focus();await page.keyboard.press('Enter');
  check('Drawer keyboard opens',await page.locator('#primary-navigation').getAttribute('role')==='dialog');
  check('Drawer focus inside',await page.locator('#primary-navigation').evaluate(el=>el.contains(document.activeElement)));
  check('Drawer background inert',await page.locator('.main-area').evaluate(el=>el.inert));
  await page.keyboard.press('Escape');check('Drawer escape and focus return',await toggle.evaluate(el=>el===document.activeElement)&&!await page.locator('.main-area').evaluate(el=>el.inert));
  await page.goto(base+`/question-banks/import?session_id=${fixture.sessions.duplicates}`);await page.waitForFunction(()=>Alpine.$data(document.querySelector('.import-workspace')).step===3);
  const compare=page.getByRole('button',{name:'Đối chiếu câu này'}).filter({visible:true}).first();await compare.click();
  check('Duplicate comparison native modal',await page.locator('#import-duplicate-dialog').evaluate(el=>el.matches(':modal')));
  check('Duplicate pair no overflow',await page.locator('#import-duplicate-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth+1));
  await page.keyboard.press('Escape');check('Duplicate comparison returns focus',await compare.evaluate(el=>el===document.activeElement));
  await login('admin');await page.goto(base+'/users/students');await page.locator('[data-dialog-open="people-create-dialog"]').first().click();
  check('Create user native modal',await page.locator('#people-create-dialog').evaluate(el=>el.matches(':modal')));await page.keyboard.press('Escape');
  await page.setViewportSize({width:1440,height:1000});await page.goto(base+`/assessments/${fixture.exams.editor}/matrix`);
  const download=await context.request.get(base+`/assessments/${fixture.exams.editor}/matrix?download=xlsx`);
  check('Matrix Excel actual response',download.status()===200&&download.headers()['content-type'].includes('spreadsheetml'));
  fs.writeFileSync(path.join(out,'qa/matrix.xlsx'),await download.body());
  await page.emulateMedia({media:'print'});check('Matrix print hides navigation',!await page.locator('#primary-navigation').isVisible());
  await page.pdf({path:path.join(out,'qa/matrix-a4.pdf'),format:'A4',printBackground:true});await page.emulateMedia({media:'screen'});
  for(const width of [375,1440]){await page.setViewportSize({width,height:1000});for(const code of [400,403,404,405,429,500]){
   const response=await page.goto(base+'/qa/errors/'+code);check('Error '+code+' preserves status @'+width,response.status()===code);check('Error '+code+' no overflow @'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));check('Error '+code+' one heading @'+width,await page.locator('main h1').count()===1);
   if(code===404){const file=`screenshots/error404-${width}.png`;await page.screenshot({path:path.join(out,file)});shots.push(file);}
  }}
  check('No JavaScript errors',errors.length===0,errors);check('No missing static assets',assets.length===0,assets);check('No unexpected API errors',apiFailures.length===0,apiFailures);check('No external script/font/style',external.length===0,external);
  const report={status:'passed',checkCount:checks.length,checks,pages,screenshots:shots,errors,assets,external,apiFailures,mutationScope:'Authentication only; all other UI cases GET/read-only. AI refresh=1 deliberately omitted.'};
  fs.writeFileSync(path.join(out,'browser-qa.json'),JSON.stringify(report,null,2));fs.rmSync(path.join(out,'browser-failure.json'),{force:true});console.log(JSON.stringify({checks:checks.length,pageCases:pages.length,screenshots:shots.length,errors:errors.length}));
 }catch(error){fs.writeFileSync(path.join(out,'browser-failure.json'),JSON.stringify({error:error.stack,checks,errors,assets,external,apiFailures,pages},null,2));throw error;}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
