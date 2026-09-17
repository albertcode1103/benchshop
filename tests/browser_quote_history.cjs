// All network traffic is mocked. No NAS reads or writes.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path');
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true});
  try {
    const page = await browser.newPage();
    const errors = [];
    let version = 4, archived = false;
    const snapshot = {id:'q', version:1, title:'Historical title', customer_name:'Old customer', currency:'USD', total_price:40, items:[{kind:'tool', line_id:'l1', code:'T-1', name:'Historical tool', quantity:2, price:20}], revision:{revision_number:1, created_at:'2026-09-17 10:00:00'}};
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => sessionStorage.setItem('boten_admin_token','fixture'));
    await page.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.pathname.startsWith('/api/')) {
        assert.equal(route.request().method(), 'GET', 'history/apply must not write before save');
        if(url.pathname.endsWith('/auth/me')) return route.fulfill({json:{id:'sales',role:'sales'}});
        if(url.pathname.endsWith('/history/r1')) return route.fulfill({json:{quote:snapshot,current_version:4,can_apply:!archived}});
        if(url.pathname.endsWith('/history')) return route.fulfill({json:{quote:{id:'q',title:'Current quote'},revisions:[{id:'r1',revision_number:1,record_version:1,event:'created'}],deliveries:[]}});
        if(url.pathname.endsWith('/quotes/q')) return route.fulfill({json:{...snapshot,version,lifecycle_status:archived?'archived':'draft',title:'Current quote',source_type:'direct'}});
        return route.fulfill({json:{items:[],total:0}});
      }
      let rel = decodeURIComponent(url.pathname).replace(/^\//,'');
      if(!path.extname(rel)) rel += 'index.html';
      const file = path.resolve(rel);
      if(!file.startsWith(process.cwd()+path.sep)||!fs.existsSync(file)) return route.fulfill({status:404,body:''});
      return route.fulfill({body:fs.readFileSync(file),contentType:({'.html':'text/html','.js':'text/javascript','.css':'text/css'})[path.extname(file)]||'application/octet-stream'});
    });
    await page.goto('http://quote-history.test/admin/#quotes');
    await page.waitForLoadState('networkidle');
    // Capture what is passed into the existing editor, without submitting it.
    await page.evaluate(() => { window.applied = null; editQuote = async quote => { window.applied = quote; }; });
    const open = async () => {
      await page.evaluate(() => viewQuoteHistory('q'));
      await page.locator('[data-preview-revision]').click();
      await page.locator('.quote-history-preview').waitFor({state:'visible'});
    };
    await open();
    const preview = page.locator('.quote-history-preview');
    assert((await preview.innerText()).includes('Historical tool'));
    assert((await preview.innerText()).includes('Old customer'));
    assert((await preview.innerText()).includes('40.00'));
    await page.locator('[data-apply-revision]').click();
    await preview.waitFor({state:'detached'});
    const applied = await page.evaluate(() => window.applied);
    assert.equal(applied.version, 4);
    assert.equal(applied.title, 'Historical title');
    assert.equal(applied.items[0].price, 20);
    version = 5;
    await page.evaluate(() => { window.applied = null; });
    await open();
    await page.locator('[data-apply-revision]').click();
    await page.waitForFunction(() => document.querySelector('#toast')?.textContent.includes('已被更新'));
    assert.equal(await page.evaluate(() => window.applied), null);
    await page.evaluate(() => document.querySelectorAll('dialog').forEach(d => d.close()));
    archived = true;
    await open();
    assert(await page.locator('[data-apply-revision]').isDisabled());
    assert.deepEqual(errors, []);
    console.log('PASS: history list, snapshot preview, explicit apply with current version, concurrent-edit rejection, archived readonly, no writes');
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exit(1);});
