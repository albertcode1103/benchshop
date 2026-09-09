const PROFILE_TOKEN_KEY = "boten_user_token";
const profileLanguage = localStorage.getItem("boten-language") === "en" ? "en" : "zh";
let profileUser = null;
let profileCountries = [];
let profileSharePage = 1;
let profileShareTotal = 0;
let profileInquiryPage = 1;
let profileInquiryTotal = 0;
const PROFILE_SHARE_PAGE_SIZE = 10;
const PROFILE_INQUIRY_PAGE_SIZE = 10;

const profileCopy = {
  zh: {
    pageTitle: "个人中心", backHome: "返回主页", myProfile: "我的资料", myAccount: "我的账号", contact: "联系方式", security: "密码与安全", signOut: "退出登录",
    profileDesc: "维护用于识别和联系您的基本资料。", name: "姓名", gender: "性别", unset: "未设置", male: "男", female: "女", other: "其他", birth: "生日", signature: "个性签名", saveProfile: "保存资料",
    contactDesc: "修改登录邮箱、国家和手机号。保存后需要重新登录。", email: "邮箱", country: "国家", phone: "手机号", currentPassword: "当前密码", saveRelogin: "保存并重新登录",
    securityDesc: "设置至少 8 个字符的新密码。修改后需要重新登录。", newPassword: "新密码", confirmPassword: "确认新密码", changeRelogin: "修改密码并重新登录",
    loading: "正在加载账号资料…", saved: "资料已保存。", redirecting: "修改已保存，即将返回登录页面。", nameRequired: "请填写姓名。", passwordRequired: "请输入当前密码。", passwordLength: "新密码至少需要 8 个字符。", passwordMismatch: "两次输入的新密码不一致。", requestFailed: "操作失败，请检查填写内容后重试。", networkError: "无法连接服务，请稍后重试。", selectCountry: "请选择国家", skip: "跳到主要内容", profileNav: "个人中心导航", phoneInvalid: "请输入有效手机号。", countryRequired: "请选择国家。", loadErrorTitle: "暂时无法加载个人中心", loadErrorMessage: "登录状态仍会保留，请检查服务状态后重试。", retry: "重新加载", myBusiness: "我的业务", myShares: "我的分享记录", myQuotes: "我的报价单", sharesDesc: "查看当前账号生成过的配置分享码及有效状态。", quotesDesc: "查看业务员发送给您的正式报价和 PDF。", active: "有效", expired: "已过期", closed: "已关闭", items: "项内容", views: "次查看", quoteCount: "份报价", createdAt: "创建于", expiresAt: "有效期至", details: "查看详情", copyCode: "复制分享码", copied: "分享码已复制", emptyShares: "当前账号还没有分享记录。", emptyQuotes: "当前账号还没有收到报价单。", previous: "上一页", next: "下一页", page: "第 {page} 页", newQuote: "新报价", viewed: "已查看", updated: "已更新", archivedQuote: "已撤回（仅历史记录）", sentAt: "发送于", quotationDetails: "报价详情", shareDetails: "分享详情", downloadPdf: "下载 PDF", unavailable: "当前已失效", total: "合计", quantity: "数量", unitPrice: "单价", loadingBusiness: "正在加载…", close: "关闭"
  },
  en: {
    pageTitle: "Profile", backHome: "Back to Home", myProfile: "My Profile", myAccount: "My Account", contact: "Contact Details", security: "Password & Security", signOut: "Sign Out",
    profileDesc: "Maintain the personal details used to identify your account.", name: "Name", gender: "Gender", unset: "Not set", male: "Male", female: "Female", other: "Other", birth: "Birthday", signature: "Signature", saveProfile: "Save Profile",
    contactDesc: "Update your sign-in email, country, and phone number. You will need to sign in again.", email: "Email", country: "Country", phone: "Phone", currentPassword: "Current Password", saveRelogin: "Save and Sign In Again",
    securityDesc: "Set a new password with at least 8 characters. You will need to sign in again.", newPassword: "New Password", confirmPassword: "Confirm New Password", changeRelogin: "Change Password and Sign In Again",
    loading: "Loading account details…", saved: "Profile saved.", redirecting: "Changes saved. Returning to sign in.", nameRequired: "Enter your name.", passwordRequired: "Enter your current password.", passwordLength: "The new password must contain at least 8 characters.", passwordMismatch: "The new passwords do not match.", requestFailed: "The request failed. Check the entered information and try again.", networkError: "Unable to reach the service. Try again later.", selectCountry: "Select country", skip: "Skip to main content", profileNav: "Profile navigation", phoneInvalid: "Enter a valid phone number.", countryRequired: "Select a country.", loadErrorTitle: "Unable to load your profile", loadErrorMessage: "Your sign-in is still saved. Check the service and try again.", retry: "Try Again", myBusiness: "My Business", myShares: "My Shares", myQuotes: "My Quotations", sharesDesc: "View configuration share codes created by this account and their current status.", quotesDesc: "View formal quotations sent to your account by the sales team.", active: "Active", expired: "Expired", closed: "Closed", items: "items", views: "views", quoteCount: "quotations", createdAt: "Created", expiresAt: "Expires", details: "View Details", copyCode: "Copy Code", copied: "Share code copied", emptyShares: "This account has no share records yet.", emptyQuotes: "This account has not received any quotations yet.", previous: "Previous", next: "Next", page: "Page {page}", newQuote: "New", viewed: "Viewed", updated: "Updated", archivedQuote: "Withdrawn (history only)", sentAt: "Sent", quotationDetails: "Quotation Details", shareDetails: "Share Details", downloadPdf: "Download PDF", unavailable: "Currently unavailable", total: "Total", quantity: "Quantity", unitPrice: "Unit Price", loadingBusiness: "Loading…", close: "Close"
  }
};
Object.assign(profileCopy.zh, {
  myInquiries: "我的询价", inquiriesDesc: "查看已经提交给销售人员的询价和当前处理进度。",
  emptyInquiries: "当前账号还没有询价记录。", inquiryDetails: "询价详情", inquiryNumber: "询价编号",
  inquirySource: "来源", currentDevice: "当前设备", cart: "购物车", submittedItems: "项内容",
  copyInquiry: "复制询价编号", inquiryCopied: "询价编号已复制", cancelInquiry: "取消询价",
  cancelInquiryConfirm: "仅处于新询价状态且尚未开始处理的记录可以取消。确定取消这条询价吗？",
  confirmCancel: "确认取消", inquiryCancelled: "询价已取消。", note: "补充说明",
  newInquiry: "新询价", assignedInquiry: "已分配", contactedInquiry: "已联系",
  quotedInquiry: "已报价", closedInquiry: "已完成", cancelledInquiry: "已取消"
});
Object.assign(profileCopy.en, {
  myInquiries: "My Inquiries", inquiriesDesc: "Review inquiries sent to sales and follow their current progress.",
  emptyInquiries: "This account has no inquiry records yet.", inquiryDetails: "Inquiry Details", inquiryNumber: "Inquiry number",
  inquirySource: "Source", currentDevice: "Current device", cart: "Cart", submittedItems: "items",
  copyInquiry: "Copy inquiry number", inquiryCopied: "Inquiry number copied", cancelInquiry: "Cancel Inquiry",
  cancelInquiryConfirm: "Only a new inquiry that has not been processed can be cancelled. Cancel this inquiry?",
  confirmCancel: "Cancel Inquiry", inquiryCancelled: "Inquiry cancelled.", note: "Note",
  newInquiry: "New", assignedInquiry: "Assigned", contactedInquiry: "Contacted",
  quotedInquiry: "Quoted", closedInquiry: "Completed", cancelledInquiry: "Cancelled"
});
const pc = profileCopy[profileLanguage];

class ProfileRequestError extends Error {
  constructor(message, { code = "REQUEST_FAILED", field = null, status = 0 } = {}) {
    super(message);
    this.name = "ProfileRequestError";
    this.code = code;
    this.field = field;
    this.status = status;
  }
}

async function profileRequest(path, options = {}) {
  const token = sessionStorage.getItem(PROFILE_TOKEN_KEY);
  if (!token) throw new Error("SESSION_REQUIRED");
  let response;
  try {
    response = await fetch(`${window.BOTEN_API_BASE || ""}/api/v1${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", "X-UI-Language": profileLanguage === "en" ? "en" : "zh-CN", Authorization: `Bearer ${token}`, ...(options.headers || {}) }
    });
  } catch (_) { throw new ProfileRequestError(pc.networkError, { code: "NETWORK_UNAVAILABLE" }); }
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ProfileRequestError(body.detail || pc.requestFailed, {
      code: body.error?.code || `HTTP_${response.status}`,
      field: body.error?.field,
      status: response.status
    });
  }
  return body;
}

function applyProfileCopy() {
  document.documentElement.lang = profileLanguage === "en" ? "en" : "zh-CN";
  document.title = `${pc.pageTitle} | BOTEN`;
  document.getElementById("profile-skip-link").textContent = pc.skip;
  document.getElementById("profile-brand-link").setAttribute("aria-label", pc.backHome);
  document.getElementById("profile-sidebar").setAttribute("aria-label", pc.profileNav);
  document.getElementById("profile-business-dialog-close").setAttribute("aria-label", pc.close);
  const values = {
    "profile-back-home": pc.backHome, "profile-account-group": pc.myAccount, "profile-sign-out": pc.signOut,
    "profile-details-title": pc.myProfile, "profile-details-description": pc.profileDesc, "profile-name-label": pc.name,
    "profile-gender-label": pc.gender, "profile-birth-label": pc.birth, "profile-signature-label": pc.signature, "profile-details-submit": pc.saveProfile,
    "profile-contact-title": pc.contact, "profile-contact-description": pc.contactDesc, "profile-email-label": pc.email, "profile-country-label": pc.country,
    "profile-phone-label": pc.phone, "profile-contact-password-label": pc.currentPassword, "profile-contact-submit": pc.saveRelogin,
    "profile-security-title": pc.security, "profile-security-description": pc.securityDesc, "profile-current-password-label": pc.currentPassword,
    "profile-new-password-label": pc.newPassword, "profile-confirm-password-label": pc.confirmPassword, "profile-password-submit": pc.changeRelogin,
    "profile-load-error-title": pc.loadErrorTitle, "profile-load-error-message": pc.loadErrorMessage,
    "profile-load-retry": pc.retry, "profile-load-back": pc.backHome, "profile-business-group": pc.myBusiness,
    "profile-shares-title": pc.myShares, "profile-shares-description": pc.sharesDesc,
    "profile-inquiries-title": pc.myInquiries, "profile-inquiries-description": pc.inquiriesDesc,
    "profile-quotes-title": pc.myQuotes, "profile-quotes-description": pc.quotesDesc,
    "profile-shares-prev": pc.previous, "profile-shares-next": pc.next,
    "profile-inquiries-prev": pc.previous, "profile-inquiries-next": pc.next
  };
  Object.entries(values).forEach(([id, value]) => { const element = document.getElementById(id); if (element) element.textContent = value; });
  const panelLabels = { profile: pc.myProfile, "account-contact": pc.contact, "account-security": pc.security, "my-shares": pc.myShares, "my-inquiries": pc.myInquiries, "my-quotes": pc.myQuotes };
  document.querySelectorAll("[data-account-panel]").forEach((button) => {
    const badge = button.querySelector(".profile-unread-badge");
    if (!badge) button.textContent = panelLabels[button.dataset.accountPanel];
    else button.firstChild.textContent = `${panelLabels[button.dataset.accountPanel]} `;
  });
  const gender = document.getElementById("profile-gender");
  gender.options[0].textContent = pc.unset; gender.options[1].textContent = pc.male; gender.options[2].textContent = pc.female; gender.options[3].textContent = pc.other;
  document.querySelectorAll("[data-language]").forEach((button) => { button.classList.toggle("active", button.dataset.language === profileLanguage); button.setAttribute("aria-pressed", String(button.dataset.language === profileLanguage)); });
}

function showProfilePanel(name) {
  const supported = ["profile", "account-contact", "account-security", "my-shares", "my-inquiries", "my-quotes"];
  const panel = supported.includes(name) ? name : "profile";
  document.querySelectorAll("[data-account-content]").forEach((section) => { section.hidden = section.dataset.accountContent !== panel; });
  document.querySelectorAll("[data-account-panel]").forEach((button) => { const active = button.dataset.accountPanel === panel; button.classList.toggle("active", active); button.toggleAttribute("aria-current", active); });
  if (location.hash !== `#${panel}`) history.replaceState(null, "", `#${panel}`);
}

function renderProfileUser() {
  const name = profileUser.display_name || profileUser.email || profileUser.phone || pc.pageTitle;
  document.getElementById("profile-initial").textContent = name.charAt(0).toUpperCase();
  document.getElementById("profile-sidebar-name").textContent = name;
  document.getElementById("profile-sidebar-contact").textContent = profileUser.email || [profileUser.phone_calling_code, profileUser.phone].filter(Boolean).join(" ");
  document.getElementById("profile-display-name").value = profileUser.display_name || "";
  document.getElementById("profile-gender").value = profileUser.gender || "";
  document.getElementById("profile-birth-date").value = profileUser.birth_date || "";
  document.getElementById("profile-signature").value = profileUser.signature || "";
  document.getElementById("profile-email").value = profileUser.email || "";
  document.getElementById("profile-country").value = profileUser.phone_country || "CN";
  document.getElementById("profile-phone").value = profileUser.phone || "";
  updateProfileCallingCode();
  updateSignatureCount();
}

function setFormStatus(id, message, type = "") {
  const status = document.getElementById(id); status.textContent = message; status.className = `profile-form-status${type ? ` is-${type}` : ""}`;
}

function focusProfileError(error, fallbackId) {
  const fields = { display_name: "profile-display-name", gender: "profile-gender", birth_date: "profile-birth-date", signature: "profile-signature", email: "profile-email", phone_country: "profile-country", phone: "profile-phone", current_password: fallbackId, password: "profile-new-password", confirm_password: "profile-confirm-password" };
  const target = document.getElementById(fields[error.field] || fallbackId); target?.setAttribute("aria-invalid", "true"); target?.focus();
}

async function saveProfileDetails(event) {
  event.preventDefault();
  const name = document.getElementById("profile-display-name").value.trim();
  if (!name) { setFormStatus("profile-details-status", pc.nameRequired, "error"); document.getElementById("profile-display-name").focus(); return; }
  const button = document.getElementById("profile-details-submit"); button.disabled = true;
  try {
    profileUser = await profileRequest("/auth/profile/details", { method: "PATCH", body: JSON.stringify({ display_name: name, gender: document.getElementById("profile-gender").value, birth_date: document.getElementById("profile-birth-date").value || null, signature: document.getElementById("profile-signature").value.trim(), version: profileUser.version }) });
    renderProfileUser(); setFormStatus("profile-details-status", pc.saved, "success");
  } catch (error) { setFormStatus("profile-details-status", error.message || pc.requestFailed, "error"); focusProfileError(error, "profile-display-name"); }
  finally { button.disabled = false; }
}

function nationalPhone(required = true) {
  const phone = document.getElementById("profile-phone").value.trim().replace(/\s+/g, "");
  if (!phone && !required) return null;
  if (!/^\d{6,15}$/.test(phone)) throw Object.assign(new Error(pc.phoneInvalid), { field: "phone" });
  return phone;
}

async function saveProfileContact(event) {
  event.preventDefault();
  const password = document.getElementById("profile-contact-password").value;
  if (!password) { setFormStatus("profile-contact-status", pc.passwordRequired, "error"); document.getElementById("profile-contact-password").focus(); return; }
  const button = document.getElementById("profile-contact-submit"); button.disabled = true;
  try {
    const phoneValue = document.getElementById("profile-phone").value.trim();
    const countryValue = document.getElementById("profile-country").value;
    if (phoneValue && !countryValue) throw Object.assign(new Error(pc.countryRequired), { field: "phone_country" });
    const payload = {
      current_password: password,
      email: document.getElementById("profile-email").value.trim().toLowerCase()
    };
    if (phoneValue) {
      payload.phone_country = countryValue;
      payload.phone = nationalPhone();
    }
    await profileRequest("/auth/profile/contact", { method: "PATCH", body: JSON.stringify(payload) });
    setFormStatus("profile-contact-status", pc.redirecting, "success"); sessionStorage.removeItem(PROFILE_TOKEN_KEY); setTimeout(() => location.replace("../?auth=login"), 500);
  } catch (error) { setFormStatus("profile-contact-status", error.message || pc.requestFailed, "error"); focusProfileError(error, "profile-contact-password"); button.disabled = false; }
}

async function saveProfilePassword(event) {
  event.preventDefault();
  const current = document.getElementById("profile-current-password").value;
  const next = document.getElementById("profile-new-password").value;
  const confirm = document.getElementById("profile-confirm-password").value;
  if (!current) { setFormStatus("profile-password-status", pc.passwordRequired, "error"); document.getElementById("profile-current-password").focus(); return; }
  if (next.length < 8) { setFormStatus("profile-password-status", pc.passwordLength, "error"); document.getElementById("profile-new-password").focus(); return; }
  if (next !== confirm) { setFormStatus("profile-password-status", pc.passwordMismatch, "error"); document.getElementById("profile-confirm-password").focus(); return; }
  const button = document.getElementById("profile-password-submit"); button.disabled = true;
  try {
    await profileRequest("/auth/change-password", { method: "POST", body: JSON.stringify({ current_password: current, new_password: next, confirm_password: confirm }) });
    setFormStatus("profile-password-status", pc.redirecting, "success"); sessionStorage.removeItem(PROFILE_TOKEN_KEY); setTimeout(() => location.replace("../?auth=login"), 500);
  } catch (error) { setFormStatus("profile-password-status", error.message || pc.requestFailed, "error"); focusProfileError(error, "profile-current-password"); button.disabled = false; }
}

function updateProfileCallingCode() {
  const country = profileCountries.find((item) => item.code === document.getElementById("profile-country").value);
  document.getElementById("profile-calling-code").textContent = country?.calling_code || "-";
}

function updateSignatureCount() { document.getElementById("profile-signature-count").textContent = `${document.getElementById("profile-signature").value.length} / 160`; }

function escapeProfileHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[character]));
}

function normalizeProfileCatalogCode(value) {
  const raw = String(value || "").trim().toUpperCase();
  const code = raw.replace(/\s+/g, "");
  const match = code.match(/^(BTE|BTK|BTC|BT)-?([A-Z0-9]+)$/);
  return match ? `${match[1]}-${match[2]}` : raw;
}

function profileCatalogName(name, code) {
  let text = String(name || "").trim();
  const canonical = normalizeProfileCatalogCode(code);
  for (const alias of [String(code || "").trim(), canonical, canonical.replace(/-/g, "")].filter(Boolean).sort((a, b) => b.length - a.length)) {
    const escaped = alias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const updated = text.replace(new RegExp(`^${escaped}(?=$|[\\s·:：/\\\\|_—–-])(?:[\\s·:：/\\\\|_—–-]+)?`, "i"), "").trim();
    if (updated !== text) { text = updated; break; }
  }
  return text;
}

function profileCatalogIdentity(code, name, fallback = "--") {
  const canonical = normalizeProfileCatalogCode(code);
  const cleanName = profileCatalogName(name, canonical) || fallback;
  return `${canonical ? `<small class="profile-catalog-code">${escapeProfileHtml(canonical)}</small>` : ""}<span>${escapeProfileHtml(cleanName)}</span>`;
}

function profileDate(value) {
  if (!value) return "--";
  const dateValue = new Date(value);
  if (Number.isNaN(dateValue.getTime())) return String(value);
  return new Intl.DateTimeFormat(profileLanguage === "en" ? "en" : "zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(dateValue);
}

function profileMoney(value, currency) {
  return new Intl.NumberFormat(profileLanguage === "en" ? "en-US" : "zh-CN", { style: "currency", currency: currency === "USD" ? "USD" : "CNY" }).format(Number(value || 0));
}

function shareStatusLabel(status) { return pc[status] || status; }

function inquiryStatusLabel(status) {
  return {
    new: pc.newInquiry, assigned: pc.assignedInquiry, contacted: pc.contactedInquiry,
    quoted: pc.quotedInquiry, closed: pc.closedInquiry, cancelled: pc.cancelledInquiry
  }[status] || status || "--";
}

function inquirySourceLabel(source) {
  return source === "current_device" ? pc.currentDevice : source === "cart" ? pc.cart : source || "--";
}

async function copyProfileText(value, button, statusId, successMessage) {
  try {
    await navigator.clipboard.writeText(value);
    const original = button.textContent;
    button.textContent = successMessage;
    setTimeout(() => { if (button.isConnected) button.textContent = original; }, 1400);
  } catch (error) {
    const field = document.createElement("textarea");
    field.value = value;
    field.setAttribute("readonly", "");
    field.className = "profile-copy-fallback";
    document.body.appendChild(field);
    field.select();
    const copied = document.execCommand("copy");
    field.remove();
    if (!copied) throw error;
    setFormStatus(statusId, successMessage, "success");
  }
}

async function loadProfileInquiries(page = profileInquiryPage) {
  const status = document.getElementById("profile-inquiries-status");
  status.textContent = pc.loadingBusiness;
  try {
    const result = await profileRequest(`/customer/me/inquiries?page=${page}&page_size=${PROFILE_INQUIRY_PAGE_SIZE}`);
    profileInquiryPage = Number(result.page || 1);
    profileInquiryTotal = Number(result.total || 0);
    const list = document.getElementById("profile-inquiries-list");
    list.innerHTML = result.items.length ? result.items.map((inquiry) => `
      <article class="profile-business-card">
        <div class="profile-business-card-main"><strong translate="no">${escapeProfileHtml(inquiry.inquiry_number)}</strong><span>${escapeProfileHtml(inquirySourceLabel(inquiry.source_type))}</span></div>
        <div class="profile-business-card-actions"><button class="btn btn-secondary btn-sm" type="button" data-copy-inquiry="${escapeProfileHtml(inquiry.inquiry_number)}">${pc.copyInquiry}</button><button class="btn btn-secondary btn-sm" type="button" data-open-inquiry="${escapeProfileHtml(inquiry.id)}">${pc.details}</button>${inquiry.status === "new" ? `<button class="btn btn-secondary btn-sm profile-danger-action" type="button" data-cancel-inquiry="${escapeProfileHtml(inquiry.id)}" data-inquiry-version="${Number(inquiry.version || 0)}" data-inquiry-number="${escapeProfileHtml(inquiry.inquiry_number)}">${pc.cancelInquiry}</button>` : ""}</div>
        <div class="profile-business-card-meta"><span class="profile-status-badge${inquiry.status === "new" ? " is-new" : inquiry.status === "cancelled" ? " is-off" : ""}">${escapeProfileHtml(inquiryStatusLabel(inquiry.status))}</span><span>${Number(inquiry.item_count || 0)} ${pc.submittedItems}</span><span>${pc.createdAt} ${profileDate(inquiry.created_at)}</span>${inquiry.updated_at && inquiry.updated_at !== inquiry.created_at ? `<span>${pc.updated} ${profileDate(inquiry.updated_at)}</span>` : ""}</div>
      </article>`).join("") : `<div class="profile-list-empty">${pc.emptyInquiries}</div>`;
    const pages = Math.max(1, Math.ceil(profileInquiryTotal / PROFILE_INQUIRY_PAGE_SIZE));
    document.getElementById("profile-inquiries-page").textContent = pc.page.replace("{page}", String(profileInquiryPage));
    document.getElementById("profile-inquiries-prev").disabled = profileInquiryPage <= 1;
    document.getElementById("profile-inquiries-next").disabled = profileInquiryPage >= pages;
    status.textContent = "";
    status.className = "profile-form-status";
  } catch (error) {
    status.textContent = error.message || pc.requestFailed;
    status.className = "profile-form-status is-error";
  }
}

async function loadProfileShares(page = profileSharePage) {
  const status = document.getElementById("profile-shares-status");
  status.textContent = pc.loadingBusiness;
  try {
    const result = await profileRequest(`/customer/me/shares?page=${page}&page_size=${PROFILE_SHARE_PAGE_SIZE}`);
    profileSharePage = Number(result.page || 1);
    profileShareTotal = Number(result.total || 0);
    const list = document.getElementById("profile-shares-list");
    list.innerHTML = result.items.length ? result.items.map((share) => `
      <article class="profile-business-card">
        <div class="profile-business-card-main"><strong>${escapeProfileHtml(share.title || share.code)}</strong><span>${escapeProfileHtml(share.code)}</span></div>
        <div class="profile-business-card-actions"><button class="btn btn-secondary btn-sm" type="button" data-copy-share="${escapeProfileHtml(share.code)}">${pc.copyCode}</button><button class="btn btn-secondary btn-sm" type="button" data-open-share="${escapeProfileHtml(share.id)}">${pc.details}</button></div>
        <div class="profile-business-card-meta"><span class="profile-status-badge${share.status === "active" ? "" : " is-off"}">${shareStatusLabel(share.status)}</span><span>${Number(share.item_count || 0)} ${pc.items}</span><span>${Number(share.view_count || 0)} ${pc.views}</span><span>${Number(share.quote_count || 0)} ${pc.quoteCount}</span><span>${pc.createdAt} ${profileDate(share.created_at)}</span><span>${pc.expiresAt} ${profileDate(share.expires_at)}</span></div>
      </article>`).join("") : `<div class="profile-list-empty">${pc.emptyShares}</div>`;
    const pages = Math.max(1, Math.ceil(profileShareTotal / PROFILE_SHARE_PAGE_SIZE));
    document.getElementById("profile-shares-page").textContent = pc.page.replace("{page}", String(profileSharePage));
    document.getElementById("profile-shares-prev").disabled = profileSharePage <= 1;
    document.getElementById("profile-shares-next").disabled = profileSharePage >= pages;
    status.textContent = ""; status.className = "profile-form-status";
  } catch (error) { status.textContent = error.message || pc.requestFailed; status.className = "profile-form-status is-error"; }
}

async function loadProfileQuotes() {
  const status = document.getElementById("profile-quotes-status");
  status.textContent = pc.loadingBusiness;
  try {
    const result = await profileRequest("/customer/me/quotes");
    const unreadBadge = document.getElementById("profile-quote-unread");
    unreadBadge.textContent = String(result.unread_count || 0);
    unreadBadge.hidden = !result.unread_count;
    const list = document.getElementById("profile-quotes-list");
    list.innerHTML = result.items.length ? result.items.map((quote) => {
      const delivery = quote.delivery || {};
      const archived = quote.lifecycle_status === "archived" || quote.prices_hidden;
      const viewed = Boolean(delivery.viewed_at);
      const state = archived ? pc.archivedQuote : quote.unread ? (viewed ? pc.updated : pc.newQuote) : pc.viewed;
      return `<article class="profile-business-card${quote.unread ? " is-unread" : ""}">
        <div class="profile-business-card-main"><strong>${escapeProfileHtml(quote.title)}</strong><span>${escapeProfileHtml(quote.sender?.display_name || quote.sender?.email || "BOTEN")}</span></div>
        <div class="profile-business-card-actions">${archived ? "" : `<button class="btn btn-secondary btn-sm" type="button" data-open-quote="${escapeProfileHtml(quote.id)}">${pc.details}</button><button class="btn btn-secondary btn-sm" type="button" data-download-quote="${escapeProfileHtml(quote.id)}">${pc.downloadPdf}</button>`}</div>
        <div class="profile-business-card-meta"><span class="profile-status-badge${quote.unread ? " is-new" : ""}">${state}</span>${archived ? "" : `<span>${profileMoney(quote.total_price, quote.currency)}</span>`}<span>${pc.sentAt} ${profileDate(delivery.delivered_at)}</span></div>
      </article>`;
    }).join("") : `<div class="profile-list-empty">${pc.emptyQuotes}</div>`;
    status.textContent = ""; status.className = "profile-form-status";
  } catch (error) { status.textContent = error.message || pc.requestFailed; status.className = "profile-form-status is-error"; }
}

function openProfileBusinessDialog(title, kicker, body, actions = "") {
  document.getElementById("profile-business-dialog-title").textContent = title;
  document.getElementById("profile-business-dialog-kicker").textContent = kicker;
  document.getElementById("profile-business-dialog-body").innerHTML = body;
  const actionBar = document.getElementById("profile-business-dialog-actions");
  actionBar.innerHTML = actions;
  actionBar.hidden = !actions;
  const dialog = document.getElementById("profile-business-dialog");
  if (!dialog.open) dialog.showModal();
}

function renderProfileDevicePreview(item, index) {
  const snapshot = item.snapshot || {};
  const product = snapshot.product || {};
  const categories = snapshot.categories || [];
  const baseIds = new Set(["motor", "voltage", "channel"]);
  const configured = (value) => {
    const normalized = String(value || "").trim().toLocaleLowerCase();
    return Boolean(normalized) && !new Set(["未配置", "未选择", "无", "none", "not configured", "not selected", "n/a", "—", "-"]).has(normalized);
  };
  const singleValue = (id) => categories.find((category) => category.id === id)?.options?.map((option) => option.name || option.code).filter(configured).join(" / ") || "";
  const basics = [
    [profileLanguage === "en" ? "Model" : "型号", product.name],
    [profileLanguage === "en" ? "Name" : "名称", product.title_name],
    [profileLanguage === "en" ? "Appearance" : "外观颜色", snapshot.color?.label || snapshot.color?.code],
    [profileLanguage === "en" ? "Motor" : "电机", singleValue("motor")],
    [profileLanguage === "en" ? "Power Supply" : "电源", singleValue("voltage")],
    [profileLanguage === "en" ? "Channels" : "通道", singleValue("channel")],
  ].filter(([, value]) => configured(value)).map(([label, value]) => `<div><span>${label}</span><strong>${escapeProfileHtml(value)}</strong></div>`).join("");
  const optionGroups = categories.filter((category) => !baseIds.has(category.id) && (category.options || []).length).map((category) => {
    const rows = category.options.map((option) => `<li><span>${profileCatalogIdentity(option.code, option.name, profileLanguage === "en" ? "Unnamed option" : "未命名配置")}${option.description ? `<small>${escapeProfileHtml(String(option.description).replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim())}</small>` : ""}</span><strong>× 1</strong></li>`).join("");
    return `<section class="profile-device-option-group"><header><strong>${escapeProfileHtml(category.name)}</strong><small>${category.options.length} ${profileLanguage === "en" ? "items" : "项"}</small></header><ul>${rows}</ul></section>`;
  }).join("");
  const warning = item.available ? "" : `<small class="profile-device-warning">${pc.unavailable}${item.missing?.length ? `: ${item.missing.map(escapeProfileHtml).join(", ")}` : ""}</small>`;
  return `<article class="profile-device-preview${item.available ? "" : " is-unavailable"}"><h4>${profileLanguage === "en" ? "Device" : "设备"} ${index + 1} · ${escapeProfileHtml(product.name || item.display_name || "--")} <span>× ${Number(item.quantity || 1)}</span></h4>${warning}<section class="profile-device-basics"><header><strong>${profileLanguage === "en" ? "Device Information" : "设备信息"}</strong><small>${profileLanguage === "en" ? "Model and base configuration" : "型号与基本配置"}</small></header><div>${basics}</div></section><div class="profile-device-option-groups">${optionGroups || `<p class="profile-device-empty">${profileLanguage === "en" ? "No optional configuration selected." : "该设备未选择其他选配项目"}</p>`}</div></article>`;
}

async function openOwnShare(shareId) {
  const result = await profileRequest(`/customer/me/shares/${encodeURIComponent(shareId)}?lang=${profileLanguage}`);
  const devices = result.items.filter((item) => (item.item_type || "device_config") === "device_config");
  const deviceSection = devices.length ? `<section class="profile-detail-group profile-device-section"><h3>${profileLanguage === "en" ? "Devices" : "设备"}</h3>${devices.map(renderProfileDevicePreview).join("")}</section>` : "";
  const catalogSections = [["tool", profileLanguage === "en" ? "Service Tools" : "维修工具"], ["accessory", profileLanguage === "en" ? "Accessories" : "设备附件"]].map(([type, label]) => {
    const items = result.items.filter((item) => (item.item_type || "device_config") === type);
    if (!items.length) return "";
    return `<section class="profile-detail-group"><h3>${label}</h3><div class="profile-detail-list">${items.map((item) => {
      const snapshot = item.snapshot || {};
      const missing = item.available ? "" : `<small>${pc.unavailable}${item.missing?.length ? `: ${item.missing.map(escapeProfileHtml).join(", ")}` : ""}</small>`;
      return `<div class="profile-detail-row${item.available ? "" : " is-unavailable"}"><span>${profileCatalogIdentity(snapshot.code, snapshot.name || item.display_name)}${missing}</span><strong>× ${Number(item.quantity || 1)}</strong></div>`;
    }).join("")}</div></section>`;
  }).join("");
  const body = deviceSection + catalogSections;
  const note = result.note ? `<section class="profile-detail-group profile-share-note"><h3>${profileLanguage === "en" ? "Share note" : "分享备注"}</h3><p>${escapeProfileHtml(result.note)}</p></section>` : "";
  openProfileBusinessDialog(result.title || result.code, pc.shareDetails, note + (body || `<div class="profile-list-empty">${pc.emptyShares}</div>`));
}

async function openOwnInquiry(inquiryId) {
  const inquiry = await profileRequest(`/customer/me/inquiries/${encodeURIComponent(inquiryId)}?lang=${profileLanguage}`);
  const groups = [["device_config", profileLanguage === "en" ? "Devices" : "设备"], ["tool", profileLanguage === "en" ? "Service Tools" : "维修工具"], ["accessory", profileLanguage === "en" ? "Accessories" : "设备附件"]];
  const summary = `<section class="profile-detail-group"><div class="profile-detail-list">
    <div class="profile-detail-row"><span>${pc.inquiryNumber}</span><strong translate="no">${escapeProfileHtml(inquiry.inquiry_number)}</strong></div>
    <div class="profile-detail-row"><span>${pc.inquirySource}</span><strong>${escapeProfileHtml(inquirySourceLabel(inquiry.source_type))}</strong></div>
    <div class="profile-detail-row"><span>${profileLanguage === "en" ? "Status" : "状态"}</span><strong>${escapeProfileHtml(inquiryStatusLabel(inquiry.status))}</strong></div>
    <div class="profile-detail-row"><span>${pc.createdAt}</span><strong>${profileDate(inquiry.created_at)}</strong></div>
  </div></section>`;
  const sourceCodes = (inquiry.source_codes || []).length
    ? `<section class="profile-detail-group"><h3>${profileLanguage === "en" ? "Related share codes" : "关联分享码"}</h3><div class="profile-source-codes">${inquiry.source_codes.map((code) => `<code translate="no">${escapeProfileHtml(code)}</code>`).join("")}</div></section>`
    : "";
  const contents = groups.map(([type, label]) => {
    const items = (inquiry.items || []).filter((item) => (item.item_type || "device_config") === type);
    if (!items.length) return "";
    return `<section class="profile-detail-group"><h3>${label}</h3><div class="profile-detail-list">${items.map((item) => {
      const snapshot = item.snapshot || {};
      const product = snapshot.product || {};
      const name = type === "device_config" ? [product.name, product.title_name].filter(Boolean).join(" ") : "";
      const unavailable = item.availability && item.availability !== "active";
      const warning = unavailable ? `<small>${pc.unavailable}</small>` : "";
      return `<div class="profile-detail-row${unavailable ? " is-unavailable" : ""}"><span>${type === "device_config" ? escapeProfileHtml(name || item.display_name || "--") : profileCatalogIdentity(snapshot.code, snapshot.name || item.display_name)}${warning}</span><strong>× ${Number(item.quantity || 1)}</strong></div>`;
    }).join("")}</div></section>`;
  }).join("");
  const note = inquiry.message ? `<section class="profile-detail-group"><h3>${pc.note}</h3><p class="profile-inquiry-note">${escapeProfileHtml(inquiry.message)}</p></section>` : "";
  const actions = inquiry.status === "new"
    ? `<button class="btn btn-secondary profile-danger-action" type="button" data-cancel-inquiry="${escapeProfileHtml(inquiry.id)}" data-inquiry-version="${Number(inquiry.version || 0)}" data-inquiry-number="${escapeProfileHtml(inquiry.inquiry_number)}">${pc.cancelInquiry}</button>`
    : "";
  openProfileBusinessDialog(inquiry.inquiry_number, pc.inquiryDetails, summary + sourceCodes + contents + note, actions);
}

function confirmCancelOwnInquiry(inquiryId, version, inquiryNumber) {
  const body = `<section class="profile-detail-group"><p class="profile-inquiry-confirm">${escapeProfileHtml(pc.cancelInquiryConfirm)}</p></section>`;
  const actions = `<button class="btn btn-secondary" type="button" data-close-business-dialog>${pc.close}</button><button class="btn btn-danger" type="button" data-confirm-cancel-inquiry="${escapeProfileHtml(inquiryId)}" data-inquiry-version="${Number(version || 0)}">${pc.confirmCancel}</button>`;
  openProfileBusinessDialog(inquiryNumber, pc.cancelInquiry, body, actions);
}

async function cancelOwnInquiry(button) {
  const inquiryId = button.dataset.confirmCancelInquiry;
  button.disabled = true;
  try {
    await profileRequest(`/customer/me/inquiries/${encodeURIComponent(inquiryId)}/cancel`, {
      method: "POST", body: JSON.stringify({ version: Number(button.dataset.inquiryVersion || 0) })
    });
    document.getElementById("profile-business-dialog").close();
    setFormStatus("profile-inquiries-status", pc.inquiryCancelled, "success");
    await loadProfileInquiries();
  } finally {
    if (button.isConnected) button.disabled = false;
  }
}

async function openOwnQuote(quoteId) {
  const quote = await profileRequest(`/customer/me/quotes/${encodeURIComponent(quoteId)}`);
  const rows = (quote.items || []).map((item) => `<div class="profile-detail-row"><span>${profileCatalogIdentity(item.code, item.name)}<small>${pc.quantity}: ${Number(item.quantity || 1)}</small></span><strong>${profileMoney(Number(item.quantity || 1) * Number(item.price || 0), quote.currency)}</strong></div>`).join("");
  const body = `<section class="profile-detail-group"><h3>${escapeProfileHtml(quote.sender?.display_name || "BOTEN")}</h3><div class="profile-detail-list">${rows}</div><div class="profile-quote-total"><span>${pc.total}</span><strong>${profileMoney(quote.total_price, quote.currency)}</strong></div></section>`;
  openProfileBusinessDialog(quote.title, pc.quotationDetails, body, `<button class="btn btn-primary" type="button" data-download-quote="${escapeProfileHtml(quote.id)}">${pc.downloadPdf}</button>`);
  await loadProfileQuotes();
}

async function downloadOwnQuote(quoteId) {
  const response = await fetch(`${window.BOTEN_API_BASE || ""}/api/v1/customer/me/quotes/${encodeURIComponent(quoteId)}/pdf`, { headers: { Authorization: `Bearer ${sessionStorage.getItem(PROFILE_TOKEN_KEY)}`, "X-UI-Language": profileLanguage === "en" ? "en" : "zh-CN" } });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || pc.requestFailed); }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a"); link.href = url; link.download = `BOTEN-quote-${quoteId.slice(0, 8)}.pdf`; document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  await loadProfileQuotes();
}

async function handleProfileBusinessAction(event) {
  const copyButton = event.target.closest("[data-copy-share]");
  if (copyButton) {
    try { await copyProfileText(copyButton.dataset.copyShare, copyButton, "profile-shares-status", pc.copied); }
    catch (error) { setFormStatus("profile-shares-status", error.message || pc.requestFailed, "error"); }
    return;
  }
  const copyInquiryButton = event.target.closest("[data-copy-inquiry]");
  if (copyInquiryButton) {
    try { await copyProfileText(copyInquiryButton.dataset.copyInquiry, copyInquiryButton, "profile-inquiries-status", pc.inquiryCopied); }
    catch (error) { setFormStatus("profile-inquiries-status", error.message || pc.requestFailed, "error"); }
    return;
  }
  const shareButton = event.target.closest("[data-open-share]");
  const inquiryButton = event.target.closest("[data-open-inquiry]");
  const quoteButton = event.target.closest("[data-open-quote]");
  const downloadButton = event.target.closest("[data-download-quote]");
  const cancelButton = event.target.closest("[data-cancel-inquiry]");
  const confirmCancelButton = event.target.closest("[data-confirm-cancel-inquiry]");
  const closeButton = event.target.closest("[data-close-business-dialog]");
  try {
    if (shareButton) await openOwnShare(shareButton.dataset.openShare);
    if (inquiryButton) await openOwnInquiry(inquiryButton.dataset.openInquiry);
    if (quoteButton) await openOwnQuote(quoteButton.dataset.openQuote);
    if (downloadButton) await downloadOwnQuote(downloadButton.dataset.downloadQuote);
    if (cancelButton) confirmCancelOwnInquiry(cancelButton.dataset.cancelInquiry, cancelButton.dataset.inquiryVersion, cancelButton.dataset.inquiryNumber);
    if (confirmCancelButton) await cancelOwnInquiry(confirmCancelButton);
    if (closeButton) document.getElementById("profile-business-dialog").close();
  } catch (error) {
    const statusId = shareButton ? "profile-shares-status" : inquiryButton || cancelButton || confirmCancelButton ? "profile-inquiries-status" : "profile-quotes-status";
    setFormStatus(statusId, error.message || pc.requestFailed, "error");
  }
}

async function signOutProfile() {
  try { await profileRequest("/auth/logout", { method: "POST" }); } catch (_) {}
  sessionStorage.removeItem(PROFILE_TOKEN_KEY); location.replace("../");
}

async function initProfilePage() {
  applyProfileCopy();
  if (!sessionStorage.getItem(PROFILE_TOKEN_KEY)) { location.replace("../?auth=login"); return; }
  try {
    [profileUser, profileCountries] = await Promise.all([profileRequest("/auth/profile"), profileRequest(`/auth/countries?lang=${profileLanguage}`)]);
  } catch (error) {
    if (error?.status === 401 || error?.code === "ACCOUNT_SESSION_EXPIRED") {
      sessionStorage.removeItem(PROFILE_TOKEN_KEY);
      location.replace("../?auth=login");
      return;
    }
    document.querySelectorAll("[data-account-content]").forEach((section) => { section.hidden = true; });
    document.getElementById("profile-load-error").hidden = false;
    document.getElementById("profile-load-error-message").textContent = error?.message || pc.loadErrorMessage;
    document.getElementById("profile-load-retry").addEventListener("click", () => location.reload());
    return;
  }
  const countrySelect = document.getElementById("profile-country");
  countrySelect.innerHTML = `<option value="">${pc.selectCountry}</option>` + profileCountries.items.map((item) => `<option value="${item.code}">${item.name}</option>`).join("");
  profileCountries = profileCountries.items;
  document.getElementById("profile-birth-date").max = new Date().toISOString().slice(0, 10);
  renderProfileUser();
  showProfilePanel(location.hash.slice(1));
  loadProfileShares().catch(() => {});
  loadProfileInquiries().catch(() => {});
  loadProfileQuotes().catch(() => {});
  document.querySelectorAll("[data-account-panel]").forEach((button) => button.addEventListener("click", () => showProfilePanel(button.dataset.accountPanel)));
  document.getElementById("profile-details-form").addEventListener("submit", saveProfileDetails);
  document.getElementById("profile-contact-form").addEventListener("submit", saveProfileContact);
  document.getElementById("profile-password-form").addEventListener("submit", saveProfilePassword);
  document.getElementById("profile-country").addEventListener("change", updateProfileCallingCode);
  document.getElementById("profile-signature").addEventListener("input", updateSignatureCount);
  document.getElementById("profile-sign-out").addEventListener("click", signOutProfile);
  document.getElementById("profile-shares-prev").addEventListener("click", () => { if (profileSharePage > 1) loadProfileShares(profileSharePage - 1); });
  document.getElementById("profile-shares-next").addEventListener("click", () => { if (profileSharePage * PROFILE_SHARE_PAGE_SIZE < profileShareTotal) loadProfileShares(profileSharePage + 1); });
  document.getElementById("profile-inquiries-prev").addEventListener("click", () => { if (profileInquiryPage > 1) loadProfileInquiries(profileInquiryPage - 1); });
  document.getElementById("profile-inquiries-next").addEventListener("click", () => { if (profileInquiryPage * PROFILE_INQUIRY_PAGE_SIZE < profileInquiryTotal) loadProfileInquiries(profileInquiryPage + 1); });
  document.getElementById("profile-shares-list").addEventListener("click", handleProfileBusinessAction);
  document.getElementById("profile-inquiries-list").addEventListener("click", handleProfileBusinessAction);
  document.getElementById("profile-quotes-list").addEventListener("click", handleProfileBusinessAction);
  document.getElementById("profile-business-dialog-actions").addEventListener("click", handleProfileBusinessAction);
  document.getElementById("profile-business-dialog-close").addEventListener("click", () => document.getElementById("profile-business-dialog").close());
  document.getElementById("profile-language-switcher").addEventListener("click", (event) => { const button = event.target.closest("[data-language]"); if (!button || button.dataset.language === profileLanguage) return; localStorage.setItem("boten-language", button.dataset.language); location.reload(); });
  window.addEventListener("hashchange", () => showProfilePanel(location.hash.slice(1)));
  document.querySelectorAll("input, select, textarea").forEach((field) => field.addEventListener("input", () => field.removeAttribute("aria-invalid")));
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initProfilePage);
else initProfilePage();
