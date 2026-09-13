// Read-only fixtures: no request reaches the NAS API.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const origin = 'http://127.0.0.1:8082';
async function fixture(context, control) {
  await context.route('**/api/**', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname;
    assert.equal(request.method(), 'GET', 'Homepage must not write business data');
    if (control.fail && path === '/api/v1/products') return route.fulfill({status:503,json:{detail:'Fixture unavailable'}});
    if (control.failTools && path.endsWith('/catalog/items') && url.searchParams.get('type')==='tools') return route.fulfill({status:503,json:{detail:'Fixture unavailable'}});
    let data = {items:[],total:0};
    if (path.endsWith('/auth/me') || path.endsWith('/auth/profile')) data={id:'fixture',role:'customer',display_name:'Homepage QA',email:'home@example.invalid',version:1};
    if (path === '/api/v1/products') data={items:control.empty?[]:[{id:'qa',visible_zh:true,visible_en:false},{id:'second',visible_zh:true,visible_en:true}]};
    if (path.endsWith('/snapshot')) data={id:path.includes('/qa/')?'qa':'second',model:path.includes('/qa/')?'BOTEN QA':'BOTEN SECOND',name:'Test equipment / 测试设备',colors:[{code:'red',name:'Red'}],base_option_groups:[],optional_categories:[{id:'cri',name:'Configuration',multiple:true,options:Array.from({length:8},(_,i)=>({id:'opt'+i,code:'BTK-'+i,name:'Test option '+i,image_path:'assets/images/placeholder-option.svg'}))}],images:[]};
    if (path.endsWith('/catalog/items')) data={items:control.empty?[]:[{id:'tool',code:'T-1',name:'Fixture tool',image_path:'assets/images/placeholder-option.svg'}]};
    await route.fulfill({json:data});
  });
}
(async()=>{
  fs.mkdirSync('tmp/home-review',{recursive:true});
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    for (const lang of (process.argv.includes('--flows-only') ? [] : ['zh','en'])) for (const theme of ['light','dark']) for(const [width,height] of [[1440,900],[1024,768],[768,1024],[430,932],[393,852],[320,568],[844,390]]) {
      const context=await browser.newContext({viewport:{width,height},colorScheme:theme});
      await context.addInitScript(l=>localStorage.setItem('boten-language',l),lang);
      await fixture(context,{});
      const page=await context.newPage(), errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.goto(origin);
      await page.locator('#home-device:not([disabled])').waitFor();
      assert.equal(await page.locator('body').getAttribute('data-selection-view'),'home');
      assert.equal(await page.locator('#home-device-model').textContent(),lang==='zh'?'BOTEN QA':'BOTEN SECOND');
      if (lang === 'zh') {
        const before = await page.evaluate(()=>JSON.stringify(state.getSnapshot()));
        await page.locator('#home-device-next').click();
        assert.equal(await page.locator('#home-device-model').textContent(),'BOTEN SECOND');
        assert.equal(await page.evaluate(()=>JSON.stringify(state.getSnapshot())),before,'carousel must not change configuration');
        await page.locator('#home-device').click();
        assert.equal(await page.evaluate(()=>state.currentModelId),'second');
        await page.locator('a.brand').click();
        await page.locator('#home-device-prev').click();
        assert.equal(await page.locator('#home-device-model').textContent(),'BOTEN QA');
        await page.locator('#home-device-next').focus();
        await page.keyboard.press('ArrowLeft');
        assert.equal(await page.locator('#home-device-model').textContent(),'BOTEN SECOND');
        await page.keyboard.press('ArrowRight');
        assert.equal(await page.locator('#home-device-model').textContent(),'BOTEN QA');
      } else assert.equal(await page.locator('#home-carousel-arrows').isVisible(),false);
      assert.equal(await page.locator('#summary-toggle').isVisible(),false);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`overflow ${width}`);
      for(const selector of ['#home-browse','[data-home-catalog="tools"]','[data-home-catalog="accessories"]']) {
        assert((await page.locator(selector).boundingBox()).height>=44);
      }
      if ([1440,393].includes(width)) await page.screenshot({path:`tmp/home-review/${lang}-${theme}-${width}.png`,fullPage:true});
      await page.locator('#home-browse').click();
      await page.locator('#catalog-model-drawer.open').waitFor();
      await page.keyboard.press('Escape');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'home-browse');
      await page.locator('#home-device').click();
      await page.locator('.option-card-config').first().waitFor();
      await page.locator('.option-card-config').first().click();
      const selection=await page.evaluate(()=>JSON.stringify(state.getSnapshot()));
      await page.locator('a.brand').click();
      await page.locator('#home-page').waitFor();
      assert.equal(await page.evaluate(()=>JSON.stringify(state.getSnapshot())),selection);
      await page.waitForFunction(()=>scrollY===0);
      await page.locator('#catalog-drawer-toggle').click();
      assert.equal(await page.locator('.catalog-drawer-menu > button').first().getAttribute('id'),'catalog-home-entry');
      assert.equal(await page.locator('#catalog-home-entry').getAttribute('aria-current'),'page');
      assert.equal(await page.locator('#catalog-home-entry img').count(),0);
      await page.locator('#catalog-home-entry').click();
      await page.locator('[data-home-catalog="tools"]').click();
      assert.equal(await page.locator('body').getAttribute('data-selection-view'),'catalog:tools');
      await page.reload();
      await page.waitForFunction(()=>document.body.dataset.selectionView==='catalog:tools');
      await page.locator('a.brand').click();
      await page.locator('[data-home-catalog="accessories"]').click();
      assert.equal(await page.locator('body').getAttribute('data-selection-view'),'catalog:accessories');
      await page.goto(origin);
      await page.locator('#home-device:not([disabled])').waitFor();
      assert.equal(await page.locator('body').getAttribute('data-selection-view'),'home');
      assert.deepEqual(errors,[]);
      console.log('PASS homepage',lang,theme,width,height);
      await context.close();
    }
    {
      const context=await browser.newContext({viewport:{width:393,height:852}});
      await context.addInitScript(()=>sessionStorage.setItem('boten_user_token','fixture-only'));
      await fixture(context,{}); const page=await context.newPage();
      await page.goto(origin);await page.waitForLoadState('networkidle');
      await page.locator('#account-toggle').click();
      await page.locator('#account-theme-toggle').click();
      assert.equal(await page.locator('body').getAttribute('data-selection-view'),'home');
      await page.keyboard.press('Escape');
      await page.locator('#language-switcher button:visible').click();
      await page.waitForFunction(()=>document.querySelector('#home-title')?.textContent==='Test Equipment & Service Tools');
      await page.locator('#home-device:not([disabled])').waitFor();
      await page.waitForLoadState('networkidle');
      assert.equal(await page.locator('body').getAttribute('data-selection-view'),'home');
      await page.evaluate(()=> {
        serverCart=[savedConfigToCartItem({id:'fixture-cart',snapshot:{product:{id:'second',name:'BOTEN SECOND'},color:{code:'red'},categories:[{id:'cri',name:'CRI',multiple:true,options:[{id:'opt2',code:'BTK-2',name:'Saved option'}]}]}})];
        renderCartPanel(); renderCartCount();
      });
      await page.locator('#cart-toggle').click();
      assert(await page.locator('#main-content').evaluate(e=>e.inert));
      await page.locator('.cart-item-edit').click();
      assert.equal(await page.locator('body').getAttribute('data-selection-view'),'device');
      assert.deepEqual(await page.evaluate(()=>state.selections.cri),['opt2']);
      await page.locator('a.brand').click();
      assert.equal(await page.evaluate(()=>serverCart.length),1);
      assert.equal(await page.evaluate(()=>editingConfig.id),'fixture-cart');
      assert.deepEqual(await page.evaluate(()=>state.selections.cri),['opt2']);
      console.log('PASS homepage language, theme, cart edit and retained draft');
      await context.close();
    }
    for(const mode of ['fail','empty','failTools']) {
      const context=await browser.newContext(); const control={[mode]:true};
      await fixture(context,control);const page=await context.newPage();
      await page.goto(origin); await page.locator('#home-page').waitFor();
      if(mode==='fail') {
        await page.locator('#home-retry').waitFor();
        control.fail=false;await page.locator('#home-retry').click();
        await page.locator('#home-device:not([disabled])').waitFor();
      } else if(mode==='empty') {
        await page.waitForFunction(()=>document.querySelector('#home-device-status').textContent==='暂无可用产品');
        assert(await page.locator('#home-browse').isDisabled());
      } else {
        await page.locator('[data-home-retry="tools"]').waitFor();
        control.failTools=false;await page.locator('[data-home-retry="tools"]').click();
        await page.locator('[data-home-retry="tools"]').waitFor({state:'hidden'});
      }
      console.log('PASS homepage',mode);await context.close();
    }
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
