// Isolated API fixtures; never saves a real configuration or submits an inquiry.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 fs.mkdirSync('tmp/summary-footer',{recursive:true});
 let checks=0;
 try {
  for(const lang of ['zh','en']) {
   const page=await browser.newPage({viewport:{width:430,height:932},hasTouch:true,reducedMotion:'reduce'});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(l=>localStorage.setItem('boten-language',l),lang);
   await page.route('**/api/**',async route=>{
    assert.equal(route.request().method(),'GET');
    const p=new URL(route.request().url()).pathname;
    let data={items:[],total:0};
    if(p==='/api/v1/products')data={items:[{id:'qa',visible_zh:true,visible_en:true}]};
    if(p.endsWith('/snapshot'))data={id:'qa',model:'BOTEN CR1016',name:'Multi-Functional Injector & Pump Test Bench',colors:[{code:'red',name:'Red',is_default:true}],base_option_groups:[{type:'motor',name:'Motor',options:[{id:'motor',name:'22kW'}]}],optional_categories:[{id:'cri',name:'Test kits / 测试套件',multiple:true,options:Array.from({length:40},(_,i)=>({id:'opt'+i,code:'BTK-'+i,name:'Long selected configuration / 已选配置 '.repeat(2)}))}]};
    await route.fulfill({json:data});
   });
   await page.goto('http://127.0.0.1:8082/');await page.waitForLoadState('networkidle');
   await page.locator('#home-device:not([disabled])').click();
   await page.evaluate(()=>document.fonts.ready);
   for(const [width,height] of [[430,932],[320,568],[768,600],[844,390],[390,350],[1440,900]]){
    await page.setViewportSize({width,height});
    await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
    for(const long of [false,true]){
     await page.evaluate(isLong=>{
      state.setAllOptions('cri',isLong?Array.from({length:40},(_,i)=>'opt'+i):[]);
      const status=document.getElementById('config-save-status');status.hidden=!isLong;status.textContent='Please retry / 请重试。'.repeat(20);
     },long);
     if(width<1024)await page.locator('#summary-toggle').click();
     await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
     if(long&&width<1024){
      await page.evaluate(()=>{document.querySelector('.summary-content').scrollTop=0;setConfigSaveStatus('Save failed / 保存失败。'.repeat(20),'error');});
      await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
      assert(await page.locator('.summary-content').evaluate(e=>e.scrollTop>0),'save feedback not scrolled into view');
     }
     const before=await page.locator('.summary-actions').boundingBox();
     assert.equal(await page.locator('#summary-model #summary-base-options .summary-base-row').count(),2);
     assert.equal(await page.locator('#summary-list .summary-base-row').count(),0);
     for(const entry of await page.locator('#summary-model .summary-label, #summary-model-code, #summary-model-name, #summary-base-options dt, #summary-base-options dd').all()) {
      assert.equal(await entry.evaluate(e=>getComputedStyle(e).fontSize),'14px');
     }
     const modelBefore=await page.locator('#summary-model').boundingBox();
     const body=page.locator(width<1024?'.summary-content':'#summary-list');
     if(long){
      assert(await body.evaluate(e=>e.scrollHeight>e.clientHeight),'long list must scroll');
      await body.evaluate(e=>e.scrollTop=e.scrollHeight);
      if(width<1024)await page.locator('#summary-panel').evaluate(e=>e.scrollTop=200);
     }
     const after=await page.locator('.summary-actions').boundingBox();
     if(width>=1024) assert.equal((await page.locator('#summary-model').boundingBox()).y,modelBefore.y,'base module moved with optional list');
     assert.equal(after.y,before.y,`${lang} ${width} ${long}: footer moved during scrolling`);
     assert(after.y>=0&&after.y+after.height<=height,'footer clipped');
     assert(await page.locator('#summary-panel').evaluate(e=>e.scrollWidth<=e.clientWidth+1),'horizontal overflow');
     if(width<1024){
      assert(await body.evaluate(e=>e.clientHeight>40),'body collapsed');
      assert(await page.locator('#summary-panel').evaluate(e=>e.scrollTop===0),'outer panel scrolls');
      await page.locator('#save-cart').click({trial:true});
      await page.locator('#sales-contact-open').click({trial:true});
      if(long&&[430,844].includes(width))await page.screenshot({path:`tmp/summary-footer/${lang}-${width}.png`});
      await page.keyboard.press('Escape');
      assert(await page.locator('#summary-toggle').evaluate(e=>e===document.activeElement),'focus not restored');
     }
     checks++;
    }
   }
   assert.deepEqual(errors,[]);await page.close();
  }
  console.log('PASS',checks,'summary footer cases: zh/en, short/long, mobile/landscape/desktop, fixed actions, scroll body, click targets, Escape/focus.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
