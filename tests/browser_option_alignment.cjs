// All API requests use fixtures; no NAS data is read or written.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {for(const lang of ['zh','en'])for(const width of [1440,393,320]){
  const page=await browser.newPage({viewport:{width,height:900}});
  await page.addInitScript(l=>localStorage.setItem('boten-language',l),lang);
  await page.route('**/api/**',async route=>{
   assert.equal(route.request().method(),'GET');const p=new URL(route.request().url()).pathname;
   let data={items:[]};
   if(p==='/api/v1/products')data={items:[{id:'qa',visible_zh:true,visible_en:true}]};
   if(p.endsWith('/snapshot'))data={id:'qa',model:'QA',name:'QA',colors:[{code:'red',name:'红色 / Red'},{code:'green',name:'绿色 / Green'}],base_option_groups:['motor','voltage','channel'].map(type=>({type,name:type,options:[{id:type+'1',name:lang==='zh'?'标准配置':'Standard configuration'},{id:type+'2',name:lang==='zh'?'加长名称测试选项':'Longer configuration label'}]})),optional_categories:[]};
   if(p.endsWith('/snapshot')) data.optional_categories=[{id:'cri',name:'Config',multiple:true,options:[{id:'a',code:'BTK-A',name:'Long configuration name / 长配置名称',special_note:'Special note / 专有备注',image_path:'assets/images/placeholder-option.svg'},{id:'b',code:'BTK-B',name:'Second option',image_path:'assets/images/placeholder-option.svg'}]}];
   if(p.endsWith('/snapshot')) data.specifications=lang==='en'?[{label:'Dimensions',value:'1200 × 800 mm'}]:[];
   await route.fulfill({json:data});
  });
  await page.goto('http://127.0.0.1:8082/');
  await page.locator('#home-device:not([disabled])').click();
  await page.evaluate(()=>document.fonts.ready);
  for(const selector of ['.device-overview > summary','#overview-title','.overview-toggle-label','#overview-description-title','#overview-specifications-title']) {
   assert.equal(await page.locator(selector).evaluate(e=>getComputedStyle(e).fontSize),'14px');
  }
  for(const element of await page.locator('#page-desc, #product-specifications th, #product-specifications td').all()) {
   assert.equal(await element.evaluate(e=>getComputedStyle(e).fontSize),'12px');
  }
  await page.locator('.device-overview > summary').click();
  assert.equal(await page.locator('.device-overview').evaluate(e=>e.open),false);
  await page.locator('.device-overview > summary').click();
  assert.equal(await page.locator('.device-overview').evaluate(e=>e.open),true);
  const cards=page.locator('.color-options-grid .option-card, .text-options .option-card');
  assert((await cards.count())>=6);
  for(const card of await cards.all()){
   for(const selected of [false,true]){
    await card.evaluate((e,on)=>e.classList.toggle('active',on),selected);
    const delta=await card.evaluate(e=>{const a=e.getBoundingClientRect(),b=e.querySelector('.option-name').getBoundingClientRect();return Math.abs(a.y+a.height/2-b.y-b.height/2)});
    assert(delta<1,`label off center ${lang} ${width}: ${delta}`);
   }
  }
  const tile=page.locator('.option-card-config').first();
  const layout=await tile.evaluate(e=>{
   const r=e.getBoundingClientRect(),m=e.querySelector('.option-media').getBoundingClientRect();
   return {left:m.left-r.left,top:m.top-r.top,right:r.right-m.right,padding:getComputedStyle(e.querySelector('img')).padding,bodyPadding:getComputedStyle(e.querySelector('.option-config-body')).paddingLeft,ratio:m.width/m.height};
  });
  assert.equal(layout.left,2);assert.equal(layout.top,2);assert.equal(layout.right,2);
  assert.equal(layout.padding,'0px');assert.equal(layout.bodyPadding,width<639?'8px':'16px');assert(Math.abs(layout.ratio-2)<.01);
  await tile.locator('.option-name').click();
  assert.equal(await tile.getAttribute('aria-checked'),'true');
  await tile.locator('.option-media').click();
  assert.equal(await tile.getAttribute('aria-checked'),'false');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  console.log('PASS overview typography/toggle, compact labels and config cards',lang,width);await page.close();
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
