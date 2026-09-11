const assert = require('node:assert/strict');
const { chromium } = require('playwright');
(async () => {
 const browser = await chromium.launch({channel:'msedge',headless:true});
 try {
  const page = await browser.newPage({acceptDownloads:true});
  let creates=0, pdfs=0;
  await page.addInitScript(()=>sessionStorage.setItem('boten_user_token','fixture'));
  await page.route('**/api/v1/**', async route=>{
   const p=new URL(route.request().url()).pathname;
   if(p.endsWith('/auth/me')) return route.fulfill({json:{id:'qa',role:'customer'}});
   if(p.endsWith('/customer/me/shares')) return route.fulfill({json:{items:[],quota:{limited:true,used:10,limit:10,remaining:0}}});
   if(p.endsWith('/cart/share')) { creates++; assert(route.request().postDataJSON().idempotency_key); assert.equal(route.request().postDataJSON().reuse_existing,true); return route.fulfill({json:{id:'fixture-share',code:'123456',reused:true,note:'Original'}}); }
   if(p.endsWith('/shares/123456/pdf')) { pdfs++; return pdfs===1 ? route.fulfill({status:503,json:{detail:'retry'}}) : route.fulfill({headers:{'Content-Disposition':'attachment; filename="ShareBench-BOTEN123456.pdf"'},contentType:'application/pdf',body:'%PDF-1.4\n%%EOF'}); }
   if(route.request().method()!=='GET')return route.abort();
   return route.continue();
  });
  const origin = process.env.BOTEN_TEST_ORIGIN || 'http://127.0.0.1:8081';
  await page.goto(origin + '/'); await page.waitForLoadState('networkidle');
  const keys = await page.evaluate(() => Array.from({length:100}, () => createPdfRequestKey()));
  assert.equal(new Set(keys).size, 100);
  assert(keys.every(key => /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(key)));
  await page.evaluate(()=>{serverCart=[{id:'fixture',itemType:'device_config',groups:[],modelName:'QA'}];openCartPanel();void exportCartPdf();});
  await page.locator('.cart-share-note-dialog textarea').fill('备注');
  await page.locator('.cart-share-note-dialog [value="confirm"]').click();
  await page.waitForFunction(()=>!cartPdfPending);
  assert.equal(creates,1); assert.equal(pdfs,1);
  const download = page.waitForEvent('download');
  await page.evaluate(()=>void exportCartPdf());
  assert.equal((await download).suggestedFilename(),'ShareBench-BOTEN123456.pdf');
  await page.waitForFunction(()=>!cartPdfPending);
  assert.equal(creates,1); assert.equal(pdfs,2);
  assert.match(await page.locator('#cart-operation-status').innerText(), /123456/);
  console.log('Share then PDF failure/retry: one share, stable filename passed');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
