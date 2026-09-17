const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try { for(const width of [1440,393,320]) {
    const page=await browser.newPage({viewport:{width,height:900}});
    await page.route('**/api/**',async route=>{
      assert.equal(route.request().method(),'GET');
      const path=new URL(route.request().url()).pathname;
      let data={items:[],total:0};
      if(path==='/api/v1/products')data={items:['one','two'].map(id=>({id,visible_zh:true,visible_en:true}))};
      if(path.endsWith('/snapshot'))data={id:path.split('/')[4],model:path.split('/')[4],name:'Test title',colors:[],base_option_groups:[],optional_categories:[],images:[]};
      await route.fulfill({json:data});
    });
    await page.clock.install({time:new Date('2026-01-01T00:00:00Z')});
    await page.clock.pauseAt(new Date('2026-01-01T00:00:01Z'));
    await page.goto('http://127.0.0.1:8082/');
    await page.locator('#home-device:not([disabled])').waitFor();
    const name=()=>page.locator('#home-device-model').textContent();
    // Reset the interval after all startup observer callbacks have settled.
    await page.locator('.home-carousel').dispatchEvent('mouseenter');
    await page.locator('.home-carousel').dispatchEvent('mouseleave');
    await page.clock.runFor(4999); assert.equal(await name(),'one');
    await page.clock.runFor(1); assert.equal(await name(),'two');
    const img=await page.locator('.home-device-viewport').boundingBox();
    for(const side of ['prev','next']) {
      const box=await page.locator('#home-device-'+side).boundingBox();
      assert(Math.abs(box.y+box.height/2-img.y-img.height/2)<2,'arrow must center on image');
      assert(box.x>=img.x && box.x+box.width<=img.x+img.width+1);
    }
    await page.locator('.home-carousel').dispatchEvent('mouseenter');
    await page.clock.runFor(10000); assert.equal(await name(),'two');
    await page.locator('.home-carousel').dispatchEvent('mouseleave');
    await page.clock.runFor(5000); assert.equal(await name(),'one');
    assert.equal(await page.locator('.home-carousel-header, #home-device-play, #home-device-position').count(),0);
    await page.clock.runFor(5000); assert.equal(await name(),'two');
    await page.locator('#home-device-next').focus();
    await page.clock.runFor(10000); assert.equal(await name(),'two');
    await page.locator('#home-title').focus();
    await page.clock.runFor(5000); assert.equal(await name(),'one');
    await page.evaluate(()=>document.body.dataset.selectionView='device');
    await page.clock.runFor(10000); assert.equal(await name(),'one');
    await page.evaluate(()=>document.body.dataset.selectionView='home');
    await page.clock.runFor(5000); assert.equal(await name(),'two');
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.reload(); await page.locator('#home-device:not([disabled])').waitFor();
    await page.clock.runFor(10000); assert.equal(await name(),'one');
    console.log('PASS autoplay, pause, view, reduced motion, centered arrows',width);
    await page.close();
  }} finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
