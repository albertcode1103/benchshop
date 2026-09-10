const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../admin/admin.js'), 'utf8');
const start = source.indexOf('function quoteCustomerContext(');
const end = source.indexOf('\nasync function openInquiryQuote(', start);
assert.ok(start >= 0 && end > start);
const inquiry = {
  id: 'inquiry-test', created_by: 'customer-test',
  customer_name_snapshot: 'Original name', customer_email_snapshot: 'original@example.test',
  customer_phone_snapshot: 'Original phone',
};
const context = vm.createContext({state: {inquiries: [inquiry]}});
vm.runInContext(source.slice(start, end), context);
const read = context.quoteCustomerContext;
const edited = read({source_inquiry_id: inquiry.id, customer_name: 'Edited name',
  customer_email: 'edited@example.test', customer_phone: 'Edited phone', customer_address: 'Edited address'});
assert.equal(edited.customerPhone, 'Edited phone');
assert.equal(edited.customerName, 'Edited name');
assert.equal(edited.customerEmail, 'edited@example.test');
assert.equal(edited.customerAddress, 'Edited address');
assert.equal(edited.recipientUserId, 'customer-test');
const blank = read({source_inquiry_id: inquiry.id, customer_name: '', customer_email: '', customer_phone: ''});
for (const field of ['customerName', 'customerEmail', 'customerPhone']) assert.equal(blank[field], '');
const legacy = read({source_inquiry_id: inquiry.id});
assert.equal(legacy.customerPhone, inquiry.customer_phone_snapshot);
assert.equal(legacy.customerName, inquiry.customer_name_snapshot);
assert.equal(legacy.customerEmail, inquiry.customer_email_snapshot);
context.state.inquiries = [];
assert.equal(read({}, inquiry).recipientUserId, 'customer-test');
assert.equal(read({}).customerPhone, '');
console.log('Quote customer snapshot behavior passed');
