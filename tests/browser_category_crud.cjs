// Browser actions against in-memory API fixtures only.
const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
 const page=await browser.newPage();let sequence=0;
 const roots=['tools','accessories'].map(type=>({id:'catalog-'+type,catalog_type:type,name:type,name_en:type,enabled:true,children:[]}));
 await page.addInitScript(()=>sessionStorage.setItem('boten_admin_token','fixture'));
 await page.route('**/api/v1/**',route=>{
  const p=new URL(route.request().url()).pathname,method=route.request().method();
  if(p.endsWith('/auth/me'))return route.fulfill({json:{id:'qa',role:'admin'}});
  if(p.endsWith('/admin/catalog-tree'))return route.fulfill({json:{items:roots}});
  if(p.includes('/admin/catalog/categories')&&method!=='GET'){
   if(method==='POST'){const body=route.request().postDataJSON(),root=roots.find(r=>r.id===body.parent_id);assert(root);const item={...body,id:'fixture-'+(++sequence),name:body.name_zh,catalog_type:root.catalog_type,version:1,options:[]};root.children.push(item);return route.fulfill({json:item});}
   const id=p.split('/').pop(),root=roots.find(r=>r.children.some(c=>c.id===id)),item=root.children.find(c=>c.id===id);
   if(method==='PATCH'){const body=route.request().postDataJSON();Object.assign(item,body,{name:body.name_zh,version:item.version+1});return route.fulfill({json:item});}
   if(method==='DELETE'){root.children=root.children.filter(c=>c.id!==id);return route.fulfill({status:204});}
  }
  if(method!=='GET')return route.abort();return route.fulfill({json:{items:[],total:0}});
 });
 await page.goto('http://127.0.0.1:8081/admin/#tool-catalog');await page.waitForLoadState('networkidle');
 for(const type of ['tools','accessories']){
  await page.evaluate(t=>switchView(t==='tools'?'tool-catalog':'accessory-catalog'),type);
  await page.locator('#add-config-category').click();
  await page.locator('dialog[open] [name=name_zh]').fill('新增分类');
  await page.locator('dialog[open] [data-lang=en]').click();await page.locator('dialog[open] [name=name_en]').fill('New category');
  await page.locator('dialog[open] [value=default]').click();await page.waitForFunction(()=>!document.querySelector('.catalog-category-editor-dialog[open]'));
  const item=roots.find(r=>r.catalog_type===type).children[0];assert(item);
  await page.evaluate(c=>editConfigCategory(c),item);
  await page.locator('dialog[open] [data-lang=zh]').click();await page.locator('dialog[open] [name=name_zh]').fill('已修改');
  await page.locator('dialog[open] [value=default]').click();await page.waitForFunction(()=>!document.querySelector('.catalog-category-editor-dialog[open]'));assert.equal(item.name,'已修改');
  await page.evaluate(c=>editConfigCategory(c),item);await page.locator('.catalog-delete-action').click();
  await page.locator('.confirm-dialog').getByRole('button',{name:'删除分类',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.catalog-category-editor-dialog[open]'));
  assert.equal(roots.find(r=>r.catalog_type===type).children.length,0);
 }
 console.log('Tools/accessories category create/edit/delete browser workflows passed');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
