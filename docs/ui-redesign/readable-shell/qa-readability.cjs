const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base='http://127.0.0.1:8771',out=path.resolve('docs/ui-redesign/readable-shell');
fs.mkdirSync(path.join(out,'screenshots'),{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true}),checks=[],errors=[],assets=[],shots=[];
 const check=(name,ok,detail)=>{assert(ok,name+(detail?' '+JSON.stringify(detail):''));checks.push(name);};
 try{
  const context=await browser.newContext({locale:'vi-VN',reducedMotion:'reduce'}),page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400&&r.url().includes('/static/'))assets.push(r.url());});
  const f=await(await context.request.get(base+'/qa/fixture')).json();
  const login=async role=>{await page.goto(base+'/logout');await page.goto(base+'/login');await page.locator('[name=username]').fill('qa_'+role);await page.locator('[name=password]').fill('Academy123!');await page.locator('[type=submit]').click();await page.waitForURL(u=>u.pathname!=='/login');};
  const go=async route=>{const r=await page.goto(base+route);check('GET '+route,r.status()===200);await page.locator('body.has-ui-shell').waitFor();await page.evaluate(async()=>{await document.fonts.ready;});};
  for(const [width,height] of [[1440,900],[1440,568],[1024,768],[768,900],[375,667]]){
   await page.setViewportSize({width,height});
   for(const role of ['teacher','admin','student']){
    await login(role);await go(role==='teacher'?'/my-students':role==='admin'?'/users/teachers':'/practice?course_id='+f.courses.teacher);
    const sidebar=page.locator('#primary-navigation'),links=sidebar.locator('.nav-item');
    check(role+' preserves role menu @'+width+'x'+height,await links.count()===(role==='student'?4:10));
    check(role+' links permanently named @'+width,await links.evaluateAll(ns=>ns.every(n=>n.getAttribute('aria-label')?.trim())));
    check(role+' icons initialized @'+width,await links.locator('svg').count()===await links.count());
    check(role+' exactly one active destination @'+width,await sidebar.locator('[aria-current=page]').count()===1);
    check('Body text16',await page.locator('body').evaluate(n=>getComputedStyle(n).fontSize)==='16px');
    check('One UI font',await page.locator('body').evaluate(n=>getComputedStyle(n).fontFamily.includes('Be Vietnam Pro')));
    check('Local UI font loaded',await page.evaluate(()=>document.fonts.check('16px "Be Vietnam Pro"')));
    check(role+' no page overflow @'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    if(width>=1200){
     check('Desktop main frame rounded',await page.locator('.main-area').evaluate(n=>getComputedStyle(n).borderTopLeftRadius==='36px'));
     check('Desktop rail104px',Math.round(await sidebar.evaluate(n=>n.getBoundingClientRect().width))===104);
     check('Rail isblue',await sidebar.evaluate(n=>getComputedStyle(n).backgroundColor)==='rgb(30, 64, 175)');
     check('Active connectedcanvascolor',await sidebar.locator('.nav-item.active').evaluate(n=>getComputedStyle(n).backgroundColor===getComputedStyle(document.querySelector('.main-area')).backgroundColor));
     check('Active curvededges',await sidebar.locator('.nav-item.active').evaluate(n=>getComputedStyle(n,'::before').content!=='none'&&getComputedStyle(n,'::after').content!=='none'));
     check('Desktop labels visuallyhidden',await links.first().locator('.nav-item-label').evaluate(n=>getComputedStyle(n).position==='absolute'));
     const last=links.last();await last.focus();await page.waitForFunction(()=>!document.querySelector('.sidebar-tooltip').hidden);
     check('Keyboard labeltooltip',await page.locator('.sidebar-tooltip').textContent()===await last.getAttribute('aria-label'));
     check('Focused item visible in short rail',await last.evaluate(n=>{const a=n.getBoundingClientRect(),b=n.closest('.nav-section').getBoundingClientRect();return a.top>=b.top-1&&a.bottom<=b.bottom+1;}));
     check('Tooltip outside rail andonscreen',await page.locator('.sidebar-tooltip').evaluate(n=>{const r=n.getBoundingClientRect();return r.left>=104&&r.top>=0&&r.bottom<=innerHeight;}));
     await page.keyboard.press('Escape');check('Escape hides tooltip',await page.locator('.sidebar-tooltip').isHidden());
     await links.first().hover();check('Mouse labeltooltip',await page.locator('.sidebar-tooltip').isVisible());
    }else{
     check('Drawer initially closed',!await sidebar.isVisible());const trigger=page.locator('[data-sidebar-toggle]');await trigger.focus();await page.keyboard.press('Enter');
     check('Drawer expanded',await sidebar.getAttribute('aria-modal')==='true');check('Drawer haslabels',await links.first().locator('.nav-item-label').isVisible());
     check('Drawer hasbluepalette',await sidebar.evaluate(n=>getComputedStyle(n).backgroundColor)==='rgb(30, 64, 175)');
     check('Drawer focuscontained',await sidebar.evaluate(n=>n.contains(document.activeElement)));
     check('Drawer backgroundinert',await page.locator('.main-area').evaluate(n=>n.inert));
     await page.keyboard.press('Escape');check('Escape restores trigger',await trigger.evaluate(n=>n===document.activeElement));
     check('Background activeafterclose',!await page.locator('.main-area').evaluate(n=>n.inert));
     await trigger.click();await page.locator('.sidebar-scrim').click({position:{x:width-10,y:Math.round(height/2)}});check('Scrim dismisses drawer',!await sidebar.isVisible());
    }
    if(height!==568&&(width===1440||width===375)){
     await page.mouse.move(width-10,20);await page.locator('main').focus();
     if(width<1200)await page.locator('[data-sidebar-toggle]').click();
     await page.evaluate(async()=>{await document.fonts.ready;});const file=`screenshots/${role}-${width}.png`;await page.screenshot({path:path.join(out,file)});shots.push(file);
    }
   }
  }
  await page.setViewportSize({width:1440,height:900});await login('admin');
  for(const [route,label] of [[`/users/${f.users.student}/edit`,'Học sinh'],[`/users/${f.users.teacher}/edit`,'Giáo viên'],[`/question-banks/${f.banks.diagnostic}/classification/evaluation`,'Ngân hàng câu hỏi']]){await go(route);check('Correct active parent '+route,await page.locator('.nav-item[aria-current=page]').getAttribute('aria-label')===label);}
  await go('/profile');check('Profile footer selected',await page.locator('.sidebar-footer').getAttribute('aria-current')==='page');
  await page.locator('.sidebar-footer').focus();await page.setViewportSize({width:375,height:667});await page.waitForFunction(()=>document.querySelector('[data-sidebar-toggle]')===document.activeElement, null, {timeout:3000});check('Shrinking moves focus to trigger',await page.locator('[data-sidebar-toggle]').evaluate(n=>n===document.activeElement));
  await page.setViewportSize({width:1440,height:900});await page.waitForFunction(()=>document.querySelector('#primary-navigation').contains(document.activeElement), null, {timeout:3000});check('Expanding focuses visible destination',await page.locator('#primary-navigation').evaluate(n=>n.contains(document.activeElement)));
  await page.emulateMedia({media:'print'});check('Print hides rail',!await page.locator('#primary-navigation').isVisible());await page.emulateMedia({media:'screen'});
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:1440,height:900}}),npage=await nojs.newPage();await nojs.addCookies(await context.cookies());await npage.goto(base+'/courses');
  check('NoJS navigation hasvisiblelabels',await npage.locator('.nav-item-label').first().evaluate(n=>n.getBoundingClientRect().width>1));check('NoJS fallbackexpanded',Math.round(await npage.locator('.sidebar').evaluate(n=>n.getBoundingClientRect().width))===280);await nojs.close();

  await login('teacher');
  for(const width of [1440,1024,768,375]){
   await page.setViewportSize({width,height:900});
   for(const [key,route] of [['courses','/courses'],['bank','/question-banks/'+f.banks.general],['import','/question-banks/import?session_id='+f.sessions.general],['composer','/assessments/import/'+f.sessions['bank-paper']],['profile','/profile'],['settings','/teacher/ai-settings']]){
    await go(route);
    check(key+' no overflow @'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    const h1=page.locator('main h1').first();
    if(await h1.count())check(key+' readable page title @'+width,await h1.evaluate(n=>parseFloat(getComputedStyle(n).fontSize)>=26));
    const input=page.locator('main input[type=text]:visible,main input[type=search]:visible,main select:visible').first();
    if(await input.count())check(key+' readable inputs @'+width,await input.evaluate(n=>parseFloat(getComputedStyle(n).fontSize)>=16));
    if([1440,375].includes(width)){
     const file='screenshots/'+key+'-'+width+'.png';await page.screenshot({path:path.join(out,file)});shots.push(file);
    }
   }
  }
  check('No JS errors',errors.length===0,errors);check('No broken assets',assets.length===0,assets);
  fs.writeFileSync(path.join(out,'browser-qa.json'),JSON.stringify({status:'passed',checks:checks.length,passed:checks,errors,assets,shots},null,2));console.log(JSON.stringify({checks:checks.length,errors:errors.length,shots:shots.length}));
 }catch(error){fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:error.stack,checks,errors,assets},null,2));throw error;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
