
// UI-only fixtures: all requests are fulfilled in memory; no live API is contacted.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path');
const assert=require('node:assert/strict');
(async()=>{
const browser=await chromium.launch({channel:'msedge',headless:true});
const context=await browser.newContext({hasTouch:process.env.UI_TOUCH==='1'});
await context.addInitScript(()=>{sessionStorage.setItem('boten_admin_token','ui-audit-fixture');sessionStorage.setItem('boten_user_token','ui-audit-fixture');if(!localStorage.getItem('boten-language'))localStorage.setItem('boten-language','zh')});
await context.route('**/*',async route=>{
 const url=new URL(route.request().url());
 if(url.pathname.startsWith('/api/')){let data={items:[],products:[],options:[],total:0,page:1};
 if(/auth\/(me|profile)$/.test(url.pathname))data={id:'qa',role:'admin',display_name:'UI Audit',email:'qa@example.invalid',phone:'13800000000',phone_country:'CN',version:1};
 if(url.pathname.endsWith('/auth/countries'))data={items:[{code:'CN',name:'中国',calling_code:'+86'}]};
 if(url.pathname==='/api/v1/products')data={items:[{id:'cr1016',visible_zh:true,visible_en:true}]};
 if(url.pathname==='/api/v1/products/cr1016/snapshot')data={id:'cr1016',model:'BOTEN CR1016',name:'Equipment / 设备',colors:[{code:'red',name:'Red',is_default:true}],base_option_groups:[{type:'motor',name:'Motor',required:true,options:[{id:'motor-1',name:'22kW'}]}],optional_categories:[{id:'cri',name:'CRI Test Kit',multiple:true,options:[{id:'opt-1',code:'BTK-1016',name:'Long configuration name '.repeat(4)}]}]};
 return route.fulfill({json:data});}
 let rel=decodeURIComponent(url.pathname).replace(/^\//,'');if(!path.extname(rel))rel=rel.replace(/\/?$/,'/')+'index.html';if(rel.startsWith('/'))rel=rel.slice(1);
 const file=path.resolve(process.cwd(),rel);
 if(!file.startsWith(process.cwd()+path.sep)||!fs.existsSync(file))return route.fulfill({status:404,body:''});
 const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.ttf':'font/ttf','.png':'image/png','.svg':'image/svg+xml','.jpg':'image/jpeg'};
 return route.fulfill({contentType:mime[path.extname(file)]||'application/octet-stream',body:fs.readFileSync(file)});
});

const out=path.resolve('tmp/ui-responsive-20260912'+(process.env.UI_TOUCH==='1'?'/touch':''));fs.mkdirSync(out,{recursive:true});
const page=await context.newPage();const errors=[],results=[];
page.on('pageerror',e=>errors.push(e.message));
const sizes=[[1440,900],[1280,600],[1024,768],[768,600],[640,720],[390,844],[360,740],[320,568],[844,390],[390,350]];
const settle=()=>page.waitForTimeout(40);
async function bounded(locator,label,footerSelector){
 const result=await locator.evaluate((d,selector)=>{
  const r=d.getBoundingClientRect(),footer=selector?d.querySelector(selector):null;
  const f=footer?.getBoundingClientRect();
  return {w:d.clientWidth,sw:d.scrollWidth,h:r.height,x:r.x,y:r.y,right:r.right,bottom:r.bottom,vw:innerWidth,vh:innerHeight,footer:f?{x:f.x,y:f.y,right:f.right,bottom:f.bottom}:null};
 },footerSelector);
 assert(result.w>0&&result.h>0,label+' has no area');
 assert(result.x>=-1&&result.y>=-1&&result.right<=result.vw+1&&result.bottom<=result.vh+1,label+' outside viewport '+JSON.stringify(result));
 assert(result.sw<=result.w+1,label+' horizontal overflow '+JSON.stringify(result));
 if(result.footer)assert(result.footer.y>=result.y&&result.footer.bottom<=result.bottom+1&&result.footer.right<=result.right+1,label+' footer clipped '+JSON.stringify(result));
 results.push({label,...result});
}
async function closeTop(){await page.locator('dialog[open]').last().evaluate(d=>d.close());await settle();}
async function load(url){await page.goto('http://ui-audit.local'+url);await page.waitForTimeout(120);await page.evaluate(()=>document.fonts.ready);}
try {
for(const lang of ['zh','en']){
 await load('/');
 await page.evaluate(l=>{localStorage.setItem('boten-language',l);localStorage.setItem('boten-admin-language',l)},lang);
 await load('/');
 if (!process.env.UI_ACCOUNT_ONLY) {
 for(const [width,height] of (process.env.UI_ADMIN_ONLY?[]:sizes)){
  await page.setViewportSize({width,height});const label=lang+' '+width+'x'+height;
  for(const mode of ['login','register']){
   await page.evaluate(m=>{setAuthMode(m);document.getElementById('auth-dialog').showModal()},mode);
   await bounded(page.locator('#auth-dialog'),'auth '+mode+' '+label,'#auth-submit');
   await page.evaluate(()=>{const e=document.querySelector('#auth-error');e.hidden=false;e.textContent='Validation failed. Please check the entered details. '.repeat(4)});
   await bounded(page.locator('#auth-dialog'),'auth error '+label,'#auth-submit');
   await page.locator('#auth-password').focus();
   assert(await page.locator('#auth-password').evaluate(e=>{const r=e.getBoundingClientRect(),p=e.closest('.auth-fields').getBoundingClientRect();return r.top>=p.top-1&&r.bottom<=p.bottom+1}),'auth focused field obscured '+label);
   await page.keyboard.press('Escape');await settle();
  }
  for(const [id,footer] of [['share-dialog','#share-copy'],['sales-contact-dialog','#sales-contact-done']]){
   await page.evaluate(id=>document.getElementById(id).showModal(),id);
   await bounded(page.locator('#'+id),id+' '+label,footer);await closeTop();
  }
  await page.evaluate(()=>{const d=document.getElementById('customer-share-dialog');d.showModal();const c=d.querySelector('#customer-share-content');c.hidden=false;c.textContent='Configuration / 配置清单 '.repeat(200);d.querySelector('#customer-share-import').hidden=false;});
  await bounded(page.locator('#customer-share-dialog'),'share import '+label,'.customer-share-actions');await closeTop();
  await page.evaluate(()=>{window.removeResult='pending';confirmCartRemoval('Selected configurations / 已选配置 '.repeat(15)).then(r=>window.removeResult=r)});
  await bounded(page.locator('.cart-confirm-dialog'),'cart confirm '+label,'.cart-confirm-actions');
  await page.keyboard.press('Escape');await settle();assert.equal(await page.evaluate(()=>window.removeResult),false);
  await page.evaluate(()=>{document.querySelector('#cart-toggle').focus();window.noteResult='pending';requestShareNote({limited:true,used:7,limit:10},true).then(r=>window.noteResult=r)});
  await bounded(page.locator('.cart-share-note-dialog'),'share note '+label,'.cart-share-note-actions');
  await page.locator('.cart-share-note-dialog textarea').fill('布局核对 Note');
  if(width===844||width===320)await page.screenshot({path:path.join(out,'share-'+lang+'-'+width+'x'+height+'.png')});
  await page.locator('.cart-share-note-actions [value=cancel]').click();await settle();
  assert.equal(await page.evaluate(()=>window.noteResult),null,'cancel share creates no note');
  await page.evaluate(()=>{window.noteResult='pending';requestShareNote(null,true).then(r=>window.noteResult=r)});
  await page.locator('.cart-share-note-dialog textarea').fill('同样备注');
  await page.locator('.cart-share-note-dialog [value=confirm]').click();await settle();
  assert.equal(await page.evaluate(()=>window.noteResult),'同样备注','note submission unchanged');
  await page.evaluate(()=>{
   serverCart=[1,2].map(n=>({id:'fixture-'+n,itemType:'device_config',modelName:'BOTEN CR1016',productTitle:'Equipment',groups:[{id:'optional',type:'multi',category:'Test kits',count:20,value:['Selected'],detailItems:Array.from({length:20},(_,i)=>({code:'CODE-'+n+'-'+i,name:'Configuration name '.repeat(5)}))}]}));
   serverCart.push(...Array.from({length:12},(_,i)=>({id:'tool-'+i,itemType:'tool',catalogType:'tools',code:'TOOL-'+i,name:'Long tool name '.repeat(5),quantity:2,version:1})));
   renderCartPanel();openCartPanel();
  });
  await page.waitForTimeout(350);
  await bounded(page.locator('#cart-panel'),'cart '+label,'.cart-panel-footer');
  const trigger=page.locator('[data-cart-category][data-id="fixture-2"]');await trigger.click();
  await bounded(page.locator('.cart-detail-dialog'),'cart category '+label);
  assert((await page.locator('.cart-detail-dialog').textContent()).includes('CODE-2-0'));
  assert(!(await page.locator('.cart-detail-dialog').textContent()).includes('CODE-1-0'));
  await page.keyboard.press('Escape');await settle();assert(await trigger.evaluate(e=>e===document.activeElement));
  await page.evaluate(()=>showCatalogGroupDialog('tools'));
  await bounded(page.locator('.catalog-group-dialog'),'tool group '+label,'footer');await closeTop();
  await page.evaluate(()=>openInquiryDialog('cart'));
  await bounded(page.locator('.inquiry-dialog'),'cart inquiry '+label,'footer');
  await page.locator('.inquiry-dialog-status').evaluate(e=>{e.hidden=false;e.textContent='Please retry. '.repeat(30)});
  await bounded(page.locator('.inquiry-dialog'),'cart inquiry error '+label,'footer');await closeTop();
  await page.evaluate(()=>closeCartPanel());await page.waitForTimeout(350);
 }
 console.log('Public layouts passed:',lang);
 await load('/admin/');
 await page.evaluate(()=>{state.configCatalog=[{id:'catalog-tools',name:'维修工具',catalog_type:'tools',enabled:true,children:[{id:'tools-repair',name:'维修工具',name_en:'Repair Tools',catalog_type:'tools',parent_id:'catalog-tools',enabled:true,options:[]}]}];state.catalogRootId='catalog-tools'});
 for(const [width,height] of sizes){
  await page.setViewportSize({width,height});const label=lang+' '+width+'x'+height;
  await page.evaluate(()=>document.querySelector('.sidebar').classList.add('open'));await page.waitForTimeout(210);
  await bounded(page.locator('.sidebar'),'sidebar '+label,'.sidebar-footer');
  const lastNav=page.locator('.sidebar-navigation button').last();await lastNav.evaluate(e=>e.blur());await lastNav.focus();
  const navRect=await lastNav.evaluate(e=>{const r=e.getBoundingClientRect(),p=e.closest('.sidebar-navigation').getBoundingClientRect();return {top:r.top,bottom:r.bottom,containerTop:p.top,containerBottom:p.bottom}});
  assert(navRect.top>=navRect.containerTop-1&&navRect.bottom<=navRect.containerBottom+1,'sidebar last navigation unreachable '+label+' '+JSON.stringify(navRect));
  await page.evaluate(()=>document.querySelector('.sidebar').classList.remove('open'));
  await page.evaluate(()=>{window.pdfLanguageResult='pending';choosePdfLanguage().then(r=>window.pdfLanguageResult=r)});
  await bounded(page.locator('.pdf-language-dialog'),'pdf language '+label,'footer');
  assert((await page.locator('.pdf-language-dialog').boundingBox()).height<350);
  await page.keyboard.press('Escape');await settle();assert.equal(await page.evaluate(()=>window.pdfLanguageResult),null);
  await page.evaluate(()=>{window.confirmResult='pending';confirmAction('确认操作 / Confirm','Long explanation / 操作说明 '.repeat(40)).then(r=>window.confirmResult=r)});
  await bounded(page.locator('.confirm-dialog'),'admin confirm '+label,'footer');await page.keyboard.press('Escape');await settle();assert.equal(await page.evaluate(()=>window.confirmResult),false);
  for(const id of ['product-dialog','user-dialog','user-role-dialog','user-password-dialog','user-archive-dialog']){
   await page.evaluate(id=>document.getElementById(id).showModal(),id);
   await bounded(page.locator('#'+id),id+' '+label,'footer');await closeTop();
  }
  await page.evaluate(()=>addConfigOption('tools-repair'));
  await bounded(page.locator('dialog[open]').last(),'catalog item '+label,'footer');await closeTop();
  await page.evaluate(()=>addConfigCategory());
  await bounded(page.locator('dialog[open]').last(),'catalog category '+label,'footer');await closeTop();
  await page.evaluate(l=>openQuoteEditor({title:'Layout inspection',language:l,items:[{kind:'product',code:'CR1016',name:'BOTEN CR1016',quantity:1,price:100},...Array.from({length:18},(_,i)=>({kind:'tool',code:'TOOL-'+i,name:'Long tool name / 维修工具名称 '.repeat(3),quantity:2,price:10}))],customerName:'Test',customerEmail:'qa@example.invalid'}),lang);
  const quote=page.locator('.quote-editor-dialog[open]');
  await bounded(quote,'quote '+label,'footer');
  const list=quote.locator('.quote-edit-list');
  assert(await list.evaluate(e=>e.clientHeight>=80&&e.scrollWidth<=e.clientWidth+1),'quote list collapsed or overflows '+label);
  const qty=quote.locator('[data-q=qty]').last();await qty.fill('3');await qty.press('Tab');
  assert(await quote.locator('.quote-total').textContent().then(t=>t.includes('470')),'quote sum unchanged by layout');
  await quote.locator('.quote-customer-search').click();
  await bounded(page.locator('.quote-customer-picker'),'customer picker '+label,'footer');
  await page.locator('.quote-customer-picker footer button[value=cancel]').click();
  assert(await quote.locator('.quote-customer-search').evaluate(e=>e===document.activeElement),'nested focus restored');
  await qty.focus();assert(await qty.evaluate(e=>{const r=e.getBoundingClientRect(),d=e.closest('dialog'),h=d.querySelector('header').getBoundingClientRect(),f=d.querySelector('footer').getBoundingClientRect();return r.top>=h.bottom-1&&r.bottom<=f.top+1}),'quote field behind header/footer '+label);
  if(width===844||width===320)await page.screenshot({path:path.join(out,'quote-'+lang+'-'+width+'x'+height+'.png')});
  await closeTop();
 }
 console.log('Workbench layouts passed:',lang);
 }
 await load('/account/#account-contact');
 for(const [width,height] of sizes){
  await page.setViewportSize({width,height});
  assert(await page.locator('#profile-back-home').isVisible(),'home hidden '+width);
  assert(await page.locator('#profile-sign-out').isVisible(),'signout hidden '+width);
  for(const panel of ['profile','account-contact','account-security','my-shares','my-inquiries','my-quotes']){
   await page.evaluate(p=>showProfilePanel(p),panel);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'account '+panel+' horizontal overflow '+lang+' '+width);
  }
  const overflow=await page.evaluate(()=>[...document.querySelectorAll('body *')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.right>innerWidth+1}).map(e=>({tag:e.tagName,id:e.id,cls:e.className,width:e.getBoundingClientRect().width})).slice(0,15));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'account horizontal overflow '+width+' '+JSON.stringify(overflow));
  if(width===320){await page.evaluate(()=>showProfilePanel('account-contact'));await page.screenshot({path:path.join(out,'account-'+lang+'-320x568.png')});}
  await page.evaluate(()=>openProfileBusinessDialog('Share / 分享 · 123456',pc.shareDetails,renderProfileDevicePreview({available:true,quantity:1,snapshot:{product:{name:'BOTEN CR1016',title_name:'Long equipment name '.repeat(12)},color:{label:'Red'},categories:[{id:'cri',name:'Test kits',options:Array.from({length:20},(_,i)=>({code:'BTK-'+i,name:'Long configuration name '.repeat(4)}))}]}},0)));
  await bounded(page.locator('#profile-business-dialog'),'profile share '+lang+' '+width+'x'+height);await closeTop();
 }
}
assert.deepEqual(errors,[],'JavaScript errors');
console.log('PASS',results.length,'layout assertions; two languages, ten viewport sizes, touch='+process.env.UI_TOUCH);
fs.writeFileSync(path.join(out,'results'+(process.env.UI_TOUCH==='1'?'-touch':'')+'.json'),JSON.stringify(results,null,2));
} finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
