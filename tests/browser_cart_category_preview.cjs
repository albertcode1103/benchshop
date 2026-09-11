// Isolated UI fixtures; never save or mutate real customer records.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage();
    await page.route('**/api/v1/**', route => route.request().method() === 'GET' ? route.continue() : route.abort());
    await page.goto('http://127.0.0.1:8081/');
    await page.waitForFunction(() => typeof showCartDetails === 'function');
    await page.waitForLoadState('networkidle');
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 });
      for (const lang of ['zh', 'en']) {
        await page.evaluate(language => {
          localStorage.setItem('boten-language', language);
          serverCart = [1, 2].map(number => ({ id: `fixture-${number}`, itemType: 'device_config', modelName: 'BOTEN CR1016', productTitle: 'Test', colorName: 'Red', groups: [
            { id: 'color', type: 'single', category: 'Color', value: 'Red' },
            { id: 'optional', type: 'multi', category: 'Selected kit', count: 1, value: [`Option ${number}`], detailItems: [{ code: `CODE-${number}`, name: `Option ${number}` }] }
          ] }));
          document.getElementById('cart-items').innerHTML = serverCart.map((item, i) => renderDeviceCartCard(item, i + 1)).join('');
          document.querySelectorAll('[data-cart-category]').forEach(button => button.onclick = () => showCartDetails(button.dataset.id, button.dataset.cartCategory));
          openCartPanel();
        }, lang);
        const trigger = page.locator('[data-cart-category][data-id="fixture-2"]');
        await trigger.click();
        const dialog = page.locator('.cart-detail-dialog');
        assert((await dialog.textContent()).includes('CODE-2'));
        assert(!(await dialog.textContent()).includes('CODE-1'));
        const box = await dialog.boundingBox();
        assert(box.x >= 0 && box.x + box.width <= width + 1);
        await page.keyboard.press('Escape');
        await page.waitForFunction(() => !document.querySelector('.cart-detail-dialog'));
        assert(await trigger.evaluate(el => document.activeElement === el));
        assert(await page.locator('#cart-panel').evaluate(el => el.classList.contains('open')));
        await page.evaluate(() => closeCartPanel());
      }
    }
    console.log('Cart category preview: desktop/mobile, zh/en, same-model isolation and Escape focus passed');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
