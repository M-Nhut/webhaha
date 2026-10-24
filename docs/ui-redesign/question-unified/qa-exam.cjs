/* Read-only UI checks against the isolated synthetic Phase 6 preview. */
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.QUESTION_QA_URL || 'http://127.0.0.1:8772';
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const out = __dirname, checks = [], errors = [], assets = [], external = [], shots = [], metrics = [];
const check = (name, value) => { assert(value, name); checks.push(name); };
(async () => {
  fs.mkdirSync(path.join(out, 'screenshots'), {recursive:true});
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    const context = await browser.newContext({locale:'vi-VN', reducedMotion:'reduce', viewport:{width:1440,height:1000}});
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(e.message));
    page.on('response', r => { if(r.status() >= 400 && r.url().includes('/static/')) assets.push(r.url()); });
    page.on('request', r => { if(['font','script','stylesheet'].includes(r.resourceType()) && !r.url().startsWith(base)) external.push(r.url()); });
    page.on('dialog', d => d.type() === 'beforeunload' ? d.accept() : d.dismiss());
    const fixture = await (await context.request.get(base+'/qa/fixture')).json();
    const login = async role => {
      await page.goto(base+'/logout'); await page.goto(base+'/login');
      await page.locator('#username').fill('qa_'+role); await page.locator('#password').fill('Academy123!');
      await page.locator('#login-form [type=submit]').click(); await page.waitForURL(u=>u.pathname!=='/login');
    };
    const endpoint = (key, action) => `/${['fixed','diagnostic','legacy','multi_history'].includes(key)?'practice':'assessments'}/${fixture.exams[key]}/${action}`;
    const go = async route => {
      const response = await page.goto(base+route); check('HTTP 200 '+route,response.status()===200);
      await page.evaluate(async()=>{await document.fonts.ready; if(window.MathJax?.startup?.promise) await MathJax.startup.promise;});
    };
    const shot = async (name, node) => {
      const viewport=page.viewportSize(),bounds=await node.boundingBox();
      await page.setViewportSize({width:viewport.width,height:Math.max(viewport.height,Math.ceil(bounds.height+160))});
      const file='screenshots/'+name+'.png';
      await node.screenshot({path:path.join(out,file),style:'.topbar,.skip-link{visibility:hidden!important}'});
      shots.push(file); await page.setViewportSize(viewport);
    };
    const inspect = async (name, card, option, letter, text) => {
      const data = await card.evaluate((n, arg)=>{
        const c=getComputedStyle(n), opt=n.querySelector(arg.option), l=n.querySelector(arg.letter), t=n.querySelector(arg.text);
        return {cardRadius:c.borderRadius, cardShadow:c.boxShadow, optionRadius:getComputedStyle(opt).borderRadius,
          optionShadow:getComputedStyle(opt).boxShadow, optionBorder:getComputedStyle(opt).borderTopWidth,
          letterWidth:getComputedStyle(l).width, letterRadius:getComputedStyle(l).borderRadius,
          font:getComputedStyle(t).fontFamily,fontSize:getComputedStyle(t).fontSize};
      },{option,letter,text});
      metrics.push({name,...data});
      check(name+' shared surface',data.cardRadius==='28px'&&data.cardShadow!=='none');
      check(name+' shared answer',data.optionRadius==='22px'&&data.optionShadow!=='none'&&data.optionBorder==='2px');
      check(name+' shared circular letter',data.letterRadius==='999px'&&data.letterWidth===(page.viewportSize().width<768?'38px':'44px'));
      check(name+' shared readable typography',data.font.includes('Be Vietnam Pro')&&data.fontSize==='20px');
      check(name+' no page overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    };
    await login('student');
    for(const width of [375,768,1024,1440]) {
      await page.setViewportSize({width,height:1000});
      for(const key of ['fixed','diagnostic','legacy']) {
        await go(endpoint(key,'take'));
        await page.waitForFunction(()=>document.querySelector('[data-question-id]')?.dataset.answerState==='blank');
        const name=`take-${key}@${width}`, card=page.locator('.taking-question').first();
        check(name+' removed end links',await page.getByRole('link',{name:/Đến cuối bài/}).count()===0&&await page.locator('.taking-review-link').count()===0);
        check(name+' bottom submit retained',await page.locator('#taking-end [data-taking-submit]').count()===1);
        check(name+' all questions retained',await page.locator('.taking-question').count()===fixture.questions_by_exam[key].length);
        await inspect(name,card,'.taking-answer-choice','.question-letter','.question-reading');
        const choice=card.locator('.taking-answer-choice').first(); await choice.click();
        check(name+' native mouse answer',await choice.locator('input').isChecked());
        await choice.locator('input').focus(); await page.keyboard.press('ArrowDown');
        check(name+' native keyboard answer',await card.locator('input[type=radio]').nth(1).isChecked());
        check(name+' visible keyboard focus',await card.locator('.taking-answer-choice').nth(1).evaluate(n=>getComputedStyle(n).outlineWidth==='3px'));
        const truth=page.locator('.taking-question[data-question-type=true_false]').first();
        await inspect(name+' true-false',truth,'.taking-truth-item','.question-letter','.question-option-text');
        await truth.locator('.taking-truth-choices input').first().check();
        await page.waitForFunction(id=>document.querySelector('[data-question-id="'+id+'"]').dataset.answerState==='partial',await truth.getAttribute('data-question-id'));
        check(name+' true-false partial retained',await truth.getAttribute('data-answer-state')==='partial');
        const short=page.locator('.taking-short-answer textarea').first();
        check(name+' short answer shared border',await short.evaluate(n=>{const s=getComputedStyle(n);return s.borderRadius==='22px'&&s.fontSize==='20px'&&s.borderTopWidth==='2px';}));
        await short.fill('5'); await short.fill('');
        check(name+' short answer blank restored',await short.evaluate(n=>n.closest('.taking-question').dataset.answerState==='blank'));
        if([375,1440].includes(width)&&key==='fixed') {
          await shot('take-selected-'+width,card); await shot('take-truth-'+width,truth);
          await shot('take-short-'+width,page.locator('.taking-question[data-question-type=short_answer]').first());
        }
      }
      for(const key of ['graded','history','multi_history']) {
        await go(endpoint(key,'result'));
        const name=`review-${key}@${width}`, card=page.locator('.result-question').first();
        await inspect(name,card,'.result-choice','.question-letter','.question-reading');
        check(name+' selected accessible icon retained',await card.locator('[data-answer-selected=true] .result-answer-mark[aria-label]').count()>0);
        check(name+' correct answer icon retained',await card.getByRole('img',{name:/Đáp án đúng/}).count()>0);
        const truth=page.locator('.result-question').filter({has:page.locator('.result-truth-table')}).first();
        await inspect(name+' true-false',truth,'.result-truth-row','.question-letter','.question-option-text');
        check(name+' truth table semantics',await truth.getByRole('table').count()===1&&await truth.getByRole('cell').count()===16);
        check(name+' short answers share shape',await page.locator('.result-text-answers .question-answer-box').first().evaluate(n=>getComputedStyle(n).borderRadius==='22px'));
        if(key==='graded') {
          for(const state of ['correct','partial','blank','incorrect']) check(name+' status '+state,await page.locator('.result-question.is-'+state).count()>0);
          const answerText=await truth.locator('.result-truth-row').first().innerText();
          const comparisonLabels=width<768
            ? await truth.locator('.result-mobile-label').filter({hasText:'Bạn trả lời'}).first().isVisible()&&await truth.locator('.result-mobile-label').filter({hasText:'Đáp án'}).first().isVisible()
            : await truth.getByRole('columnheader',{name:'Bạn trả lời'}).count()===1&&await truth.getByRole('columnheader',{name:'Đáp án',exact:true}).count()===1;
          check(name+' selected vs key remain visible',answerText.includes('Đúng')&&comparisonLabels);
          if([375,1440].includes(width)) {
            await shot('review-choice-'+width,card); await shot('review-truth-'+width,truth);
            await shot('review-short-'+width,page.locator('.result-question').filter({has:page.locator('.result-text-answers')}).first());
            await card.locator('summary').click(); check(name+' solution shared panel',await card.locator('.question-solution').isVisible());
            await shot('review-solution-'+width,card);
          }
        }
        if(key==='history') check(name+' ungraded preserved',await page.locator('.result-question.is-ungraded').count()>0);
      }
    }
    await page.setViewportSize({width:1440,height:1000}); await go(endpoint('fixed','take'));
    await page.locator('.taking-answer-choice').first().click(); await page.locator('[data-taking-submit]').last().click();
    await page.locator('#exam-submit-dialog[open]').waitFor(); check('Submit confirmation retained',await page.locator('[data-confirm-blank]').textContent()!=='0');
    await page.keyboard.press('Escape');check('Escape returns to answer form',!await page.locator('#exam-submit-dialog').evaluate(n=>n.open));
    await page.emulateMedia({media:'print'});
    check('Taking print removes question and answer shadows',await page.locator('.taking-question').first().evaluate(n=>getComputedStyle(n).boxShadow==='none')&&await page.locator('.taking-answer-choice').first().evaluate(n=>getComputedStyle(n).boxShadow==='none'));
    check('Selected answer letter prints dark',await page.locator('.taking-answer-letter').first().evaluate(n=>getComputedStyle(n).color==='rgb(15, 23, 42)'));
    await page.emulateMedia({media:'screen'});
    const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:375,height:1000}});await nojs.addCookies(await context.cookies());
    const native=await nojs.newPage();await native.goto(base+endpoint('fixed','take'));await native.locator('.taking-answer-choice').first().click();
    check('No JS native selection retained',await native.locator('.taking-answer-choice input').first().isChecked());await nojs.close();
    await go(endpoint('graded','result'));await page.emulateMedia({media:'print'});
    check('Review print removes answer shadows',await page.locator('.result-choice').first().evaluate(n=>getComputedStyle(n).boxShadow==='none'));
    check('Review key letter prints dark',await page.locator('.result-choice.is-key .question-letter').first().evaluate(n=>getComputedStyle(n).color==='rgb(15, 23, 42)'));
    await page.emulateMedia({media:'screen'});
    await login('teacher');await go(endpoint('graded','result')+'?submission_id='+fixture.submissions.graded);
    check('Teacher accessible student selection',await page.locator('[data-answer-selected=true] .result-answer-mark').first().getAttribute('aria-label').then(s=>s.includes('Học sinh đã chọn')));
    check('Teacher review uses shared surface',await page.locator('.result-question.question-surface').count()===4);
    check('No browser errors',errors.length===0);check('No broken static assets',assets.length===0);check('No external scripts fonts styles',external.length===0);
    fs.writeFileSync(path.join(out,'browser-exam.json'),JSON.stringify({status:'passed',checks:checks.length,passed:checks,metrics,errors,assets,external,shots,scope:'Synthetic memory DB; UI-only authentication and answer previews, no submission.'},null,2));
    fs.rmSync(path.join(out,'exam-failure.json'),{force:true}); console.log(JSON.stringify({status:'passed',checks:checks.length,shots:shots.length}));
  } catch(error) {
    fs.writeFileSync(path.join(out,'exam-failure.json'),JSON.stringify({error:error.stack,checks,errors,assets},null,2));throw error;
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
