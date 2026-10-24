const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs'); const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.PHASE5_PREVIEW_URL || 'http://127.0.0.1:8767', checks=[], errors=[], posts=[];
 const output=process.cwd()+'/docs/ui-redesign/phase-5';fs.mkdirSync(output+'/screenshots',{recursive:true});
 const check=(name,value,detail)=>{checks.push({name,passed:!!value,detail});assert.ok(value,name+' '+JSON.stringify(detail));};
 const browser=await chromium.launch({channel:'chrome',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.on('pageerror',err=>errors.push(err.message));page.on('request',req=>{if(req.method()==='POST')posts.push(new URL(req.url()).pathname)});
 await page.goto(base+'/login',{waitUntil:'networkidle'});await page.locator('[name=username]').fill('qa_teacher');await page.locator('[name=password]').fill('Academy123!');await Promise.all([page.waitForNavigation(),page.locator('[name=submit]').click()]);
 const fixture=await (await page.request.get(base+'/qa/fixture')).json();
 for(const width of [375,768,1024,1440]){
  await page.setViewportSize({width,height:1000});await page.goto(base+'/question-banks/import?session_id='+fixture.sessions.duplicates,{waitUntil:'networkidle'});
  await page.waitForFunction(()=>Alpine.$data(document.querySelector('.import-workspace')).step===3&&!Alpine.$data(document.querySelector('.import-workspace')).busy);
  check('workspace no horizontal overflow '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  const opener=page.getByRole('button',{name:'Đối chiếu câu này'}).filter({visible:true}).first();await opener.click();await page.waitForFunction(()=>document.getElementById('import-duplicate-dialog').open);
  check('native comparison dialog '+width,await page.locator('#import-duplicate-dialog').evaluate(el=>el.matches(':modal')));
  check('comparison focus contained '+width,await page.evaluate(()=>document.getElementById('import-duplicate-dialog').contains(document.activeElement)));
  check('both copies labeled '+width,await page.locator('#import-duplicate-dialog h4').allTextContents().then(v=>v.includes('Đang nhập')&&v.includes('Hiện có')));
  const geometry=await page.locator('#import-duplicate-dialog').evaluate(el=>({width:el.getBoundingClientRect().width,scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,columns:getComputedStyle(el.querySelector('.duplicate-pair')).gridTemplateColumns}));
  check('dialog no horizontal overflow '+width,geometry.scrollWidth<=geometry.clientWidth+1,geometry);
  check('mobile stack or desktop pair '+width,width<768?geometry.columns.trim().split(' ').length===1:geometry.columns.trim().split(' ').length===2,geometry);
  await page.keyboard.press('Shift+Tab');check('keyboard avoids background '+width,await page.evaluate(()=>document.activeElement===document.body||document.getElementById('import-duplicate-dialog').contains(document.activeElement)));await page.keyboard.press('Tab');check('keyboard returns to dialog '+width,await page.evaluate(()=>document.getElementById('import-duplicate-dialog').contains(document.activeElement)),await page.evaluate(()=>({active:document.activeElement.tagName,open:document.getElementById('import-duplicate-dialog').open})));
  if([375,1440].includes(width)){await page.evaluate(async()=>{await MathJax.startup.promise;await renderFormulas(document.querySelector('#import-duplicate-dialog'),undefined,{immediate:true})});await page.screenshot({path:output+'/screenshots/import-duplicates-'+width+'.png',fullPage:true});}
  await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.getElementById('import-duplicate-dialog').open);
  check('comparison model cleared '+width,await page.evaluate(()=>Alpine.$data(document.querySelector('.import-workspace')).comparisonUid===null));
  check('focus restored '+width,await opener.evaluate(el=>el===document.activeElement));
 }
 await page.locator('.import-destination summary').click();await page.locator('#duplicate-destination').selectOption('');await page.getByRole('button',{name:'Đổi đích và dò lại',exact:true}).first().click();
 check('destination change confirmation native',await page.locator('#import-destination-dialog').evaluate(el=>el.matches(':modal')));
 check('destination label scoped',await page.locator('.duplicate-new-destination').textContent().then(v=>v.includes('Ngân hàng mới')));
 await page.keyboard.press('Escape');check('readonly QA no data POST',posts.every(path=>path==='/login'),posts);check('no JavaScript errors',errors.length===0,errors);
 fs.writeFileSync(output+'/duplicates-qa.json',JSON.stringify({passed:checks.length,checks,errors,posts},null,2));console.log(JSON.stringify({passed:checks.length,errors,posts}));await browser.close();
})().catch(err=>{console.error(err);process.exitCode=1;});
