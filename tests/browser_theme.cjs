// All API traffic is intercepted. Theme changes never touch NAS data.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
  fs.mkdirSync('tmp/theme-review',{recursive:true});
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    for(const lang of ['zh','en']) for(const width of [1280,393]) {
      const context=await browser.newContext({viewport:{width,height:852},colorScheme:'dark'});
      await context.addInitScript(l=>{
        sessionStorage.setItem('boten_user_token','fixture-only');
        if(!localStorage.getItem('boten-language')) localStorage.setItem('boten-language',l);
      },lang);
      let writes=0;
      await context.route('**/api/**',async route=>{
        const req=route.request(), p=new URL(req.url()).pathname;
        if(req.method()!=='GET'){writes++;return route.abort();}
        let data={items:[],total:0};
        if(p.endsWith('/auth/profile')||p.endsWith('/auth/me'))data={id:'qa',role:'customer',display_name:'Theme Test',email:'theme@example.invalid',version:1};
        if(p==='/api/v1/products')data={items:[{id:'qa',visible_zh:true,visible_en:true}]};
        if(p.endsWith('/snapshot')) data={id:'qa',model:'BOTEN QA',name:'Test equipment',colors:[{code:'red',name:'Red'}],base_option_groups:[],optional_categories:[{id:'cri',name:'Configuration / 配置',description:'Long description for theme test',multiple:true,options:Array.from({length:12},(_,i)=>({id:'opt'+i,code:'BTK-'+i,name:'Test configuration '+i,image_path:'assets/images/placeholder-option.svg'}))}],images:[]};
        await route.fulfill({json:data});
      });
      const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
      await page.goto('http://127.0.0.1:8082/');
      await page.locator('#home-device:not([disabled])').click();
      await page.locator('.option-card-config').first().waitFor();
      assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
      const darkLogo = await page.locator('.brand-logo').evaluate(e => {
        const style = getComputedStyle(e);
        return { background: style.backgroundColor, filter: style.filter, radius: style.borderRadius };
      });
      assert.equal(darkLogo.background, 'rgba(0, 0, 0, 0)');
      assert.match(darkLogo.filter, /brightness\(0\).*invert\(1\)/);
      assert.equal(darkLogo.radius, '0px');
      await page.emulateMedia({colorScheme:'light'});
      await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');
      assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
      await page.locator('#account-toggle').click();
      const toggle=page.locator('#account-theme-toggle');
      assert.equal(await toggle.textContent(),lang==='en'?'Dark Mode':'深色模式');
      assert.equal(await toggle.evaluate(e=>e.nextElementSibling.id),'account-logout');
      const selection=await page.evaluate(()=>JSON.stringify(state.getSnapshot()));
      await toggle.focus(); await page.keyboard.press('Space');
      assert.equal(await toggle.getAttribute('aria-checked'),'true');
      assert(await page.locator('#account-menu').isVisible());
      assert.equal(await page.evaluate(()=>JSON.stringify(state.getSnapshot())),selection);
      await page.keyboard.press('ArrowDown');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'account-logout');
      await page.keyboard.press('ArrowUp');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'account-theme-toggle');
      await page.screenshot({path:`tmp/theme-review/home-${lang}-${width}.png`});
      await page.keyboard.press('Escape');
      for(const id of ['auth-dialog','share-dialog','sales-contact-dialog']) {
        await page.locator('#'+id).evaluate(e=>e.showModal());
        const box=await page.locator('#'+id).boundingBox();
        assert(box && box.x>=0 && box.x+box.width<=width+1,'dialog overflow '+id);
        await page.screenshot({path:`tmp/theme-review/${id}-${lang}-${width}.png`});
        await page.locator('#'+id).evaluate(e=>e.close());
      }
      await page.reload(); await page.waitForLoadState('domcontentloaded');
      assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
      const bodyColor=await page.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor);
      assert.equal(bodyColor,'rgb(20, 24, 30)');
      await page.emulateMedia({media:'print'});
      assert.notEqual(await page.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor),bodyColor);
      await page.emulateMedia({media:'screen'});
      await page.goto('http://127.0.0.1:8082/account/');
      await page.locator('#profile-display-name').waitFor({state:'visible'});
      await page.locator('#profile-display-name').fill('Unsaved draft');
      await page.evaluate(()=>{localStorage.setItem('boten-theme','light');dispatchEvent(new StorageEvent('storage',{key:'boten-theme',newValue:'light'}));});
      assert.equal(await page.locator('#profile-display-name').inputValue(),'Unsaved draft');
      await page.evaluate(()=>{localStorage.setItem('boten-theme','dark');dispatchEvent(new StorageEvent('storage',{key:'boten-theme',newValue:'dark'}));});
      const profileLogo = await page.locator('.profile-brand img').evaluate(e => {
        const style = getComputedStyle(e);
        return { background: style.backgroundColor, filter: style.filter };
      });
      assert.equal(profileLogo.background, 'rgba(0, 0, 0, 0)');
      assert.match(profileLogo.filter, /brightness\(0\).*invert\(1\)/);
      await page.screenshot({path:`tmp/theme-review/account-${lang}-${width}.png`});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      await page.goto('http://127.0.0.1:8082/admin/');
      assert.equal(await page.locator('html').getAttribute('data-theme'),null);
      assert.equal(writes,0);assert.deepEqual(errors,[]);
      console.log('PASS theme',lang,width);await context.close();
    }
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
