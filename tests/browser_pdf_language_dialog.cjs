const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  const page=await browser.newPage();
  await page.addInitScript(()=>sessionStorage.setItem('boten_admin_token','fixture'));
  await page.route('**/api/v1/**',route=>route.fulfill({json:route.request().url().includes('/auth/me')?{id:'qa',role:'admin'}:{items:[],total:0}}));
  await page.goto('http://127.0.0.1:8081/admin/');
  await page.waitForLoadState('networkidle');
  for(const width of [1440,390]) {
   await page.setViewportSize({width,height:900});
   await page.evaluate(()=>{document.querySelector('#admin-content').setAttribute('tabindex','-1');document.querySelector('#admin-content').focus();state.catalogLanguage='zh';window.result='pending';choosePdfLanguage().then(value=>window.result=value);});
   const dialog=page.locator('.pdf-language-dialog');
   const box=await dialog.boundingBox();assert(box.height<350);assert(box.width<=400);assert(box.x>=16);
   assert(await dialog.locator('input[value=zh]').isChecked());
   await page.keyboard.press('ArrowRight');assert(await dialog.locator('input[value=en]').isChecked());
   await page.screenshot({path:`tmp/pdf-language-dialog-${width}.png`});
   await dialog.locator('[value=export]').click();
   await page.waitForFunction(()=>window.result==='en');
   assert.equal(await page.evaluate(()=>document.activeElement.id),'admin-content');
   await page.evaluate(()=>{window.result='pending';choosePdfLanguage().then(value=>window.result=value);});
   await page.keyboard.press('Escape');await page.waitForFunction(()=>window.result===null);
  }
  console.log('Compact PDF language dialog: desktop/mobile, radio keyboard, export, Escape and focus return passed');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
