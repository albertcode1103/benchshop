// Read-only NAS requests; all writes blocked. Selection changes are browser-local.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    for (const width of [1280,393]) {
      const page = await browser.newPage({viewport:{width,height:852},reducedMotion:'reduce'});
      await page.route('**/api/**', route => ['GET','HEAD'].includes(route.request().method()) ? route.continue() : route.abort());
      await page.goto('http://127.0.0.1:8082/');
      await page.locator('#home-device:not([disabled])').click();
      await page.locator('#color-options .option-card').first().waitFor();
      await page.waitForTimeout(1000);
      await page.evaluate(() => { document.querySelector('.device-overview').open=true; });
      await page.locator('#color-options').scrollIntoViewIfNeeded();
      const before = await page.evaluate(() => scrollY);
      await page.evaluate(() => document.querySelector('#color-options .option-card:not(.active)').click());
      await page.waitForTimeout(500);
      assert(Math.abs(await page.evaluate(()=>scrollY)-before)<4,'color moved page');
      assert(await page.locator('.device-overview').evaluate(e=>e.open),'overview collapsed');
      await page.locator('#category-tabs').scrollIntoViewIfNeeded();
      await page.locator('#category-tabs .tab-btn').first().focus();
      const tabY = await page.evaluate(()=>scrollY);
      await page.keyboard.press('ArrowRight');
      assert(Math.abs(await page.evaluate(()=>scrollY)-tabY)<4,'tab moved page');
      assert.equal(await page.evaluate(()=>document.activeElement.getAttribute('aria-selected')),'true');
      await page.evaluate(()=>scrollTo({top:700,behavior:'instant'}));
      const historyY = await page.evaluate(()=>scrollY);
      await page.goto('http://127.0.0.1:8082/account/');
      await page.goBack(); await page.waitForTimeout(1600);
      assert(Math.abs(await page.evaluate(()=>scrollY)-historyY)<6,'history position lost');
      await page.locator('#motor-section').scrollIntoViewIfNeeded();
      const saved = await page.evaluate(() => {
        window.botenRememberLanguageScroll();
        return JSON.parse(sessionStorage.getItem('boten-language-scroll'));
      });
      assert(saved.anchor, 'language anchor must exist');
      // Programmatic click avoids scrolling to the header before capturing location.
      await page.evaluate(()=>document.querySelector('#language-switcher [data-language="en"]').click());
      await page.waitForTimeout(1800);
      const afterOffset = await page.locator('#'+saved.anchor).evaluate(e=>e.getBoundingClientRect().top);
      assert(Math.abs(afterOffset-saved.offset)<6,`language anchor lost: ${width}, ${saved.offset} -> ${afterOffset}`);
      await page.evaluate(()=>document.querySelector('#device-select').dispatchEvent(new Event('change')));
      await page.waitForTimeout(100);
      assert.equal(await page.evaluate(()=>scrollY),0,'directory entry must start at top');
      console.log('PASS scroll policy',width);
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
