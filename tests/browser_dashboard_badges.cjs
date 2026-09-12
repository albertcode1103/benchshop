// Synthetic dashboard records; all API calls intercepted, no real data changes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const output='tmp/dashboard-badges';fs.mkdirSync(output,{recursive:true});
 try {
  const page=await browser.newPage();const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>sessionStorage.setItem('boten_admin_token','fixture'));
  await page.route('**/api/**',r=>r.fulfill({json:new URL(r.request().url()).pathname.endsWith('/auth/me')?{id:'qa',role:'admin'}:{items:[],total:0}}));
  await page.goto('http://127.0.0.1:8081/admin/');await page.waitForLoadState('networkidle');
  await page.evaluate(()=>{state.products=[{id:'cr1016',name:'BOTEN CR1016',title_name:'设备名称'}];state.shares=[{code:'123456',name:'设备配置',active:true},{code:'234567',name:'Configuration / 设备配置',active:false}];renderDashboard();});
  await page.evaluate(()=>document.fonts.ready);
  for(const [width,height] of [[1103,838],[1440,900],[390,844],[320,568]]){
   await page.setViewportSize({width,height});
   await page.locator('#dashboard-shares').scrollIntoViewIfNeeded();
   await page.screenshot({path:`${output}/${process.env.BADGE_AUDIT_LABEL||'after'}-${width}.png`});
   const badges=await page.locator('#dashboard-shares .badge').evaluateAll(es=>es.map(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect(),row=e.closest('.mini-row').getBoundingClientRect();return{display:s.display,align:s.alignItems,margin:s.marginTop,height:r.height,offset:Math.abs((r.top+r.bottom-row.top-row.bottom)/2),right:r.right,rowRight:row.right,color:s.color};}));
   for(const b of badges){assert.match(b.display,/flex/,'badge must retain flex text alignment');assert.equal(b.align,'center');assert.equal(b.margin,'0px');assert(b.height>=25);assert(b.offset<1);assert(b.right<=b.rowRight);}
   assert.notEqual(badges[0].color,badges[1].color,'active/closed colors preserved');
   assert.equal(await page.locator('#dashboard-products .mini-row > div > span').evaluate(e=>getComputedStyle(e).marginTop),'3px','description spacing preserved');
  }
  assert.deepEqual(errors,[]);console.log('PASS: dashboard active/closed badges vertically centered; four viewport sizes, colors and description spacing preserved.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
