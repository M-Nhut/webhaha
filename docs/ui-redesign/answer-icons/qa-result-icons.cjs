/* Focused read-only answer-mark checks against the isolated memory-DB preview. */
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || '/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base = process.env.RESULT_ICON_QA_URL || 'http://127.0.0.1:8772';
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const out = __dirname, checks = [], errors = [], assets = [], external = [], metrics = [], shots = [];
const check = (label, value) => { assert(value, label); checks.push(label); };
(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    const context = await browser.newContext({locale:'vi-VN', reducedMotion:'reduce', viewport:{width:1440,height:1000}});
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => { if(response.url().startsWith(base+'/static/') && response.status()>=400) assets.push(response.url()); });
    page.on('request', request => { if(['script','font','stylesheet'].includes(request.resourceType()) && !request.url().startsWith(base)) external.push(request.url()); });
    const fixture = await (await context.request.get(base+'/qa/fixture')).json();
    const login = async role => {
      await page.goto(base+'/logout'); await page.goto(base+'/login');
      await page.locator('#username').fill('qa_'+role); await page.locator('#password').fill('Academy123!');
      await page.locator('#login-form [type=submit]').click(); await page.waitForURL(url=>url.pathname!=='/login');
    };
    const route = key => `${key==='multi_history'?'/practice/':'/assessments/'}${fixture.exams[key]}/result`;
    const go = async (key, teacher=false) => {
      const response = await page.goto(base+route(key)+(teacher?'?submission_id='+fixture.submissions[key]:''));
      check(`${key} ${teacher?'teacher':'student'} HTTP 200`,response.status()===200);
      await page.evaluate(async()=>{await document.fonts.ready;if(window.MathJax?.startup?.promise)await MathJax.startup.promise;});
      await page.locator('.result-answer-mark svg').first().waitFor();
    };
    const capture = async (name, node) => {
      const viewport=page.viewportSize(), box=await node.boundingBox();
      await page.setViewportSize({width:viewport.width,height:Math.max(viewport.height,Math.ceil(box.height+320))});
      await node.evaluate(n=>n.scrollIntoView({block:'start',behavior:'instant'})); await page.evaluate(()=>scrollBy(0,-32));
      const file='screenshots/'+name+'.png';
      await node.screenshot({path:path.join(out,file),style:'.topbar { visibility:hidden !important; }'});
      const after=await node.boundingBox();check(name+' capture fits viewport',after.y>=0&&after.y+after.height<=page.viewportSize().height+1);
      shots.push(file);await page.setViewportSize(viewport);
    };
    const inspect = async (label, key) => {
      const rows=await page.locator('.result-choice').evaluateAll(nodes=>nodes.map(n=>{
        const mark=n.querySelector('.result-answer-mark'), letter=n.querySelector('.result-choice-letter'), text=n.querySelector('.result-choice-text');
        const rect=n.getBoundingClientRect(), t=text.getBoundingClientRect(), m=mark?.getBoundingClientRect();
        const expected=n.classList.contains('is-key')?'is-correct':n.dataset.answerSelected==='true'?(n.closest('.result-question').classList.contains('is-ungraded')?'is-ungraded':'is-incorrect'):null;
        return {selected:n.dataset.answerSelected==='true',key:n.classList.contains('is-key'),expected,
          count:n.querySelectorAll('.result-answer-mark').length,markClass:mark?.className||'',name:mark?.getAttribute('aria-label')||'',role:mark?.getAttribute('role')||'',
          svg:mark?.querySelectorAll('svg').length||0,decorative:mark?.querySelector('svg')?.getAttribute('aria-hidden'),color:mark?getComputedStyle(mark).color:null,
          visibleText:n.innerText,letterSize:getComputedStyle(letter).width,font:getComputedStyle(text).fontFamily,fontSize:getComputedStyle(text).fontSize,
          rowRect:{left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom},textRight:t.right,
          markRect:m?{left:m.left,right:m.right,top:m.top,bottom:m.bottom}:null};
      }));
      metrics.push({name:label,rows});
      check(label+' expected one mark or none',rows.every(r=>r.count===(r.expected?1:0)));
      check(label+' expected correctness state',rows.every(r=>!r.expected||r.markClass.split(' ').includes(r.expected)));
      check(label+' accessible marks',rows.every(r=>!r.expected||(r.role==='img'&&r.name.length>0&&r.svg===1&&r.decorative==='true')));
      check(label+' no visible answer badges',rows.every(r=>!/(Bạn chọn|Học sinh chọn|Đáp án đúng)/.test(r.visibleText)));
      check(label+' answer font retained',rows.every(r=>r.font.includes('Be Vietnam Pro')&&r.fontSize==='20px'));
      check(label+' marks stay at right',rows.every(r=>!r.markRect||(r.markRect.left>=r.textRight-1&&r.markRect.right<=r.rowRect.right-10&&r.markRect.top>=r.rowRect.top&&r.markRect.bottom<=r.rowRect.bottom)));
      check(label+' no page overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      if(key==='graded') {
        check(label+' selected correct single check',rows.some(r=>r.selected&&r.key&&r.count===1&&r.markClass.includes('is-correct')&&r.name.includes('đã chọn')));
        check(label+' unselected key check',rows.some(r=>!r.selected&&r.key&&r.count===1&&r.name==='Đáp án đúng'));
        check(label+' selected wrong red X',rows.some(r=>r.selected&&!r.key&&r.markClass.includes('is-incorrect')&&r.name.includes('đáp án sai')));
        const good=rows.find(r=>r.markClass.includes('is-correct')),bad=rows.find(r=>r.markClass.includes('is-incorrect'));
        check(label+' correct and wrong distinct colors',good.color!==bad.color);
      }
      if(key==='history') {
        check(label+' history no wrong mark',rows.every(r=>!r.markClass.includes('is-incorrect')));
        check(label+' historical selected key is qualified',rows.filter(r=>r.selected&&r.key).every(r=>r.name.includes('Bài chưa chấm')));
      }
      return rows;
    };
    await login('student');
    for(const width of [375,768,1024,1440]) {
      await page.setViewportSize({width,height:1000});
      for(const key of ['graded','history','multi_history']) {
        await go(key);const label=key+'@'+width;
        await inspect(label,key);
        if(key==='graded') {
          await page.waitForFunction(()=>document.querySelector('.result-question-prompt mjx-container'));
          check(label+' MathJax retained',await page.locator('.result-question-prompt mjx-container').count()>0);
          if([375,1440].includes(width)) {
            await capture('correct-'+width,page.locator('.result-question').first());
            await capture('incorrect-'+width,page.locator('.result-question').last());
          }
        }
        if(key==='multi_history') check(label+' multiple keys each have a check',await page.locator('.result-question').first().locator('.is-key .result-answer-mark.is-correct').count()===2);
      }
    }
    await page.setViewportSize({width:1440,height:1000}); await go('graded');
    await page.emulateMedia({media:'print'});
    const printMarks=await page.locator('.result-answer-mark').evaluateAll(nodes=>nodes.map(n=>({display:getComputedStyle(n).display,svg:!!n.querySelector('svg'),width:getComputedStyle(n.querySelector('svg')).width,stroke:getComputedStyle(n.querySelector('svg')).stroke})));
    check('Print correctness marks remain visible',printMarks.length>0&&printMarks.every(m=>m.display!=='none'&&m.svg&&m.width==='28px'&&m.stroke!=='none'));
    await page.emulateMedia({media:'screen'});
    const nativeContext=await browser.newContext({javaScriptEnabled:false,viewport:{width:375,height:1000},locale:'vi-VN'});
    await nativeContext.addCookies(await context.cookies());const native=await nativeContext.newPage();
    await native.goto(base+route('graded'));
    const nativeMarks=await native.locator('.result-answer-mark').evaluateAll(nodes=>nodes.map(n=>({role:n.getAttribute('role'),name:n.getAttribute('aria-label'),svg:n.querySelectorAll('svg').length,display:getComputedStyle(n).display,stroke:getComputedStyle(n.querySelector('svg')).stroke})));
    check('No JS inline marks remain visible and accessible',nativeMarks.length>0&&nativeMarks.every(m=>m.svg===1&&m.role==='img'&&m.name&&m.display!=='none'&&m.stroke!=='none'));
    check('No JS has no badge labels',!/(Bạn chọn|Học sinh chọn|Đáp án đúng)/.test(await native.locator('.result-choices').allInnerTexts().then(t=>t.join('\n'))));
    await nativeContext.close();
    await login('teacher');await go('graded',true);
    check('Teacher selected answers have student accessible labels',await page.locator('.result-choice[data-answer-selected=true] .result-answer-mark').evaluateAll(nodes=>nodes.every(n=>n.getAttribute('aria-label').includes('Học sinh đã chọn'))));
    check('Teacher no visible selection badges',!/(Bạn chọn|Học sinh chọn|Đáp án đúng)/.test((await page.locator('.result-choices').allInnerTexts()).join('\n')));
    check('No browser errors',errors.length===0);check('No missing static assets',assets.length===0);check('No external scripts fonts styles',external.length===0);
    const report={status:'passed',checks:checks.length,passed:checks,metrics,printMarks,nativeMarks,errors,assets,external,shots,
      scope:'Read-only synthetic memory-DB result review. No answers or submissions changed.',
      separateCoverage:'The isolated history fixture contains no selected non-key MCQ; root runs that server-rendered branch in a separate memory Flask process.'};
    fs.writeFileSync(path.join(out,'browser-qa.json'),JSON.stringify(report,null,2));fs.rmSync(path.join(out,'failure.json'),{force:true});
    console.log(JSON.stringify({status:'passed',checks:checks.length,shots:shots.length}));
  } catch(error) { fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:error.stack,checks,errors,assets,metrics},null,2));throw error; }
  finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
