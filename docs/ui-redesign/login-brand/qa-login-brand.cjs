const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const out=path.resolve('docs/ui-redesign/login-brand'),base='http://127.0.0.1:8771';
(async()=>{
 const checks=[],errors=[],assets=[],shots=[],browser=await chromium.launch({channel:'chrome',headless:true});
 const check=(name,condition)=>{assert(condition,name);checks.push(name);};
 try{
  const context=await browser.newContext({reducedMotion:'no-preference'}),page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400&&r.url().includes('/static/'))assets.push(r.url());});
  fs.mkdirSync(path.join(out,'screenshots'),{recursive:true});
  for(const width of [1440,1024,768,375]){
   await page.setViewportSize({width,height:900});const response=await page.goto(base+'/login');check('Login200 @'+width,response.status()===200);
   await page.evaluate(async()=>{await document.fonts.ready;});const logo=page.locator('.auth-identity-logo'),name=page.locator('.auth-identity-name');
   check('Logo loaded @'+width,await logo.evaluate(n=>n.complete&&n.naturalWidth>0));check('Wordmark @'+width,await name.textContent()==='LinhEdu');
   check('Identity visible @'+width,await logo.isVisible()&&await name.isVisible());
   check('Smooth animation @'+width,await logo.evaluate(n=>{const s=getComputedStyle(n);return s.animationName==='auth-logo-float'&&s.animationDuration==='5s'&&s.animationTimingFunction==='ease-in-out'&&s.animationIterationCount==='infinite';}));
   check('No horizontal overflow @'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   check('Readable form @'+width,await page.locator('#username').evaluate(n=>parseFloat(getComputedStyle(n).fontSize)>=16));
   const a=await page.locator('.auth-identity').boundingBox(),b=await page.locator('.auth-panel').boundingBox();
   check('Responsive placement @'+width,width>=1024?a.x+a.width<=b.x+1:a.y+a.height<=b.y+1);
   if(width>=1024)check('Large logo @'+width,(await logo.boundingBox()).width>=220);
   await page.locator('[data-password-toggle]').click();check('Password show works @'+width,await page.locator('#password').getAttribute('type')==='text');await page.locator('[data-password-toggle]').click();
   await page.emulateMedia({reducedMotion:'reduce'});check('Reduced motion freezes logo @'+width,await logo.evaluate(n=>getComputedStyle(n).animationName==='none'&&getComputedStyle(n).transform==='none'));
   const file='screenshots/login-'+width+'.png';await page.screenshot({path:path.join(out,file),fullPage:true});shots.push(file);await page.emulateMedia({reducedMotion:'no-preference'});
  }
  await page.setViewportSize({width:1440,height:900});await page.goto(base+'/register');check('Registration context preserved',await page.locator('.auth-context-list li').count()===3);check('Registration has no login animation',await page.locator('.auth-identity-logo').count()===0);
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:375,height:900}}),nojspage=await nojs.newPage();await nojspage.goto(base+'/login');check('No JS identity visible',await nojspage.locator('.auth-identity-logo').isVisible());check('No JS native submit available',await nojspage.locator('#login-form [type=submit]').isVisible());await nojs.close();
  check('No JS errors',errors.length===0);check('No broken assets',assets.length===0);
  fs.writeFileSync(path.join(out,'browser-qa.json'),JSON.stringify({status:'passed',checks:checks.length,passed:checks,errors,assets,shots},null,2));console.log(JSON.stringify({checks:checks.length,shots:shots.length}));
 }catch(error){fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:error.stack,checks,errors,assets},null,2));throw error;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
