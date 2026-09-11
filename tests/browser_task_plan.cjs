// All business mutations intercepted; existing catalog GETs are read-only.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
    const pdfs = [];
    let failPdf = false;
    let quota = { limited: true, used: 10, limit: 10, remaining: 0 };
    await context.route('**/api/v1/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname.endsWith('/pdf')) { pdfs.push(url); if (failPdf) { failPdf = false; return route.fulfill({status:503,json:{detail:'Temporary PDF failure; retry'}}); } return route.fulfill({ contentType: 'application/pdf', body: '%PDF-1.4\n%%EOF' }); }
      if (route.request().method() !== 'GET') return route.fulfill({ status: 409, json: { detail: 'Isolated fixture: writes blocked' } });
      if (url.pathname.includes('/auth/me')) return route.fulfill({ json: { id: 'qa', role: 'admin', display_name: 'QA' } });
      if (url.pathname.includes('/admin/') || url.pathname.includes('/staff/') || url.pathname.includes('/customer/') || url.pathname === '/api/v1/quotes') return route.fulfill({ json: { items: [], total: 0, page: 1, quota } });
      return route.continue();
    });
    const page = await context.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    fs.mkdirSync('tmp/task-plan-ui', { recursive: true });
    await page.goto('http://127.0.0.1:8081/');
    await page.locator('#catalog-stage-toggle').click();
    await page.locator('#catalog-device-entry').click();
    const close = await page.locator('#catalog-model-close').boundingBox();
    assert(close.width <= 44 && close.height <= 44);
    await page.locator('#catalog-model-close').click();
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#catalog-stage-toggle').evaluate(e => document.activeElement === e), true);
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await page.evaluate(() => openCartPanel());
      await page.locator('#cart-close').hover(); // Wait for the slide-in transition to settle.
      const panel = await page.locator('#cart-panel').boundingBox();
      assert(panel.x >= -1 && panel.x + panel.width <= width + 1);
      await page.locator('#cart-items').evaluate(e => {
        e.innerHTML = Array.from({ length: 20 }, (_, i) => `<article class="cart-item"><div class="cart-item-model">QA-${i + 1}</div><div class="cart-item-title">隔离布局验收条目</div></article>`).join('');
        e.lastElementChild.scrollIntoView({ block: 'end' });
      });
      const listEnd = await page.locator('#cart-items article').last().boundingBox();
      const footer = await page.locator('.cart-panel-footer').boundingBox();
      assert(listEnd.y + listEnd.height <= footer.y + 1);
      const positions = await page.evaluate(() => ['cart-pdf', 'cart-share', 'cart-inquiry'].map(id => {
        const e = document.getElementById(id), r = e.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, color: getComputedStyle(e).backgroundColor };
      }));
      assert(Math.abs(positions[0].y - positions[1].y) < 2);
      assert(Math.abs(positions[0].w - positions[1].w) < 2);
      assert(positions[2].y > positions[0].y);
      assert.equal(positions[2].color, 'rgb(37, 99, 235)');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.screenshot({ path: `tmp/task-plan-ui/cart-${width}.png` });
      await page.evaluate(() => closeCartPanel());
      await page.locator('#catalog-stage-toggle').click();
      await page.locator('#catalog-device-entry').click();
      await page.keyboard.press('Escape');
    }
    for (const type of ['tools', 'accessories']) {
      await page.locator('#catalog-stage-toggle').click();
      await page.locator(`[data-catalog-drawer-select="catalog:${type}"]`).click();
      await page.locator('#catalog-marketplace-search').fill('TEST');
      await page.locator('#catalog-marketplace-toggle').click();
      await page.locator('#catalog-drawer-close').click();
      assert.equal(await page.locator('#catalog-marketplace-search').inputValue(), 'TEST');
      await page.locator('#catalog-marketplace-toggle').click();
      await page.locator('#catalog-device-entry').click();
      await page.locator('.catalog-model-item').first().click();
    }
    await page.evaluate(() => { serverCart = [{ id: 'qa', itemType: 'tool' }]; void shareCart(); });
    await page.locator('.cart-confirm-dialog').waitFor();
    await page.locator('.cart-confirm-dialog button[value=cancel]').last().click();
    await page.waitForFunction(() => !shareCartPending);
    assert.equal(await page.evaluate(() => serverCart[0].id), 'qa');
    quota = { limited: true, used: 7, limit: 10, remaining: 3 };
    await page.evaluate(() => { void shareCart(); });
    await page.locator('.cart-share-note-dialog').waitFor();
    assert.match(await page.locator('.cart-share-note-dialog').innerText(), /7\/10/);
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !shareCartPending);
    await page.evaluate(() => {
      currentUser = { id: 'qa', role: 'admin', display_name: 'QA' };
      sessionStorage.setItem(USER_TOKEN_KEY, 'isolated-ui-token'); notifyAuth();
    });
    await page.locator('#account-toggle').click();
    const opened = page.waitForEvent('popup');
    await page.locator('#account-admin-entry').click();
    const adminTab = await opened;
    await adminTab.waitForLoadState();
    assert.equal(await adminTab.evaluate(() => sessionStorage.getItem('boten_admin_token')), 'isolated-ui-token');
    assert.equal(new URL(page.url()).pathname, '/');
    await adminTab.close();
    await page.goto('http://127.0.0.1:8081/admin/#shares');
    await page.waitForFunction(() => typeof choosePdfLanguage === 'function');
    assert.equal(await page.locator('#share-status-filter').inputValue(), 'active');
    for (const entry of ['share', 'inquiry', 'quote']) {
      for (const language of ['zh', 'en']) {
        await page.evaluate(entry => {
          if (entry === 'share') void exportSharePdf('123456');
          if (entry === 'quote') void exportQuote({ id: 'q' });
          if (entry === 'inquiry') { const b = document.createElement('button'); b.dataset.exportInquiry = 'i'; document.body.appendChild(b); void exportInquiryPdf(b); }
        }, entry);
        await page.locator(`.pdf-language-dialog input[value="${language}"]`).check();
        await page.locator('.pdf-language-dialog button[value=export]').click();
        await page.waitForFunction(() => !pdfExportPending);
        assert.equal(pdfs.at(-1).searchParams.get('lang'), language);
      }
    }
    const count = pdfs.length;
    await page.evaluate(() => { void exportSharePdf('123456'); void exportSharePdf('123456'); });
    assert.equal(await page.locator('.pdf-language-dialog').count(), 1);
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !pdfExportPending);
    assert.equal(pdfs.length, count);
    for (const entry of ['share','inquiry','quote']) {
      for (const failure of [true,false]) {
        failPdf = failure;
        await page.evaluate(entry=>{
          if(entry==='share') void exportSharePdf('123456');
          if(entry==='quote') void exportQuote({id:'q'});
          if(entry==='inquiry') {const button=document.createElement('button');button.dataset.exportInquiry='i';document.body.appendChild(button);void exportInquiryPdf(button);}
        },entry);
        await page.locator('.pdf-language-dialog button[value=export]').click();
        await page.waitForFunction(()=>!pdfExportPending);
        assert.equal(failPdf,false);
      }
    }
    await page.goto('http://127.0.0.1:8081/');
    for(const width of [1440,390]) {
      await page.setViewportSize({width,height:900});
      for(const method of ['button','escape','backdrop']) {
        await page.locator('#catalog-stage-toggle').click();
        await page.locator('#catalog-device-entry').click();
        const button=page.locator('#catalog-model-close');
        await button.hover();
        const box=await button.boundingBox();
        assert(box.width>=38 && box.width<=44 && box.height>=38);
        await button.focus();
        await page.keyboard.press('Tab');
        assert(await page.evaluate(()=>Boolean(document.activeElement.closest('#catalog-navigation-drawer,#catalog-model-drawer'))));
        if(method==='button') await button.click();
        if(method==='escape') await page.keyboard.press('Escape');
        if(method==='backdrop') await page.locator('#catalog-navigation-backdrop').click({position:{x:width-5,y:880}});
        assert.equal(await page.locator('#catalog-navigation-drawer').getAttribute('aria-hidden'),'true');
        assert(await page.evaluate(()=>document.activeElement.id==='catalog-stage-toggle' && document.body.style.overflow!== 'hidden' && !document.querySelector('.main').inert));
      }
    }
    assert.deepEqual(errors, []);
    console.log('PASS: drawer desktop/mobile close/Escape/backdrop/focus/scroll, footer, six PDF languages, cancel/duplicate guard and three export failure/retry cases');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
