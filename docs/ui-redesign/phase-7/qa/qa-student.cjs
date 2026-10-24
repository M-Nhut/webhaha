/* Safe Phase 7 student QA. Synthetic localhost only, no learning-data POSTs. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.PHASE7_URL || 'http://127.0.0.1:8769';
assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const out = path.resolve('docs/ui-redesign/phase-7');
const checks = [], errors = [], assets = [], external = [], posts = [];
const check = (label, pass) => { assert(pass, label); checks.push(label); };
(async () => {
 const browser = await chromium.launch({channel:'chrome',headless:true});
 try {
  const api = await browser.newContext();
  const fixture = await (await api.request.get(base+'/qa/fixture')).json();
  await api.close();
  const states = { cold:'diagnostic', no_course:null, no_diagnostic:'diagnostic', start:'generate', resume:'resume', pending:'decision', blocked:'source-unavailable', student:'resume', one_point:'generate', declining:'generate', stable:'generate' };
  for (const [key, state] of Object.entries(states)) {
   const context = await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
   const page = await context.newPage();
   page.on('pageerror', e=>errors.push(e.message));
   page.on('response', r=>{if(r.url().includes('/static/')&&r.status()>=400) assets.push(r.url());});
   page.on('request', r=>{if(['font','script','stylesheet'].includes(r.resourceType())&&!r.url().startsWith(base))external.push(r.url());});
   await page.goto(base+'/login');
   await page.locator('#username').fill('qa_'+key);await page.locator('#password').fill('Academy123!');
   await page.locator('#login-form [type=submit]').click();await page.waitForURL(url=>url.pathname!=='/login');
   await page.route('**/*', route=>{
    const request=route.request();if(request.method()!=='GET'&&!request.url().includes('/api/formulas/batch')){posts.push(request.url());return route.abort();}return route.continue();
   });
   const course = ['no_diagnostic','blocked'].includes(key)?fixture.courses[key]:fixture.courses.teacher;
   const home = '/practice'+(key==='no_course'?'':'?course_id='+course);
   const response = await page.goto(base+home);
   check(key+' home HTTP200',response.status()===200);
   await page.locator('.student-practice-home').waitFor();
   if(state){
    check(key+' correct next state',await page.locator('[data-practice-next]').getAttribute('data-practice-next')===state);
    check(key+' only one main next action',await page.locator('.student-next-actions .btn-primary').count()===1);
    if(key==='no_diagnostic'||key==='blocked')check(key+' unavailable disabled',await page.locator('.student-next-actions .btn-primary').isDisabled());
    else check(key+' next action available',await page.locator('.student-next-actions .btn-primary').isEnabled());
    check(key+' course GET with labeled control',await page.locator('.student-context-form').getAttribute('method')==='GET'&&await page.getByLabel('Chọn lớp học').count()===1);
    if(state==='generate')check(key+' generate CSRF and course POST',await page.locator('form[action="/practice/generate"][method="POST"] input[name="csrf_token"]').count()===1&&await page.locator('form[action="/practice/generate"] input[name="course_id"]').inputValue()===String(course));
    if(state==='resume')check('resume honest unsaved answers', (await page.locator('.student-next-copy').innerText()).includes('Đáp án chưa nộp không được lưu'));
    if(state==='decision')check('pending result link',(await page.locator('.student-next-actions a').getAttribute('href')).includes('/result'));
    if(key==='cold')check('no fabricated profile before diagnostic',await page.locator('.student-evidence').count()===0);
    if(key==='blocked'){await page.locator('.student-source-reason summary').click();check('source reason disclosure',await page.locator('.student-source-reason').getAttribute('open')!==null);}
    if(key==='student')check('teacher assigned paper present',await page.locator('.student-assigned-list li').count()>=1);
   }else check('no course explanatory state',await page.locator('.student-empty').isVisible());
   if(key==='student'){await page.locator('.student-evidence > summary').click();check('home evidence matrix expands',await page.locator('.student-evidence').getAttribute('open')!==null&&await page.locator('.knowledge-matrix-table tbody tr').count()===8);}
   for(const width of [375,768,1024,1440]){
    await page.setViewportSize({width,height:1000});
    check(key+' home no horizontal overflow '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    if(key==='student')check('home matrix local scroll '+width,await page.locator('.knowledge-matrix-scroll').evaluate(el=>el.scrollWidth>=el.clientWidth&&getComputedStyle(el).overflowX==='auto'));
    if([375,1440].includes(width)&&['student','cold','resume','pending','blocked'].includes(key)){
     await page.evaluate(async()=>{await document.fonts.ready;document.activeElement?.blur();scrollTo(0,0);});
     await page.screenshot({path:path.join(out,'screenshots','student-home-'+key+'-'+width+'.png'),fullPage:true});
    }
   }
   const progress=await page.goto(base+'/practice/progress?subject='+encodeURIComponent('Toán'));
   check(key+' progress HTTP200',progress.status()===200);await page.locator('.student-progress').waitFor();
   await page.waitForTimeout(200);
   const config=await page.locator('#practice-progress-data').textContent().then(JSON.parse);
   const chartData=await page.evaluate(()=>['scoreChart','masteryChart','accuracyChart'].map(id=>{
    const canvas=document.getElementById(id);const chart=canvas&&window.Chart?.getChart(canvas);return{id,exists:!!chart,values:chart?.data.datasets[0].data,max:chart?.options.scales.y.max,animation:chart?.options.animation,showLine:chart?.data.datasets[0].showLine};
   }));
   const score=chartData.find(c=>c.id==='scoreChart'),mastery=chartData.find(c=>c.id==='masteryChart'),accuracy=chartData.find(c=>c.id==='accuracyChart');
   check(key+' subject GET only',await page.locator('.student-context-form').getAttribute('method')==='GET');
   if(score.exists){check(key+' score axis10',score.max===10);check(key+' score observed unchanged',JSON.stringify(score.values)===JSON.stringify(config.history.map(h=>typeof h.score==='number'&&h.score>=0&&h.score<=10?h.score:null)));check(key+' reduced motion score disabled',score.animation===false);}
   if(mastery.exists){check(key+' mastery axis1',mastery.max===1);check(key+' mastery percentage conversion',JSON.stringify(mastery.values)===JSON.stringify(config.masteryHistory.map(h=>typeof h.mastery==='number'&&h.mastery>=0&&h.mastery<=100?h.mastery/100:null)));}
   if(accuracy.exists){check(key+' cognitive axis100',accuracy.max===100);check(key+' cognitive gaps preserved',JSON.stringify(accuracy.values)===JSON.stringify(['nhan_biet','thong_hieu','van_dung','van_dung_cao'].map(level=>{const item=config.cognitiveMastery[level];return item&&item.sample_count>0&&typeof item.mastery==='number'?item.mastery*100:null;})));}
   if(['cold','no_course','no_diagnostic'].includes(key)){check(key+' cold neutral summary',(await page.locator('.student-kpis').innerText()).includes('Chưa có dữ liệu'));check(key+' no fake fallback chart',!score.exists&&!mastery.exists&&!accuracy.exists);check(key+' unknown levels readable',await page.locator('.student-unknown').count()===4);}
   if(key==='student'){
    check('ungraded record remains null',config.history.some(h=>h.score===null));
    check('ungraded visible in history',(await page.locator('.student-history').innerText()).includes('Chưa chấm'));
    check('missing snapshot remains gap',config.masteryHistory.some(h=>h.mastery===null)&&mastery.values.includes(null));
    check('separate results links',await page.locator('.student-history a[href*="/assessments/"]').count()>=1&&await page.locator('.student-history a[href*="/practice/"]').count()>=1);
    check('score improving label',(await page.locator('.student-kpi-trend').innerText()).includes('Đang tiến bộ'));
    check('score and mastery never combined',await page.evaluate(()=>window.Chart.getChart(document.getElementById('scoreChart')).data.datasets.length===1&&window.Chart.getChart(document.getElementById('masteryChart')).data.datasets.length===1));
   }
   if(key==='one_point')check('one score no fabricated trend',score.exists&&score.showLine===false&&(await page.locator('.student-kpi-trend').innerText()).includes('Chưa đủ dữ liệu'));
   if(key==='declining')check('declining label',(await page.locator('.student-kpi-trend').innerText()).includes('Đang giảm'));
   if(key==='stable')check('stable label',(await page.locator('.student-kpi-trend').innerText()).includes('Ổn định'));
   for(const width of [375,768,1024,1440]){
    await page.setViewportSize({width,height:1000});
    check(key+' progress no horizontal overflow '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    if(key==='student')check('progress matrix local scroll '+width,await page.locator('.knowledge-matrix-scroll').evaluate(el=>el.scrollWidth>=el.clientWidth&&getComputedStyle(el).overflowX==='auto'));
    if([375,1440].includes(width)&&['student','cold','one_point','declining'].includes(key)){
     await page.evaluate(async()=>{await document.fonts.ready;document.activeElement?.blur();scrollTo(0,0);});
     await page.screenshot({path:path.join(out,'screenshots','student-progress-'+key+'-'+width+'.png'),fullPage:true});
    }
   }
   if(key==='student'){
    const disclosure=page.locator('.student-chart-data').first();await disclosure.locator('summary').click();
    check('mastery equivalent table accessible',await disclosure.getAttribute('open')!==null&&await disclosure.locator('table tbody tr').count()===config.masteryHistory.length);
    await page.route('**/vendor/chartjs/chart.umd.js*',route=>route.abort());
    await page.reload();await page.waitForTimeout(200);
    check('chart load failure keeps data tables',await page.locator('[data-chart-fallback]:visible').count()===3&&await page.locator('.student-history table').count()===1);
    await page.selectOption('#progress-subject','Tiếng Anh');await page.locator('.student-context-form [type=submit]').click();await page.waitForURL(url=>url.searchParams.get('subject')==='Tiếng Anh');
    check('subject GET changes context',await page.locator('#progress-context-title').innerText()==='Tiếng Anh');
    check('subject without evidence stays neutral',await page.locator('#scoreChart').count()===0&&(await page.locator('.student-kpis').innerText()).includes('Chưa có dữ liệu'));
   }
   await context.close();
  }
  check('no JS errors',errors.length===0);check('no missing static assets',assets.length===0);check('only local scripts fonts CSS',external.length===0);check('no learning-data POSTs',posts.length===0);
  fs.writeFileSync(path.join(out,'student-browser-qa.json'),JSON.stringify({checks:checks.length,passed:checks,errors,assets,external,posts,viewports:[375,768,1024,1440],contexts:Object.keys(states),reducedMotion:true},null,2)+'\n');
  fs.rmSync(path.join(out,'student-browser-failure.json'),{force:true});
  process.stdout.write(JSON.stringify({checks:checks.length,errors,assets,external,posts})+'\n');
 }catch(error){fs.writeFileSync(path.join(out,'student-browser-failure.json'),JSON.stringify({message:error.message,stack:error.stack,checks,errors,assets,external,posts},null,2));throw error;}
 finally{await browser.close();}
})();
