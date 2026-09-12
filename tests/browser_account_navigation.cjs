// Account layout regression. Static files + in-memory API fixtures only.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = process.cwd();
const out = path.resolve('tmp/account-navigation');
fs.mkdirSync(out, { recursive: true });
const panels = ['profile', 'account-contact', 'account-security', 'my-shares', 'my-inquiries', 'my-quotes'];
const sizes = [[1440,900], [1024,768], [900,700], [768,600], [640,720], [430,932], [390,844], [360,740], [320,568], [844,390], [390,350]];
const user = { id:'qa', role:'customer', display_name:'Account Layout Test', email:'long-account-contact@example.invalid', phone:'13800000000', phone_country:'CN', version:1 };
const timestamp = '2026-09-12T02:30:00Z';
const shares = [{ id:'share-1', code:'123456', title:'Long configuration / 长分享标题 '.repeat(4), status:'active', active:true, item_count:12, created_at:timestamp, expires_at:timestamp, customer_version:1 }];
const inquiries = [{ id:'inquiry-1', inquiry_number:'RFQ-BOTEN20260912-1234567890', status:'new', source_type:'cart', created_at:timestamp, item_count:12, version:1 }];
const quotes = [{ id:'quote-1', title:'Long quotation / 长报价标题 '.repeat(4), unread:true, total_price:12345.67, currency:'CNY', delivery:{delivered_at:timestamp} }];
(async () => {
  const browser = await chromium.launch({ channel:'msedge', headless:true });
  let checks = 0;
  try {
    for (const lang of ['zh', 'en']) {
      const context = await browser.newContext({ hasTouch:true, reducedMotion:'reduce' });
      const errors = [], writes = [];
      let responseMode = 'normal';
      await context.addInitScript(language => {
        sessionStorage.setItem('boten_user_token','layout-test');
        if (!localStorage.getItem('boten-language')) localStorage.setItem('boten-language',language);
      }, lang);
      await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.pathname.startsWith('/api/')) {
          const request = route.request();
          if (request.method() !== 'GET') {
            writes.push({url:url.pathname, method:request.method(), body:request.postDataJSON()});
            if (url.pathname.endsWith('/profile/details')) return route.fulfill({json:{...user,...request.postDataJSON(),version:2}});
            throw new Error('Unexpected mutation: '+url.pathname);
          }
          if (url.pathname.endsWith('/auth/profile')) return route.fulfill({json:user});
          if (url.pathname.endsWith('/auth/countries')) return route.fulfill({json:{items:[{code:'CN',name:lang==='en'?'China':'中国',calling_code:'+86'}]}});
          const kind = url.pathname.split('/').pop();
          if (['shares','inquiries','quotes'].includes(kind)) {
            if (responseMode === 'error') return route.fulfill({status:503,json:{detail:'Service unavailable. '.repeat(12)}});
            const items = responseMode === 'empty' ? [] : ({shares,inquiries,quotes})[kind];
            return route.fulfill({json:{items,total:items.length,page:1,unread_count:items.length ? 3:0}});
          }
          throw new Error('Unexpected API: '+url.pathname);
        }
        let rel = decodeURIComponent(url.pathname).replace(/^\//,'');
        if (rel.endsWith('/')) rel += 'index.html';
        const file = path.resolve(root,rel);
        if (!file.startsWith(root+path.sep) || !fs.existsSync(file)) return route.fulfill({status:404,body:''});
        const mime = {'.html':'text/html','.js':'text/javascript','.css':'text/css','.ttf':'font/ttf','.png':'image/png','.svg':'image/svg+xml'};
        return route.fulfill({contentType:mime[path.extname(file)]||'application/octet-stream',body:fs.readFileSync(file)});
      });
      const page = await context.newPage();
      page.on('pageerror', e => errors.push(e.message));
      await page.goto('http://account-audit.local/account/#my-quotes');
      await page.waitForFunction(() => document.querySelector('#profile-quote-unread').textContent === '3');
      await page.evaluate(() => document.fonts.ready);
      assert.equal(await page.locator('[aria-current="page"]').getAttribute('data-account-panel'),'my-quotes');
      for (const [width,height] of sizes) {
        await page.setViewportSize({width,height});
        await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
        await page.evaluate(() => window.scrollTo({top:0,behavior:'instant'}));
        const label = `${lang} ${width}x${height}`;
        if (width <= 900) {
          const nav = await page.locator('.profile-navigation').evaluate(e => {
            const r = e.getBoundingClientRect();
            return {width:e.clientWidth,scroll:e.scrollWidth,buttons:[...e.querySelectorAll('button')].map(b=>{const x=b.getBoundingClientRect();return {left:x.left,right:x.right,width:x.width,height:x.height,top:x.top};}),left:r.left,right:r.right};
          });
          assert(nav.scroll <= nav.width+1, label+' navigation scrolls sideways');
          assert.equal(nav.buttons.length,6);
          for (const b of nav.buttons) assert(b.width>40&&b.height>=44&&b.left>=nav.left-1&&b.right<=nav.right+1,label+' inaccessible navigation '+JSON.stringify(nav));
          assert.equal(new Set(nav.buttons.map(b=>b.top)).size,2,label+' navigation is not two rows');
          assert(await page.locator('.profile-identity').isVisible(),label+' identity hidden');
        }
        assert(await page.locator('#profile-back-home').isVisible());
        assert.equal(await page.locator('#profile-back-home').getAttribute('aria-label'),lang==='en'?'Home':'主页');
        assert.equal(await page.locator('#profile-back-home').getAttribute('href'),'../');
        assert.equal(await page.locator('#profile-language-switcher button:visible').count(),width<900?1:2);
        assert.equal(await page.locator('.profile-home-icon').isVisible(),width<900);
        if(width<900) for(const selector of ['#profile-back-home','#profile-language-switcher button.active']) {
          assert(await page.locator(selector).evaluate(e=>{const r=e.getBoundingClientRect();return r.width===44&&r.height===44&&getComputedStyle(e).borderRadius==='50%';}),label+' circular header control');
        }
        assert(await page.locator('#profile-sign-out').isVisible());
        for (const panel of panels) {
          await page.locator(`[data-account-panel="${panel}"]`).click();
          assert.equal(new URL(page.url()).hash,'#'+panel);
          assert.equal(await page.locator('[data-account-content]:visible').count(),1);
          assert.equal(await page.locator('[aria-current="page"]').getAttribute('data-account-panel'),panel);
          assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),label+' '+panel+' page overflow');
          assert(await page.locator('[data-account-content]:visible').evaluate(e=>e.scrollWidth<=e.clientWidth+1),label+' '+panel+' panel overflow');
          if ([320,430,1440].includes(width) && ['profile','my-quotes'].includes(panel)) {
            await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
            await page.screenshot({path:path.join(out,`${lang}-${width}-${panel}.png`),fullPage:true});
          }
          checks++;
        }
        await page.locator('[data-account-panel="my-shares"]').click();
        await page.locator('#profile-shares-list .profile-record-more summary').click();
        assert(await page.locator('#profile-shares-list .profile-record-more > div').evaluate(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth;}),label+' more menu overflows');
        await page.keyboard.press('Escape');
        assert(await page.locator('#profile-shares-list .profile-record-more summary').evaluate(e=>e===document.activeElement));
      }
      await page.setViewportSize({width:320,height:568});
      // Native keyboard activation and form draft preservation across panels.
      await page.locator('[data-account-panel="profile"]').focus();
      await page.keyboard.press('Enter');
      await page.locator('#profile-display-name').fill('Draft name');
      await page.locator('[data-account-panel="account-security"]').focus();
      await page.keyboard.press('Space');
      await page.locator('[data-account-panel="profile"]').click();
      assert.equal(await page.locator('#profile-display-name').inputValue(),'Draft name');
      await page.locator('#profile-details-submit').click();
      await page.waitForFunction(()=>document.querySelector('#profile-details-status').classList.contains('is-success'));
      assert.equal(writes.length,1);
      assert.deepEqual(writes[0],{url:'/api/v1/auth/profile/details',method:'PATCH',body:{display_name:'Draft name',gender:'',birth_date:null,version:1}});
      // Long error/empty states still allow navigation and retry/filter controls.
      for (const mode of ['empty','error']) {
        responseMode = mode;
        await page.evaluate(()=>Promise.all([loadProfileShares(),loadProfileInquiries(),loadProfileQuotes()]));
        for (const panel of panels.slice(3)) {
          await page.locator(`[data-account-panel="${panel}"]`).click();
          assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),lang+' '+mode+' overflow');
        }
      }
      assert.deepEqual(errors,[]);
      // Both mobile widths and keyboard activation toggle language, retaining the route.
      for (const width of [430,768]) {
        await page.setViewportSize({width,height:932});
        await page.locator('#profile-language-switcher button.active').focus();
        const next=width===430?(lang==='en'?'zh':'en'):lang;
        await Promise.all([page.waitForNavigation({waitUntil:'load'}),page.keyboard.press('Enter')]);
        await page.waitForFunction(l=>document.documentElement.lang===(l==='en'?'en':'zh-CN'),next);
        assert.equal(new URL(page.url()).hash,'#my-quotes');
        assert.equal(await page.evaluate(()=>localStorage.getItem('boten-language')),next);
      }
      await context.close();
    }
    console.log(`PASS account navigation: ${checks} panel/viewport checks, two languages, 11 sizes, keyboard, draft/save payload, menus, empty/error states; fixtures only.`);
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exit(1);});
