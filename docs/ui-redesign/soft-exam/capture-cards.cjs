const fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const context=await browser.newContext({reducedMotion:'reduce'}),page=await context.newPage(),base='http://127.0.0.1:8772';
 const data=await(await context.request.get(base+'/qa/fixture')).json();await page.goto(base+'/login');await page.locator('#username').fill('qa_student');await page.locator('#password').fill('Academy123!');await page.locator('#login-form [type=submit]').click();await page.waitForURL(u=>u.pathname!=='/login');
 for(const width of [375,1440]){
  await page.setViewportSize({width,height:1000});await page.goto(base+'/practice/'+data.exams.fixed+'/take');await page.waitForFunction(()=>document.querySelector('[data-question-id]')?.dataset.answerState==='blank');await page.evaluate(async()=>{await document.fonts.ready;if(window.MathJax?.startup?.promise)await MathJax.startup.promise;});
  const palette=await page.locator('body').evaluate(n=>({canvas:getComputedStyle(n).backgroundColor,accent:getComputedStyle(n).getPropertyValue('--color-primary').trim()}));
  if(palette.canvas!=='rgb(245, 247, 251)'||palette.accent!=='#1d4ed8')throw new Error('Exam palette differs from web blue '+JSON.stringify(palette));
  await page.mouse.move(width-1,0);await page.locator('main').focus();await page.locator('.taking-question').nth(1).screenshot({path:path.resolve('docs/ui-redesign/soft-exam/screenshots/question-card-'+width+'.png')});
  const second=page.locator('.taking-question').nth(1);await second.locator('.taking-answer-choice').nth(1).click();await page.mouse.move(width-1,0);await page.locator('main').focus();await second.screenshot({path:path.resolve('docs/ui-redesign/soft-exam/screenshots/selected-card-'+width+'.png')});
  const tf=page.locator('.taking-question[data-question-type=true_false]').first();await tf.locator('.taking-truth-choices input').first().check();await page.mouse.move(width-1,0);await page.locator('main').focus();await tf.screenshot({path:path.resolve('docs/ui-redesign/soft-exam/screenshots/true-false-'+width+'.png')});
  await page.locator('.taking-question[data-question-type=short_answer]').first().screenshot({path:path.resolve('docs/ui-redesign/soft-exam/screenshots/short-answer-'+width+'.png')});
 }
 await page.locator('.taking-answer-choice').first().click();await page.emulateMedia({media:'print'});
 const printed=await page.locator('.taking-answer-choice').first().evaluate(n=>({shadow:getComputedStyle(n).boxShadow,letterColor:getComputedStyle(n.querySelector('.taking-answer-letter')).color,letterBackground:getComputedStyle(n.querySelector('.taking-answer-letter')).backgroundColor}));
 if(printed.shadow!=='none'||printed.letterColor!=='rgb(15, 23, 42)'||printed.letterBackground!=='rgba(0, 0, 0, 0)')throw new Error('Selected answer print reset failed: '+JSON.stringify(printed));
 fs.writeFileSync(path.resolve('docs/ui-redesign/soft-exam/blue-palette-qa.json'),JSON.stringify({status:'passed',viewports:[375,1440],accent:'#1d4ed8',hover:'#1e40af',canvas:'#f5f7fb'},null,2));
 fs.writeFileSync(path.resolve('docs/ui-redesign/soft-exam/selected-print-qa.json'),JSON.stringify({status:'passed',...printed},null,2));
 console.log('Captured neutral cards at375 and1440; selected print passed');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
