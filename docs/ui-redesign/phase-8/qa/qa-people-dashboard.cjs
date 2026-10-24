/* Local synthetic preview only. Data writes other than authentication are intercepted. */
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.PHASE8_URL || 'http://127.0.0.1:8770';
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const out=path.resolve('docs/ui-redesign/phase-8'), checks=[], errors=[], assets=[], external=[], shots=[], intercepted=[];
const check=(name,valid)=>{ assert(valid,name); checks.push(name); };
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try {
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{ if(r.status()>=400&&r.url().includes('/static/'))assets.push(r.url()); });
  page.on('request',r=>{ if(['font','script','stylesheet'].includes(r.resourceType())&&!r.url().startsWith(base))external.push(r.url()); });
  const fixture=await(await context.request.get(base+'/qa/fixture')).json();
  await page.route('**/*',async route=>{const r=route.request();if(r.method()==='POST'&& !new URL(r.url()).pathname.endsWith('/login')){intercepted.push({url:new URL(r.url()).pathname,body:r.postData()});await route.fulfill({status:200,contentType:'text/html',body:'<p>QA intercepted request</p>'});}else await route.continue();});
  const login=async user=>{await page.goto(base+'/logout');await page.goto(base+'/login');await page.locator('[name=username]').fill(user);await page.locator('[name=password]').fill('Academy123!');await page.locator('[type=submit]').click();await page.waitForURL(u=>u.pathname!='/login');};
  const go=async(route,selector)=>{const r=await page.goto(base+route);check('GET '+route,r.status()===200);await page.locator(selector).waitFor();await page.evaluate(()=>document.fonts.ready);};
  const shot=async(name,fullPage=true)=>{await page.evaluate(()=>{scrollTo(0,0);document.activeElement?.blur();document.querySelectorAll('dialog,dialog .dialog-body').forEach(n=>n.scrollTop=0);});const file='screenshots/'+name+'.png';await page.screenshot({path:path.join(out,file),fullPage});shots.push(file);};
  const overflow=async name=>check(name+' no page overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  for(const [user,scope] of [['qa_admin','center'],['qa_teacher','teacher'],['qa_student','student'],['qa_empty_teacher','teacher'],['qa_no_course','student']]){
   await login(user);
   for(const width of [375,768,1024,1440]){
    await page.setViewportSize({width,height:1000});await go('/','.academy-dashboard');await overflow(user+' '+width);
    check(user+' real scope '+width,await page.locator('[data-dashboard-scope]').getAttribute('data-dashboard-scope')===scope);
    check(user+' exactly two KPIs '+width,await page.locator('.dashboard-metric').count()===2);
    check(user+' no large logo/hero '+width,await page.locator('main .welcome-banner, main .dashboard-logo').count()===0);
    if(user==='qa_empty_teacher'||user==='qa_no_course')check(user+' explicit empty activities '+width,await page.locator('.dashboard-empty').isVisible());
    if(user==='qa_student')check('Student shortcuts retain correct tasks '+width,await page.locator('.dashboard-shortcuts a[href="/practice"]').count()===1&&await page.locator('.dashboard-shortcuts a[href="/practice/progress"]').count()===1);
    if((width===375||width===1440)&&['qa_admin','qa_teacher','qa_student'].includes(user))await shot('dashboard-'+scope+'-'+width);
   }
  }
  await login('qa_teacher');
  for(const width of [375,768,1024,1440]){await page.setViewportSize({width,height:1000});await go('/my-students','.academy-people');await overflow('directory '+width);check('Teacher directory readonly '+width,await page.locator('main form,main button').count()===0);check('Directory contact labels '+width,(await page.locator('.people-table thead').textContent()).includes('Số điện thoại'));if(width===375||width===1440)await shot('people-my-students-'+width);}
  await login('qa_empty_teacher');await go('/my-students','.academy-people');check('Teacher empty directory',await page.locator('.people-empty').isVisible());await shot('people-my-students-empty');
  await login('qa_admin');
  for(const width of [375,768,1024,1440]){
   await page.setViewportSize({width,height:1000});
   for(const role of ['students','teachers']){
    await go('/users/'+role,'.academy-people');await overflow(role+' '+width);
    check('Correct role tab '+role+' '+width,await page.locator('.people-tabs [aria-current=page]').getAttribute('href')==='/users/'+role);
    if(width===375||width===1440)await shot('people-'+role+'-'+width);
    const opener=page.locator('.people-header [data-dialog-open]');await opener.click();
    check('Native dialog opens '+role+' '+width,await page.locator('#people-create-dialog').evaluate(n=>n.open&&n.matches(':modal')));
    check('Focus inside dialog '+role+' '+width,await page.locator('#people-create-dialog').evaluate(n=>n.contains(document.activeElement)));
    check('No unsupported admin role '+role+' '+width,await page.locator('#add_role option').evaluateAll(a=>a.map(n=>n.value).join(','))==='student,teacher');
    check('Initial role matches tab '+role+' '+width,await page.locator('#add_role').inputValue()===(role==='students'?'student':'teacher'));
    check('Native validation required '+role+' '+width,await page.locator('#people-create-dialog form').evaluate(n=>!n.checkValidity()));
    await page.locator('#add_position').fill('Giữ nguyên thông tin vị trí');await page.locator('#add_role').selectOption(role==='students'?'teacher':'student');
    check('Role changes preserve position '+role+' '+width,await page.locator('#add_position').inputValue()==='Giữ nguyên thông tin vị trí');
    await overflow('create-dialog '+role+' '+width);
    check('Dialog fits viewport '+role+' '+width,await page.locator('#people-create-dialog').evaluate(n=>{let r=n.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1;}));
    check('Dialog actions stay visible '+role+' '+width,await page.locator('#people-create-dialog .dialog-actions').evaluate(n=>{const r=n.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;}));
    if((width===375||width===1440)&&role==='students')await shot('people-create-dialog-'+width,false);
    await page.keyboard.press('Escape');check('Escape closes and restores focus '+role+' '+width,!await page.locator('#people-create-dialog').evaluate(n=>n.open)&&await opener.evaluate(n=>n===document.activeElement));
   }
   await go('/users/'+fixture.users.student+'/edit','.people-editor');await overflow('edit '+width);check('Reset separate from profile '+width,await page.locator('.people-edit-panel form').count()===1&&await page.locator('.people-password-panel form').count()===1);check('Edit native field contract '+width,await page.locator('.people-edit-panel [name=role],.people-edit-panel [name=user_code],.people-edit-panel [name=fullname],.people-edit-panel [name=username],.people-edit-panel [name=phone],.people-edit-panel [name=position],.people-edit-panel [name=is_active]').count()===7);if(width===375||width===1440)await shot('people-edit-student-'+width);
   await go('/users/'+fixture.users.admin+'/edit','.people-editor');await overflow('protected '+width);check('Admin protected readonly '+width,await page.locator('main form,main button[type=submit]').count()===0&&await page.locator('.people-profile-fields').evaluate(n=>n.disabled));if(width===375||width===1440)await shot('people-edit-protected-'+width);
  }
  for(const viewport of [{width:375,height:667},{width:667,height:375}]){await page.setViewportSize(viewport);await go('/users/students','.academy-people');await page.locator('.people-header [data-dialog-open]').click();check('Short viewport dialog actions '+viewport.width+'x'+viewport.height,await page.locator('#people-create-dialog .dialog-actions').evaluate(n=>{const r=n.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;}));await page.locator('#add_position').focus();check('Scrolled field focus remains inside dialog '+viewport.width+'x'+viewport.height,await page.locator('#add_position').evaluate(n=>{const r=n.getBoundingClientRect(),b=n.closest('.dialog-body').getBoundingClientRect();return r.top>=b.top-1&&r.bottom<=b.bottom+1;}));await page.keyboard.press('Escape');}
  await page.setViewportSize({width:1440,height:1000});
  await go('/users/students','.academy-people');let deleteForm=page.locator('[data-people-confirm]').first();let userName=await deleteForm.getAttribute('data-people-confirm');let seen='';page.once('dialog',async d=>{seen=d.message();await d.dismiss();});await deleteForm.locator('button').click();check('Delete cancel retains directory',await page.locator('.people-users-table').count()===1&&intercepted.length===0&&seen===userName);
  page.once('dialog',async d=>d.accept());await deleteForm.locator('button').click();await page.waitForLoadState();check('Confirmed delete retains POST CSRF',intercepted.length===1&&intercepted[0].url.endsWith('/delete')&&intercepted[0].body.includes('csrf_token='));
  await go('/users/'+fixture.users.student+'/edit','.people-editor');seen='';page.once('dialog',async d=>{seen=d.message();await d.dismiss();});await page.locator('.people-password-panel button').click();check('Reset cancel explains exact identity and default',seen.includes('qa_student')&&seen.includes('123456')&&intercepted.length===1);
  page.once('dialog',async d=>d.accept());await page.locator('.people-password-panel button').click();await page.waitForLoadState();check('Reset separate POST retains CSRF',intercepted.length===2&&intercepted[1].url.endsWith('/reset-password')&&intercepted[1].body.includes('csrf_token='));
  await go('/users/teachers','.academy-people');await page.locator('.people-header [data-dialog-open]').click();for(const [name,value]of Object.entries({user_code:'GVQA8',fullname:'Giáo viên QA',username:'qa_intercept',phone:'0900000000',position:'Toán lớp 12'}))await page.locator('#add_'+name).fill(value);await page.locator('#people-create-dialog button[type=submit]').click();await page.waitForLoadState();check('Create native POST preserves role fields and CSRF',intercepted.length===3&&intercepted[2].body.includes('role=teacher')&&intercepted[2].body.includes('csrf_token=')&&intercepted[2].body.includes('position='));
  await page.emulateMedia({reducedMotion:'reduce'});await go('/','.academy-dashboard');await overflow('Reduced motion dashboard');
  check('No JavaScript errors',errors.length===0);check('No missing local assets',assets.length===0);check('No external scripts fonts or CSS',external.length===0);
  fs.writeFileSync(path.join(out,'people-dashboard-qa.json'),JSON.stringify({status:'passed',checks:checks.length,details:checks,errors,assets,external,screenshots:shots,interceptedMutations:intercepted.map(x=>({url:x.url,csrf:x.body.includes('csrf_token=')})),note:'Only authentication writes reached isolated preview; create/delete/reset intercepted. Root integration tests cover real CRUD.'},null,2));
  fs.rmSync(path.join(out,'people-dashboard-failure.json'),{force:true});console.log(JSON.stringify({checks:checks.length,errors,screenshots:shots.length}));await context.close();
 }catch(error){fs.writeFileSync(path.join(out,'people-dashboard-failure.json'),JSON.stringify({checks,error:String(error),errors,assets},null,2));throw error;}finally{await browser.close();}
})();
