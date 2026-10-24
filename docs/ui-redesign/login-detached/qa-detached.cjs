const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const out=path.resolve('docs/ui-redesign/login-detached'),base='http://127.0.0.1:8771';
(async()=>{
 const checks=[],errors=[],assets=[],shots=[],browser=await chromium.launch({channel:'chrome',headless:true});
 const check=(name,condition)=>{assert(condition,name);checks.push(name);};
 try{
  const context=await browser.newContext({reducedMotion:'no-preference'}),page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400&&r.url().includes('/static/'))assets.push(r.url());});
  fs.mkdirSync(path.join(out,'screenshots'),{recursive:true});
  for(const width of [1440,1366,1024,768,375]){
   await page.setViewportSize({width,height:900});const response=await page.goto(base+'/login');check('Login200 @'+width,response.status()===200);
   await page.evaluate(async()=>{await document.fonts.ready;});const logo=page.locator('.auth-identity-logo'),name=page.locator('.auth-identity-name');
   check('Logo loaded @'+width,await logo.evaluate(n=>n.complete&&n.naturalWidth>0));check('Wordmark @'+width,await name.textContent()==='LMath');
   check('New title @'+width,(await page.title()).includes('LMath'));
   check('Exact tagline @'+width,await page.locator('.auth-identity-caption').textContent()==='Không gian học tập và giảng dạy');
   const brandLogo=await logo.boundingBox(),brandName=await name.boundingBox(),caption=await page.locator('.auth-identity-caption').boundingBox();
   check('Name beside logo @'+width,brandLogo.x+brandLogo.width<=brandName.x+1);
   check('Tagline below name @'+width,caption.y>=brandName.y+brandName.height&&Math.abs(caption.x-brandName.x)<1);
   check('No joined outer card @'+width,await page.locator('.auth-shell-login .auth-layout').evaluate(n=>{const s=getComputedStyle(n);return s.backgroundColor==='rgba(0, 0, 0, 0)'&&s.borderTopWidth==='0px';}));
   check('Left brand has no box @'+width,await page.locator('.auth-identity').evaluate(n=>{const s=getComputedStyle(n);return s.backgroundColor==='rgba(0, 0, 0, 0)'&&s.borderRightWidth==='0px'&&s.borderBottomWidth==='0px';}));
   check('Right form has own card @'+width,await page.locator('.auth-shell-login .auth-panel').evaluate(n=>{const s=getComputedStyle(n);return s.backgroundColor==='rgb(255, 255, 255)'&&s.borderTopWidth==='1px'&&s.borderTopLeftRadius==='12px';}));
   check('Identity visible @'+width,await logo.isVisible()&&await name.isVisible());
   check('Smooth animation @'+width,await logo.evaluate(n=>{const s=getComputedStyle(n);return s.animationName==='auth-logo-float'&&s.animationDuration==='5s'&&s.animationTimingFunction==='ease-in-out'&&s.animationIterationCount==='infinite';}));
   check('No horizontal overflow @'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   check('Readable form @'+width,await page.locator('#username').evaluate(n=>parseFloat(getComputedStyle(n).fontSize)>=16));
   const a=await page.locator('.auth-identity').boundingBox(),b=await page.locator('.auth-panel').boundingBox();
   check('Separated responsive placement @'+width,width>=1024?b.x-a.x-a.width>=63:b.y-a.y-a.height>=(width>=768?31:23));
   if(width>=1024)check('Larger laptop logo @'+width,(await logo.boundingBox()).width===192);
   await page.locator('[data-password-toggle]').click();check('Password show works @'+width,await page.locator('#password').getAttribute('type')==='text');await page.locator('[data-password-toggle]').click();
   await page.emulateMedia({reducedMotion:'reduce'});check('Reduced motion freezes logo @'+width,await logo.evaluate(n=>getComputedStyle(n).animationName==='none'&&getComputedStyle(n).transform==='none'));
   const file='screenshots/login-'+width+'.png';await page.screenshot({path:path.join(out,file),fullPage:true});shots.push(file);await page.emulateMedia({reducedMotion:'no-preference'});
  }
  await page.setViewportSize({width:1440,height:900});await page.goto(base+'/register');check('Registration context preserved',await page.locator('.auth-context-list li').count()===3);check('Registration retains joined card',await page.locator('.auth-shell-register .auth-layout').evaluate(n=>{const s=getComputedStyle(n);return s.backgroundColor==='rgb(255, 255, 255)'&&s.borderTopWidth==='1px'&&s.overflow==='hidden';}));check('Registration has no login animation',await page.locator('.auth-identity-logo').count()===0);
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:375,height:900}}),nojspage=await nojs.newPage();await nojspage.goto(base+'/login');check('No JS identity visible',await nojspage.locator('.auth-identity-logo').isVisible());check('No JS native submit available',await nojspage.locator('#login-form [type=submit]').isVisible());await nojs.close();
  await page.goto(base+'/login');await page.locator('#username').fill('qa_teacher');await page.locator('#password').fill('Academy123!');await page.locator('#login-form [type=submit]').click();await page.waitForURL(u=>u.pathname!=='/login');
  check('Dashboard title renamed',(await page.title()).includes('LMath'));check('Navigation brand renamed',await page.locator('.sidebar-brand-title').textContent()==='LMath');
  await page.goto(base+'/profile');check('Profile title renamed',(await page.title()).includes('LMath'));
  await page.goto(base+'/qa-brand-not-found');check('Error brand renamed',await page.locator('.error-brand-copy strong').textContent()==='LMath');
  check('Error footer renamed',(await page.locator('.error-footer').textContent()).includes('LMath'));
  check('No JS errors',errors.length===0);check('No broken assets',assets.length===0);
  fs.writeFileSync(path.join(out,'browser-qa.json'),JSON.stringify({status:'passed',checks:checks.length,passed:checks,errors,assets,shots},null,2));console.log(JSON.stringify({checks:checks.length,shots:shots.length}));
 }catch(error){fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:error.stack,checks,errors,assets},null,2));throw error;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
