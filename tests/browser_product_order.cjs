const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage();let saved=null,requestCount=0,failSave=false;
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>sessionStorage.setItem('boten_admin_token','fixture'));
  await page.route('**/api/v1/**',route=>{
   const p=new URL(route.request().url()).pathname;
   if(p.endsWith('/auth/me'))return route.fulfill({json:{id:'qa',role:'admin'}});
   if(p.endsWith('/products-order')){saved=route.request().postDataJSON();requestCount++;return new Promise(resolve=>setTimeout(resolve,250)).then(()=>route.fulfill(failSave?{status:409,json:{detail:'设备列表已变化，请刷新后重新排序'}}:{json:{items:saved.items.map(i=>({...i,name:i.id,enabled:true,version:i.version+1}))}}));}
   if(route.request().method()!=='GET')return route.abort();
   return route.fulfill({json:{items:[],total:0}});
  });
  await page.goto('http://127.0.0.1:8081/admin/#products');await page.waitForLoadState('networkidle');
  const original=['one','two','three','four','five'];
  const order=()=>page.evaluate(()=>state.productOrderDraft.map(i=>i.id));
  const field=id=>page.locator(`[data-product-order-position="${id}"]`);
  async function insert(id,value,enter=false){await field(id).fill(value);if(enter)await field(id).press('Enter');else await page.locator(`[data-insert-product-order="${id}"]`).click();}
  for(const lang of ['zh','en'])for(const width of [1440,320]){
   await page.setViewportSize({width,height:width===320?568:900});
   await page.evaluate(language=>{state.catalogLanguage=language;state.products=['one','two','three','four','five'].map((id,index)=>({id,name:id,name_en:id+' EN',title_name:'设备名称',title_name_en:'Equipment name',version:1,enabled:index!==3,...[{visible_zh:true,visible_en:true},{visible_zh:true,visible_en:false},{visible_zh:0,visible_en:1},{visible_zh:false,visible_en:true},{}][index]}));renderProducts();},lang);
   const expectedStatus=['已启用：中文 EN','已启用：中文','已启用：EN','已下架：EN','已启用：中文 EN'];
   assert.deepEqual(await page.locator('#products-table tr td:nth-child(3)').allTextContents(),expectedStatus);
   assert.deepEqual(await page.locator('#products-table tr td:nth-child(4)').allTextContents(),Array(5).fill('编辑'));
   assert(await page.locator('#products-table').evaluate(t=>[...t.querySelectorAll('.badge')].every(b=>b.getBoundingClientRect().right<=b.closest('td').getBoundingClientRect().right)),'language status stays in status column');
   fs.mkdirSync('tmp/product-order',{recursive:true});await page.screenshot({path:`tmp/product-order/status-${lang}-${width}.png`});
   const before=requestCount;
   await page.locator('[data-start-product-order]').click();
   assert(await field('one').evaluate(e=>e===document.activeElement),'entering sort focuses first position');
   assert.deepEqual(await page.locator('#products-table tr td:nth-child(3)').allTextContents(),expectedStatus);
   assert(!(await page.locator('#products-table tr td:nth-child(4)').allTextContents()).some(text=>/中文|EN/.test(text)),'language removed from sorting actions');
   for(const value of ['','0','6','1.5','-1']){await insert('five',value,true);assert.deepEqual(await order(),original);assert.equal(await field('five').evaluate(e=>e.validity.valid),false);}
   await insert('five','2',true);assert.deepEqual(await order(),['one','five','two','three','four']);
   assert(await field('five').evaluate(e=>e===document.activeElement),'focus follows inserted product');
   await insert('one','5');assert.deepEqual(await order(),['five','two','three','four','one']);
   await insert('three','1');assert.deepEqual(await order(),['three','five','two','four','one']);
   await insert('three','1');assert.deepEqual(await order(),['three','five','two','four','one']);
   assert.deepEqual(await page.locator('[data-product-order-position]').evaluateAll(inputs=>inputs.map(i=>i.value)),['1','2','3','4','5']);
   assert.equal(requestCount,before,'draft changes must not write data');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no whole-page overflow');
   assert(await page.locator('#products-table').evaluate(t=>[...t.querySelectorAll('[data-insert-product-order]')].every(b=>b.getBoundingClientRect().right<=b.closest('td').getBoundingClientRect().right)),'insert controls stay within action column');
   fs.mkdirSync('tmp/product-order',{recursive:true});await page.screenshot({path:`tmp/product-order/${lang}-${width}.png`});
   await page.locator('[data-cancel-product-order]').click();assert.deepEqual(await page.evaluate(()=>state.products.map(i=>i.id)),original);assert.equal(requestCount,before);
   assert(await page.locator('[data-start-product-order]').evaluate(e=>e===document.activeElement),'cancel restores sort focus');
   await page.locator('[data-start-product-order]').click();await insert('five','1');
   failSave=true;await page.locator('[data-save-product-order]').click();
   await page.waitForFunction(()=>state.productOrderSaving);
   assert(await page.locator('[data-cancel-product-order]').isDisabled());assert(await field('one').isDisabled());
   await page.waitForFunction(()=>!state.productOrderSaving);
   assert(await page.locator('[data-save-product-order]').evaluate(e=>e===document.activeElement),'failed save focuses retry');
   assert.deepEqual(await order(),['five','one','two','three','four']);
   assert.deepEqual(await page.evaluate(()=>state.products.map(i=>i.id)),original);
   failSave=false;await page.locator('[data-save-product-order]').click();
   await page.waitForFunction(()=>!state.productOrderDraft&&!state.productOrderSaving);
   assert(await page.locator('[data-start-product-order]').evaluate(e=>e===document.activeElement),'successful save restores sort focus');
   assert.equal(requestCount,before+2);assert.deepEqual(saved.items, ['five','one','two','three','four'].map(id=>({id,version:1})));
   assert.deepEqual(await page.evaluate(()=>state.products.map(i=>i.id)),['five','one','two','three','four']);
  }
  await page.locator('[data-start-product-order]').click();await page.locator('[data-save-product-order]').click();
  await page.waitForFunction(()=>state.productOrderSaving);
  await page.locator('#add-product-button').focus();
  assert(await page.locator('#add-product-button').evaluate(e=>e===document.activeElement),'waiting user can focus an available control');
  await page.waitForFunction(()=>!state.productOrderSaving);
  assert(await page.locator('#add-product-button').evaluate(e=>e===document.activeElement),'save completion must not steal new focus');
  await page.evaluate(()=>{state.products=[];renderProducts()});await page.locator('[data-start-product-order]').click();
  assert(await page.locator('[data-cancel-product-order]').evaluate(e=>e===document.activeElement),'empty sort focuses cancel');
  await page.locator('[data-cancel-product-order]').click();
  assert.deepEqual(errors,[]);
  console.log('Product numeric insertion: boundaries, stable shifting, Enter, focus, cancel, save/409 retry and payload versions passed; zh/en at 1440px and 320px. All API requests isolated.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
