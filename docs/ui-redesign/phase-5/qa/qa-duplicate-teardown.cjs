const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const base=process.env.PHASE5_PREVIEW_URL || 'http://127.0.0.1:8767', errors=[],checks=[];
 const check=(name,condition)=>{checks.push({name,passed:!!condition});assert.ok(condition,name)};
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
 const page=await browser.newPage();page.on('pageerror',err=>errors.push(err.message));
 await page.goto(base+'/login',{waitUntil:'networkidle'});await page.locator('[name=username]').fill('qa_teacher');await page.locator('[name=password]').fill('Academy123!');await Promise.all([page.waitForNavigation(),page.locator('[name=submit]').click()]);
 const fixture=await(await page.request.get(base+'/qa/fixture')).json();
 await page.goto(base+'/question-banks/import?bank_id='+fixture.banks.general,{waitUntil:'networkidle'});
 const source=fixture.sources.general+'\n'+fixture.sources.general;
 await page.locator('input[type=file]').setInputFiles({name:'duplicate-teardown-own-session.tex',mimeType:'text/plain',buffer:Buffer.from(source)});
 await page.waitForFunction(()=>{let state=Alpine.$data(document.querySelector('.import-workspace'));return state.step===3&&!state.busy});
 check('own synthetic import ready',true);
 const opener=page.getByRole('button',{name:'Đối chiếu câu này'}).filter({visible:true}).first();
 await opener.click();await page.waitForFunction(()=>document.getElementById('import-duplicate-dialog').open);
 await page.getByRole('button',{name:'Đóng đối chiếu'}).click();await page.waitForTimeout(200);
 check('button close clears owner',await page.evaluate(()=>Alpine.$data(document.querySelector('.import-workspace')).comparisonUid===null));
 await opener.click();await page.waitForFunction(()=>document.getElementById('import-duplicate-dialog').open);
 await page.keyboard.press('Escape');await page.waitForTimeout(200);
 check('Escape clears owner',await page.evaluate(()=>Alpine.$data(document.querySelector('.import-workspace')).comparisonUid===null));
 await opener.click();await page.waitForFunction(()=>document.getElementById('import-duplicate-dialog').open);
 await page.evaluate(async bank=>{let state=Alpine.$data(document.querySelector('.import-workspace'));state.destinationDraft=String(bank);await state.changeDestination()},fixture.banks.empty);
 await page.waitForTimeout(250);
 check('actual destination POST succeeded',await page.evaluate(bank=>Alpine.$data(document.querySelector('.import-workspace')).lockedBankId===bank,fixture.banks.empty));
 check('destination closes comparison',await page.evaluate(()=>!document.getElementById('import-duplicate-dialog').open&&Alpine.$data(document.querySelector('.import-workspace')).comparisonUid===null));
 await opener.click();await page.waitForFunction(()=>document.getElementById('import-duplicate-dialog').open);
 const sid=await page.evaluate(()=>Alpine.$data(document.querySelector('.import-workspace')).sessionId);
 await page.route('**/question-banks/import/'+sid+'/preview',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({success:true,questions:[],stats:{total:0,valid:0,warning:0,error:0},duplicate_report:{bank_id:fixture.banks.empty,bank_name:'Ngân hàng thử',total:0,new:0,eligible:0},bank_id:fixture.banks.empty,status:'ready_for_review'})}));
 await page.evaluate(async()=>{let state=Alpine.$data(document.querySelector('.import-workspace'));await state.refreshDuplicateReport()});await page.waitForTimeout(250);
 check('refresh removes comparison safely',await page.evaluate(()=>!document.getElementById('import-duplicate-dialog').open&&Alpine.$data(document.querySelector('.import-workspace')).comparisonUid===null));
 check('no JavaScript exceptions during teardown',errors.length===0);
 fs.writeFileSync('docs/ui-redesign/phase-5/duplicate-teardown-qa.json',JSON.stringify({passed:checks.length,checks,errors},null,2));console.log(JSON.stringify({passed:checks.length,errors}));
 }finally{await browser.close()}
})().catch(err=>{console.error(err);process.exitCode=1});
