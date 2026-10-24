/* Only synthetic image transport and print UI state change; no result POSTs. */
const assert=require('node:assert/strict'); const fs=require('node:fs'); const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base=process.env.PHASE6_URL || 'http://127.0.0.1:8768'; assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const checks=[];const check=(name,value)=>{assert(value,name);checks.push(name);};
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
  const context=await browser.newContext({viewport:{width:375,height:900}});const page=await context.newPage();
  const fixture=await(await context.request.get(base+'/qa/fixture')).json();
  await page.goto(base+'/login');await page.locator('#username').fill('qa_student');await page.locator('#password').fill('Academy123!');await page.locator('#login-form [type=submit]').click();await page.waitForURL(url=>url.pathname!='/login');
  await page.route('**/qa/media/graph.svg',route=>route.abort(),{times:1});
  await page.goto(`${base}/assessments/${fixture.exams.graded}/result`);
  await page.locator('[data-result-image]').first().evaluate(el=>{el.loading='eager';});
  await page.locator('.result-image-error').first().waitFor({state:'visible'});
  check('Missing image has readable fallback',await page.locator('.result-image-error').first().isVisible());
  check('Broken image opener hidden',await page.locator('[data-result-image-open]').first().isHidden());
  await page.locator('[data-result-image-retry]').first().click();
  await page.locator('[data-result-image-open]').first().waitFor({state:'visible'});
  check('Image retry recovers hidden lazy image',await page.locator('[data-result-image]').first().evaluate(el=>el.naturalWidth>0));
  check('Retry clears error message',await page.locator('.result-image-error').first().isHidden());
  const disclosures=page.locator('[data-result-explanation]');await disclosures.first().locator('summary').click();
  const before=await disclosures.evaluateAll(nodes=>nodes.map(n=>n.open));
  await page.evaluate(()=>dispatchEvent(new Event('beforeprint')));
  check('Print opens all explanation disclosures',await disclosures.evaluateAll(nodes=>nodes.every(n=>n.open)));
  await page.evaluate(()=>dispatchEvent(new Event('afterprint')));
  check('Print restores original disclosure state',JSON.stringify(before)===JSON.stringify(await disclosures.evaluateAll(nodes=>nodes.map(n=>n.open))));
  await page.emulateMedia({reducedMotion:'reduce'});
  check('Reduced motion no overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  const out=path.resolve('docs/ui-redesign/phase-6/result-media-qa.json');fs.writeFileSync(out,JSON.stringify({passed:checks.length,checks,readOnly:true},null,2));console.log(JSON.stringify({passed:checks.length}));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
