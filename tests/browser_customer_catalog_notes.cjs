// Isolated rendering fixtures include old-API notes. No NAS requests or writes.
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true});
  try {
    const page = await browser.newPage();
    await page.route('**/*', route => route.fulfill({contentType:'text/html', body:'<div id="options-panel"></div><div id="catalog-product-grid"></div><div id="catalog-marketplace-empty"></div><div id="catalog-marketplace-panel"></div>'}));
    await page.goto('http://catalog-notes.test');
    await page.evaluate(() => {
      window.botenAssetUrl = value => value || '';
      window.normalizeCatalogCode = value => value;
      window.catalogDisplayName = value => value;
    });
    for (const file of ['catalog-api', 'renderer', 'cart', 'catalog-marketplace'])
      await page.addScriptTag({path:path.resolve(`js/${file}.js`)});
    for (const lang of ['zh', 'en']) {
      await page.evaluate(lang => localStorage.setItem('boten-language', lang), lang);
      for (const type of ['optional', 'tools', 'accessories']) {
        await page.evaluate(({type, lang}) => {
          const option = {id:'fixture', code:'TEST-1', name:lang === 'zh' ? '公开名称' : 'Public name',
            description:lang === 'zh' ? '公开描述' : 'Public description', note:'SECRET_INTERNAL', special_note:'SECRET_INTERNAL', specialNote:'SECRET_INTERNAL'};
          if(type === 'optional') {
            const category = {id:'config', name:'Config', description:'', multiple:true, options:[option]};
            renderOptions({categories:[category]}, 'config', {});
            const mapped = mapApiCategory(category);
            if(JSON.stringify(mapped).includes('SECRET')) throw new Error('mapper retained notes');
            serverCart = [savedConfigToCartItem({id:'fixture', snapshot:{product:{name:'Device'}, color:{label:'Red'}, categories:[category]}})];
          } else {
            catalogMarketplaceState.type = type;
            catalogMarketplaceState.items = [option, {...option, id:'empty', code:'TEST-2', description:''}];
            catalogMarketplaceState.query = '';
            renderCatalogMarketplace();
            catalogMarketplaceState.query = 'SECRET_INTERNAL';
            if(filteredMarketplaceItems().length) throw new Error('notes are searchable');
            catalogMarketplaceState.query = '';
            serverCart = [savedCatalogToCartItem({...option, catalog_type:type, quantity:1})];
          }
          showCartDetails('fixture');
        }, {type, lang});
        const body = await page.locator('body').innerText();
        assert(!body.includes('SECRET_INTERNAL'), `${type}/${lang}: internal note visible`);
        assert(body.includes('TEST-1'));
        assert(body.includes(lang === 'zh' ? '公开名称' : 'Public name'));
        assert(body.includes(lang === 'zh' ? '公开描述' : 'Public description'));
        await page.evaluate(() => document.querySelector('dialog').close());
        await page.locator('dialog').waitFor({state:'detached'});
      }
    }
    console.log('PASS: three catalog types × two languages; empty description, search, mapping and cart details hide internal notes');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
