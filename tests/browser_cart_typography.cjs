// Read-only, isolated fixtures for cart list typography; no real account writes.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  for(const lang of ['zh','en']){
   const page=await browser.newPage({viewport:{width:393,height:852}});
   await page.addInitScript(l=>{localStorage.setItem('boten-language',l);sessionStorage.setItem('boten_user_token','fixture');},lang);
   await page.route('**/api/**',async r=>{
    assert.equal(r.request().method(),'GET');
    const p=new URL(r.request().url()).pathname;
    await r.fulfill({json:/auth\/(me|profile)$/.test(p)?{id:'qa',role:'customer',display_name:'QA'}:{items:[],total:0}});
   });
   await page.goto('http://127.0.0.1:8081/');await page.waitForLoadState('networkidle');
   await page.evaluate(()=>{
    serverCart=[{id:'device',itemType:'device_config',modelName:'BOTEN CR1016',productTitle:'Multi-Functional Injector & Pump Test Bench',groups:[{id:'motor',type:'single',category:'Motor / 电机',value:'22KW SERVO MOTOR'},{id:'cri',type:'multi',category:'CR Injector Test Kit / 共轨喷油器测试套件',count:2,value:['A','B'],detailItems:[{code:'A',name:'配置一'},{code:'B',name:'配置二'}]}]},...['tools','accessories'].map((type,i)=>({id:type,itemType:i?'accessory':'tool',catalogType:type,code:'TEST-001',name:'Test / 测试项目',quantity:3}))];
    renderCartPanel();openCartPanel();
   });
   assert.equal(await page.locator('#cart-items .cart-item').count(),3);
   for(const width of [393,320,1440]){
    await page.setViewportSize({width,height:852});
    const bad=await page.locator('#cart-items').evaluate(root=>[...root.querySelectorAll('*')].filter(e=>[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())&&getComputedStyle(e).fontSize!=='12px').map(e=>({cls:e.className,size:getComputedStyle(e).fontSize})));
    assert.deepEqual(bad,[],lang+' '+width+' text is not 12px');
    assert(await page.locator('#cart-items').evaluate(e=>e.scrollWidth<=e.clientWidth),lang+' overflow');
    assert(await page.locator('.cart-item-actions .btn').first().evaluate(e=>e.getBoundingClientRect().height>=36),'button hit area reduced');
    assert.notEqual(await page.locator('#cart-inquiry').evaluate(e=>getComputedStyle(e).fontSize),'12px','footer changed');
   }
   await page.locator('[data-cart-category]').click();
   assert(await page.locator('.cart-detail-dialog').isVisible());
   await page.keyboard.press('Escape');
   await page.close();
  }
  console.log('PASS cart typography: zh/en, 393/320/1440px, device/tools/accessories, all list text 12px, footer unchanged and category preview works.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
