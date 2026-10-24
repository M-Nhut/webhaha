/* Real submissions only against the isolated synthetic preview. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.PHASE6_URL||'http://127.0.0.1:8768';
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const out=path.resolve('docs/ui-redesign/phase-6');fs.mkdirSync(path.join(out,'screenshots'),{recursive:true});
const checks=[],errors=[],assets=[],external=[],shots=[];
const check=(name,condition)=>{assert(condition,name);checks.push(name);};
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
  await page.addInitScript(()=>{const actual=Date.now;window.__qa_clock=0;Date.now=()=>actual()+window.__qa_clock;});
  page.on('pageerror',e=>errors.push(e.message));
  page.on('dialog',d=>d.type()==='beforeunload'?d.accept():d.dismiss());
  page.on('response',r=>{if(r.status()>=400&&r.url().includes('/static/'))assets.push(r.url());});
  page.on('request',r=>{if(['font','script','stylesheet'].includes(r.resourceType())&&!r.url().startsWith(base))external.push(r.url());});
  const fixture=await(await context.request.get(base+'/qa/fixture')).json();
  const login=async(role)=>{
   await page.goto(base+'/logout');await page.goto(base+'/login');
   await page.locator('[name=username]').fill('qa_'+role);await page.locator('[name=password]').fill('Academy123!');
   await page.locator('[type=submit]').click();await page.waitForURL(u=>u.pathname!=='/login');
  };
  const prefix=key=>['fixed','diagnostic','legacy','decision','source_invalid','diagnostic_done','multi_history'].includes(key)?'practice':'assessments';
  const endpoint=(key,action)=>`/${prefix(key)}/${fixture.exams[key]}/${action}`;
  const go=async(route)=>{const r=await page.goto(base+route);check('GET '+route,r.status()===200);};
  const taking=()=>page.waitForFunction(()=>document.querySelector('[data-question-id]')?.dataset.answerState==='blank');
  const shot=async(name,modal=false)=>{
   if(!modal)await page.evaluate(()=>{window.scrollTo(0,0);document.activeElement?.blur();});
   await page.evaluate(async()=>{if(window.MathJax?.startup?.promise)await MathJax.startup.promise;window.FormulaRenderer?.renderFormulas(document.querySelector('main'),{},{immediate:true});if(window.MathJax?.typesetPromise)await MathJax.typesetPromise();});
   const file='screenshots/'+name+'.png';await page.screenshot({path:path.join(out,file),fullPage:!modal});shots.push(file);
  };
  await login('student');
  for(const width of [375,768,1024,1440]){
   await page.setViewportSize({width,height:1000});
   for(const key of ['published','fixed','diagnostic','legacy']){
    await go(endpoint(key,'take'));await taking();
    check(`Focused shell ${key}@${width}`,!await page.locator('.sidebar').isVisible());
    check(`No overflow ${key}@${width}`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    check(`All native questions ${key}@${width}`,await page.locator('[data-question-id]').count()===fixture.questions_by_exam[key].length);
    if(width===375||width===1440)await shot(`take-final-${key}-${width}`);
   }
  }
  await page.setViewportSize({width:1440,height:1000});
  if(process.env.PHASE6_CAPTURE_ONLY!=='1'){
   await go(endpoint('published','take'));await taking();
   const qs=fixture.questions_by_exam.published,single=qs.find(q=>q.kind==='single'),tf=qs.find(q=>q.kind==='true_false'),short=qs.find(q=>q.kind==='short_answer');
   await page.locator(`[name="q_${single.id}"][value="${single.answers.find(a=>a.correct).id}"]`).check();
   await page.locator(`[name="q_${tf.id}_ans_${tf.answers[0].id}"][value="${tf.answers[0].correct?'1':'0'}"]`).check();
   await page.waitForFunction(id=>document.querySelector(`[data-question-id="${id}"]`).dataset.answerState==='partial',tf.id);
   check('TF incomplete is partial',await page.locator(`[data-question-id="${tf.id}"]`).getAttribute('data-answer-state')==='partial');
   await page.locator(`[name="q_${short.id}_text"]`).fill('5');await page.locator(`[name="q_${short.id}_text"]`).fill('');
   await page.waitForFunction(id=>document.querySelector(`[data-question-id="${id}"]`).dataset.answerState==='blank',short.id);
   check('Cleared short answer becomes blank',await page.locator(`[data-question-id="${short.id}"]`).getAttribute('data-answer-state')==='blank');
   await page.locator('[data-taking-submit]').first().click();await page.locator('#exam-submit-dialog[open]').waitFor();
   check('Confirmation reports partial and blank',(await page.locator('[data-confirm-partial]').textContent())==='1'&&(await page.locator('[data-confirm-blank]').textContent())==='1');
   await page.keyboard.press('Escape');check('Confirmation Escape returns to form',!await page.locator('#exam-submit-dialog').evaluate(n=>n.open));
   const fill=async(key)=>{
    for(const q of fixture.questions_by_exam[key]){
     if(q.kind==='single')await page.locator(`[name="q_${q.id}"][value="${q.answers.find(a=>a.correct).id}"]`).check();
     else if(q.kind==='true_false')for(const a of q.answers)await page.locator(`[name="q_${q.id}_ans_${a.id}"][value="${a.correct?'1':'0'}"]`).check();
     else await page.locator(`[name="q_${q.id}_text"]`).fill('5');
    }
   };
   const submit=async()=>{await page.locator('[data-taking-submit]').first().click();await page.locator('#exam-submit-dialog[open]').waitFor();await page.locator('[data-taking-confirm-submit]').click();};
   await fill('published');
   const takeUrl=base+endpoint('published','take');
   await page.route(takeUrl,r=>r.request().method()==='POST'?r.fulfill({status:403,contentType:'text/html',body:'<h1>Phiên thử nghiệm bị từ chối</h1>'}):r.continue());
   await submit();await page.locator('[data-taking-error]').waitFor({state:'visible'});
   check('Failed submit retains all native answers',await page.locator('#exam-form input:checked').count()===5&&await page.locator(`[name="q_${short.id}_text"]`).inputValue()==='5');
   check('Failed submit enables retry',await page.locator('[data-taking-submit]').first().isEnabled());
   await shot('take-send-error-1440');
   await page.unroute(takeUrl);await page.locator('[data-taking-submit]').first().click();await page.locator('#exam-submit-dialog[open]').waitFor();
   await page.setViewportSize({width:375,height:900});await shot('submit-confirm-375',true);
   await page.setViewportSize({width:1440,height:1000});await page.locator('[data-taking-confirm-submit]').click();await page.waitForURL('**/assessments/*/result');
   check('Standalone native submit scores ten',parseFloat(await page.locator('.result-score-value').textContent())===10);
   await shot('submitted-standalone-1440');
   await page.goto(takeUrl);check('Second attempt redirects to result',page.url().endsWith('/result'));
   for(const key of ['fixed','diagnostic']){
    await go(endpoint(key,'take'));await taking();await fill(key);await submit();await page.waitForURL('**/practice/*/result');
    check(`${key} real 22-question submit scores ten`,parseFloat(await page.locator('.result-score-value').textContent())===10);
    await shot(`submitted-${key}-1440`);
   }
   await go(endpoint('empty','take'));await taking();
   await page.evaluate(()=>{window.__qa_clock=Number(document.querySelector('[data-exam-taking]').dataset.durationSeconds)*1000+1500;window.dispatchEvent(new Event('pageshow'));});
   await page.waitForURL('**/assessments/*/result');check('Expiry submits unanswered form through same guard',parseFloat(await page.locator('.result-score-value').textContent())===0);
   await shot('submitted-expiry-1440');
  }
  await login('teacher');await go('/assessments');check('Management list has no invented student completion state',!await page.locator('main').textContent().then(s=>s.includes('Chưa làm')));
  await go(endpoint('graded','result'));check('Teacher submission table',await page.locator('.results-table').isVisible());
  await login('admin');await go(endpoint('published','matrix'));check('Matrix preserves nineteen columns',await page.locator('.matrix-7991 thead tr').first().evaluate(row=>[...row.cells].reduce((sum,cell)=>sum+cell.colSpan,0))===19);
  check('No browser JS exceptions',errors.length===0);check('No broken static assets',assets.length===0);check('No external scripts/styles/fonts',external.length===0);
  const report={date:'2026-10-15',checks:checks.length,passed:checks,errors,assets,external,screenshots:shots};
  fs.writeFileSync(path.join(out,process.env.PHASE6_CAPTURE_ONLY==='1'?'capture-qa.json':'browser-qa.json'),JSON.stringify(report,null,2));
  if(fs.existsSync(path.join(out,'qa-failure.json')))fs.unlinkSync(path.join(out,'qa-failure.json'));
  console.log(JSON.stringify({checks:checks.length,errors,screenshots:shots.length}));
 }catch(e){fs.writeFileSync(path.join(out,'qa-failure.json'),JSON.stringify({error:e.message,checks,errors,assets},null,2));throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
