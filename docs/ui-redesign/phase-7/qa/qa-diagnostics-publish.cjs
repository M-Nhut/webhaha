/* REAL publication/deletion only on the explicitly enabled isolated synthetic preview.
 * Only the exam ID returned by this run's publication response may be deleted.
 * Run after root coordination: PHASE7_ALLOW_SYNTHETIC_WRITES=1 ... node <this file>.
 */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.PHASE7_BASE_URL||'http://127.0.0.1:8769';
assert.equal(base,'http://127.0.0.1:8769','This mutation QA is restricted to the isolated Phase7 preview.');
assert.equal(process.env.PHASE7_ALLOW_SYNTHETIC_WRITES,'1','Wait for root GO and explicitly enable synthetic writes.');
const output=path.resolve(__dirname,'..'),title='Nghiệm thu Phase 7 · Đầu vào';
const checks=[],errors=[],requests=[],screenshots=[];
let createdExamId=null,deleted=false,cleanupFallback=false,mainError=null,initialFixtureIds=new Set();
let forwardedPublishResponse=null;
const report=()=>({title,base,checks,errors,requests,screenshots,createdExamId,deleted,cleanupFallback,error:mainError?.stack||null,onlyCreatedPaperMayBeDeleted:true,actualPublishResponseReadBeforeNavigation:true});
const save=()=>fs.writeFileSync(path.join(output,'diagnostics-publish-qa.json'),JSON.stringify(report(),null,2));
const check=(name,value)=>{assert(value,name);checks.push(name);save();};
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 let context,page;
 try{
  context=await browser.newContext({viewport:{width:1440,height:1000},locale:'vi-VN'});page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.method()==='POST')requests.push({path:new URL(r.url()).pathname,method:'POST'});});
  const fixtureResponse=await context.request.get(base+'/qa/fixture');assert(fixtureResponse.ok());
  const fixture=await fixtureResponse.json();
  check('Explicit rich synthetic fixture',fixture.wizard.question_ids.length===22&&fixture.wizard.choices_count===97&&Number.isInteger(fixture.courses.teacher));
  initialFixtureIds=new Set(Object.values(fixture.exams).filter(Number.isInteger));
  await page.goto(base+'/login');await page.locator('[name=username]').fill('qa_admin');await page.locator('[name=password]').fill('Academy123!');
  await Promise.all([page.waitForURL(u=>u.pathname!='/login'),page.locator('[type=submit]').click()]);
  await page.goto(base+'/diagnostics/new');
  await page.locator('#dw-bank').selectOption(String(fixture.wizard.bank_id));await page.locator('#dw-start').click();await page.locator('.dw-question').first().waitFor();
  const ids=new Set(fixture.wizard.question_ids.map(Number));let selected=0,pages=0;
  while(true){
   pages++;
   const currentIds=await page.locator('#dw-candidates input[type=checkbox]').evaluateAll(es=>es.map(e=>Number(e.id.replace('dw-choice-',''))));
   for(const id of currentIds)if(ids.has(id)){await page.locator('#dw-choice-'+id).check();selected++;}
   if(await page.locator('#dw-next-page').isDisabled())break;
   const oldPage=await page.locator('#dw-page-label').innerText();await page.locator('#dw-next-page').click();await page.waitForFunction(old=>document.getElementById('dw-page-label').textContent!==old,oldPage);
  }
  check('Real97-choice4-page selection exact22',pages===4&&selected===22&&await page.locator('#dw-review').isEnabled());
  check('Real coverage8 complete',(await page.locator('#dw-coverage').innerText()).includes('8/8'));
  await page.locator('#dw-review').click();await page.locator('[data-step="3"]').waitFor({state:'visible'});
  check('Serverreview22 and frozen digest',await page.locator('[data-review-end]').count()===22&&(await page.locator('#dw-review-digest').inputValue()).length>=32);
  check('Confirmation initially blocked',await page.locator('#dw-confirm').isDisabled());
  for(const end of await page.locator('[data-review-end]').all()){await end.scrollIntoViewIfNeeded();await page.waitForTimeout(35);}
  await page.waitForFunction(()=>!document.getElementById('dw-confirm').disabled);
  check('All22 reviewed before confirmation',(await page.locator('#dw-read-status').innerText()).includes('22/22'));
  await page.locator('#dw-title').fill(title);await page.locator('#dw-course').selectOption(String(fixture.courses.teacher));await page.locator('#dw-confirm').check();
  check('Namedclassandtitle receipt enables publish',await page.locator('#dw-publish').isEnabled()&&(await page.locator('#dw-publish-context').innerText()).includes(title));
  // Forward the original browser POST unchanged to the real handler. Read its
  // actual body before releasing it, since the app navigates immediately on success.
  await page.route('**/diagnostics/new',async route=>{
   if(route.request().method()!=='POST')return route.continue();
   const response=await route.fetch();const body=await response.body();
   forwardedPublishResponse={status:response.status(),data:JSON.parse(body.toString('utf8'))};
   await route.fulfill({response,body});
  });
  await page.locator('#dw-publish').click();
  await page.waitForURL(base+'/diagnostics');
  const published=forwardedPublishResponse?.data;
  assert(forwardedPublishResponse?.status===200&&published?.success&&Number.isSafeInteger(published.exam_id)&&published.exam_id>0,'Publication must return a confirmed new exam ID.');
  assert(!initialFixtureIds.has(published.exam_id),'Never treat an existing fixture as a created paper.');
  createdExamId=published.exam_id;save();console.log('Created synthetic diagnostic ID '+createdExamId+'; this run owns cleanup.');
  await page.waitForURL(base+'/diagnostics');
  const ownDelete=()=>page.locator(`form[action="/diagnostics/${createdExamId}/delete"]`);
  check('Published paper appears by exact ownID',await ownDelete().count()===1&&await ownDelete().getAttribute('data-title')===title);
  check('Creation success receipt',(await page.locator('body').innerText()).includes('Đã tạo và giao đề đánh giá đầu vào'));
  await page.evaluate(async()=>{scrollTo(0,0);document.activeElement?.blur();await document.fonts.ready;});
  let file='screenshots/diagnostics-publish-receipt-1440.png';await page.screenshot({path:path.join(output,file),fullPage:true});screenshots.push(file);save();
  const resultResponse=await page.goto(base+`/practice/${createdExamId}/result`);
  check('New diagnostic result GET allowed',resultResponse.status()===200);
  check('New diagnostic has an explicit empty result',await page.getByRole('heading',{name:'Chưa có bài nộp',exact:true}).count()===1&&await page.locator('h1').innerText()===title);
  file='screenshots/diagnostics-publish-empty-results-1440.png';await page.screenshot({path:path.join(output,file),fullPage:true});screenshots.push(file);save();
  await page.goto(base+'/diagnostics');await ownDelete().locator('[data-delete-open]').click();
  check('Native deletion names only this new paper',await page.locator('#diagnostic-delete-dialog').evaluate(e=>e.open)&&await page.locator('#diagnostic-delete-name').innerText()===title);
  file='screenshots/diagnostics-publish-delete-dialog-1440.png';await page.screenshot({path:path.join(output,file),fullPage:false});screenshots.push(file);save();
  const deleteResponsePromise=page.waitForResponse(r=>new URL(r.url()).pathname===`/diagnostics/${createdExamId}/delete`&&r.request().method()==='POST');
  await page.locator('#diagnostic-delete-confirm').click();const deleteResponse=await deleteResponsePromise;
  await page.waitForURL(base+'/diagnostics');await page.locator('#diagnostic-delete-dialog').waitFor({state:'hidden'});
  check('Existing CSRF delete handler redirected',deleteResponse.status()===302||deleteResponse.status()===303);
  check('Only created paper removed from register',await ownDelete().count()===0);
  deleted=true;save();
  check('Deletion success receipt',(await page.locator('body').innerText()).includes('Đã xóa bài đánh giá đầu vào thành công'));
  check('One actual publication and one actual deletion',requests.filter(r=>r.path==='/diagnostics/new').length===1&&requests.filter(r=>r.path===`/diagnostics/${createdExamId}/delete`).length===1);
  check('No existing fixture deleted',requests.filter(r=>/\/diagnostics\/\d+\/delete/.test(r.path)).every(r=>r.path===`/diagnostics/${createdExamId}/delete`));
  check('No JS exceptions',errors.length===0);
 }catch(error){mainError=error;save();console.error(error);}
 finally{
  // Failure cleanup is restricted to the positively identified newly created paper.
  if(createdExamId&&!deleted&&!initialFixtureIds.has(createdExamId)&&page&&context){
   try{
    await page.goto(base+'/diagnostics');
    const form=page.locator(`form[action="/diagnostics/${createdExamId}/delete"]`);
    if(await form.count()){
     assert.equal(await form.getAttribute('data-title'),title,'Cleanup only owns the returned paper.');
     const csrf=await form.locator('[name=csrf_token]').inputValue();
     const response=await context.request.post(base+`/diagnostics/${createdExamId}/delete`,{form:{csrf_token:csrf}});
     await page.goto(base+'/diagnostics');deleted=response.ok()&&await form.count()===0;cleanupFallback=true;
    }else deleted=true;
   }catch(cleanupError){errors.push('Cleanup failed for own exam '+createdExamId+': '+cleanupError.message);}
  }
  save();await context?.close();await browser.close();
 }
 if(mainError||!deleted){console.error('Failed; own createdExamId='+createdExamId+', deleted='+deleted);process.exitCode=1;}
 else console.log(checks.length+' real diagnostic publish/delete checks passed; created paper '+createdExamId+' removed.');
})().catch(error=>{mainError=error;save();console.error(error);process.exitCode=1;});
