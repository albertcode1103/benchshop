// Navigation-only regression: no mutations to real business records.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    const page = await browser.newPage();
    const home='http://127.0.0.1:8081/';
    await page.route('**/api/v1/**',route=>route.request().method()==='GET' ? route.continue() : route.abort());
    for (const width of [1440,390]) {
      await page.setViewportSize({width,height:800});
      await page.goto(home);
      await page.waitForFunction(()=>document.querySelector('#device-select')?.options.length>0);
      await page.waitForLoadState('networkidle');
      const selected=await page.locator('#device-select').inputValue();
      for(const action of ['navigate','back','reload','bfcache']) {
        await page.evaluate(()=>window.scrollTo({top:700,behavior:'instant'}));
        assert(await page.evaluate(()=>scrollY>100));
        if(action==='navigate') {
          await page.goto(home+'admin/');
          await page.goto(home);
        } else if(action==='back') {
          await page.goto(home+'admin/');
          await page.goBack();
        } else if(action==='reload') await page.reload();
        else await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
        await page.waitForLoadState('networkidle');
        await page.waitForFunction(()=>scrollY===0);
        assert.equal(await page.locator('#device-select').inputValue(),selected);
      }
    }
    console.log('PASS: home navigation, history, refresh and cached pageshow reset scroll at 1440/390 without changing selected device');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
