// All API traffic is intercepted, including writes; never changes NAS data.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    for (const width of [1440, 393]) for (const lang of ['zh', 'en']) {
      const page = await browser.newPage({ viewport: { width, height: 884 } });
      let writes = 0;
      page.on('pageerror', error => console.error('PAGE ERROR', error));
      await page.addInitScript(l => {
        localStorage.setItem('boten-language', l);
        sessionStorage.setItem('boten_user_token', 'fixture-only');
      }, lang);
      await page.route('**/api/**', async route => {
        const path = new URL(route.request().url()).pathname;
        let data = { items: [] };
        if (route.request().method() !== 'GET') {
          assert(path.endsWith('/configs')); writes++;
          return route.fulfill({ json: { id: 'saved' } });
        }
        if (/\/auth\/(me|profile)$/.test(path)) data = { id: 'qa', role: 'customer', display_name: 'QA', email: 'qa@example.invalid' };
        if (path === '/api/v1/products') data = { items: [{ id: 'qa', visible_zh: true, visible_en: true }] };
        if (path.endsWith('/snapshot')) data = {
          id: 'qa', model: 'QA', name: 'QA', colors: [{ code: 'red', name: 'Red' }],
          base_option_groups: [{ type: 'motor', name: 'Motor', options: [{ id: 'motor', name: '22kW' }] }],
          optional_categories: [{ id: 'cri', name: 'Options', multiple: true, options: [{ id: 'a', code: 'A', name: 'Optional kit' }, { id: 'b', code: 'B', name: 'Second kit' }] }]
        };
        await route.fulfill({ json: data });
      });
      await page.goto('http://127.0.0.1:8082/');
      await page.locator('#home-device:not([disabled])').click();
      const trigger = async id => {
        if (width < 1024) await page.locator('#summary-toggle').click();
        await page.locator(id).click();
      };
      for (const id of ['#save-cart', '#sales-contact-open']) {
        await trigger(id);
        await page.locator('#cart-confirm-title').waitFor();
        assert.equal(writes, 0);
        assert.equal(await page.locator('#summary-panel').evaluate(e => e.classList.contains('open')), false);
        assert(await page.locator('#config-section').evaluate(e => e.getBoundingClientRect().top >= 0 && e.getBoundingClientRect().top < innerHeight / 2));
        await page.keyboard.press('Escape');
        await page.locator('#cart-confirm-title').waitFor({ state: 'detached' });
        assert.equal(await page.evaluate(() => document.activeElement.id), 'config-section');
        assert.equal(writes, 0);
      }
      await trigger('#sales-contact-open');
      await page.locator('.cart-confirm-actions [value="confirm"]').click();
      await page.locator('.inquiry-dialog').waitFor();
      assert.equal(writes, 0); // Confirmation only opens the existing inquiry form.
      await page.keyboard.press('Escape');
      await trigger('#save-cart');
      await page.locator('.cart-confirm-actions [value="confirm"]').click();
      await page.waitForFunction(() => document.querySelector('#cart-panel').classList.contains('open'));
      assert.equal(writes, 1);
      await page.locator('#cart-close').click();
      await page.locator('.option-card-config').first().click();
      await trigger('#sales-contact-open');
      await page.locator('.inquiry-dialog').waitFor();
      assert.equal(await page.locator('#cart-confirm-title').count(), 0);
      await page.keyboard.press('Escape');
      console.log('PASS blank confirmation, cancel, scroll, save and selected bypass', width, lang);
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
