const assert = require('node:assert/strict');
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage();
    let attempts = 0;
    await page.route('**/api/v1/customer/inquiries/current-configuration', route => {
      const body = route.request().postDataJSON();
      assert.deepEqual(Object.keys(body).sort(), ['color', 'idempotency_key', 'lang', 'message', 'product_id', 'selections']);
      attempts++;
      return attempts === 1
        ? route.fulfill({ status: 422, json: { detail: [{ type: 'extra_forbidden', loc: ['body', 'name'], msg: 'Extra inputs are not permitted' }] } })
        : route.fulfill({ status: 201, json: { inquiry_number: 'QA-INQUIRY' } });
    });
    await page.goto('http://127.0.0.1:8081/');
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => openInquiryDialog('current_device'));
    await page.locator('.inquiry-dialog [value="submit"]').click();
    await page.waitForFunction(() => document.querySelector('.inquiry-dialog-status').textContent.includes('校验失败'));
    assert(!await page.locator('.inquiry-dialog-status').innerText().then(t => t.includes('[object Object]')));
    await page.locator('.inquiry-dialog [value="submit"]').click();
    await page.waitForFunction(() => document.querySelector('.inquiry-dialog-status').textContent.includes('QA-INQUIRY'));
    assert.equal(attempts, 2);
    console.log('Inquiry field whitelist, readable 422 and success retry passed (mocked API, no business data written).');
  } finally { await browser.close(); }
})();
