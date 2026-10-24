/* Verify the viewport frame using only the isolated, synthetic Phase 9 preview. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.FRAME_QA_URL||'http://127.0.0.1:8771',out=__dirname;
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const checks=[],errors=[],assets=[],pages=[],shots=[];
const check=(name,ok,details)=>{assert(ok,name+(details?' '+JSON.stringify(details):''));checks.push(name);};
(async()=>{
  fs.mkdirSync(path.join(out,'screenshots'),{recursive:true});
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try{
    const context=await browser.newContext({locale:'vi-VN',reducedMotion:'reduce',viewport:{width:1440,height:900}}),page=await context.newPage();
    page.on('pageerror',e=>errors.push(e.message));
    page.on('response',r=>{if(r.status()>=400&&r.url().includes('/static/'))assets.push(r.url());});
    page.on('dialog',d=>d.type()==='beforeunload'?d.accept():d.dismiss());
    const fixture=await(await context.request.get(base+'/qa/fixture')).json(),course=fixture.courses.teacher,student=fixture.users.student,bank=fixture.banks.diagnostic;
    const login=async role=>{
      await page.goto(base+'/logout');await page.goto(base+'/login');
      await page.locator('[name=username]').fill('qa_'+role);await page.locator('[name=password]').fill('Academy123!');
      await page.locator('[type=submit]').click();await page.waitForURL(u=>u.pathname!=='/login');
    };
    const go=async(route,name)=>{
      const r=await page.goto(base+route);check(name+' HTTP200',r.status()===200,{url:page.url(),status:r.status()});
      await page.locator('body.has-ui-shell').waitFor();await page.evaluate(async()=>{await document.fonts.ready;if(window.MathJax?.startup?.promise)await MathJax.startup.promise;});
      if(name==='import')await page.waitForFunction(()=>window.Alpine&&Alpine.$data(document.querySelector('.import-workspace')).step>=3&&!Alpine.$data(document.querySelector('.import-workspace')).busy);
      if(name.startsWith('ai-')&&name!=='ai-settings')await page.waitForFunction(()=>document.getElementById('ai-content')&&!document.getElementById('ai-content').hidden);
    };
    const geometry=()=>page.evaluate(()=>{
      const main=document.querySelector('.main-area'),header=document.querySelector('.topbar'),m=main.getBoundingClientRect(),h=header.getBoundingClientRect(),style=getComputedStyle(main);
      return{width:innerWidth,height:innerHeight,frame:parseFloat(getComputedStyle(document.body).getPropertyValue('--layout-frame')),left:m.left,right:m.right,top:m.top,bottom:m.bottom,mainHeight:m.height,headerTop:h.top,headerBottom:h.bottom,
        pageHeight:document.documentElement.scrollHeight,pageWidth:document.documentElement.scrollWidth,scrollX,scrollY,canvas:style.backgroundColor,blue:getComputedStyle(document.body).backgroundColor,radius:style.borderRadius,overflow:style.overflowY,
        contentWidth:main.scrollWidth,clientWidth:main.clientWidth,scroll:main.scrollTop,scrollHeight:main.scrollHeight,clientHeight:main.clientHeight};
    });
    const verify=async name=>{
      const g=await geometry(),left=g.width>=1200?104:g.frame;
      check(name+' fixed gray canvas bounds',Math.abs(g.top-g.frame)<1&&Math.abs(g.bottom-(g.height-g.frame))<1&&Math.abs(g.left-left)<1&&Math.abs(g.right-(g.width-g.frame))<1,g);
      check(name+' blue and gray palette',g.blue==='rgb(30, 64, 175)'&&g.canvas==='rgb(245, 247, 251)',g);
      check(name+' persistent nonzero frame',g.frame>0&&g.radius!=='0px');
      check(name+' outer document stays in viewport',g.pageHeight<=g.height+1&&g.pageWidth<=g.width+1&&g.scrollY===0&&g.scrollX===0,g);
      check(name+' canvas owns content overflow',g.overflow==='auto'&&g.contentWidth<=g.clientWidth+1,g);
      await page.locator('.main-area').evaluate(n=>n.scrollTop=n.scrollHeight/2);
      await page.waitForTimeout(30);const middle=await geometry();
      let lastHeight=-1,stable=0;
      for(let attempt=0;attempt<10&&stable<3;attempt++){
        const height=await page.locator('.main-area').evaluate(n=>{n.scrollTop=n.scrollHeight;return n.scrollHeight;});
        stable=height===lastHeight?stable+1:0;lastHeight=height;await page.waitForTimeout(80);
      }
      await page.locator('.main-area').evaluate(n=>n.scrollTop=n.scrollHeight);
      const bottom=await geometry();
      for(const [position,v]of [['middle',middle],['bottom',bottom]]){
        check(name+' frame remains visible at '+position,Math.abs(v.top-g.top)<1&&Math.abs(v.bottom-g.bottom)<1&&v.scrollY===0&&v.pageHeight<=v.height+1,v);
        check(name+' header remains inside canvas at '+position,Math.abs(v.headerTop-v.top)<1&&v.headerBottom<=v.bottom,v);
      }
      if(g.scrollHeight>g.clientHeight+1)check(name+' final content reachable',Math.abs(bottom.scroll+bottom.clientHeight-bottom.scrollHeight)<2,bottom);
      pages.push({name,width:g.width,frame:g.frame,scrollHeight:g.scrollHeight,clientHeight:g.clientHeight});
    };
    const shot=async name=>{const file='screenshots/'+name+'.png';await page.screenshot({path:path.join(out,file)});shots.push(file);};
    const sets=[['teacher',[
      ['dashboard','/'],['profile','/profile'],['banks','/question-banks'],['bank-form','/question-banks/new?mode=general'],['bank-detail',`/question-banks/${bank}`],
      ['bank-classification',`/question-banks/${bank}/classification`],['classification-evaluation',`/question-banks/${bank}/classification/evaluation`],['curriculum','/curriculum'],
      ['import',`/question-banks/import?session_id=${fixture.sessions.duplicates}`],['assessment-from-bank',`/assessments/from-bank?course_id=${course}&bank_ids=${fixture.banks.general}`],
      ['assessment-editor',`/assessments/import/${fixture.sessions.paper}`],['assessments','/assessments'],['matrix',`/assessments/${fixture.exams.editor}/matrix`],
      ['diagnostics','/diagnostics'],['teacher-list','/teacher/practice'],['teacher-detail',`/teacher/practice/${student}?course_id=${course}`],['practice-draft',`/teacher/practice/drafts/${fixture.exams.draft}`],
      ['courses','/courses'],['course-detail',`/courses/${course}`],['my-students','/my-students'],['ai-class-overview',`/ai-reports/class?course_id=${course}`],
      ['ai-individual-overview',`/ai-reports/individual?course_id=${course}&student_id=${student}`],['ai-class-detail',`/ai-reports/class?course_id=${course}&view=detail`],
      ['ai-individual-detail',`/ai-reports/individual?course_id=${course}&student_id=${student}&view=detail`],['ai-settings','/teacher/ai-settings']
    ]],['admin',[
      ['diagnostic-form','/diagnostics/new'],['course-form','/courses/new'],['users','/users/students'],['edit-user',`/users/${student}/edit`]
    ]],['student',[
      ['practice',`/practice?course_id=${course}`],['progress','/practice/progress?subject=Toán'],['result',`/assessments/${fixture.exams.standalone}/result`]
    ]]];
    for(const width of [375,768,1024,1440]){
      await page.setViewportSize({width,height:900});
      for(const [role,routes]of sets){
        await login(role);
        for(const [name,route]of routes){
          await go(route,name);await verify(name+'@'+width);
          if([375,1440].includes(width)&&['bank-detail','assessment-editor','result','ai-class-detail'].includes(name))await shot(name+'-bottom-'+width);
        }
        console.log(role+' @'+width+' complete');
      }
    }
    await login('teacher');
    for(const [width,height]of [[1440,568],[375,667],[844,390]]){
      await page.setViewportSize({width,height});await go('/question-banks/'+fixture.banks.general,'bank-interactions');
      const main=page.locator('.main-area');await main.evaluate(n=>n.scrollTop=0);
      await page.mouse.move(width-60,Math.min(height-60,300));await page.mouse.wheel(0,700);
      await page.waitForFunction(()=>document.querySelector('.main-area').scrollTop>0);
      check('Wheel scrolls inner canvas '+width+'x'+height,await main.evaluate(n=>n.scrollTop>0)&&await page.evaluate(()=>scrollY===0));
      await main.evaluate(n=>n.scrollTop=0);await page.locator('#main-content').focus();await page.keyboard.press('PageDown');
      await page.waitForFunction(()=>document.querySelector('.main-area').scrollTop>0);
      check('Keyboard scrolls inner canvas '+width+'x'+height,await page.evaluate(()=>scrollY===0));
      await main.evaluate(n=>n.scrollTop=0);
      const detail=page.locator('.bank-detail-toolbar button').first();await detail.click();await page.locator('.bank-answer-row').first().waitFor();
      await page.locator('.bank-answer-row').first().scrollIntoViewIfNeeded();
      await page.waitForFunction(()=>document.querySelector('.bank-answer-row mjx-container')||document.querySelector('.bank-question-prompt mjx-container'));
      check('Lazy math inside scroll canvas '+width+'x'+height,await page.locator('mjx-container').count()>0);
      await main.evaluate(n=>n.scrollTop=0);await page.locator('[data-add-question-open]').click();
      check('Native question dialog outside canvas clipping '+width+'x'+height,await page.locator('#add-question-modal').evaluate(n=>{const r=n.getBoundingClientRect();return n.open&&r.top>=0&&r.bottom<=innerHeight+1;}));
      await page.keyboard.press('Escape');
      if(width<1200){
        await page.locator('[data-sidebar-toggle]').click();check('Drawer keeps background inert '+width,await main.evaluate(n=>n.inert));
        check('Drawer focuses visible navigation '+width,await page.locator('.sidebar').evaluate(n=>n.contains(document.activeElement)));
        await page.keyboard.press('Escape');check('Drawer restores keyboard trigger '+width,await page.locator('[data-sidebar-toggle]').evaluate(n=>n===document.activeElement));
      }
      await verify('short-height '+width+'x'+height);await shot('short-height-'+width+'x'+height);
    }
    await page.setViewportSize({width:1440,height:900});await go('/question-banks/'+bank,'anchor');
    const card=page.locator('.bank-question-card').last();await card.evaluate(n=>n.scrollIntoView({block:'start'}));
    check('Anchor scroll stays within canvas',await page.evaluate(()=>scrollY===0)&&await card.evaluate(n=>{const r=n.getBoundingClientRect(),m=document.querySelector('.main-area').getBoundingClientRect();return r.top>=m.top&&r.top<m.bottom;}));
    await page.emulateMedia({media:'print'});
    check('Print restores full document flow',await page.locator('.main-area').evaluate(n=>getComputedStyle(n).overflowY==='visible')&&await page.locator('.app-shell').evaluate(n=>getComputedStyle(n).display==='block'));
    check('Print omits sidebar and blue frame',!await page.locator('.sidebar').isVisible()&&await page.locator('body').evaluate(n=>getComputedStyle(n).backgroundColor==='rgb(255, 255, 255)'));
    await page.emulateMedia({media:'screen'});
    const cookies=await context.cookies();
    for(const width of [375,1440]){
      const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width,height:900}});await nojs.addCookies(cookies);const native=await nojs.newPage();
      await native.goto(base+'/question-banks/'+fixture.banks.general);
      const g=await native.locator('.main-area').evaluate(n=>{const r=n.getBoundingClientRect();return{top:r.top,bottom:r.bottom,height:r.height,scrollHeight:n.scrollHeight,clientHeight:n.clientHeight,documentHeight:document.documentElement.scrollHeight};});
      check('No JS canvas remains bounded '+width,g.bottom<=901&&g.height>100&&g.documentHeight<=901,g);
      check('No JS navigation labels remain visible '+width,await native.locator('.nav-item-label').first().isVisible());
      await native.locator('.main-area').evaluate(n=>n.scrollTop=n.scrollHeight);
      check('No JS inner content reachable '+width,await native.locator('.main-area').evaluate(n=>Math.abs(n.scrollTop+n.clientHeight-n.scrollHeight)<2));
      await nojs.close();
    }
    const fallback=await browser.newContext({viewport:{width:1440,height:900}});await fallback.addCookies(cookies);
    await fallback.addInitScript(()=>delete window.IntersectionObserver);const fallbackPage=await fallback.newPage();await fallbackPage.goto(base+'/question-banks/'+fixture.banks.general);
    await fallbackPage.locator('body.has-ui-shell').waitFor();
    const prompt=fallbackPage.locator('#qcard-'+fixture.questions['general-long']+' .bank-question-prompt');await prompt.scrollIntoViewIfNeeded();
    await prompt.locator('mjx-container').first().waitFor();
    check('Math fallback follows inner scroll without IntersectionObserver',await prompt.locator('mjx-container').count()>0);await fallback.close();
    await login('resume');await page.goto(base+`/practice/${fixture.exams.resume}/take`);
    check('Focused exam keeps document scrolling',await page.locator('body.academy-exam-focus').count()===1&&await page.locator('.main-area').evaluate(n=>getComputedStyle(n).overflowY==='visible'));
    await page.goto(base+'/logout');await page.goto(base+'/login');
    check('Login remains outside framed shell',await page.locator('body.academy-shell').count()===0&&await page.locator('body').evaluate(n=>getComputedStyle(n).overflowY!=='hidden'));
    check('No JS errors',errors.length===0,errors);check('No missing static assets',assets.length===0,assets);
    fs.writeFileSync(path.join(out,'browser-qa.json'),JSON.stringify({status:'passed',base,checks:checks.length,passed:checks,pages,errors,assets,shots,scope:'UI-only changes and reads against synthetic memory database; no business writes.'},null,2));
    fs.rmSync(path.join(out,'failure.json'),{force:true});console.log(JSON.stringify({status:'passed',checks:checks.length,pages:pages.length,shots:shots.length}));
  }catch(error){fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:error.stack,checks,errors,assets,pages},null,2));throw error;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
