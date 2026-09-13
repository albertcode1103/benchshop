const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {for(const width of [1440,1188,900,899,393,320]){
  const page=await browser.newPage({viewport:{width,height:884}});
  await page.route('**/api/**',route=>route.fulfill({json:{items:[],total:0}}));
  await page.goto('http://127.0.0.1:8082/');
  for(const language of ['zh','en']) {
   await page.evaluate(lang=>{
    document.querySelectorAll('#language-switcher button').forEach(b=>b.classList.toggle('active',b.dataset.language===lang));
   },language);
   const result=await page.evaluate(()=>{
    const language=document.querySelector('#language-switcher'),button=language.querySelector('.active');
    const box=language.getBoundingClientRect();
    const pseudo=getComputedStyle(button,'::after');
    return {height:box.height,others:['account-toggle','cart-toggle'].map(id=>document.getElementById(id).getBoundingClientRect().height),font:getComputedStyle(button).fontSize,iconWidth:pseudo.width,iconHeight:pseudo.height,mask:pseudo.maskImage||pseudo.webkitMaskImage,overflow:document.documentElement.scrollWidth>innerWidth};
   });
   assert(result.others.every(height=>Math.abs(result.height-height)<1),JSON.stringify(result));
   if(width>=900) assert.equal(result.font,'12px');
   else { assert.equal(result.font,'0px');assert.equal(result.iconWidth,'22px');assert.equal(result.iconHeight,'22px');assert.match(result.mask,/translate\.svg/); }
   assert.equal(result.overflow,false);
  }
  console.log('PASS header height, desktop labels and mobile translate icon',width);await page.close();
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
