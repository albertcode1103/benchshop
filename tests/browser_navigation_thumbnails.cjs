// All API calls intercepted: no real catalog or customer records are changed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
(async () => {
 const browser = await chromium.launch({channel:'msedge',headless:true});
 const errors=[];
 fs.mkdirSync('tmp/navigation-thumbnails',{recursive:true});
 try {
  for(const lang of ['zh','en']) {
   const page=await browser.newPage(); let unavailable=false, empty=false;
   page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(lang=>localStorage.setItem('boten-language',lang),lang);
   await page.route('**/thumb-fixture/**',r=>r.request().url().includes('broken')
    ?r.fulfill({status:404,body:''})
    :r.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="180" height="90"><rect width="180" height="90" fill="#888"/></svg>'}));
   await page.route('**/api/v1/**',async r=>{
    assert.equal(r.request().method(),'GET');
    const u=new URL(r.request().url()),p=u.pathname;
    if(p==='/api/v1/products')return r.fulfill({json:{items:empty?[]:[{id:'first',visible_zh:1,visible_en:0},{id:'second',visible_zh:1,visible_en:1},{id:'missing',visible_zh:1,visible_en:1},{id:'broken',visible_zh:1,visible_en:1}]}});
    if(p.endsWith('/snapshot')){const id=p.split('/')[4];return r.fulfill({json:{id,schema_version:2,model:'BOTEN '+id,name:'Long product name 长产品名称 '.repeat(4),colors:[],base_option_groups:[],optional_categories:[],images:id==='missing'?[]:[{path:`/thumb-fixture/${id}.svg`},{path:'/thumb-fixture/not-first.svg'}]}});}
    if(p==='/api/v1/catalog/items')return r.fulfill(unavailable?{status:503,json:{detail:'Unavailable'}}:{json:{items:empty?[]:[{id:'one',image_path:u.searchParams.get('type')==='tools'?'/thumb-fixture/tools.svg':null},{id:'two',image_path:'/thumb-fixture/should-not-use.svg'}]}});
    return r.fulfill({json:{items:[],options:[],total:0}});
   });
   await page.goto('http://127.0.0.1:8081/');await page.waitForLoadState('networkidle');
   for(const [width,height] of [[1428,852],[640,600],[390,844],[320,568],[844,390]]){
    await page.setViewportSize({width,height});
    await page.locator('#catalog-stage-toggle').click();await page.waitForLoadState('networkidle');
    const first=lang==='zh'?'first':'second';
    assert((await page.locator('#catalog-device-entry img').getAttribute('src')).endsWith(`${first}.svg`));
    assert((await page.locator('[data-catalog-drawer-select="catalog:tools"] img').getAttribute('src')).endsWith('/tools.svg'));
    assert((await page.locator('[data-catalog-drawer-select="catalog:accessories"] img').getAttribute('src')).endsWith('placeholder-option.svg'),'missing first item must not use second item');
    await page.locator('#catalog-device-entry').click();await page.waitForTimeout(300);
    assert.equal(await page.locator('#catalog-navigation-drawer').evaluate(e=>e.inert),width<640);
    if(width<640){
     for(const key of ['Shift+Tab','Tab'])for(let i=0;i<8;i++){
      await page.keyboard.press(key);
      assert(await page.locator('#catalog-model-drawer').evaluate(e=>e.contains(document.activeElement)),'focus stays in top drawer');
     }
    }
    await page.waitForFunction(()=>document.querySelector('[data-catalog-drawer-select="device:broken"] img')?.src.endsWith('placeholder-option.svg'));
    assert((await page.locator('[data-catalog-drawer-select="device:missing"] img').getAttribute('src')).endsWith('placeholder-option.svg'));
    const geometry=await page.locator('#catalog-model-list button').evaluateAll(buttons=>buttons.map(b=>{const i=b.querySelector('img'),r=i.getBoundingClientRect(),t=b.querySelector('.catalog-navigation-copy').getBoundingClientRect(),c=b.getBoundingClientRect();return{w:r.width,h:r.height,fit:getComputedStyle(i).objectFit,right:r.right,textLeft:t.left,textRight:t.right,cardRight:c.right,overflow:b.scrollWidth>b.clientWidth,alt:i.alt};}));
    for(const g of geometry){assert.equal(g.w,48);assert.equal(g.h,48);assert.equal(g.fit,'contain');assert(g.right<g.textLeft&&g.textRight<g.cardRight);assert(!g.overflow);assert.equal(g.alt,'');}
    await page.screenshot({path:`tmp/navigation-thumbnails/${lang}-${width}x${height}.png`});
    await page.keyboard.press('Escape');assert(await page.locator('#catalog-stage-toggle').evaluate(e=>document.activeElement===e));
   }
   await page.locator('#catalog-stage-toggle').click();await page.locator('#catalog-device-entry').click();await page.locator('[data-catalog-drawer-select="device:second"] img').click();
   assert.equal(await page.evaluate(()=>state.currentModelId),'second');assert.equal(await page.locator('#catalog-navigation-drawer').getAttribute('aria-hidden'),'true');
   await page.setViewportSize({width:1428,height:852});await page.locator('#catalog-stage-toggle').click();await page.locator('#catalog-device-entry').click();
   await page.locator('#catalog-device-entry').focus();await page.setViewportSize({width:390,height:844});await page.waitForTimeout(100);
   assert(await page.locator('#catalog-navigation-drawer').evaluate(e=>e.inert));
   assert(await page.locator('#catalog-model-drawer').evaluate(e=>e.contains(document.activeElement)),'resize moves covered focus');
   await page.locator('#catalog-model-back').focus();await page.setViewportSize({width:1428,height:852});await page.waitForTimeout(100);
   assert(!(await page.locator('#catalog-navigation-drawer').evaluate(e=>e.inert)));
   assert(await page.locator('#catalog-model-list').evaluate(e=>e.contains(document.activeElement)),'desktop resize avoids hidden back button');
   await page.setViewportSize({width:390,height:844});await page.locator('#catalog-model-back').click();
   assert(!(await page.locator('#catalog-navigation-drawer').evaluate(e=>e.inert)));
   assert(await page.locator('#catalog-device-entry').evaluate(e=>e===document.activeElement));await page.keyboard.press('Escape');
   unavailable=true;await page.locator('#catalog-stage-toggle').click();await page.waitForLoadState('networkidle');
   assert((await page.locator('[data-catalog-drawer-select="catalog:tools"] img').getAttribute('src')).endsWith('placeholder-option.svg'));
   await page.keyboard.press('Escape');empty=true;unavailable=false;await page.reload();await page.waitForLoadState('networkidle');
   await page.locator('#catalog-stage-toggle').click();await page.waitForLoadState('networkidle');
   assert((await page.locator('#catalog-device-entry img').getAttribute('src')).endsWith('placeholder-option.svg'));
   await page.locator('#catalog-device-entry').click();await page.waitForTimeout(100);
   assert(await page.locator('#catalog-model-close').evaluate(e=>e===document.activeElement),'empty directory still focuses a visible control');
   await page.keyboard.press('Tab');assert(await page.locator('#catalog-model-back').evaluate(e=>e===document.activeElement));
   await page.locator('#catalog-model-back').click();
   await page.locator('[data-catalog-drawer-select="catalog:tools"] img').click();assert(await page.locator('#catalog-marketplace').isVisible());
   await page.close();
  }
  assert.deepEqual(errors,[]);console.log('PASS: navigation thumbnails, zh/en, five viewports, ordered first images, missing/broken/empty/error fallbacks, selection and focus; API writes prohibited.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
