const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage();let saved=null;
  await page.addInitScript(()=>sessionStorage.setItem('boten_admin_token','fixture'));
  await page.route('**/api/v1/**',route=>{
   const p=new URL(route.request().url()).pathname;
   if(p.endsWith('/auth/me'))return route.fulfill({json:{id:'qa',role:'admin'}});
   if(p.endsWith('/products-order')){saved=route.request().postDataJSON();return route.fulfill({json:{items:saved.items.map(i=>({...i,name:i.id,enabled:true,version:i.version+1}))}});}
   if(route.request().method()!=='GET')return route.abort();
   return route.fulfill({json:{items:[],total:0}});
  });
  await page.goto('http://127.0.0.1:8081/admin/#products');await page.waitForLoadState('networkidle');
  await page.evaluate(()=>{state.products=['one','two'].map(id=>({id,name:id,version:1,enabled:true,visible_zh:true,visible_en:true}));renderProducts();});
  await page.locator('[data-start-product-order]').click();
  await page.locator('[data-product-order-step="1"][data-step="-1"]').click();
  await page.locator('[data-cancel-product-order]').click();
  assert.equal(await page.locator('#products-table tr').first().locator('td').first().textContent(),'one');
  await page.locator('[data-start-product-order]').click();await page.locator('[data-product-order-step="1"][data-step="-1"]').click();await page.locator('[data-save-product-order]').click();
  await page.waitForFunction(()=>!state.productOrderDraft);assert.deepEqual(saved.items.map(i=>i.id),['two','one']);
  console.log('Product order: reorder/cancel/save passed with isolated API');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
