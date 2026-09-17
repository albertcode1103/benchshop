// All APIs are mocked; product writes stay in memory and never reach NAS.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const page = await browser.newPage();
  const errors = [], saved = [];
  let product = {id:'spec-test',model:'BOTEN TEST',product_name_zh:'测试设备',product_name_en:'Test device',version:1,enabled:true,visible_zh:true,visible_en:true,translation_status:'reviewed',colors:[{code:'red',name_zh:'红色',name_en:'Red',enabled:true,is_default:true}],base_option_groups:[],price_variants:[],optional_config_ids:[],optional_config_overrides:{},specifications:[{id:'spec-existing',label:'转速',label_en:'Speed',value:'1000 rpm',value_en:'1000 rpm',sort_order:0}],images:[]};
  await page.addInitScript(()=>sessionStorage.setItem('boten_admin_token','fixture'));
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*', route => {
    const url=new URL(route.request().url());
    if(url.pathname.startsWith('/api/')) {
      if(route.request().method()!=='GET') {
        assert(url.pathname.endsWith('/products/spec-test/editor'),'unexpected mutation');
        const payload=route.request().postDataJSON(); saved.push(payload);
        product={...product,...payload,version:product.version+1};
        return route.fulfill({json:product});
      }
      if(url.pathname.endsWith('/auth/me')) return route.fulfill({json:{id:'qa',role:'admin'}});
      if(url.pathname.endsWith('/products/spec-test/editor')) return route.fulfill({json:product});
      return route.fulfill({json:{items:[],total:0}});
    }
    let rel=decodeURIComponent(url.pathname).replace(/^\//,'');
    if(!path.extname(rel)) rel+='index.html';
    const file=path.resolve(process.cwd(),rel);
    if(!file.startsWith(process.cwd()+path.sep)||!fs.existsSync(file))return route.fulfill({status:404,body:''});
    return route.fulfill({body:fs.readFileSync(file),contentType:({'.html':'text/html','.js':'text/javascript','.css':'text/css','.ttf':'font/ttf','.svg':'image/svg+xml'})[path.extname(file)]||'application/octet-stream'});
  });
  try {
    await page.goto('http://spec.test/admin/#products'); await page.waitForLoadState('networkidle');
    await page.evaluate(()=>openProductEditor('spec-test'));
    const rows=page.locator('#product-specifications-editor .specification-row');
    const field=(index,name)=>rows.nth(index).locator(`[data-spec-field=${name}]`);
    const language=lang=>page.locator(`#product-dialog .lang-toggle[data-lang=${lang}]`).click();
    await field(0,'label').fill('最大转速'); await field(0,'value').fill('3000 rpm');
    await page.locator('#add-specification-button').click();
    assert.equal(await field(0,'label').inputValue(),'最大转速','adding a row preserves unsaved label');
    assert.equal(await field(0,'value').inputValue(),'3000 rpm','adding a row preserves unsaved value');
    await field(1,'label').fill('功率'); await field(1,'value').fill('22 kW');
    await page.locator('#add-specification-button').click();
    assert.equal(await field(1,'value').inputValue(),'22 kW','consecutive additions preserve a new row');
    await field(2,'label').fill('通道'); await field(2,'value').fill('4');
    await language('en');
    assert.equal(await field(0,'label').inputValue(),'Speed','untouched language preserved');
    await field(0,'label').fill('Maximum speed'); await field(0,'value').fill('3000 rpm');
    await field(1,'label').fill('Power'); await field(1,'value').fill('22 kW');
    await field(2,'label').fill('Channels'); await field(2,'value').fill('4');
    await page.locator('#add-specification-button').click();
    assert.equal(await field(0,'label').inputValue(),'Maximum speed','English edits survive adding');
    await rows.nth(3).locator('[data-remove-spec]').click();
    await rows.nth(2).locator('[data-move-spec][data-direction="-1"]').click();
    assert.equal(await field(1,'label').inputValue(),'Channels');
    await language('zh');
    assert.equal(await field(0,'label').inputValue(),'最大转速');
    assert.equal(await field(1,'label').inputValue(),'通道');
    assert.equal(await field(2,'label').inputValue(),'功率');
    await field(1,'value').fill('8');
    await rows.nth(2).locator('[data-remove-spec]').click();
    assert.equal(await field(1,'value').inputValue(),'8','deletion preserves other edits');
    await page.locator('#save-product-button').click();
    await page.waitForFunction(()=>!document.querySelector('#product-dialog').open);
    assert.equal(saved.length,1);
    assert.deepEqual(saved[0].specifications.map(s=>[s.label,s.value,s.label_en,s.value_en,s.sort_order]),[['最大转速','3000 rpm','Maximum speed','3000 rpm',0],['通道','8','Channels','4',1]]);
    await page.evaluate(()=>openProductEditor('spec-test'));
    assert.equal(await field(1,'value').inputValue(),'8');
    await language('en'); assert.equal(await field(1,'value').inputValue(),'4');
    assert.deepEqual(errors,[]);
    console.log('PASS product specifications: unsaved/new rows, consecutive additions, both languages, reorder/delete, save payload and reopen; no live API.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
