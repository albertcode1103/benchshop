// Read-only live-page checks plus isolated runtime configuration cases.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { chromium } = require('playwright');
const source = fs.readFileSync('js/runtime-config.js', 'utf8');
for (const url of ['http://127.0.0.1:8081/', 'http://192.168.31.53:8081/', 'http://192.168.31.69:8080/', 'https://bench.example/']) {
  const window = { location: new URL(url) };
  vm.runInNewContext(source, { window });
  assert.equal(window.BOTEN_API_BASE, '');
  assert.equal(window.botenAssetUrl('/api/v1/uploads/test.png'), '/api/v1/uploads/test.png');
}
const custom = { BOTEN_API_BASE: 'https://api.example', location: new URL('https://bench.example') };
vm.runInNewContext(source, { window: custom });
assert.equal(custom.BOTEN_API_BASE, 'https://api.example');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage();
    const apiRequests = [];
    page.on('request', request => { if (request.url().includes('/api/')) apiRequests.push(request.url()); });
    await page.goto('http://192.168.31.53:8081/');
    await page.waitForLoadState('networkidle');
    assert.equal(await page.evaluate(() => window.BOTEN_API_BASE), '');
    assert(apiRequests.length > 0);
    assert(apiRequests.every(url => new URL(url).port === '8081'));
    for (const path of ['/api/v1/ready', '/api/v1/products', '/admin/', '/account/']) {
      assert.equal((await page.request.get('http://192.168.31.53:8081' + path)).status(), 200);
    }
    console.log('LAN-origin browser requests and local/NAS/HTTPS runtime defaults passed');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
