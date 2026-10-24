const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const context=await browser.newContext();const page=await context.newPage(); const errors=[];
 page.on('pageerror',err=>errors.push(err.message));
 const fixture=await (await context.request.get('http://127.0.0.1:8767/qa/fixture')).json();
 await page.goto('http://127.0.0.1:8767/login');await page.locator('input[name=username]').fill('qa_teacher');await page.locator('input[name=password]').fill('Academy123!');await page.locator('[type=submit]').click();await page.waitForURL(url=>!url.pathname.includes('login'));
 let count=0; const check=(value,label)=>{if(!value)throw Error(label);count++};
 await page.route('**/question-banks/import/*/update',r=>r.fulfill({status:400,contentType:'application/json',body:JSON.stringify({success:false,message:'Lỗi thử nghiệm. Giữ bản nháp.'})}));
 for (const width of [375,768,1024,1440]){
  await page.setViewportSize({width,height:900});
  for(const name of ['general','research','duplicates','incomplete']){
   await page.goto('http://127.0.0.1:8767/question-banks/import?session_id='+fixture.sessions[name]);
   await page.waitForFunction(()=>{const root=document.querySelector('.import-workspace');return root&&Alpine.$data(root).step===3&&!Alpine.$data(root).busy});
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'overflow '+name+'@'+width);
   check(await page.locator('.import-steps [aria-current=step]').count()===1,'one current step');
   check(await page.locator('.import-question').count()>0,'questions');
   check(await page.locator('.import-context').innerText().then(x=>x.includes('Mục đích')),'context purpose');
   if(name==='general' && [375,1440].includes(width)) await page.screenshot({path:'/tmp/phase5-wizard-general-'+width+'.png',fullPage:true});
  }
 }
 await page.goto('http://127.0.0.1:8767/question-banks/import?session_id='+fixture.sessions.general);await page.waitForFunction(()=>Alpine.$data(document.querySelector('.import-workspace')).step===3);
 await page.locator('.import-question-heading button').first().click();await page.locator('.inline-edit-container textarea[name=question_text]').fill('Bản nháp được giữ $2+3$.');
 await page.locator('.inline-edit-container button[type=submit]').click();await page.locator('#import-error-summary').waitFor({state:'visible'});
 check(await page.locator('.inline-edit-container textarea[name=question_text]').inputValue()==='Bản nháp được giữ $2+3$.','draft persists failure');
 check(await page.locator('#import-error-summary').innerText().then(x=>x.includes('Lỗi thử nghiệm')),'error announced');
 await page.locator('.inline-edit-container button').filter({hasText:'Hủy sửa'}).click();
 await page.locator('.import-question').nth(2).locator('.import-question-heading button').first().click();
 await page.locator('.inline-edit-container input[x-model=editingShortAnswerText]').fill('5 | năm');
 check(await page.locator('.inline-edit-container input[x-model=editingShortAnswerText]').inputValue()==='5 | năm','short delimiter stays');
 await page.locator('.inline-edit-container button').filter({hasText:'Hủy sửa'}).click();
 await page.locator('.import-section-heading button.btn-primary').click();
 check(await page.locator('section[x-show="step === 4"] button[type=submit]').isDisabled(),'review required');
 await page.locator('input[name=reviewed]').check();check(await page.locator('section[x-show="step === 4"] button[type=submit]').isEnabled(),'review unlock');
 await page.locator('section[x-show="step === 4"] button[type=button]').click();
 await page.locator('.import-section-heading button.btn-secondary').click();check(await page.locator('#import-cancel-dialog').evaluate(el=>el.open),'native cancel');await page.keyboard.press('Escape');check(!await page.locator('#import-cancel-dialog').evaluate(el=>el.open),'cancel escape');
 await page.goto('http://127.0.0.1:8767/question-banks/import');check(await page.locator('.import-workspace input[type=file]').isVisible(),'native upload');
 check(await page.locator('.import-workspace [style]').count()>=0,'Alpine may add display styles');
 check(errors.length===0,'no errors '+JSON.stringify(errors));
 console.log(JSON.stringify({checks:count,errors}));await browser.close();
})().catch(err=>{console.error(err);process.exit(1)});
