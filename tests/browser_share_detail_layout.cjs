const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
 for(const lang of ['zh','en']) {
  const page=await browser.newPage();
  await page.addInitScript(language=>{sessionStorage.setItem('boten_user_token','fixture');localStorage.setItem('boten-language',language);},lang);
  await page.route('**/api/v1/**',route=>{
   const p=new URL(route.request().url()).pathname;
   if(route.request().method()!=='GET') return route.abort();
   if(p.endsWith('/auth/profile')||p.endsWith('/auth/me')) return route.fulfill({json:{id:'qa',role:'customer',display_name:'QA',email:'qa@example.test',phone_country:'CN'}});
   if(p.endsWith('/customer/me/shares/test'))return route.fulfill({json:{title:'QA',code:'123456',items:[{item_type:'device_config',available:true,quantity:1,snapshot:{product:{name:'BOTEN CR1016',title_name:'Long '.repeat(25)},color:{label:'Red'},categories:[]}}]}});
   return route.fulfill({json:{items:[],total:0}});
  });
  await page.goto('http://127.0.0.1:8081/account/#my-shares');
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:900});
   await page.evaluate(()=>openOwnShare('test'));
   assert.equal(await page.locator('#profile-business-dialog-title').textContent(),'QA · 123456');
   const rows=page.locator('.profile-device-basics > div > div');
   assert.equal(await rows.count(),3);
   const boxes=await rows.evaluateAll(nodes=>nodes.map(node=>({top:node.getBoundingClientRect().top,bottom:node.getBoundingClientRect().bottom,right:getComputedStyle(node.querySelector('strong')).textAlign})));
   assert(boxes.every(row=>row.right==='right'));assert(boxes[1].top>=boxes[0].bottom-1);
   await page.evaluate(()=>{document.getElementById('profile-business-dialog').close();openProfileBusinessDialog('Quote',pc.quotationDetails,'');});
   assert(!(await page.locator('#profile-business-dialog').getAttribute('class')||'').includes('profile-share-details'));
   await page.evaluate(()=>document.getElementById('profile-business-dialog').close());
  }
  await page.close();
 }
 console.log('Share detail title, row layout and non-share isolation: zh/en desktop/mobile passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
