// Serve local source, intercept every API request: never change real catalog/business data.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
(async () => {
 const browser = await chromium.launch({channel:'msedge',headless:true});
 const page = await browser.newPage(); const errors=[], writes=[];
 let ready=false, empty=false, allHidden=false, delaySave=false;
 const products=[{id:'first',visible_zh:1,visible_en:1},{id:'cr918s',visible_zh:1,visible_en:0},{id:'cr1016',visible_zh:1,visible_en:1},{id:'no-color',visible_zh:1,visible_en:1}];
 const editor={id:'cr918s',version:3,model:'BOTEN CR918S',product_name_zh:'中文设备',product_name_en:'English device',enabled:true,visible_zh:true,visible_en:false,colors:[{code:'red',label:'红色',label_en:'Red',enabled:true,is_default:true}],base_option_groups:[],price_variants:[],images:[],specifications:[],optional_config_ids:[]};
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{sessionStorage.setItem('boten_user_token','fixture');sessionStorage.setItem('boten_admin_token','fixture');if(!localStorage.getItem('boten-language'))localStorage.setItem('boten-language','zh');});
 await page.route('**/api/v1/**',async route=>{
  const req=route.request(),url=new URL(req.url()),p=url.pathname;
  if(req.method()!=='GET'){
   const body=req.postDataJSON();writes.push({p,body});
   if(delaySave)await new Promise(r=>setTimeout(r,300));
   return route.fulfill({json:p.endsWith('/editor')?{...editor,...body}:{id:'fixture-config',inquiry_number:'RFQ-FIXTURE'}});
  }
  if(p.endsWith('/auth/me')||p.endsWith('/auth/profile'))return route.fulfill({json:{id:'qa',display_name:'QA',role:'admin',email:'qa@example.invalid'}});
  if(p==='/api/v1/products')return route.fulfill({json:{items:empty?[]:products.map(i=>({...i,visible_en:allHidden?0:i.visible_en}))}});
  if(p.endsWith('/snapshot')){
   const id=decodeURIComponent(p.split('/')[4]);const complete=id!=='cr918s'||ready;
   return route.fulfill({json:{id,schema_version:2,model:'BOTEN '+id,name:url.searchParams.get('lang')==='en'?'English '+id:'中文 '+id,colors:id==='no-color'?[]:[{code:'red',name:'Red',is_default:true}],base_option_groups:complete?[{type:'motor',name:'Motor',required:true,options:[{id:'default-motor',name:'Default'},{id:'other-motor',name:'Other'}]}]:[],optional_categories:[],images:[]}});
  }
  if(p.endsWith('/products/cr918s/editor'))return route.fulfill({json:editor});
  return route.fulfill({json:{items:[],total:0,options:[]}});
 });
 async function load(url='/'){await page.goto('http://127.0.0.1:8081'+url);await page.waitForLoadState('networkidle');}
 async function choose(id){await page.evaluate(id=>{state.setModel(id);window.botenShowDeviceSelection(id);},id);}
 async function assertBlocked(){assert(await page.locator('#save-cart').isDisabled());assert(await page.locator('#sales-contact-open').isDisabled());assert(await page.locator('#configuration-availability').isVisible());}
 try {
  await load();
  assert.equal(await page.evaluate(()=>state.currentModelId),'first','first visible device follows saved order');
  assert(await page.locator('#device-select option[value="device:cr918s"]').count());
  await choose('cr918s');await assertBlocked();
  const before=writes.length;
  await page.evaluate(async()=>{addCurrentConfigToCart();requestCurrentInquiry();openInquiryDialog('current_device');await saveCurrentConfigToServer();});
  assert.equal(writes.length,before,'blocked entrypoints cannot write');await assertBlocked();
  await page.reload();await page.waitForLoadState('networkidle');assert.equal(await page.evaluate(()=>state.currentModelId),'cr918s');
  await page.locator('#language-switcher [data-language=en]').click();await page.waitForLoadState('networkidle');
  assert.equal(await page.evaluate(()=>state.currentModelId),'first');
  assert.equal(await page.locator('#device-select option[value="device:cr918s"]').count(),0);
  assert(await page.evaluate(()=>configData.models.some(i=>i.id==='cr918s')),'history data remains loaded');
  await page.evaluate(()=>{state.setModel('cr918s');state.selections.motor='other-motor';sessionStorage.setItem('boten-language-config',JSON.stringify(state.getSnapshot()));});
  await page.reload();await page.waitForLoadState('networkidle');
  assert.equal(await page.evaluate(()=>state.currentModelId),'first');assert.equal(await page.evaluate(()=>state.selections.motor),'default-motor');
  allHidden=true;await page.reload();await page.waitForLoadState('networkidle');
  assert.equal(await page.evaluate(()=>state.currentModelId),null);await assertBlocked();
  assert.match(await page.locator('#page-title').textContent(),/No devices/);
  assert.equal(await page.locator('#device-select option[value="catalog:tools"]').count(),1);
  await page.locator('#catalog-stage-toggle').click();await page.locator('[data-catalog-drawer-select="catalog:tools"]').click();assert(await page.locator('#catalog-marketplace').isVisible());
  await page.evaluate(()=>openCartPanel());assert(await page.locator('#cart-panel').evaluate(e=>e.classList.contains('open')));await page.evaluate(()=>closeCartPanel());
  empty=true;await page.evaluate(()=>sessionStorage.setItem('boten-page-selection-view','device'));await load();assert.equal(await page.evaluate(()=>window.catalogSource),'api');assert.equal(await page.evaluate(()=>state.currentModelId),null);await assertBlocked();
  empty=false;allHidden=false;await page.evaluate(()=>localStorage.setItem('boten-language','zh'));await load();
  await choose('no-color');await assertBlocked();assert(!(await page.locator('#summary-list').textContent()).includes('undefined'));
  await choose('first');assert(!(await page.locator('#save-cart').isDisabled()));
  delaySave=true;const saving=page.evaluate(()=>saveCurrentConfigToServer());await page.waitForFunction(()=>currentConfigSaving);await choose('cr918s');await saving;await assertBlocked();delaySave=false;await page.evaluate(()=>closeCartPanel());
  ready=true;await load();await choose('cr918s');assert(!(await page.locator('#save-cart').isDisabled()));assert(!(await page.locator('#sales-contact-open').isDisabled()));
  await page.evaluate(()=>saveCurrentConfigToServer());assert.deepEqual(writes.at(-1).body.selections,{motor:'default-motor'});assert.equal(writes.at(-1).body.product_id,'cr918s');await page.evaluate(()=>closeCartPanel());
  await page.evaluate(()=>openInquiryDialog('current_device'));await page.locator('.inquiry-dialog button[value=submit]').click();
  await page.waitForFunction(()=>document.querySelector('.inquiry-dialog-status')?.textContent.includes('RFQ-FIXTURE'));
  assert.equal(writes.at(-1).body.product_id,'cr918s');
  await load('/admin/#products');
  fs.mkdirSync('tmp/catalog-readiness',{recursive:true});
  for(const [width,height] of [[1355,838],[320,568],[844,390]]){
   await page.setViewportSize({width,height});await page.evaluate(()=>openProductEditor('cr918s'));
   const dialog=page.locator('#product-dialog');
   const geometry=await dialog.evaluate(d=>{const f=d.querySelector('footer').getBoundingClientRect(),r=d.getBoundingClientRect(),b=d.querySelector('#save-product-button').getBoundingClientRect(),c=d.querySelector('[name=visible_zh]').getBoundingClientRect();return {bottom:f.bottom,dialogBottom:r.bottom,buttonBottom:b.bottom,buttonRight:b.right,right:r.right,checkbox:c.width,height:c.height};});
   assert(geometry.bottom<=height&&geometry.buttonBottom<=geometry.dialogBottom&&geometry.buttonRight<=geometry.right);
   assert.equal(geometry.checkbox,18);assert.equal(geometry.height,18);
   assert(await dialog.locator('[name=visible_zh]').isChecked());assert(!(await dialog.locator('[name=visible_en]').isChecked()));
   await page.screenshot({path:`tmp/catalog-readiness/footer-${width}x${height}.png`});
   const cancelCount=writes.length;await dialog.locator('[name=visible_en]').check();await dialog.locator('footer button[value=cancel]').click();
   if(await page.locator('.confirm-dialog').isVisible())await page.locator('.confirm-dialog button[value=confirm]').click();
   await page.waitForFunction(()=>!document.getElementById('product-dialog').open);assert.equal(writes.length,cancelCount);
   await page.evaluate(()=>openProductEditor('cr918s'));assert(!(await dialog.locator('[name=visible_en]').isChecked()));
   await dialog.locator('[name=visible_zh]').uncheck();const count=writes.length;await dialog.locator('#save-product-button').click();
   assert.equal(writes.length,count);assert(await dialog.isVisible());assert((await dialog.textContent()).includes('至少选择一种'));
   await dialog.locator('[name=visible_en]').check();await dialog.locator('#save-product-button').click();await page.waitForFunction(()=>!document.getElementById('product-dialog').open);
   assert.equal(writes.at(-1).body.visible_zh,false);assert.equal(writes.at(-1).body.visible_en,true);assert.equal(writes.at(-1).body.enabled,true);assert.equal(writes.at(-1).body.version,3);
  }
  assert.deepEqual(errors,[]);console.log('PASS: incomplete/empty catalogs, language fallback, selection isolation, submission guards/recovery, admin footer layouts and save validation; all writes intercepted.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
