const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  for(const lang of ['zh','en']){
   const page=await browser.newPage();let hiddenId;
   await page.addInitScript(language=>localStorage.setItem('boten-language',language),lang);
   await page.route('**/api/v1/**',async route=>{
    if(route.request().method()!=='GET')return route.abort();
    if(new URL(route.request().url()).pathname==='/api/v1/products'){
     const response=await route.fetch();const data=await response.json();hiddenId=data.items[0].id;
     data.items[0].visible_zh=false;data.items[0].visible_en=true;
     return route.fulfill({json:data});
    }
    return route.continue();
   });
   await page.goto('http://127.0.0.1:8081/');await page.waitForLoadState('networkidle');
   assert(await page.evaluate(id=>configData.models.some(model=>model.id===id),hiddenId));
   await page.locator('#catalog-stage-toggle').click();await page.locator('#catalog-device-entry').click();
   assert.equal(await page.locator(`[data-catalog-drawer-select="device:${hiddenId}"]`).count(),lang==='en'?1:0);
   await page.close();
  }
  console.log('Language navigation filtering preserves full device data: zh/en passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
