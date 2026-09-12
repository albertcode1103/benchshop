// Isolated catalogs and cart: no writes or real customer records.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  for(const lang of ['zh','en'])for(const width of [430,1440]){
   const page=await browser.newPage({viewport:{width,height:932},reducedMotion:width===430?'reduce':'no-preference'});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(l=>localStorage.setItem('boten-language',l),lang);
   await page.route('**/api/**',async r=>{
    assert.equal(r.request().method(),'GET');const u=new URL(r.request().url()),p=u.pathname;
    let result={items:[],total:0};
    if(p==='/api/v1/products')result={items:['first','second'].map(id=>({id,visible_zh:true,visible_en:true}))};
    if(p.endsWith('/snapshot'))result={id:p.split('/')[4],model:'BOTEN '+p.split('/')[4],name:'Test equipment',colors:[{code:'red',name:'Red'}],base_option_groups:[],optional_categories:[{id:'cri',name:'CRI',multiple:true,options:Array.from({length:20},(_,i)=>({id:'opt'+i,code:'BTK-'+i,name:'Configuration '+i}))}],images:[]};
    if(p==='/api/v1/catalog/items'){
     // The view must remain at the top when delayed data finishes rendering.
     await new Promise(resolve=>setTimeout(resolve,200));
     result={items:Array.from({length:20},(_,i)=>({id:'item'+i,code:'BTC-'+i,name:'Test catalog item '+i,category_id:'qa',category_name:'QA'}))};
    }
    await r.fulfill({json:result});
   });
   await page.goto('http://127.0.0.1:8081/');await page.waitForLoadState('networkidle');
   await page.evaluate(()=>{window.getCatalogCartSnapshot=()=>[{optionId:'item0',quantity:3}];state.selectOption('cri','opt0',true);});
   const selected=await page.evaluate(()=>JSON.stringify(state.selections));
   for(const target of ['catalog:tools','catalog:accessories','device:second','device:first']){
    await page.evaluate(()=>window.scrollTo({top:650,behavior:'instant'}));
    assert(await page.evaluate(()=>scrollY>100),'start below the top: '+JSON.stringify(await page.evaluate(()=>({y:scrollY,height:document.documentElement.scrollHeight,overflow:document.body.style.overflow,dialogs:document.querySelectorAll('dialog[open]').length,view:document.body.dataset.selectionView,items:catalogMarketplaceState.items.length,status:document.getElementById('catalog-marketplace-status').textContent}))));
    await page.locator('#catalog-drawer-toggle').click();
    if(target.startsWith('device:'))await page.locator('#catalog-device-entry').click();
    await page.locator(`[data-catalog-drawer-select="${target}"]`).click();
    if(target.startsWith('catalog:'))await page.waitForFunction(()=>!catalogMarketplaceState.loading&&catalogMarketplaceState.items.length===20);
    await page.waitForLoadState('networkidle');await page.waitForTimeout(100);
    assert.equal(await page.evaluate(()=>scrollY),0,target+' starts at page top');
    assert.equal(await page.locator('#catalog-navigation-drawer').getAttribute('aria-hidden'),'true');
    assert.equal(await page.evaluate(()=>window.getCatalogCartSnapshot()[0].quantity),3,'cart state retained');
    if(target.startsWith('catalog:')){
     assert.equal(await page.evaluate(()=>JSON.stringify(state.selections)),selected,'category navigation does not reset device options');
     assert.equal(await page.locator('#catalog-marketplace-toggle-label').textContent(),lang==='en'?'Catalog':'目录');
     await page.locator('#catalog-marketplace-toggle').click();
     assert.equal(await page.locator('#catalog-navigation-drawer').getAttribute('aria-hidden'),'false');
     await page.keyboard.press('Escape');
    }
    else {
     assert.equal(await page.evaluate(()=>state.currentModelId),target.slice(7));
     assert.equal(await page.locator('#catalog-stage-toggle-label').textContent(),lang==='en'?'Catalog':'目录');
     await page.locator('#catalog-stage-toggle').click();
     assert.equal(await page.locator('#catalog-navigation-drawer').getAttribute('aria-hidden'),'false');
     await page.keyboard.press('Escape');
    }
   }
   await page.evaluate(()=>window.scrollTo({top:650,behavior:'instant'}));
   const before=await page.evaluate(()=>scrollY);
   await page.locator('#catalog-drawer-toggle').click();await page.keyboard.press('Escape');await page.waitForTimeout(100);
   assert.equal(await page.evaluate(()=>scrollY),before,'cancel does not reset scroll');
   assert.deepEqual(errors,[]);await page.close();
  }
  console.log('PASS: catalog/device navigation starts at scrollY=0; zh/en, desktop/mobile, reduced motion, delayed loading, cart and selection preservation, cancel retains position.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
