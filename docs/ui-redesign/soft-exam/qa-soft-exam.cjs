const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.SOFT_EXAM_URL||'http://127.0.0.1:8772',out=path.resolve('docs/ui-redesign/soft-exam');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true}),checks=[],errors=[],assets=[],shots=[];
 const check=(name,ok)=>{assert(ok,name);checks.push(name);};
 try{
  fs.mkdirSync(path.join(out,'screenshots'),{recursive:true});
  const context=await browser.newContext({locale:'vi-VN',reducedMotion:'reduce',viewport:{width:1440,height:1000}}),page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.type()==='beforeunload'?d.accept():d.dismiss());page.on('response',r=>{if(r.status()>=400&&r.url().includes('/static/'))assets.push(r.url());});
  const data=await(await context.request.get(base+'/qa/fixture')).json();
  await page.goto(base+'/login');check('Login remains neutral canvas',await page.locator('body').evaluate(n=>getComputedStyle(n).backgroundColor)==='rgb(245, 247, 251)');
  await page.locator('#username').fill('qa_student');await page.locator('#password').fill('Academy123!');await page.locator('#login-form [type=submit]').click();await page.waitForURL(u=>u.pathname!=='/login');
  const take=key=>`/${key==='published'?'assessments':'practice'}/${data.exams[key]}/take`;
  const go=async key=>{const r=await page.goto(base+take(key));check('GET '+key+' status '+r.status()+' url '+page.url(),r.status()===200);await page.waitForFunction(()=>document.querySelector('[data-question-id]')?.dataset.answerState==='blank');await page.evaluate(async()=>{await document.fonts.ready;if(window.MathJax?.startup?.promise)await MathJax.startup.promise;});};
  for(const width of [375,768,1024,1440]){
   await page.setViewportSize({width,height:1000});
   for(const key of ['published','fixed','diagnostic','legacy']){
    await go(key);const suffix=key+'@'+width,q=page.locator('.taking-question').first(),choice=q.locator('.taking-answer-choice').first();
    check('No page overflow '+suffix,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    check('Focused page '+suffix,!await page.locator('.sidebar').isVisible());
    check('Questions preserved '+suffix,await page.locator('[data-question-id]').count()===data.questions_by_exam[key].length);
    check('Soft question card '+suffix,await q.evaluate(n=>getComputedStyle(n).borderRadius==='28px'&&getComputedStyle(n).boxShadow!=='none'));
    check('Raised answer card '+suffix,await choice.evaluate(n=>getComputedStyle(n).borderRadius==='22px'&&getComputedStyle(n).boxShadow!=='none'));
    check('Circle letter '+suffix,await choice.locator('.taking-answer-letter').evaluate(n=>getComputedStyle(n).borderRadius==='999px'));
    check('Readable question '+suffix,await q.locator('.taking-prompt').evaluate(n=>parseFloat(getComputedStyle(n).fontSize)>=20));
    await choice.click();check('Native selection '+suffix,await choice.locator('input').isChecked());check('Selection checkmark '+suffix,await choice.locator('.taking-answer-check').isVisible());
    await q.locator('input[type=radio]').first().focus();await page.keyboard.press('ArrowDown');check('Keyboard radio navigation '+suffix,await q.locator('input[type=radio]').nth(1).isChecked());
    check('Visible keyboard focus '+suffix,await q.locator('.taking-answer-choice').nth(1).evaluate(n=>getComputedStyle(n).outlineStyle==='solid'&&getComputedStyle(n).outlineWidth==='3px'));
    const tf=page.locator('.taking-question[data-question-type=true_false]').first();
    await tf.locator('.taking-truth-choices input').first().check();await page.waitForFunction(id=>document.querySelector('[data-question-id="'+id+'"]').dataset.answerState==='partial',await tf.getAttribute('data-question-id'));
    check('True false partial '+suffix,await tf.getAttribute('data-answer-state')==='partial');
    const short=page.locator('.taking-short-answer textarea').first();await short.fill('5');await short.fill('');
    check('Cleared short answer blank '+suffix,await short.evaluate(n=>n.closest('.taking-question').dataset.answerState==='blank'));
    if([375,1440].includes(width)&&key==='fixed'){
     const file='screenshots/question-card-'+width+'.png';await page.locator('.taking-question').nth(1).screenshot({path:path.join(out,file)});shots.push(file);
     const chosen='screenshots/selected-card-'+width+'.png';await q.screenshot({path:path.join(out,chosen)});shots.push(chosen);
    }
    if([375,1440].includes(width)&&key==='published'){
     for(const [name,node]of [['true-false',tf],['short-answer',short.locator('xpath=ancestor::section[contains(@class,"taking-question")]')]]){const file='screenshots/'+name+'-'+width+'.png';await node.screenshot({path:path.join(out,file)});shots.push(file);}
    }
   }
  }
  await go('published');
  for(const q of data.questions_by_exam.published){
   if(q.kind==='single'){const a=q.answers.find(a=>a.correct);await page.locator('.taking-answer-choice').filter({has:page.locator(`[name="q_${q.id}"][value="${a.id}"]`)}).click();}
   else if(q.kind==='true_false')for(const a of q.answers)await page.locator(`[name="q_${q.id}_ans_${a.id}"][value="${a.correct?'1':'0'}"]`).check();
   else await page.locator(`[name="q_${q.id}_text"]`).fill('5');
  }
  await page.locator('[data-taking-submit]').last().click();await page.locator('#exam-submit-dialog[open]').waitFor();
  check('Confirmation counts all answered',(await page.locator('[data-confirm-blank]').textContent())==='0'&&(await page.locator('[data-confirm-partial]').textContent())==='0');
  await page.keyboard.press('Escape');check('Escape returns to exam',!await page.locator('#exam-submit-dialog').evaluate(n=>n.open));
  await page.locator('[data-taking-submit]').last().click();await page.locator('#exam-submit-dialog[open]').waitFor();await page.locator('[data-taking-confirm-submit]').click();await page.waitForURL('**/assessments/*/result');
  check('Real submit still scores ten',parseFloat(await page.locator('.result-score-value').textContent())===10);
  const other=await browser.newContext({javaScriptEnabled:false,viewport:{width:375,height:1000}});await other.addCookies(await context.cookies());const nojs=await other.newPage();await nojs.goto(base+take('fixed'));await nojs.locator('.taking-answer-choice').first().click();check('No JS native answer works',await nojs.locator('.taking-answer-choice input').first().isChecked());await other.close();
  await go('fixed');await page.emulateMedia({media:'print'});check('Print omits raised shadows',await page.locator('.taking-answer-choice').first().evaluate(n=>getComputedStyle(n).boxShadow==='none'));await page.emulateMedia({media:'screen'});
  check('No JS errors',errors.length===0);check('No broken assets',assets.length===0);
  if(fs.existsSync(path.join(out,'failure.json')))fs.unlinkSync(path.join(out,'failure.json'));
  fs.writeFileSync(path.join(out,'browser-qa.json'),JSON.stringify({status:'passed',checks:checks.length,passed:checks,errors,assets,shots,mutations:'Authentication and one real standalone submission against synthetic memory database only'},null,2));console.log(JSON.stringify({checks:checks.length,shots:shots.length}));
 }catch(error){fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:error.stack,checks,errors,assets},null,2));throw error;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
