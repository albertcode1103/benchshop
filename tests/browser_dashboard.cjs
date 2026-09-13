// All resources and API responses are served in memory. No NAS requests or writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

const base = 'http://dashboard.test';
const root = process.cwd();
const output = path.join(root, 'tmp/dashboard');
fs.mkdirSync(output, {recursive: true});
function fixture(role = 'admin', days = 30) {
  const inquiry = {id: 'i1', inquiry_number: 'RFQ-20260913-0001', customer_name: '中文客户 / International customer '.repeat(3), assignee_name: '业务员 A', status: 'assigned', business_status: 'assigned', created_at: '2026-09-13 00:00:00', updated_at: '2026-09-09 00:00:00'};
  const draft = {id: 'q1', quote_number: '', title: '待处理报价 / Quotation '.repeat(3), customer_name: 'Example customer', lifecycle_status: 'draft', updated_at: '2026-09-13 00:00:00'};
  const due = {...draft, id: 'q2', quote_number: 'QUOTA-20260913-0002', lifecycle_status: 'sent', valid_until: '2026-09-16'};
  const dates = Array.from({length: days}, (_, i) => new Date(Date.UTC(2026, 8, 13 - days + i + 1)).toISOString().slice(0, 10));
  return {generated_at: '2026-09-13T04:00:00Z', days, timezone: 'Asia/Shanghai', scopes: {inquiries: '公共询价', shares: '公共分享', quotes: role === 'admin' ? '全部报价' : '我的报价', tasks: role === 'admin' ? '全部待跟进询价' : '分配给我的询价'},
    counts: {followup: 26, stale: 21, drafts: 4, due: 2}, tasks: {inquiries: [inquiry], drafts: [draft], due: [due]},
    recent: {inquiries: [inquiry], quotes: [draft, due], shares: [{id: 's1', code: '123456', name: '长名称分享 '.repeat(12), status: 'active', created_at: '2026-09-13 00:00:00'}, {id: 's2', code: '234567', name: 'Closed share', status: 'closed', created_at: '2026-09-13 00:00:00'}, {id: 's3', code: '345678', name: 'Expired share', status: 'expired', created_at: '2026-09-13 00:00:00'}]},
    trend: {dates, inquiries: dates.map((_, i) => i % 6), quotes: dates.map((_, i) => i % 3), shares: dates.map((_, i) => i % 9)},
    catalog: ['products', 'config-catalog', 'tool-catalog', 'accessory-catalog'].map((view, i) => ({view, label: ['设备', '配置', '工具', '附件'][i], enabled: i + 7, total: i + 12})), shares: {active: 123, views: 567},
    ...(role === 'admin' ? {admin: {customers: 17, staff: 4, audits: [{id: 'log1', actor: '管理员', action: '更新', entity_type: '产品', entity_id: 'cr1016', created_at: '2026-09-13 00:00:00'}]}} : {})};
}

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const errors = [];
  const requests = [];
  let mode = 'ok', role = 'admin';
  let holdLists = false, releaseLists;
  const context = await browser.newContext();
  await context.addInitScript(() => sessionStorage.setItem('boten_admin_token', 'fixture'));
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.pathname.startsWith('/api/')) {
      requests.push(url.pathname + url.search);
      if (url.pathname.endsWith('/auth/me')) return route.fulfill({json: {id: role === 'admin' ? 'admin' : 'a', role, display_name: 'Test user'}});
      if (url.pathname.endsWith('/staff/dashboard')) {
        if (mode === 'old') return route.fulfill({status: 404, json: {detail: 'Not Found'}});
        if (mode === 'failure') return route.fulfill({status: 500, json: {detail: 'failed'}});
        const data = fixture(role, Number(url.searchParams.get('days') || 30));
        if (mode === 'empty') { data.counts = {followup: 0, stale: 0, drafts: 0, due: 0}; data.tasks = {inquiries: [], drafts: [], due: []}; data.recent = {inquiries: [], quotes: [], shares: []}; }
        return route.fulfill({json: data});
      }
      if (holdLists && url.pathname.endsWith('/admin/products')) await new Promise(resolve => {releaseLists = resolve;});
      if (url.pathname === '/api/v1/quotes/q1') return route.fulfill({json: {...fixture(role).tasks.drafts[0], items: [], version: 1}});
      return route.fulfill({json: {items: [], total: 0, page: 1, products: []}});
    }
    let rel = decodeURIComponent(url.pathname).replace(/^\//, '');
    if (!path.extname(rel)) rel = rel.replace(/\/?$/, '/') + 'index.html';
    const file = path.resolve(root, rel);
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) return route.fulfill({status: 404, body: ''});
    const mime = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.ttf': 'font/ttf', '.svg': 'image/svg+xml', '.png': 'image/png'};
    return route.fulfill({body: fs.readFileSync(file), contentType: mime[path.extname(file)] || 'application/octet-stream'});
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  try {
    holdLists = true;
    await page.goto(base + '/admin/', {waitUntil: 'domcontentloaded'});
    await page.locator('#dashboard-body').waitFor({state: 'visible'});
    assert.equal(await page.locator('[data-dashboard-count=followup]').innerText(), '26', 'dashboard does not await list APIs');
    holdLists = false;
    // loadData may not yet have reached the held route, so release only if present.
    releaseLists?.();
    await page.waitForLoadState('networkidle');
    for (const [width, height] of [[1440, 900], [1024, 768], [768, 600], [390, 844], [320, 568]]) {
      await page.setViewportSize({width, height});
      await page.screenshot({path: path.join(output, `dashboard-${width}.png`), fullPage: true});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `page overflow at ${width}`);
      const panels = await page.locator('.dashboard-view .panel').evaluateAll(nodes => nodes.filter(n => !n.hidden).map(n => ({width: n.clientWidth, scroll: n.scrollWidth})));
      assert(panels.every(p => p.scroll <= p.width + 1), `panel overflow at ${width}`);
    }
    await page.locator('[data-dashboard-recent=shares]').click();
    assert.deepEqual(await page.locator('#dashboard-recent .badge').allTextContents(), ['有效', '已关闭', '已过期']);
    await page.locator('[data-dashboard-share="234567"]').click();
    assert.match(await page.locator('[data-share-drawer-body]').innerText(), /已关闭/);
    assert(await page.locator('[data-share-quote]').isDisabled());
    await page.locator('[data-share-drawer-close]').click();
    const badges = await page.locator('#dashboard-recent .badge').evaluateAll(nodes => nodes.map(n => {const s = getComputedStyle(n), r = n.getBoundingClientRect(), row = n.closest('.mini-row').getBoundingClientRect();return {display:s.display, margin:s.marginTop, offset:Math.abs((r.top+r.bottom-row.top-row.bottom)/2)};}));
    assert(badges.every(b => /flex/.test(b.display) && b.margin === '0px' && b.offset < 1));
    await page.locator('[data-dashboard-days="7"]').focus();
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => dashboardState.data.days === 7 && !dashboardState.loading);
    assert.equal(await page.locator('#dashboard-trend-date option').count(), 7);
    await page.locator('#dashboard-trend-date').selectOption({index: 0});
    assert.match(await page.locator('#dashboard-trend-detail').innerText(), /公共询价 0 份/);
    await page.locator('[data-dashboard-quote=q1]').first().click();
    await page.locator('.quote-editor-dialog[open]').waitFor();
    await page.evaluate(() => { const dialog = document.querySelector('.quote-editor-dialog[open]'); dialog.close(); dialog.remove(); });
    await page.evaluate(() => { state.shares = []; state.users = []; state.userTotal = 999; renderDashboard(); });
    assert.equal(await page.locator('[data-dashboard-count=followup]').innerText(), '26');
    await page.locator('[data-dashboard-queue=stale]').click();
    await page.waitForFunction(() => document.querySelector('[data-view-panel=inquiries]').classList.contains('active'));
    assert.equal(await page.locator('#inquiry-queue-filter').inputValue(), 'stale');
    assert(requests.some(r => r.includes('/staff/inquiries?') && r.includes('queue=stale') && r.includes('page=1')));
    await page.locator('#inquiry-filter-reset').click();
    assert.equal(await page.evaluate(() => state.inquiryQueue), 'all');
    await page.evaluate(() => switchView('dashboard'));
    await page.waitForFunction(() => !dashboardState.loading);
    await page.locator('[data-dashboard-queue=due]').click();
    await page.waitForFunction(() => document.querySelector('[data-view-panel=quotes]').classList.contains('active'));
    assert.equal(await page.locator('#quote-due-filter').inputValue(), 'due');
    assert(requests.some(r => r.includes('/quotes?') && r.includes('status=sent') && r.includes('due=true')));
    await page.locator('#quote-filter-reset').click();
    assert.equal(await page.evaluate(() => state.quoteDue), false);
    await page.evaluate(() => switchView('dashboard'));
    await page.waitForFunction(() => !dashboardState.loading);
    mode = 'failure';
    await page.locator('#dashboard-refresh').click();
    await page.waitForFunction(() => !dashboardState.loading);
    assert.match(await page.locator('#dashboard-message').innerText(), /保留上次数据/);
    assert.equal(await page.locator('[data-dashboard-count=followup]').innerText(), '26');
    mode = 'old';
    await page.reload();
    await page.waitForFunction(() => !!dashboardState.error);
    assert.match(await page.locator('#dashboard-message').innerText(), /尚不支持新版仪表盘/);
    assert(await page.locator('#dashboard-body').isHidden());
    mode = 'empty';
    await page.locator('#dashboard-refresh').click();
    await page.waitForFunction(() => !dashboardState.loading);
    assert.equal(await page.locator('[data-dashboard-count=followup]').innerText(), '0');
    assert.match(await page.locator('#dashboard-inquiries').innerText(), /暂无记录/);
    role = 'sales'; mode = 'ok';
    await page.goto(base + '/admin/');
    await page.locator('#dashboard-body').waitFor({state: 'visible'});
    assert(await page.locator('#dashboard-admin').isHidden());
    assert.match(await page.locator('#dashboard-scope').innerText(), /业务员/);
    assert.match(await page.locator('[data-dashboard-count=drafts]').locator('..').innerText(), /我的报价/);
    assert(await page.locator('.nav-item[data-view=dashboard]').isVisible());
    await page.goto(base + '/admin/#quotes');
    await page.locator('[data-view-panel=quotes].active').waitFor();
    assert.deepEqual(errors, []);
    console.log('PASS dashboard: 5 viewports, independent loading, role scope, queues/reset, date controls, keyboard, badges, errors/old API, empty state and direct links.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
