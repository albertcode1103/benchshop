// Isolated UI fixtures: all API writes blocked; no customer data is modified.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
const kinds = {
  tools: [['repair','维修工具','Repair Tools'],['measuring','测量工具','Measuring Tools'],['disassembly','拆装工具','Disassembly and Assembly Tools'],['other','其他工具','Other Tools']],
  accessories: [['cables','测试线','Test Cables'],['hoses','油管','Hoses'],['adapters','适配器','Adapters'],['plugs','插头','Plugs'],['connectors','接头','Connectors'],['other','其他','Other']]
};
const roots = Object.entries(kinds).map(([type, categories]) => ({
  id: `catalog-${type}`, catalog_type: type, enabled: true, name: type, name_en: type,
  children: categories.map(([id,name,name_en], index) => ({
    id: `${type}-${id}`, parent_id: `catalog-${type}`, catalog_type: type, enabled: true, name, name_en,
    options: index === 0 ? [{id:`${type}-sample`,category_id:`${type}-${id}`,code:'QA-001',name:'验收项目',name_en:'Sample item',enabled:true,version:1,price:123,price_usd:20}] : []
  }))
}));
(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    const context = await browser.newContext();
    await context.addInitScript(() => sessionStorage.setItem('boten_admin_token','isolated-ui-token'));
    await context.route('**/api/v1/**', async route => {
      const url = new URL(route.request().url());
      if (route.request().method() !== 'GET') return route.fulfill({status:409,json:{detail:'Test writes blocked'}});
      if (url.pathname === '/api/v1/catalog/items') {
        const root = roots.find(r => r.catalog_type === url.searchParams.get('type'));
        const en = url.searchParams.get('lang') === 'en';
        return route.fulfill({json:{categories:root.children.map(c=>({id:c.id,name:en?c.name_en:c.name})),items:root.children.flatMap(c=>c.options.map(o=>({...o,name:en?o.name_en:o.name,category_name:en?c.name_en:c.name})))}});
      }
      if (url.pathname.includes('/auth/me')) return route.fulfill({json:{id:'qa',role:'admin',display_name:'QA'}});
      if (url.pathname === '/api/v1/admin/catalog-tree') return route.fulfill({json:{items:roots}});
      if (/\/(admin|staff|customer)\//.test(url.pathname) || url.pathname === '/api/v1/quotes') return route.fulfill({json:{items:[],total:0}});
      return route.continue();
    });
    const page = await context.newPage();
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    fs.mkdirSync('tmp/catalog-categories',{recursive:true});
    for(const width of [1440,390]) {
      await page.setViewportSize({width,height:900});
      await page.goto('http://127.0.0.1:8081/');
      for(const type of ['tools','accessories']) {
        await page.locator('#catalog-stage-toggle').click();
        await page.locator(`[data-catalog-drawer-select="catalog:${type}"]`).click();
        await page.locator(`#catalog-category-filters [data-catalog-category="${type}-${kinds[type][0][0]}"]`).waitFor();
        assert.equal(await page.locator('#catalog-category-filters button').count(),kinds[type].length+1);
        await page.locator('#catalog-marketplace-search').fill('QA');
        await page.locator(`#catalog-category-filters [data-catalog-category="${type}-${kinds[type][0][0]}"]`).click();
        assert.equal(await page.locator('#catalog-product-grid article').count(),1);
        await page.locator(`#catalog-category-filters [data-catalog-category="${type}-${kinds[type][1][0]}"]`).click();
        assert.equal(await page.locator('#catalog-product-grid article').count(),0);
        await page.locator('#catalog-category-filters [data-catalog-category="all"]').click();
        assert.equal(await page.locator('#catalog-product-grid article').count(),1);
        assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
        await page.waitForFunction(()=>getComputedStyle(document.getElementById('catalog-navigation-backdrop')).opacity==='0');
        await page.screenshot({path:`tmp/catalog-categories/public-${type}-${width}.png`});
        await page.evaluate(type=>{localStorage.setItem('boten-language','en');window.selectMarketplaceCatalog(type);},type);
        await page.locator('#catalog-category-filters').getByRole('button',{name:kinds[type][0][2],exact:true}).waitFor();
        assert.equal(await page.locator('#catalog-marketplace-search').inputValue(),'QA');
        await page.evaluate(()=>localStorage.setItem('boten-language','zh'));
        await page.locator('#catalog-marketplace-toggle').click();
        await page.locator('#catalog-device-entry').click();
        await page.locator('.catalog-model-item').first().click();
      }
      await page.goto('http://127.0.0.1:8081/admin/#tool-catalog');
      await page.waitForFunction(()=>state.configCatalog.length > 0);
      await page.evaluate(()=>switchView('tool-catalog',false));
      await page.locator('[data-catalog-list-query]').waitFor({state:'visible'});
      assert.equal(await page.locator('[data-catalog-list-category]').count(),5);
      await page.locator('[data-catalog-list-query]').fill('QA-001');
      assert.equal(await page.locator('.catalog-v2-table tbody tr').count(),1);
      await page.locator('[data-catalog-list-category="tools-measuring"]').click();
      assert.equal(await page.locator('.catalog-v2-table tbody tr').count(),0);
      await page.locator('[data-catalog-list-category="all"]').click();
      await page.screenshot({path:`tmp/catalog-categories/admin-${width}.png`});
      await page.evaluate(()=>window.addConfigOption('catalog-tools'));
      const category=page.locator('dialog[open] select[name=category_id]');
      assert.equal(await category.locator('option').count(),5);
      assert.equal(await category.inputValue(),'');
      assert.equal(await category.evaluate(e=>e.checkValidity()),false);
      await category.selectOption('tools-measuring');
      assert.equal(await category.evaluate(e=>e.checkValidity()),true);
      await page.keyboard.press('Escape');
    }
    assert.deepEqual(errors,[]);
    console.log('Public/admin classification filters, search, empty state, required fields and 1440/390 layouts passed');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
