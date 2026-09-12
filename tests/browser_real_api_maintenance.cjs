const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const apiOrigin = process.env.BOTEN_E2E_API_ORIGIN;
const siteOrigin = process.env.BOTEN_E2E_SITE_ORIGIN;
if (!apiOrigin || !siteOrigin) throw new Error('Set BOTEN_E2E_API_ORIGIN and BOTEN_E2E_SITE_ORIGIN to an isolated environment.');
const priceKeys = new Set(['amount', 'base_price', 'grand_total', 'is_free', 'line_total', 'motor_base_price_cny', 'motor_base_price_usd', 'price', 'price_cny', 'price_cny_minor', 'price_usd', 'price_usd_minor', 'price_confirmed', 'pricing', 'pricing_by_currency', 'reference_price', 'total_price', 'unit_price']);
function hasPriceValue(value) {
  if (Array.isArray(value)) return value.some(hasPriceValue);
  if (!value || typeof value !== 'object') return false;
  return Object.entries(value).some(([key, item]) => priceKeys.has(key) || hasPriceValue(item));
}

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const runKey = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const page = await browser.newPage({ acceptDownloads: true });
    await page.addInitScript((origin) => { window.BOTEN_API_BASE = origin; }, apiOrigin);
    await page.goto(siteOrigin + '/');
    await page.waitForLoadState('networkidle');

    const request = (route, { token, method = 'GET', body } = {}) => page.evaluate(async ({ apiOrigin, route, token, method, body }) => {
      const response = await fetch(apiOrigin + '/api/v1' + route, {
        method,
        headers: { 'Content-Type': 'application/json', 'X-UI-Language': 'zh-CN', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const contentType = response.headers.get('content-type') || '';
      const bytes = contentType.includes('application/pdf') ? Array.from(new Uint8Array(await response.arrayBuffer())) : null;
      const payload = bytes ? null : await response.json().catch(() => ({}));
      return { status: response.status, payload, bytes, filename: response.headers.get('content-disposition') || '' };
    }, { apiOrigin, route, token, method, body });
    const required = async (route, options) => {
      const result = await request(route, options);
      assert(result.status >= 200 && result.status < 300, `${options?.method || 'GET'} ${route}: ${result.status} ${JSON.stringify(result.payload)}`);
      return result;
    };
    const login = async (email) => (await required('/auth/login', { method: 'POST', body: { identifier: email, password: 'password123' } })).payload;

    const customer = await login('e2e-customer@example.test');
    const sales = await login('e2e-sales@example.test');
    const admin = await login('e2e-admin@example.test');
    assert.equal(customer.user.role, 'customer'); assert.equal(sales.user.role, 'sales'); assert.equal(admin.user.role, 'admin');
    const profile = (await required('/auth/profile/details', { token: customer.session.token, method: 'PATCH', body: {
      address: 'Isolated E2E customer address', version: customer.user.version,
    } })).payload;
    customer.user = profile;
    const selections = {
      motor: 'base-cr1016-motor-motor-22kw-servo-motor',
      voltage: 'base-cr1016-power-voltage-default-380v-3phase',
      cri: ['cri-1016'],
    };
    const config = (await required('/configs', { token: sales.session.token, method: 'POST', body: {
      name: 'Maintenance E2E configuration', product_id: 'cr1016', color: 'Red', selections, lang: 'zh',
    } })).payload;
    const share = (await required('/cart/share', { token: sales.session.token, method: 'POST', body: {
      items: [{ item_type: 'device_config', id: config.id }], lang: 'zh', note: '隔离三角色验收', idempotency_key: `${runKey}-share-1`, reuse_existing: true,
    } })).payload;
    const replay = (await required('/cart/share', { token: sales.session.token, method: 'POST', body: {
      items: [{ item_type: 'device_config', id: config.id }], lang: 'en', note: 'different note is retained', idempotency_key: `${runKey}-share-2`, reuse_existing: true,
    } })).payload;
    assert.equal(replay.code, share.code); assert.equal(replay.note, '隔离三角色验收');

    const preview = (await required(`/customer/shares/${share.code}`, { token: customer.session.token })).payload;
    assert.equal(preview.note, '隔离三角色验收'); assert(!hasPriceValue(preview));
    await required(`/customer/shares/${share.code}/import`, { token: customer.session.token, method: 'POST', body: { lang: 'zh', idempotency_key: `${runKey}-import` } });
    const currentInquiry = (await required('/customer/inquiries/current-configuration', { token: customer.session.token, method: 'POST', body: {
      product_id: 'cr1016', color: 'Red', selections, lang: 'zh', message: '当前设备询价', idempotency_key: `${runKey}-current-inquiry`,
    } })).payload;
    const cartInquiry = (await required('/customer/inquiries/cart', { token: customer.session.token, method: 'POST', body: {
      lang: 'zh', message: '购物车询价', idempotency_key: `${runKey}-cart-inquiry`,
    } })).payload;
    assert.equal(currentInquiry.source_type, 'current_device'); assert.equal(cartInquiry.source_type, 'cart');
    assert(!hasPriceValue(cartInquiry));

    const staffList = (await required('/staff/inquiries?status=new', { token: sales.session.token })).payload.items;
    const staffItem = staffList.find((item) => item.id === cartInquiry.id); assert(staffItem, 'sales must discover the customer inquiry');
    const assigned = (await required(`/staff/inquiries/${cartInquiry.id}`, { token: sales.session.token, method: 'PATCH', body: {
      version: staffItem.version, status: 'assigned', assigned_to: sales.user.id,
    } })).payload;
    const quoteResult = (await required(`/staff/inquiries/${cartInquiry.id}/convert-to-quote`, { token: sales.session.token, method: 'POST', body: {
      version: assigned.version, currency: 'CNY', idempotency_key: `${runKey}-quote`,
    } })).payload;
    const quote = quoteResult.quote;
    assert(quote.customer_phone.replace(/\D/g, '').endsWith(customer.user.phone.replace(/\D/g, '')), 'converted quote must retain the customer phone');
    assert.equal(quote.customer_address, 'Isolated E2E customer address', 'converted quote must retain the customer address');
    await required(`/staff/quotes/${quote.id}/deliver`, { token: sales.session.token, method: 'POST', body: {
      recipient_user_id: customer.user.id, version: quote.version, idempotency_key: `${runKey}-deliver`,
    } });
    const customerQuote = (await required(`/customer/me/quotes/${quote.id}`, { token: customer.session.token })).payload;
    assert.equal(customerQuote.id, quote.id);

    const pdfRequests = [
      ['share-zh', `/shares/${share.code}/pdf?lang=zh`, sales.session.token, /^ShareBench-BOTEN\d{6}\.pdf$/],
      ['share-en', `/shares/${share.code}/pdf?lang=en`, sales.session.token, /^ShareBench-BOTEN\d{6}\.pdf$/],
      ['inquiry-zh', `/staff/inquiries/${cartInquiry.id}/pdf?lang=zh`, sales.session.token, /^RFQ-BOTEN\d{8}-\d{2,}\.pdf$/],
      ['inquiry-en', `/staff/inquiries/${cartInquiry.id}/pdf?lang=en`, sales.session.token, /^RFQ-BOTEN\d{8}-\d{2,}\.pdf$/],
      ['quote-zh', `/quotes/${quote.id}/pdf?lang=zh`, sales.session.token, /^QUOTA-BOTEN\d{8}-\d{4,}\.pdf$/],
      ['quote-en', `/quotes/${quote.id}/pdf?lang=en`, sales.session.token, /^QUOTA-BOTEN\d{8}-\d{4,}\.pdf$/],
      ['customer-quote', `/customer/me/quotes/${quote.id}/pdf`, customer.session.token, /^QUOTA-BOTEN\d{8}-\d{4,}\.pdf$/],
    ];
    const output = process.env.BOTEN_E2E_PDF_DIR;
    if (output) fs.mkdirSync(output, { recursive: true });
    for (const [label, route, token, filename] of pdfRequests) {
      const result = await required(route, { token });
      const name = decodeURIComponent((result.filename.match(/filename="?([^";]+)"?/) || [])[1] || '');
      assert.match(name, filename, `${label}: ${result.filename}`);
      const data = Buffer.from(result.bytes); assert(data.subarray(0, 4).equals(Buffer.from('%PDF')), `${label} is not PDF`);
      if (output) fs.writeFileSync(path.join(output, `${label}-${name}`), data);
    }
    const ownShares = (await required('/customer/me/shares?status=active', { token: sales.session.token })).payload.items;
    const ownShare = ownShares.find((item) => item.id === share.id); assert(ownShare, 'share owner must see active share');
    await required(`/customer/me/shares/${share.id}/status`, { token: sales.session.token, method: 'PATCH', body: { active: false, version: ownShare.customer_version } });
    const closed = await request(`/customer/shares/${share.code}`, { token: customer.session.token });
    assert.equal(closed.status, 410, 'closed share code must be unavailable');
    console.log('Browser-to-isolated-API three-role, share reuse, inquiries, quote delivery, 7 PDF downloads, and close invalidation passed.');
  } finally { await browser.close(); }
})();
