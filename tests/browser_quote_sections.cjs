// Synthetic quotations only: no live API, saves, exports or deliveries.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true});
  const context = await browser.newContext();
  const errors = [], writes = [];
  const root = process.cwd();
  fs.mkdirSync('tmp/quote-sections', {recursive:true});
  await context.addInitScript(() => sessionStorage.setItem('boten_admin_token','fixture'));
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith('/api/')) {
      if (route.request().method() !== 'GET') writes.push(url.pathname);
      return route.fulfill({json: url.pathname.endsWith('/auth/me') ? {id:'admin',role:'admin'} : {items:[],products:[],options:[],total:0}});
    }
    let rel = decodeURIComponent(url.pathname).replace(/^\//,'');
    if (!path.extname(rel)) rel += 'index.html';
    const file = path.resolve(root,rel);
    if (!file.startsWith(root+path.sep) || !fs.existsSync(file)) return route.fulfill({status:404,body:''});
    return route.fulfill({body:fs.readFileSync(file),contentType:({'.html':'text/html','.js':'text/javascript','.css':'text/css','.ttf':'font/ttf','.svg':'image/svg+xml'})[path.extname(file)]||'application/octet-stream'});
  });
  const page = await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));
  try {
    await page.goto('http://quote.test/admin/#quotes');
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => {
      const items = [];
      for (let device=1;device<=2;device++) {
        items.push({kind:'product',line_id:`base-${device}`,device_key:`d${device}`,device_sequence:device,device_label:`Device ${device} · BOTEN CR1016`,code:'BOTEN CR1016',name:'设备',price:10000,quantity:1});
        for (const [id,label] of [['cri','共轨喷油器选配套件'],['pump','共轨泵选配套件']]) {
          for (let n=0;n<10;n++) items.push({kind:'option',line_id:`${device}-${id}-${n}`,source_id:`${id}-${n}`,parent_device_key:`d${device}`,device_sequence:device,category_id:id,category_name:label,name:`测试配置 ${n}`,code:`BTK-${device}${id}${n}`,price:10+n,quantity:1});
        }
        items.push({kind:'option',line_id:`old-${device}`,parent_device_key:`d${device}`,device_sequence:device,name:'历史无分类配置',price:5,quantity:1});
      }
      for (let n=0;n<10;n++) items.push({kind:'tool',line_id:`tool-${n}`,name:`工具 ${n}`,price:5,quantity:1});
      for (let n=0;n<10;n++) items.push({kind:'accessory',line_id:`acc-${n}`,name:`附件 ${n}`,price:5,quantity:1});
      openQuoteEditor({title:'分类滚动测试',items});
    });
    const dialog = page.locator('.quote-editor-dialog[open]');
    await dialog.waitFor();
    const original = await dialog.locator('[name=quote_items_state]').inputValue();
    assert.equal(await dialog.locator('.quote-category-title').count(),8);
    assert.equal(await dialog.locator('.quote-commerce-group-title').count(),4);
    for (const [width,height] of [[1440,900],[1024,768],[390,844],[844,390],[390,350]]) {
      await page.setViewportSize({width,height});
      for (const target of ['设备 1 · BOTEN CR1016 · 共轨喷油器选配套件','设备 1 · BOTEN CR1016 · 共轨泵选配套件','设备 2 · BOTEN CR1016 · 共轨喷油器选配套件','维修工具','设备附件']) {
        await page.evaluate(label => {
          const dialog = document.querySelector('.quote-editor-dialog');
          const list = dialog.querySelector('.quote-edit-list');
          const host = getComputedStyle(list).overflowY === 'visible' ? dialog.querySelector('.quote-editor-body') : list;
          const marker = [...dialog.querySelectorAll('[data-quote-context]')].find(n=>n.dataset.quoteContext===label);
          const head = dialog.querySelector('.quote-edit-head').getBoundingClientRect().height;
          const context = dialog.querySelector('.quote-scroll-context').getBoundingClientRect().height;
          host.scrollTop += marker.getBoundingClientRect().top - host.getBoundingClientRect().top - head - context + 8;
        },target);
        await page.waitForFunction(label => document.querySelector('.quote-scroll-context span').textContent === label,target);
        const geometry = await dialog.evaluate(d => {
          const list=d.querySelector('.quote-edit-list'), host=getComputedStyle(list).overflowY==='visible'?d.querySelector('.quote-editor-body'):list;
          const h=d.querySelector('.quote-edit-head').getBoundingClientRect(), c=d.querySelector('.quote-scroll-context').getBoundingClientRect(), r=host.getBoundingClientRect();
          return {offset:h.height ? Math.abs(c.top-h.bottom) : Math.abs(c.top-r.top),head:h.height ? Math.abs(h.top-r.top) : 0,overflow:d.scrollWidth-d.clientWidth};
        });
        assert(geometry.offset<2 && geometry.head<2, JSON.stringify({width,height,target,geometry}));
        assert(geometry.overflow<=1);
        if (target.startsWith('设备 2')) await page.screenshot({path:`tmp/quote-sections/${width}x${height}.png`});
      }
      // Reverse scrolling must restore the earlier device/category, too.
      await page.evaluate(() => {document.querySelector('.quote-edit-list').scrollTop=0;document.querySelector('.quote-editor-body').scrollTop=0;});
      await page.waitForFunction(()=>document.querySelector('.quote-scroll-context span').textContent==='设备 1 · BOTEN CR1016 · 基础配置');
    }
    const lastQty = dialog.locator('[data-q=qty]').last();
    await lastQty.focus();
    assert(await lastQty.evaluate(e => { const r=e.getBoundingClientRect(),d=e.closest('dialog'),c=d.querySelector('.quote-scroll-context').getBoundingClientRect(),f=d.querySelector('footer').getBoundingClientRect(); return r.top >= c.bottom-1 && r.bottom <= f.top+1; }), 'low-height focused input stays visible below context');
    assert.equal(await dialog.locator('[name=quote_items_state]').inputValue(),original,'scrolling leaves quotation state unchanged');
    // Removing the only legacy-category row rebuilds headings without changing other inputs.
    await dialog.locator('[data-delete-quote-line="21"]').click();
    await page.locator('.confirm-dialog button[value=confirm]').click();
    assert.equal(await dialog.locator('.quote-category-title').count(),7);
    assert.equal(await dialog.locator('.quote-edit-row').count(),63);
    assert.deepEqual(writes,[]);
    assert.deepEqual(errors,[]);
    console.log('PASS quote sections: two same-model devices, categories, legacy fallback, tools/accessories, forward/reverse sticky tracking, desktop/mobile/short layouts, unchanged data and deletion.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
