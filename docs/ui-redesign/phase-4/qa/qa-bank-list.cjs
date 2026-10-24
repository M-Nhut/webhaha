const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base='http://127.0.0.1:8766';
const checks=[];
const check=(name,condition,detail)=>{checks.push({name,passed:!!condition,detail});assert.ok(condition,name+': '+JSON.stringify(detail));};
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try {
  const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'vi-VN'});
  const page=await context.newPage();
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const go=async(url)=>{const r=await page.goto(base+url,{waitUntil:'networkidle'});await page.evaluate(()=>document.fonts.ready);return r;};
  await go('/login?next=/question-banks');
  await page.locator('[name=username]').fill('qa_teacher');await page.locator('[name=password]').fill('Academy123!');
  await Promise.all([page.waitForURL('**/question-banks'),page.locator('[name=submit]').click()]);
  await page.waitForLoadState('networkidle');
  for(const width of [375,768,1024,1440]){
   await page.setViewportSize({width,height:1000});await go('/question-banks');
   check(`bank list ${width} no page overflow`,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   const countLabels=await page.locator('.bank-difficulty-counts').first().locator('dt').allTextContents();
   check(`bank list ${width} all four labels`,JSON.stringify(countLabels)==='["Nhận biết","Thông hiểu","Vận dụng","Vận dụng cao"]',countLabels);
   if(width===375){
    const small=await page.locator('.bank-row-actions .btn,.bank-import-link,.bank-page-actions .btn').evaluateAll(es=>es.filter(e=>e.getBoundingClientRect().width>0).filter(e=>e.getBoundingClientRect().height<44).map(e=>({text:e.textContent,height:e.getBoundingClientRect().height})));
    check('mobile bank list 44px controls',small.length===0,small);
   }
  }
  const shared=page.locator('section[aria-labelledby=shared-banks-heading]');
  check('teacher shared bank cannot edit/delete',await shared.locator('[data-bank-delete-open]').count()===0 && await shared.getByRole('link',{name:/^Sửa /}).count()===0);
  check('teacher shared bank exact import available',await shared.locator('.bank-import-link').count()>0);
  const first=page.locator('[data-bank-delete-open]').first();
  const deleteURL=await first.evaluate(e=>e.closest('form').action);
  const csrf=await first.evaluate(e=>e.closest('form').querySelector('[name=csrf_token]').value);
  const originalName=await first.getAttribute('data-bank-name');
  await first.click();const dialog=page.locator('#bank-delete-dialog');
  check('dialog identifies bank by original name',(await dialog.locator('[data-bank-delete-name]').textContent())===originalName);
  await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});
  check('Escape returns focus',await first.evaluate(e=>document.activeElement===e));
  await first.evaluate(e=>{e.dataset.bankName='<script>window.bankXSS=true</script> " & \' ngân hàng';});
  await first.click();
  check('bank name inserted as literal text',await dialog.locator('[data-bank-delete-name]').textContent()==='<script>window.bankXSS=true</script> " & \' ngân hàng');
  check('bank name cannot inject tags',await dialog.locator('script').count()===0 && !(await page.evaluate(()=>window.bankXSS)));
  await dialog.locator('[data-dialog-close]').last().click();await dialog.waitFor({state:'hidden'});
  await first.evaluate(e=>{e.dataset.bankName='';});await first.click();
  check('empty bank name safely renders empty',(await dialog.locator('[data-bank-delete-name]').textContent())==='');
  await dialog.locator('[data-dialog-close]').last().click();await dialog.waitFor({state:'hidden'});
  await first.evaluate((e,name)=>{e.dataset.bankName=name;},originalName);
  let captured;
  await page.route('**/question-banks/*/delete',async route=>{captured={url:route.request().url(),method:route.request().method(),body:route.request().postData()};await route.fulfill({status:200,contentType:'text/html',body:'<html><body>QA intercepted POST. No bank was deleted.</body></html>'});});
  await first.click();await Promise.all([page.waitForURL(deleteURL),dialog.locator('[data-bank-delete-confirm]').click()]);
  check('confirm posts to original bank',captured.url===deleteURL && captured.method==='POST',captured?.url);
  check('confirm retains original CSRF',new URLSearchParams(captured.body).get('csrf_token')===csrf);
  await page.unroute('**/question-banks/*/delete');
  await go('/question-banks/new');
  await page.locator('[data-bank-form-submit]').click();
  await page.waitForTimeout(30);
  check('native invalid form keeps page',page.url()===base+'/question-banks/new');
  check('native invalid linked error summary',await page.locator('#bank-form-errors').isVisible()&&await page.locator('#bank-form-errors a').count()===2);
  check('native invalid focuses summary',await page.locator('#bank-form-errors').evaluate(e=>e===document.activeElement));
  await go('/logout');await go('/login?next=/question-banks');
  await page.locator('[name=username]').fill('qa_admin');await page.locator('[name=password]').fill('Academy123!');
  await Promise.all([page.waitForURL('**/question-banks'),page.locator('[name=submit]').click()]);await page.waitForLoadState('networkidle');
  check('admin owner name matches User.fullname',(await page.locator('.bank-owner').allTextContents()).some(t=>t.includes('Nguyễn Minh Anh')));
  const privateEdit=page.locator('.bank-row').filter({hasText:'Đại số 10'}).getByRole('link',{name:/^Sửa /});
  await privateEdit.click();await page.waitForLoadState('networkidle');
  check('admin private form identifies teacher owner',(await page.locator('.bank-form-context').textContent()).includes('Nguyễn Minh Anh'));
  check('no JavaScript runtime errors',errors.length===0,errors);
  fs.writeFileSync('/tmp/phase4-bank-list-readonly-qa.json',JSON.stringify({checks,errors},null,2));
  console.log(checks.length+' read-only browser checks passed; all deletion POST requests intercepted.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
