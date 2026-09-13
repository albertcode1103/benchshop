// An empty runtime base is deliberate for the NAS Nginx same-origin proxy.
const API_BASE = typeof window.BOTEN_API_BASE === "string"
  ? window.BOTEN_API_BASE
  : (window.location.port === "8001" ? "" : `${window.location.protocol}//${window.location.hostname || "127.0.0.1"}:8001`);
const TOKEN_KEY = "boten_admin_token";
const CUSTOMER_TOKEN_KEY = "boten_user_token";
const SIDEBAR_COLLAPSED_KEY = "boten_admin_sidebar_collapsed";

function getStoredCollapsedCategories() { try { const value = JSON.parse(localStorage.getItem("boten-admin-collapsed-categories") || "[]"); return Array.isArray(value) ? value : []; } catch (_) { return []; } }
const state = { user: null, products: [], users: [], userTotal: 0, userPage: 1, userPageSize: 20, userQuery: "", userRoleFilter: "all", userStatusFilter: "all", userArchivedFilter: false, shares: [], shareTotal: 0, sharePage: 1, sharePageSize: 20, shareQuery: "", shareStatus: "active", shareProduct: "", shareCreatedFrom: "", shareCreatedTo: "", shareActiveTotal: 0, shareViewTotal: 0, inquiries: [], inquiryTotal: 0, inquiryPage: 1, inquiryPageSize: 20, inquiryQuery: "", inquiryStatus: "all", quoteQuery: "", quoteStatus: "all", quotes: [], audits: [], countries: [], editingProduct: null, mappingEditor: null, catalogLanguage: localStorage.getItem("boten-admin-language") || "zh", configCatalog: [], collapsedCategories: new Set(getStoredCollapsedCategories()) };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
let shareDrawerElement = null;
let shareDrawerBackdrop = null;
let inquiryDrawerElement = null;
let inquiryDrawerBackdrop = null;
let shareSearchTimer = null;
let previousShareFocus = null;
let previousInquiryFocus = null;

function closeTableActionMenus(except = null) {
  document.querySelectorAll(".table-actions-menu[open]").forEach((menu) => {
    if (menu !== except) menu.removeAttribute("open");
  });
}

function positionTableActionMenu(menu) {
  const summary = menu.querySelector("summary");
  const panel = menu.querySelector(":scope > div");
  if (!summary || !panel || !menu.open) return;
  const summaryRect = summary.getBoundingClientRect();
  const viewportPadding = 8;
  const menuWidth = Math.max(132, panel.offsetWidth);
  const menuHeight = panel.offsetHeight;
  const left = Math.max(viewportPadding, Math.min(summaryRect.right - menuWidth, window.innerWidth - menuWidth - viewportPadding));
  const below = summaryRect.bottom + 6;
  const top = below + menuHeight <= window.innerHeight - viewportPadding
    ? below
    : Math.max(viewportPadding, summaryRect.top - menuHeight - 6);
  Object.assign(panel.style, { position: "fixed", right: "auto", left: `${left}px`, top: `${top}px`, zIndex: "100" });
}

class ApiError extends Error {
  constructor(message, { code = "REQUEST_FAILED", field = null, status = 0, requestId = "", params = {} } = {}) {
    super(String(message || "请求未完成")); this.name = "ApiError"; this.code = code; this.field = field; this.status = status; this.requestId = requestId; this.params = params;
  }
}

const ACCOUNT_ERROR_TEXT_ZH = {
  ACCOUNT_NOT_FOUND: "账号不存在或已被移除", ACCOUNT_EMAIL_INVALID: "请输入有效的邮箱地址", ACCOUNT_EMAIL_DUPLICATE: "该邮箱已被其他账号使用",
  ACCOUNT_PHONE_INVALID: "手机号格式或长度与所选国家不匹配", ACCOUNT_PHONE_DUPLICATE: "该手机号已被其他账号使用", ACCOUNT_PHONE_COUNTRY_INVALID: "请选择有效国家",
  ACCOUNT_CONTACT_REQUIRED: "邮箱和手机号至少保留一项", ACCOUNT_NAME_REQUIRED: "请填写显示名称", ACCOUNT_NAME_TOO_LONG: "显示名称不能超过 100 个字符",
  ACCOUNT_PASSWORD_TOO_SHORT: "密码至少需要 8 个字符", ACCOUNT_PASSWORD_TOO_LONG: "密码不能超过 128 个字符", ACCOUNT_PASSWORD_CONFIRMATION_MISMATCH: "两次输入的新密码不一致",
  ACCOUNT_ROLE_INVALID: "请选择有效角色", ACCOUNT_SELF_DISABLE_FORBIDDEN: "不能停用当前登录账号", ACCOUNT_SELF_ROLE_CHANGE_FORBIDDEN: "不能移除当前登录账号的管理员角色",
  ACCOUNT_SELF_ARCHIVE_FORBIDDEN: "不能归档当前登录账号", ACCOUNT_LAST_ADMIN_REQUIRED: "系统必须至少保留一个可用管理员账号", ACCOUNT_VERSION_CONFLICT: "该账号已被其他管理员修改，请重新加载后再编辑",
  ACCOUNT_ARCHIVED: "该账号已归档", ACCOUNT_NOT_ARCHIVED: "该账号未归档", ACCOUNT_SESSION_EXPIRED: "登录状态已失效，请重新登录", ACCOUNT_PERMISSION_DENIED: "当前账号没有执行此操作的权限", ACCOUNT_CURRENT_PASSWORD_INVALID: "当前密码不正确", ACCOUNT_IDENTIFIER_REQUIRED: "请填写邮箱或手机号", ACCOUNT_CREDENTIALS_INVALID: "邮箱、手机号或密码不正确",
  ACCOUNT_RATE_LIMITED: "操作过于频繁，请稍后再试", ACCOUNT_VALIDATION_FAILED: "请检查填写内容", INQUIRY_STATUS_TRANSITION_INVALID: "询价不能回退到所选状态，请刷新后按当前流程继续", QUOTE_SOURCE_ALREADY_EXISTS: "该来源已有你的有效报价，请先打开或归档原报价", SERVER_UNAVAILABLE: "服务器处理失败，请稍后重试"
  , SHARE_NOT_FOUND: "分享码不存在，请核对后重试", SHARE_EXPIRED: "分享码已过期，请联系客户重新生成", SHARE_CLOSED: "分享已被关闭，请联系客户重新启用或生成新分享"
};
const ACCOUNT_ERROR_TEXT_EN = {
  ACCOUNT_NOT_FOUND: "The account no longer exists", ACCOUNT_EMAIL_INVALID: "Enter a valid email address", ACCOUNT_EMAIL_DUPLICATE: "This email is already used by another account",
  ACCOUNT_PHONE_INVALID: "Enter a valid phone number for the selected country", ACCOUNT_PHONE_DUPLICATE: "This phone number is already used by another account", ACCOUNT_PHONE_COUNTRY_INVALID: "Select a valid country",
  ACCOUNT_CONTACT_REQUIRED: "Keep at least an email address or phone number", ACCOUNT_NAME_REQUIRED: "Enter a display name", ACCOUNT_NAME_TOO_LONG: "The display name cannot exceed 100 characters",
  ACCOUNT_PASSWORD_TOO_SHORT: "The password must contain at least 8 characters", ACCOUNT_PASSWORD_TOO_LONG: "The password cannot exceed 128 characters", ACCOUNT_PASSWORD_CONFIRMATION_MISMATCH: "The new passwords do not match",
  ACCOUNT_ROLE_INVALID: "Select a supported account role", ACCOUNT_SELF_DISABLE_FORBIDDEN: "You cannot disable your current account", ACCOUNT_SELF_ROLE_CHANGE_FORBIDDEN: "You cannot remove your own administrator access",
  ACCOUNT_SELF_ARCHIVE_FORBIDDEN: "You cannot archive your current account", ACCOUNT_LAST_ADMIN_REQUIRED: "At least one enabled administrator account is required", ACCOUNT_VERSION_CONFLICT: "This account was changed by another administrator. Reload it and try again",
  ACCOUNT_ARCHIVED: "This account is archived", ACCOUNT_NOT_ARCHIVED: "This account is not archived", ACCOUNT_SESSION_EXPIRED: "Your session has expired. Sign in again", ACCOUNT_PERMISSION_DENIED: "You do not have permission to perform this action", ACCOUNT_CURRENT_PASSWORD_INVALID: "The current password is incorrect", ACCOUNT_IDENTIFIER_REQUIRED: "Enter an email address or phone number", ACCOUNT_CREDENTIALS_INVALID: "The email, phone number, or password is incorrect",
  ACCOUNT_RATE_LIMITED: "Too many requests. Try again later", ACCOUNT_VALIDATION_FAILED: "Check the entered information", INQUIRY_STATUS_TRANSITION_INVALID: "The inquiry cannot move back to that status. Refresh it and continue", QUOTE_SOURCE_ALREADY_EXISTS: "You already have an active quote for this source. Open or archive it first", SERVER_UNAVAILABLE: "The server could not complete the request. Try again later"
  , SHARE_NOT_FOUND: "The share code was not found. Check it and try again", SHARE_EXPIRED: "The share code expired. Ask the customer to create a new one", SHARE_CLOSED: "The share was closed. Ask the customer to reopen it or create a new one"
};
function accountErrorText(code) { return (document.documentElement.lang || "zh-CN").toLowerCase().startsWith("en") ? ACCOUNT_ERROR_TEXT_EN[code] : ACCOUNT_ERROR_TEXT_ZH[code]; }

async function api(path, requestOptions = {}) {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const { timeout: timeoutMs = 15000, ...options } = requestOptions;
  const method = String(options.method || "GET").toUpperCase();
  // 页面首次进入会并发读取多个目录。仅对不会修改数据的 GET 请求重试一次，
  // 避免 NAS 冷启动或 SQLite 短暂繁忙时把正常页面误显示成加载失败。
  const attempts = method === "GET" ? 2 : 1;
  let failure;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const controller = new AbortController();
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          "X-UI-Language": document.documentElement.lang || "zh-CN",
          ...(options.headers || {})
        }, signal: controller.signal
      });
      if (response.ok && method !== "GET" && !path.startsWith("/api/v1/auth/")) document.dispatchEvent(new Event("business-data-changed"));
      if (response.status === 204) return null;
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const code = body.error?.code || response.headers.get("X-Error-Code") || `HTTP_${response.status}`;
        const responseDetail = typeof body.detail === "string" ? body.detail : "";
        const safeMessage = response.status >= 500 ? "服务器处理失败，请稍后重试" : (accountErrorText(code) || responseDetail || `请求失败 (${response.status})`);
        throw new ApiError(safeMessage, { code, field: body.error?.field, status: response.status, requestId: body.request_id || response.headers.get("X-Request-ID") || "", params: body.error?.params || {} });
      }
      return body;
    } catch (error) {
      if (timedOut) failure = new ApiError("请求超时，请稍后重试", { code: "REQUEST_TIMEOUT" });
      else if (error instanceof ApiError) failure = error;
      else failure = new ApiError("网络暂不可用，请检查连接后重试", { code: "NETWORK_UNAVAILABLE" });
      const retryable = failure.code === "REQUEST_TIMEOUT"
        || failure.code === "NETWORK_UNAVAILABLE"
        || [502, 503, 504].includes(failure.status);
      if (attempt + 1 < attempts && retryable) await new Promise(resolve => setTimeout(resolve, 500));
      else break;
    } finally {
      clearTimeout(timeout);
    }
  }
  throw failure;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

function catalogAssetUrl(path) {
  const value = String(path || "").trim();
  if (!value) return "";
  if (value.startsWith("/api/")) return `${API_BASE}${value}`;
  if (/^(?:[a-z]+:|\/|\.{1,2}\/)/i.test(value)) return value;
  // The administration page is served from /admin/, while catalog asset
  // paths are stored relative to the customer-facing site root.
  return `../${value}`;
}

async function uploadCatalogImage(file, control) {
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) { showToast("图片不能超过 8 MB"); return; }
  const button = $("[data-pick-image]", control);
  const pathInput = $('[name="image_path"],[data-color-field="image_path"]', control);
  if (button) { button.disabled = true; button.textContent = "上传中…"; }
  try {
    const result = await api(`/api/v1/admin/media?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
      timeout: 30000
    });
    if (pathInput) pathInput.value = result.path;
    const widthInput = $('[name="image_width"],[data-color-field="image_width"]', control);
    const heightInput = $('[name="image_height"],[data-color-field="image_height"]', control);
    if (widthInput) widthInput.value = result.width || "";
    if (heightInput) heightInput.value = result.height || "";
    const preview = $("[data-color-image-preview],[data-catalog-image-preview]", control);
    if (preview) preview.innerHTML = `<img src="${escapeHtml(catalogAssetUrl(result.path))}" alt="图片缩略图" width="152" height="92" />`;
    showToast("图片上传成功");
  } catch (failure) {
    showToast(failure.name === "AbortError" ? "图片上传超时" : failure.message);
  } finally {
    if (button) { button.disabled = false; button.textContent = button.dataset.idleLabel || "上传图片"; }
  }
}

function confirmAction(title, message, confirmLabel = "确认删除") {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    const token = `confirm-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const titleId = `${token}-title`;
    const descriptionId = `${token}-description`;
    const cancelLabel = confirmLabel === "放弃修改" ? "继续编辑" : "取消";
    const opener = document.activeElement;
    dialog.className = "confirm-dialog";
    dialog.dataset.dynamic = "true";
    dialog.setAttribute("aria-labelledby", titleId);
    dialog.setAttribute("aria-describedby", descriptionId);
    dialog.innerHTML = `<form method="dialog" class="dialog-card confirm-card"><header class="confirm-card-header"><span class="confirm-card-icon" aria-hidden="true">!</span><div class="confirm-card-heading"><span class="eyebrow">请确认操作</span><h2 id="${titleId}">${escapeHtml(title)}</h2></div><button class="icon-button" value="cancel" aria-label="关闭确认窗口">×</button></header><div class="confirm-card-body"><p id="${descriptionId}">${escapeHtml(message)}</p></div><footer><button class="button button-quiet" value="cancel">${cancelLabel}</button><button class="button button-danger" value="confirm">${escapeHtml(confirmLabel)}</button></footer></form>`;
    document.body.appendChild(dialog);
    let settled = false;
    dialog.addEventListener("close", () => { if (!settled) resolve(false); dialog.remove(); if (opener?.isConnected) opener.focus(); });
    dialog.querySelector("form").addEventListener("submit", (event) => { event.preventDefault(); settled = true; const confirmed = event.submitter?.value === "confirm"; dialog.close(); resolve(confirmed); });
    dialog.showModal();
    queueMicrotask(() => dialog.querySelector('button[value="cancel"]')?.focus());
  });
}

function renderCatalogThumbnail(option) {
  const source = catalogAssetUrl(option.image_path);
  if (!source) return '<span class="config-thumbnail-empty">—</span>';
  return `<span class="config-thumbnail"><img src="${escapeHtml(source)}" alt="${escapeHtml(option.code)}" width="112" height="72" loading="lazy" onerror="this.parentElement.classList.add('missing')" /><span aria-hidden="true">—</span></span>`;
}

function toFiniteNumber(value, fallback = 0) {
  const amount = typeof value === "number" ? value : Number(String(value ?? "").trim());
  return Number.isFinite(amount) ? amount : fallback;
}

function toPositiveInteger(value, fallback = 1) {
  return Math.max(1, Math.floor(toFiniteNumber(value, fallback)));
}

function showToast(message, type = "status") {
  const toast = $("#toast");
  const openDialogs = Array.from(document.querySelectorAll("dialog[open]"));
  const host = openDialogs.at(-1) || document.body;
  if (toast.parentElement !== host) host.appendChild(toast);
  toast.textContent = message;
  toast.classList.toggle("error", type === "error");
  toast.setAttribute("role", type === "error" ? "alert" : "status");
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    toast.hidden = true;
    if (toast.parentElement !== document.body) document.body.appendChild(toast);
  }, 2800);
}

async function runButtonAction(button, pendingLabel, action) {
  if (!button || button.disabled) return;
  const originalLabel = button.textContent;
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  button.textContent = pendingLabel;
  try { return await action(); }
  finally { button.disabled = false; button.removeAttribute("aria-busy"); button.textContent = originalLabel; }
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));
}

function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(String(value).includes("T") ? value : `${value.replace(" ", "T")}Z`);
  return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).format(date);
}

function formatNumber(value, options = {}) {
  return new Intl.NumberFormat("zh-CN", options).format(Number(value || 0));
}

function roleLabel(role) {
  return { admin: "管理员", sales: "业务员", customer: "客户", guest: "游客" }[role] || role;
}

async function checkApi() {
  const loginStatus = $("#api-status");
  const sidebarStatus = $("#sidebar-api-status");
  try {
    await api("/api/v1/health");
    if (loginStatus) { loginStatus.textContent = "服务连接正常"; loginStatus.style.color = "var(--green)"; }
    if (sidebarStatus) { sidebarStatus.classList.remove("is-error"); sidebarStatus.querySelector("span").textContent = "API 正常"; }
    return true;
  } catch (_) {
    if (loginStatus) { loginStatus.textContent = "无法连接后端，请先启动 8001 端口的 API 服务"; loginStatus.style.color = "var(--red)"; }
    if (sidebarStatus) { sidebarStatus.classList.add("is-error"); sidebarStatus.querySelector("span").textContent = "API 不可用"; }
    return false;
  }
}

async function restoreSession() {
  const token = sessionStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(CUSTOMER_TOKEN_KEY);
  if (!token) return false;
  if (!sessionStorage.getItem(TOKEN_KEY)) sessionStorage.setItem(TOKEN_KEY, token);
  try {
    const user = await api("/api/v1/auth/me");
    if (!["admin", "sales"].includes(user.role)) throw new Error("该账号没有后台访问权限");
    state.user = user;
    await enterAdmin();
    return true;
  } catch (_) {
    sessionStorage.removeItem(TOKEN_KEY);
    return false;
  }
}

async function login(event) {
  event.preventDefault();
  const error = $("#login-error");
  const submit = $("#login-form button[type=submit]");
  error.hidden = true;
  submit.disabled = true;
  submit.firstElementChild.textContent = "正在登录…";
  try {
    const result = await api("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ identifier: $("#login-identifier").value.trim(), password: $("#login-password").value })
    });
    if (!["admin", "sales"].includes(result.user.role)) throw new Error("该账号没有后台访问权限");
    sessionStorage.setItem(TOKEN_KEY, result.session.token);
    state.user = result.user;
    await enterAdmin();
  } catch (failure) {
    error.textContent = failure.message;
    error.hidden = false;
  } finally {
    submit.disabled = false;
    submit.firstElementChild.textContent = "进入后台";
  }
}

async function enterAdmin() {
  $("#login-page").hidden = true;
  $("#admin-app").hidden = false;
  $("#admin-name").textContent = state.user.display_name || "Administrator";
  $("#admin-email").textContent = state.user.email || state.user.phone || "管理员";
  $("#admin-avatar").textContent = (state.user.display_name || state.user.email || "A").charAt(0).toUpperCase();
  const isAdmin = state.user.role === "admin";
  $$('[data-admin-only]').forEach((element) => { element.hidden = !isAdmin; });
  $(".sidebar-brand-label").textContent = "工作台";
  const requestedView = window.location.hash.slice(1);
  const catalogViews = ["config-catalog", "tool-catalog", "accessory-catalog"];
  const allowed = isAdmin ? ["dashboard", "products", ...catalogViews, "shares", "inquiries", "quotes", "audit", "users"] : ["dashboard", "products", ...catalogViews, "shares", "inquiries", "quotes"];
  switchView(allowed.includes(requestedView) ? requestedView : "dashboard", false);
  $("#inquiry-queue-scope").textContent = isAdmin ? "待办包含未分配询价" : "待办仅限分配给我的询价";
  await loadData();
}

function userListPath() {
  const query = new URLSearchParams({ page: String(state.userPage), page_size: String(state.userPageSize), status: state.userStatusFilter, archived: String(state.userArchivedFilter) });
  if (state.userQuery) query.set("q", state.userQuery);
  if (state.userRoleFilter !== "all") query.set("role", state.userRoleFilter);
  return `/api/v1/admin/users?${query}`;
}

function syncUserFilterUrl() {
  const url = new URL(window.location.href);
  [["userQuery", state.userQuery], ["userRole", state.userRoleFilter], ["userStatus", state.userStatusFilter], ["userArchived", state.userArchivedFilter ? "1" : ""], ["userPage", state.userPage > 1 ? String(state.userPage) : ""]].forEach(([key, value]) => value && value !== "all" ? url.searchParams.set(key, value) : url.searchParams.delete(key));
  history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

function restoreUserFilterState() {
  const query = new URLSearchParams(window.location.search);
  state.userQuery = query.get("userQuery") || "";
  state.userRoleFilter = ["admin", "sales", "customer"].includes(query.get("userRole")) ? query.get("userRole") : "all";
  state.userStatusFilter = ["enabled", "disabled"].includes(query.get("userStatus")) ? query.get("userStatus") : "all";
  state.userArchivedFilter = query.get("userArchived") === "1";
  state.userPage = Math.max(1, Number(query.get("userPage") || 1) || 1);
  if ($("#user-search")) $("#user-search").value = state.userQuery;
  if ($("#user-status-filter")) $("#user-status-filter").value = state.userStatusFilter;
  if ($("#user-archived-filter")) $("#user-archived-filter").checked = state.userArchivedFilter;
  $$("[data-user-role]", $("#user-role-filter")).forEach((item) => { const active = item.dataset.userRole === state.userRoleFilter; item.classList.toggle("active", active); item.setAttribute("aria-pressed", String(active)); });
}

function syncBusinessFilterUrl() {
  const url = new URL(window.location.href);
  const values = {
    shareQuery: state.shareQuery,
    shareStatus: state.shareStatus,
    sharePage: state.sharePage > 1 ? String(state.sharePage) : "",
    inquiryQuery: state.inquiryQuery,
    inquiryStatus: state.inquiryStatus,
    inquiryPage: state.inquiryPage > 1 ? String(state.inquiryPage) : "",
    quoteQuery: state.quoteQuery,
    quoteStatus: state.quoteStatus,
    inquiryQueue: state.inquiryQueue,
    quoteDue: state.quoteDue ? "due" : "",
  };
  Object.entries(values).forEach(([key, value]) => value && value !== "all" ? url.searchParams.set(key, value) : url.searchParams.delete(key));
  history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

function restoreBusinessFilterState() {
  const query = new URLSearchParams(window.location.search);
  state.shareQuery = query.get("shareQuery") || "";
  state.shareStatus = ["all", "active", "expired", "closed"].includes(query.get("shareStatus")) ? query.get("shareStatus") : "active";
  state.sharePage = Math.max(1, Number(query.get("sharePage") || 1) || 1);
  state.inquiryQuery = query.get("inquiryQuery") || "";
  state.inquiryStatus = ["business_new", "business_assigned", "business_contacted", "business_pending", "business_sent", "business_archived", "business_closed", "business_cancelled"].includes(query.get("inquiryStatus")) ? query.get("inquiryStatus") : "all";
  state.inquiryPage = Math.max(1, Number(query.get("inquiryPage") || 1) || 1);
  state.inquiryQueue = ["followup", "stale"].includes(query.get("inquiryQueue")) ? query.get("inquiryQueue") : "all";
  state.quoteDue = query.get("quoteDue") === "due";
  $("#inquiry-queue-filter").value = state.inquiryQueue;
  $("#quote-due-filter").value = state.quoteDue ? "due" : "all";
  state.quoteQuery = query.get("quoteQuery") || "";
  state.quoteStatus = ["draft", "sent", "archived"].includes(query.get("quoteStatus")) ? query.get("quoteStatus") : "all";
  if ($("#share-query")) $("#share-query").value = state.shareQuery;
  if ($("#share-status-filter")) $("#share-status-filter").value = state.shareStatus;
  if ($("#inquiry-query")) $("#inquiry-query").value = state.inquiryQuery;
  if ($("#inquiry-status-filter")) $("#inquiry-status-filter").value = state.inquiryStatus;
  if ($("#quote-query")) $("#quote-query").value = state.quoteQuery;
  if ($("#quote-status-filter")) $("#quote-status-filter").value = state.quoteStatus;
}

function quoteListPath() {
  const query = new URLSearchParams({ status: state.quoteStatus });
  if (state.quoteDue) query.set("due", "true");
  if (state.quoteQuery) query.set("query", state.quoteQuery);
  return `/api/v1/quotes?${query}`;
}

async function loadUsers() {
  const response = await api(userListPath());
  state.users = response.items || [];
  state.userTotal = Number(response.total || 0);
  state.userPage = Number(response.page || 1);
  renderUsers();
  syncUserFilterUrl();
}

function shareListPath() {
  const query = new URLSearchParams({ page: String(state.sharePage), page_size: String(state.sharePageSize), status: state.shareStatus });
  if (state.shareQuery) query.set("query", state.shareQuery);
  const endpoint = state.user?.role === "admin" ? "/api/v1/admin/shares" : "/api/v1/staff/shares";
  return `${endpoint}?${query}`;
}

async function loadShares() {
  const response = await api(shareListPath());
  state.shares = response.items || [];
  state.shareTotal = Number(response.total || 0);
  state.sharePage = Number(response.page || 1);
  state.shareActiveTotal = Number(response.active_total || 0);
  state.shareViewTotal = Number(response.view_total || 0);
  renderShares();
  syncBusinessFilterUrl();
}

function inquiryListPath() {
  const query = new URLSearchParams({ page: String(state.inquiryPage), page_size: String(state.inquiryPageSize), status: state.inquiryStatus, lang: state.catalogLanguage === "en" ? "en" : "zh" });
  if (state.inquiryQuery) query.set("query", state.inquiryQuery);
  if (state.inquiryQueue && state.inquiryQueue !== "all") query.set("queue", state.inquiryQueue);
  return `/api/v1/staff/inquiries?${query}`;
}

async function loadInquiries() {
  const response = await api(inquiryListPath());
  state.inquiries = response.items || [];
  state.inquiryTotal = Number(response.total || 0);
  state.inquiryPage = Number(response.page || 1);
  renderInquiries();
  syncBusinessFilterUrl();
}

async function refreshUsersAfterMutation() {
  try { await loadUsers(); }
  catch (_) { showToast("操作已保存，但列表同步失败，请手动刷新", "error"); }
}

function userMatchesCurrentFilters(user) {
  const needle = state.userQuery.toLowerCase();
  const searchable = `${user.display_name || ""} ${user.email || ""} ${user.phone || ""}`.toLowerCase();
  return Boolean(user.archived) === state.userArchivedFilter
    && (state.userRoleFilter === "all" || user.role === state.userRoleFilter)
    && (state.userStatusFilter === "all" || (state.userStatusFilter === "enabled") === Boolean(user.enabled))
    && (!needle || searchable.includes(needle));
}

function applyUserMutation(user, { created = false } = {}) {
  const index = state.users.findIndex((item) => item.id === user.id);
  const matches = userMatchesCurrentFilters(user);
  if (matches && index >= 0) state.users[index] = user;
  else if (matches && index < 0 && state.userPage === 1) { state.users.unshift(user); if (state.users.length > state.userPageSize) state.users.pop(); }
  else if (!matches && index >= 0) state.users.splice(index, 1);
  if (created && matches) state.userTotal += 1;
  else if (!matches && index >= 0) state.userTotal = Math.max(0, state.userTotal - 1);
  renderUsers();
}

async function loadData() {
  const isAdmin = state.user.role === "admin";
  const initialPaths = { shares: shareListPath(), inquiries: inquiryListPath(), quotes: quoteListPath(), users: userListPath() };
  const requests = {
    shares: api(shareListPath()),
    inquiries: api(inquiryListPath()),
    quotes: api(quoteListPath()),
    products: api("/api/v1/admin/products"),
    configCatalog: api("/api/v1/admin/catalog-tree"),
    countries: api("/api/v1/auth/countries?lang=zh")
  };
  if (isAdmin) {
    requests.users = api(userListPath());
    requests.audits = api("/api/v1/admin/audit-logs");
  }

  const keys = Object.keys(requests);
  const settled = await Promise.allSettled(Object.values(requests));
  const results = Object.fromEntries(keys.map((key, index) => [key, settled[index]]));
  const failures = [];
  const value = (key) => {
    const result = results[key];
    if (result?.status === "fulfilled") return result.value;
    if (result?.reason) failures.push({ key, error: result.reason });
    return null;
  };

  const shares = value("shares");
  const inquiries = value("inquiries");
  const quotes = value("quotes");
  const products = value("products");
  const configCatalog = value("configCatalog");
  const countries = value("countries");
  const users = isAdmin ? value("users") : null;
  const audits = isAdmin ? value("audits") : null;

  if (initialPaths.shares === shareListPath()) {
    state.shares = shares?.items || [];
    state.shareTotal = Number(shares?.total || state.shares.length);
    state.shareActiveTotal = Number(shares?.active_total || 0);
    state.shareViewTotal = Number(shares?.view_total || 0);
  }
  if (initialPaths.inquiries === inquiryListPath()) {
    state.inquiries = inquiries?.items || [];
    state.inquiryTotal = Number(inquiries?.total || 0);
    state.inquiryPage = Number(inquiries?.page || 1);
  }
  if (initialPaths.quotes === quoteListPath()) state.quotes = quotes?.items || [];
  state.products = products?.items || [];
  state.configCatalog = configCatalog?.items || [];
  state.countries = countries?.items || [];
  if (initialPaths.users === userListPath()) {
    state.users = users?.items || [];
    state.userTotal = Number(users?.total || 0);
  }
  state.audits = audits?.items || [];

  renderConfigCatalog(state.configCatalog);
  renderAll();
  setTimeout(() => {
    addCatalogLanguageSwitches();
    applyCatalogLanguage(state.catalogLanguage);
    restoreCollapsedCategories();
  }, 0);

  const errorTargets = {
    shares: ["#shares-table", 8], inquiries: ["#inquiries-table", 8], quotes: ["#quotes-table", 5], products: ["#products-table", 4],
    configCatalog: ["#config-catalog-list", 0], users: ["#users-table", 5], audits: ["#audit-table", 5]
  };
  failures.forEach(({ key, error }) => {
    const targetInfo = errorTargets[key];
    if (!targetInfo) return;
    const target = $(targetInfo[0]);
    if (!target) return;
    const message = `无法加载数据：${escapeHtml(error.message)}<br><small>请稍后重试；若持续出现，请检查 API 服务状态。</small>`;
    target.innerHTML = targetInfo[1] ? `<tr><td colspan="${targetInfo[1]}" class="empty">${message}</td></tr>` : `<div class="empty">${message}</div>`;
  });
  if (failures.length) {
    const authFailure = failures.find(({ error }) => error.status === 401 || /session|token|401/i.test(error.message));
    if (authFailure) logout();
    else showToast(`部分数据加载失败（${failures.length} 项），其他功能仍可继续使用`, "error");
  }
}

function renderAll() {
    renderProducts(); renderUsers(); renderShares(); renderInquiries(); renderQuotes(); renderAudits(); renderDashboard();
}

function renderProducts() {
  const english = state.catalogLanguage === "en";
  const priceLabel = $("[data-view-panel=\"products\"] thead th:nth-child(3)");
  if (priceLabel) priceLabel.textContent = english ? "价格 / USD" : "价格 / 人民币";
  $("#products-table").innerHTML = state.products.map((product) => `
    <tr><td><strong translate="no">${escapeHtml(english ? (product.name_en || product.name) : product.name)}</strong></td><td>${escapeHtml(english ? (product.title_name_en || product.title_name) : product.title_name)}</td><td>${english ? "$" + formatNumber(product.price_usd) : "¥" + formatNumber(product.base_price)}</td><td><span class="badge ${product.enabled ? "good" : "off"}">${product.enabled ? "已启用" : "已下架"}</span></td><td class="align-right"><button class="table-action" data-edit-product="${product.id}">编辑</button></td></tr>
  `).join("") || '<tr><td colspan="5" class="empty">暂无产品数据</td></tr>';
}

function renderConfigCatalog(categories) {
  const target = $("#config-catalog-list"); if (!target) return;
  target.innerHTML = categories.map((category) => `<section class="config-catalog-group"><header><div class="catalog-collapse-target" data-collapse-category="${escapeHtml(category.id)}" role="button" tabindex="0" aria-expanded="true"><h3>${escapeHtml(category.name)}</h3><p>${escapeHtml(category.description || "")}</p></div><div><span>${category.options.length} 项</span><button class="text-button" data-add-option="${escapeHtml(category.id)}">添加配置</button><details class="catalog-more"><summary>更多</summary><div><button class="text-button" data-edit-category='${escapeHtml(JSON.stringify(category))}'>编辑分类</button></div></details></div></header><div class="config-catalog-table"><table><thead><tr><th>编号</th><th>名称</th><th>图片</th><th>参考价格</th><th>状态</th><th></th></tr></thead><tbody>${category.options.map((option) => `<tr><td><strong translate="no">${escapeHtml(option.code)}</strong></td><td>${escapeHtml(option.name)}<br><small>${escapeHtml(option.description || "")}</small></td><td class="config-image-cell">${renderCatalogThumbnail(option)}</td><td>¥${formatNumber(option.price)}</td><td><span class="badge ${option.enabled ? "good" : "off"}">${option.enabled ? "启用" : "停用"}</span></td><td class="align-right"><button class="table-action" data-edit-option='${escapeHtml(JSON.stringify(option))}'>编辑</button></td></tr>`).join("")}</tbody></table></div></section>`).join("") || '<div class="empty">暂无配置目录</div>';
}

async function addConfigCategory() { categoryCard(); }
async function editConfigCategory(category) { categoryCard(category); }

function addLanguageToggles() { ["#product-dialog", "#config-option-dialog"].forEach((selector) => { const dialog = $(selector); const header = $(".dialog-card > header", dialog); if (!header || $(".lang-toggle", header)) return; const box = document.createElement("div"); box.className = "catalog-language dialog-language"; box.innerHTML = '<button type="button" class="lang-toggle active" data-lang="zh" aria-pressed="true">中文</button><button type="button" class="lang-toggle" data-lang="en" aria-pressed="false">EN</button>'; box.addEventListener("click", (event) => { const button = event.target.closest(".lang-toggle"); if (!button) return; event.stopPropagation(); toggleDialogLanguage(button); }); header.appendChild(box); }); const examples={name:"例如：CR318C",name_en:"例如：CR318C",title_name:"例如：共轨喷油器试验台",title_name_en:"例如：Common Rail Test Bench",description:"例如：适用于多种喷油器测试",description_en:"例如：Designed for common rail injector testing",code:"例如：BTK-1019",price:"例如：1500"}; Object.entries(examples).forEach(([name,placeholder])=>$$(`[name="${name}"]`).forEach(el=>{if(!el.placeholder)el.placeholder=placeholder;})); }
function toggleDialogLanguage(button) { const dialog = button.closest("dialog"); const lang = button.dataset.lang; $$(".lang-toggle", dialog).forEach((item) => { const active = item === button; item.classList.toggle("active", active); item.setAttribute("aria-pressed", String(active)); }); $$('[name$="_en"]', dialog).forEach((field) => { const label = field.closest("label"); if (label) label.hidden = lang !== "en"; }); $$('[name="name"],[name="title_name"],[name="description"]', dialog).forEach((field) => { const label = field.closest("label"); if (label) label.hidden = lang === "en"; }); $$('[data-color-name-lang]', dialog).forEach((label) => { label.hidden = label.dataset.colorNameLang !== lang; }); if (dialog.id === "product-dialog") { state.catalogLanguage = lang; localStorage.setItem("boten-admin-language", lang); renderMappingEditor(); } }
function applyCatalogLanguage(lang) { state.catalogLanguage=lang; $$(".catalog-language button").forEach(b=>b.classList.toggle("active",b.dataset.catalogLang===lang)); $$("#products-table tr").forEach((row,i)=>{const p=state.products[i];if(!p)return;const cells=row.children;cells[0].querySelector("strong").textContent=lang==="en"?(p.name_en||p.name):p.name;cells[1].textContent=lang==="en"?(p.title_name_en||p.title_name):p.title_name;}); $$(".config-catalog-group").forEach((group,i)=>{const c=state.configCatalog[i];if(!c)return;group.querySelector("h3").textContent=lang==="en"?(c.name_en||c.name):c.name;const p=group.querySelector("header p");if(p)p.textContent=lang==="en"?(c.description_en||c.description||""):(c.description||"");$$('tbody tr',group).forEach((row,n)=>{const o=c.options[n];if(!o)return;const cell=row.children[1];cell.childNodes[0].textContent=lang==="en"?(o.name_en||o.name):o.name;const small=cell.querySelector("small");if(small)small.textContent=lang==="en"?(o.description_en||o.description||""):(o.description||"");});}); }
function addCatalogLanguageSwitches(){[["products","设备目录"],["config-catalog","配置目录"]].forEach(([view])=>{const header=$(`[data-view-panel="${view}"] .panel-header`);if(!header||$(".catalog-language",header))return;const box=document.createElement("div");box.className="catalog-language";box.innerHTML='<button type="button" class="active" data-catalog-lang="zh">中文</button><button type="button" data-catalog-lang="en">EN</button>';header.appendChild(box);box.addEventListener("click",e=>{const b=e.target.closest("[data-catalog-lang]");if(b)applyCatalogLanguage(b.dataset.catalogLang);});});}
function openConfigOptionEditor(option) {
  const form = $("#config-option-form");
  form.dataset.optionVersion = String(option.version || 1);
  const zhButton = $(`.lang-toggle[data-lang="${state.catalogLanguage}"]`, $("#config-option-dialog")); if (zhButton) toggleDialogLanguage(zhButton);
  form.elements.option_id.value = option.id; form.elements.code.value = option.code || ""; form.elements.name.value = option.name || ""; form.elements.name_en.value = option.name_en || ""; form.elements.image_path.value = option.image_path || ""; form.elements.description.value = option.description || ""; form.elements.description_en.value = option.description_en || ""; form.elements.notes.value = option.notes || ""; form.elements.price.value = option.price || 0; if (form.elements.price_usd) form.elements.price_usd.value = option.price_usd || 0; form.elements.enabled.checked = option.enabled;
  $("#config-option-error").hidden = true; $("#config-option-dialog").showModal();
}

async function openProductEditor(productId) {
  try {
    const product = await api(`/api/v1/admin/products/${productId}`);
    state.editingProduct = product;
    const form = $("#product-form");
    form.elements.product_id.value = product.id;
    form.elements.name.value = product.name; form.elements.name_en.value = product.name_en || "";
    form.elements.title_name.value = product.title_name; form.elements.title_name_en.value = product.title_name_en || "";
    form.elements.description.value = product.description || ""; form.elements.description_en.value = product.description_en || "";
    form.elements.base_price.value = product.base_price;
    if (form.elements.price_usd) form.elements.price_usd.value = product.price_usd || 0;
    form.elements.sort_order.value = product.sort_order;
    form.elements.enabled.checked = product.enabled;
    const specificationEditor = $("#product-specifications-editor");
    const renderSpecifications = () => { specificationEditor.innerHTML = (state.editingProduct.specifications || []).map((s, i) => `<div class="specification-row" data-id="${escapeHtml(s.id || "")}"><input data-spec="label" aria-label="中文项目" value="${escapeHtml(s.label || "")}" placeholder="中文项目"><input data-spec="label_en" aria-label="英文项目" value="${escapeHtml(s.label_en || "")}" placeholder="英文项目"><input data-spec="value" aria-label="中文数据" value="${escapeHtml(s.value || "")}" placeholder="中文数据"><input data-spec="value_en" aria-label="英文数据" value="${escapeHtml(s.value_en || "")}" placeholder="英文数据"><button type="button" class="button button-quiet" data-move-spec="${i}" data-direction="-1" ${i ? "" : "disabled"}>↑</button><button type="button" class="button button-quiet" data-move-spec="${i}" data-direction="1" ${i === state.editingProduct.specifications.length - 1 ? "" : "disabled"}>↓</button><button type="button" class="button button-quiet" data-remove-spec="${i}">删除</button></div>`).join(""); };
    state.editingProduct.specifications = Array.isArray(product.specifications) ? product.specifications : [];
    renderSpecifications();
    $("#add-specification-button").onclick = () => { state.editingProduct.specifications.push({ label: "", label_en: "", value: "", value_en: "" }); renderSpecifications(); };
    const captureSpecifications = () => { state.editingProduct.specifications = Array.from(specificationEditor.querySelectorAll(".specification-row")).map((row) => ({ id: row.dataset.id || null, label: row.querySelector('[data-spec="label"]').value, label_en: row.querySelector('[data-spec="label_en"]').value, value: row.querySelector('[data-spec="value"]').value, value_en: row.querySelector('[data-spec="value_en"]').value })); };
    specificationEditor.onclick = (event) => { const remove = event.target.closest("[data-remove-spec]"); const move = event.target.closest("[data-move-spec]"); if (remove) { captureSpecifications(); state.editingProduct.specifications.splice(Number(remove.dataset.removeSpec), 1); renderSpecifications(); } if (move) { captureSpecifications(); const from = Number(move.dataset.moveSpec); const to = from + Number(move.dataset.direction); const items = state.editingProduct.specifications; [items[from], items[to]] = [items[to], items[from]]; renderSpecifications(); } };
    $("#product-dialog-title").textContent = `编辑 ${product.name}`;
    renderColorEditor(product.colors);
    state.mappingEditor = {
      categories: product.categories,
      selected: new Set(product.categories.flatMap((category) => category.options.filter((option) => option.selected).map((option) => option.id))),
      notes: new Map(product.categories.flatMap((category) => category.options.map((option) => [option.id, { zh: option.description_override || "", en: option.description_override_en || "", mapped: Boolean(option.mapped), dirty: false }]))),
      motorPrices: new Map(product.categories.flatMap((category) => category.id === "motor" ? category.options.map((option) => [option.id, { base_price_cny: option.motor_base_price_cny ?? product.base_price ?? 0, base_price_usd: option.motor_base_price_usd ?? product.price_usd ?? 0 }]) : [])),
      query: "",
      filter: "all",
      collapsed: new Set(product.categories.map((category) => category.id))
    };
    window.renderMappingEditor();
    switchEditorTab("basic");
    $("#product-error").hidden = true;
    const zhButton = $(`.lang-toggle[data-lang="${state.catalogLanguage}"]`, $("#product-dialog")); if (zhButton) toggleDialogLanguage(zhButton);
    $("#product-dialog").showModal();
  } catch (failure) { showToast(failure.message); }
}

function renderColorEditor(colors) {
  $("#color-editor-list").innerHTML = colors.map((color) => colorEditorRow(color)).join("");
}

function colorEditorRow(color = { code: "", label: "", label_en: "", image_path: "", is_default: false }) {
  const code = color.code || `color-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const image = color.image_path ? `<img src="${escapeHtml(catalogAssetUrl(color.image_path))}" alt="颜色图片缩略图" width="152" height="92" />` : "<span>暂无图片</span>";
  return `<div class="color-editor-row">
    <input data-color-field="code" type="hidden" value="${escapeHtml(code)}" />
    <label class="color-name-field" data-color-name-lang="zh"><span>颜色名称</span><input data-color-field="label" value="${escapeHtml(color.label)}" placeholder="例如：绿色" /></label>
    <label class="color-name-field" data-color-name-lang="en" hidden><span>颜色名称</span><input data-color-field="label_en" value="${escapeHtml(color.label_en || color.label)}" placeholder="e.g. Green" /></label>
    <label class="color-image-field"><span>颜色图片</span><div class="color-image-control"><input data-color-field="image_path" type="hidden" value="${escapeHtml(color.image_path || "")}" /><div class="color-image-preview" data-color-image-preview>${image}</div><button class="button button-secondary" type="button" data-pick-image>上传图片</button><input type="file" accept="image/png,image/jpeg,image/webp" data-image-file hidden /></div></label>
    <label class="default-color"><input data-color-field="is_default" type="radio" name="default-color" ${color.is_default ? "checked" : ""} /><span>默认</span></label>
    <button class="icon-button" data-remove-color type="button" aria-label="删除颜色">✕</button>
  </div>`;
}

async function deleteCurrentConfigOption() {
  const optionId = $("#config-option-form").elements.option_id.value;
  if (!optionId) return;
  const button = $("#delete-config-option");
  try {
    const references = await api(`/api/v1/admin/config-catalog/options/${encodeURIComponent(optionId)}/references`);
    if (references.mapping_count) {
      const names = references.products.map((product) => product.name).join("、");
      showToast(`该配置仍被 ${references.mapping_count} 台设备使用：${names}`);
      return;
    }
    if (!await confirmAction("删除配置", `确定永久删除 ${references.code} ${references.name}？`)) return;
    await runButtonAction(button, "删除中…", async () => {
      await api(`/api/v1/admin/config-catalog/options/${encodeURIComponent(optionId)}`, { method: "DELETE" });
      $("#config-option-dialog").close();
      showToast("配置已删除");
      await loadData();
    });
  } catch (failure) { showToast(failure.message); }
}

async function deleteConfigCategory(category) {
  const references = await api(`/api/v1/admin/config-catalog/categories/${encodeURIComponent(category.id)}/references`);
  if (references.protected) {
    showToast("电机和供电属于系统基础分类，不能删除");
    return false;
  }
  if (references.option_count) {
    showToast(`分类中仍有 ${references.option_count} 项配置，请先处理配置项`);
    return false;
  }
  if (!await confirmAction("删除配置分类", `确定永久删除“${references.name}”？`)) return false;
  await api(`/api/v1/admin/config-catalog/categories/${encodeURIComponent(category.id)}`, { method: "DELETE" });
  showToast("配置分类已删除");
  return true;
}

function renderMappingEditor() {
  const editor = state.mappingEditor;
  if (!editor) return;
  $$("[data-motor-price-cny]").forEach((field) => { const id = field.dataset.motorPriceCny; const usd = $(`[data-motor-price-usd="${CSS.escape(id)}"]`); editor.motorPrices.set(id, { base_price_cny: Number(field.value || 0), base_price_usd: Number(usd?.value || 0) }); });
  const lang = $(".lang-toggle.active", $("#product-dialog"))?.dataset.lang || state.catalogLanguage || "zh";
  const query = (editor.query || "").trim().toLocaleLowerCase();
  const groups = editor.categories.map((category) => {
    const options = category.options.filter((option) => {
      const note = editor.notes.get(option.id);
      const matchesFilter = editor.filter === "selected" ? editor.selected.has(option.id) : editor.filter === "noted" ? Boolean(note?.zh || note?.en) : true;
      const haystack = [option.code, option.name, option.name_en, option.description, option.description_en, note?.zh, note?.en].join(" ").toLocaleLowerCase();
      return matchesFilter && (!query || haystack.includes(query));
    });
    if (!options.length) return "";
    const collapsed = editor.collapsed?.has(category.id);
    return `
    <section class="mapping-group ${category.id === "motor" ? "motor-mapping-group" : ""} ${collapsed ? "collapsed" : ""}">
      <header><button type="button" class="mapping-group-toggle" data-mapping-category="${escapeHtml(category.id)}" aria-expanded="${String(!collapsed)}"><h3>${escapeHtml(lang === "en" ? (category.name_en || category.name) : category.name)}</h3><span>${category.options.filter((option) => editor.selected.has(option.id)).length} / ${category.options.length} ${lang === "en" ? "enabled" : "项已启用"}</span></button></header>
      <div class="mapping-options" ${collapsed ? "hidden" : ""}>${options.map((option) => {
        const optionName = lang === "en" ? (option.name_en || option.name) : option.name;
        const description = lang === "en" ? (option.description_en || option.description) : option.description;
        const specialNote = editor.notes.get(option.id)?.[lang] || "";
        const motorPrice = category.id === "motor" ? (editor.motorPrices.get(option.id) || { base_price_cny: option.motor_base_price_cny ?? state.editingProduct?.base_price ?? 0, base_price_usd: option.motor_base_price_usd ?? state.editingProduct?.price_usd ?? 0 }) : null;
        return `<div class="mapping-option"><input type="checkbox" value="${escapeHtml(option.id)}" aria-label="${lang === "en" ? "Enable" : "启用"} ${escapeHtml(optionName)}" ${editor.selected.has(option.id) ? "checked" : ""} /><div class="mapping-option-copy"><strong>${escapeHtml(optionName)}</strong>${description ? `<small>${escapeHtml(description.replace(/<[^>]*>/g, " "))}</small>` : ""}${specialNote ? `<b class="mapping-special-note">${escapeHtml(specialNote)}</b>` : ""}${motorPrice ? `<div class="motor-price-fields"><label>人民币基础价<input type="number" min="0" step="1" data-motor-price-cny="${escapeHtml(option.id)}" value="${Number(motorPrice.base_price_cny || 0)}"></label><label>美元基础价<input type="number" min="0" step="1" data-motor-price-usd="${escapeHtml(option.id)}" value="${Number(motorPrice.base_price_usd || 0)}"></label></div>` : ""}</div><button type="button" class="text-button mapping-note-button" data-edit-mapping-note="${escapeHtml(option.id)}">标注</button></div>`;
      }).join("")}</div>
    </section>
  `; }).join("");
  $("#mapping-editor").innerHTML = groups || `<div class="mapping-empty">${lang === "en" ? "No matching configurations" : "没有符合条件的配置"}</div>`;
  $$('[data-mapping-filter]').forEach((button) => button.classList.toggle("active", button.dataset.mappingFilter === editor.filter));
  const expand = $("#mapping-expand-all");
  if (expand) expand.textContent = editor.collapsed?.size ? "展开全部" : "全部折叠";
}

function openMappingNoteEditor(optionId) {
  const editor = state.mappingEditor;
  const option = editor?.categories.flatMap((category) => category.options).find((item) => item.id === optionId);
  if (!option) return;
  const note = editor.notes.get(optionId) || { zh: "", en: "", mapped: false, dirty: false };
  const dialog = document.createElement("dialog");
  dialog.className = "mapping-note-dialog";
  dialog.dataset.dynamic = "true";
  dialog.innerHTML = `<form method="dialog" class="dialog-card"><header><div><span class="eyebrow">MODEL-SPECIFIC NOTE</span><h2>编辑标注</h2></div><div class="dialog-actions"><div class="catalog-language dialog-language"><button type="button" class="lang-toggle" data-note-lang="zh">中文</button><button type="button" class="lang-toggle" data-note-lang="en">EN</button></div><button class="icon-button" value="cancel" aria-label="关闭">×</button></div></header><p class="mapping-note-option-name"></p><label data-note-field="zh"><span>专有标注</span><textarea name="note_zh" rows="4" placeholder="没有标注可留空">${escapeHtml(note.zh)}</textarea></label><label data-note-field="en"><span>专有标注</span><textarea name="note_en" rows="4" placeholder="没有标注可留空">${escapeHtml(note.en)}</textarea></label><footer><button class="button button-quiet" value="cancel">取消</button><button class="button button-danger" value="clear">清空标注</button><button class="button button-primary" value="save">保存标注</button></footer></form>`;
  document.body.appendChild(dialog);
  const form = $("form", dialog);
  const setLang = (lang) => {
    $$('[data-note-field]', dialog).forEach((field) => { field.hidden = field.dataset.noteField !== lang; });
    $$('[data-note-lang]', dialog).forEach((button) => {
      const active = button.dataset.noteLang === lang;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    $(".mapping-note-option-name", dialog).textContent = lang === "en" ? (option.name_en || option.name) : option.name;
  };
  $$('[data-note-lang]', dialog).forEach((button) => button.addEventListener("click", (event) => { event.stopPropagation(); setLang(button.dataset.noteLang); }));
  setLang(state.catalogLanguage || "zh");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const action = event.submitter?.value;
    if (action !== "save" && action !== "clear") { dialog.close(); dialog.remove(); return; }
    editor.notes.set(optionId, { ...note, zh: action === "clear" ? "" : form.elements.note_zh.value.trim(), en: action === "clear" ? "" : form.elements.note_en.value.trim(), dirty: true });
    dialog.close(); dialog.remove();
    window.renderMappingEditor();
  });
  dialog.showModal();
}

function switchEditorTab(tab) {
  $$(".editor-tab").forEach((button) => { const active = button.dataset.editorTab === tab; button.classList.toggle("active", active); button.setAttribute("aria-selected", String(active)); button.tabIndex = active ? 0 : -1; });
  $$(".editor-panel").forEach((panel) => { const active = panel.dataset.editorPanel === tab; panel.classList.toggle("active", active); panel.hidden = !active; });
}

function collectColors() {
  return $$(".color-editor-row", $("#color-editor-list")).map((row) => ({
    code: $('[data-color-field="code"]', row).value.trim(),
    label: $('[data-color-field="label"]', row).value.trim(),
    label_en: $('[data-color-field="label_en"]', row).value.trim(),
    image_path: $('[data-color-field="image_path"]', row).value.trim() || null,
    is_default: $('[data-color-field="is_default"]', row).checked
  }));
}

function reconcileMappingEditor() {
  const editor = state.mappingEditor;
  if (!editor) return [];
  const validIds = new Set(editor.categories.flatMap((category) => category.options.map((option) => option.id)));
  const staleIds = Array.from(editor.selected).filter((optionId) => !validIds.has(optionId));
  staleIds.forEach((optionId) => editor.selected.delete(optionId));
  for (const optionId of editor.notes.keys()) {
    if (!validIds.has(optionId)) editor.notes.delete(optionId);
  }
  for (const optionId of editor.motorPrices.keys()) {
    if (!validIds.has(optionId)) editor.motorPrices.delete(optionId);
  }
  return staleIds;
}

async function saveProduct(event) {
  event.preventDefault();
  const form = event.currentTarget;
  // Buttons with formmethod="dialog" (取消/关闭) also dispatch submit.
  // They must close the dialog without sending any API mutation.
  if (event.submitter?.value === "cancel") {
    form.closest("dialog")?.close();
    return;
  }
  const productId = form.elements.product_id.value;
  const error = $("#product-error");
  const submit = $("#save-product-button");
  error.hidden = true; submit.disabled = true; submit.textContent = "正在保存…";
  try {
    const colors = collectColors();
    if (!colors.length) throw new Error("至少需要一种外观颜色");
    if (colors.some((color) => !color.code || !color.label || !color.label_en)) throw new Error("请完整填写中英文颜色名称");
    const staleOptionIds = reconcileMappingEditor();
    if (staleOptionIds.length) {
      renderMappingEditor();
      throw new Error("配置目录已更新，已移除不存在的配置项。请确认当前勾选后再次保存。");
    }
    const validOptionIds = new Set(state.mappingEditor?.categories.flatMap((category) => category.options.map((option) => option.id)) || []);
    const optionIds = Array.from(state.mappingEditor?.selected || []).filter((optionId) => validOptionIds.has(optionId));
    const optionOverrides = {};
    for (const [optionId, note] of state.mappingEditor?.notes || []) {
      if (validOptionIds.has(optionId) && (note.mapped || note.dirty || note.zh || note.en || state.mappingEditor.selected.has(optionId))) {
        optionOverrides[optionId] = { description_override: note.zh || null, description_override_en: note.en || null };
      }
    }
    const motorPrices = Object.fromEntries(Array.from(state.mappingEditor?.motorPrices || []).filter(([optionId]) => validOptionIds.has(optionId) && state.mappingEditor.selected.has(optionId)));
    $$("[data-motor-price-cny]").forEach((field) => {
      const id = field.dataset.motorPriceCny;
      if (!validOptionIds.has(id) || !state.mappingEditor?.selected.has(id)) return;
      const usd = $(`[data-motor-price-usd="${CSS.escape(id)}"]`);
      motorPrices[id] = { base_price_cny: Math.max(0, toFiniteNumber(field.value)), base_price_usd: Math.max(0, toFiniteNumber(usd?.value)) };
    });
    await api(`/api/v1/admin/products/${productId}/configuration`, {
      method: "PUT",
      body: JSON.stringify({
        version: state.editingProduct.version,
        name: form.elements.name.value.trim(), name_en: form.elements.name_en.value.trim(), title_name: form.elements.title_name.value.trim(), title_name_en: form.elements.title_name_en.value.trim(),
        description: form.elements.description.value.trim(), description_en: form.elements.description_en.value.trim(), base_price: Math.max(0, toFiniteNumber(form.elements.base_price.value)), price_usd: Math.max(0, toFiniteNumber(form.elements.price_usd?.value)),
        sort_order: Math.max(0, Math.floor(toFiniteNumber(form.elements.sort_order.value))), enabled: form.elements.enabled.checked,
        colors, option_ids: optionIds, option_overrides: optionOverrides, motor_prices: motorPrices,
        specifications: Array.from($("#product-specifications-editor").querySelectorAll(".specification-row")).map((row, i) => ({ id: row.dataset.id || null, label: row.querySelector('[data-spec="label"]').value, label_en: row.querySelector('[data-spec="label_en"]').value, value: row.querySelector('[data-spec="value"]').value, value_en: row.querySelector('[data-spec="value_en"]').value, sort_order: i }))
      })
    });
    $("#product-dialog").close(); showToast("产品配置已保存"); await loadData();
  } catch (failure) {
    error.textContent = failure.message === "Failed to fetch"
      ? "无法连接 API，请确认 8001 端口服务已启动并重新登录后台"
      : failure.message;
    error.hidden = false;
  }
  finally { submit.disabled = false; submit.textContent = "保存产品"; }
}

function renderUsers() {
  $("#users-table").innerHTML = state.users.map((user) => `
    <tr>
      <td><div class="user-cell"><div class="avatar">${escapeHtml((user.display_name || user.email || "U").charAt(0).toUpperCase())}</div><strong>${escapeHtml(user.display_name || "未命名用户")}</strong></div></td>
      <td><div class="account-contact"><span>${escapeHtml(user.email || "未填写邮箱")}</span><span>${escapeHtml(user.phone ? `${user.phone_calling_code || ""} ${user.phone}` : "未填写手机号")}</span></div></td><td><span class="badge">${roleLabel(user.role)}</span></td>
      <td><span class="badge ${user.archived ? "off" : user.enabled ? "good" : "off"}">${user.archived ? "已归档" : user.enabled ? "正常" : "已停用"}</span></td>
      <td class="align-right">${user.archived ? `<button class="table-action" data-restore-user="${user.id}">恢复</button>` : `<span class="table-actions"><button class="table-action" data-edit-user="${user.id}">编辑资料</button><details class="table-actions-menu"><summary aria-label="更多账号操作">更多</summary><div><button class="table-action" data-edit-user-role="${user.id}">修改角色</button><button class="table-action" data-reset-user-password="${user.id}">重置密码</button><button class="table-action ${user.enabled ? "danger" : ""}" data-user-status="${user.id}" data-user-version="${user.version}" data-enabled="${!user.enabled}">${user.enabled ? "停用账号" : "启用账号"}</button><button class="table-action danger" data-archive-user="${user.id}">归档账号</button></div></details></span>`}</td>
    </tr>
  `).join("") || '<tr><td colspan="5" class="empty">该筛选条件下暂无账号</td></tr>';
  const pages = Math.max(1, Math.ceil(state.userTotal / state.userPageSize));
  $("#user-page-summary").textContent = `共 ${state.userTotal} 个账号 · 第 ${state.userPage}/${pages} 页`;
  $("#user-page-prev").disabled = state.userPage <= 1;
  $("#user-page-next").disabled = state.userPage >= pages;
}

function renderShares() {
  const isAdmin = state.user?.role === "admin";
  $("#shares-table").innerHTML = state.shares.map((share) => {
    const valid = share.active && new Date(share.expires_at) > new Date();
    const canReopen = isAdmin && !share.active && new Date(share.expires_at) > new Date();
    const quoteLabel = share.own_latest_quote_id ? "查看我的报价" : Number(share.quote_count || 0) ? "再次报价" : "报价";
    const actions = valid ? `<span class="table-actions"><button class="table-action" data-lookup-share="${escapeHtml(share.code)}">查看</button><details class="table-actions-menu"><summary aria-label="更多分享操作">更多</summary><div><button class="table-action" data-export-share="${escapeHtml(share.code)}">导出 PDF</button><button class="table-action" data-quote-share="${escapeHtml(share.code)}">${quoteLabel}</button>${isAdmin ? `<button class="table-action danger" data-close-share="${share.id}">关闭</button>` : ""}</div></details></span>` : canReopen ? `<button class="table-action" data-open-share="${share.id}">重新启用</button>` : "—";
    const itemCountLabel = renderShareItemSummary(share);
    const statusText = !share.active ? "已关闭" : valid ? "有效" : "已过期";
    const activity = `${formatNumber(share.view_count)} 次访问${share.last_viewed_at ? ` · 最近 ${escapeHtml(formatDate(share.last_viewed_at))}` : ""}`;
    return `<tr><td><button class="share-code-button" translate="no" data-lookup-share="${escapeHtml(share.code)}" ${valid ? "" : "disabled"}>${escapeHtml(share.code)}</button><small class="business-cell-meta">${escapeHtml(formatDateTime(share.created_at))}</small></td><td>${renderCustomerLines(share.sender_name, share.sender_email, share.sender_phone)}</td><td>${itemCountLabel}</td><td><span class="badge ${valid ? "good" : "off"}">${statusText}</span><small class="business-cell-meta">有效期至 ${escapeHtml(formatDate(share.expires_at))}</small><small class="business-cell-meta">${activity}</small></td><td>${renderQuoteSourceStatus(share)}</td><td class="align-right">${actions}</td></tr>`;
  }).join("") || '<tr><td colspan="6" class="empty">暂无分享记录</td></tr>';
  const pages = Math.max(1, Math.ceil(state.shareTotal / state.sharePageSize));
  if ($("#share-page-summary")) $("#share-page-summary").textContent = `共 ${state.shareTotal} 条 · 第 ${state.sharePage}/${pages} 页`;
  if ($("#share-page-prev")) $("#share-page-prev").disabled = state.sharePage <= 1;
  if ($("#share-page-next")) $("#share-page-next").disabled = state.sharePage >= pages;
}

function renderShareItemSummary(share) {
  const hasTypedCounts = ["device_count", "tool_quantity", "accessory_quantity"].some((key) => Object.prototype.hasOwnProperty.call(share, key));
  const counts = hasTypedCounts
    ? { device: Number(share.device_count || 0), tool: Number(share.tool_quantity || 0), accessory: Number(share.accessory_quantity || 0) }
    : { device: Number(share.item_count || 0), tool: 0, accessory: 0 };
  return renderCommerceCountLines(counts);
}

function renderCommerceCountLines(counts) {
  const lines = [[Number(counts.device || 0), "台设备"], [Number(counts.tool || 0), "件工具"], [Number(counts.accessory || 0), "件附件"]]
    .filter(([count]) => count > 0)
    .map(([count, label]) => `<div>${escapeHtml(formatNumber(count))}${label}</div>`)
    .join("");
  return lines ? `<div class="business-content-counts">${lines}</div>` : '<span class="business-cell-empty">未包含有效项目</span>';
}

function renderCustomerLines(name, email, phone) {
  const lines = [name, email, phone]
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .map((value, index) => `<span${index === 0 ? ' class="customer-name"' : ""}>${escapeHtml(value)}</span>`)
    .join("");
  return lines ? `<span class="business-customer-lines">${lines}</span>` : '<span class="business-cell-empty">未填写</span>';
}

function renderQuotes() {
  const target = $("#quotes-table"); if (!target) return;
  target.innerHTML = state.quotes.map((quote) => {
    const symbol = quote.currency === "USD" ? "$" : "¥";
    const status = quote.lifecycle_status || "draft";
    const delivery = Number(quote.delivery_count || 0) ? `已发送给 ${escapeHtml(quote.recipient_summary || `${quote.delivery_count} 个账号`)}` : "尚未发送";
    const number = quote.quote_number || quote.id.slice(0, 8);
    const source = quote.source_type === "inquiry" || quote.source_inquiry_id
      ? `来源：客户询价${quote.source_code ? ` · ${quote.source_code}` : ""}`
      : quote.source_type === "share" || quote.source_share_id
        ? `来源：分享配置${quote.source_code ? ` · ${quote.source_code}` : ""}`
        : "来源：直接创建";
    const primary = status === "archived" ? `<button class="table-action" data-restore-quote="${escapeHtml(quote.id)}">恢复</button>` : `<button class="table-action" data-edit-quote="${escapeHtml(quote.id)}">编辑</button>`;
    const destructive = status === "draft" ? `<button class="table-action danger" data-delete-quote="${escapeHtml(quote.id)}">删除</button>` : `<button class="table-action danger" data-archive-quote="${escapeHtml(quote.id)}">归档</button>`;
    const exportAction = status === "archived" ? "" : `<button class="table-action" data-export-quote="${escapeHtml(quote.id)}">导出 PDF</button>`;
    const actions = `<span class="table-actions">${primary}<details class="table-actions-menu"><summary aria-label="更多报价操作">更多</summary><div>${exportAction}<button class="table-action" data-quote-history="${escapeHtml(quote.id)}">版本与发送历史</button>${status === "archived" ? "" : destructive}</div></details></span>`;
    return `<tr><td><strong class="business-cell-title">${escapeHtml(quote.title)}</strong><small class="business-cell-meta"><span translate="no">${escapeHtml(number)}</span> · V${formatNumber(quote.version || 1)}</small><small class="business-cell-meta">${escapeHtml(source)}</small></td><td>${renderCustomerLines(quote.customer_name, quote.customer_email, quote.customer_phone)}</td><td><span class="badge ${status === "archived" ? "off" : status === "sent" ? "good" : ""}">${escapeHtml(quoteLifecycleLabel(status))}</span><small class="business-cell-meta">${delivery}</small></td><td>${escapeHtml(quote.display_name || quote.email || quote.phone || "—")}<small class="business-cell-meta">更新于 ${escapeHtml(formatDate(quote.updated_at))}</small></td><td class="business-number-cell">${symbol}${formatNumber(quote.total_price, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td><td class="align-right">${actions}</td></tr>`;
  }).join("") || '<tr><td colspan="6" class="empty">暂无报价单</td></tr>';
}

async function loadQuotes() {
  const result = await api(quoteListPath());
  state.quotes = result.items || [];
  renderQuotes();
  syncBusinessFilterUrl();
}

function quoteLifecycleLabel(status) {
  return { draft: "草稿", sent: "已发送", archived: "已归档" }[status] || status || "草稿";
}

function inquiryStatusLabel(status) {
  return { new: "新询价", assigned: "已分配", contacted: "已联系", quoted: "已转报价", closed: "已完成", cancelled: "客户已取消" }[status] || status || "—";
}

function inquiryListStatusLabel(item) {
  const name = String(item.assignee_name || "").trim();
  return item.status === "assigned" && name ? `已分配：${name}` : inquiryStatusLabel(item.status);
}

function renderInquiryQuoteStatus(item) {
  const count = Number(item.quote_count || 0);
  if (count > 0) return `<span class="badge good">已报价 · ${count} 份</span>`;
  return item.historical_quote_count ? '<span class="badge off">历史报价已归档</span>' : '<span class="badge inquiry-unquoted">未报价</span>';
}

function renderInquiryBusinessStatus(item) {
  const status = item.business_status || item.status;
  const sent = Number(item.sent_quote_count || 0), draft = Number(item.draft_quote_count || 0);
  const label = status === "sent" ? `已报价 · ${sent} 份` : ({ pending: "待报价", archived: "报价已归档" }[status] || inquiryListStatusLabel(item));
  const style = status === "sent" ? "good" : status === "pending" ? "inquiry-converted" : ["closed", "cancelled", "archived"].includes(status) ? "off" : "warn";
  const owner = item.assignee_name && status !== "assigned" ? `<small>负责人：${escapeHtml(item.assignee_name)}</small>` : "";
  const detail = (sent && status !== "sent" ? `<small>已报价 ${sent} 份</small>` : "") + (draft ? `<small>草稿 ${draft} 份</small>` : "");
  return `<span class="badge ${style}">${escapeHtml(label)}</span>${owner}${detail}`;
}

function renderQuoteSourceStatus(item) {
  const count = Number(item.quote_count || 0);
  if (!count) return item.historical_quote_count ? '<span class="badge off">历史报价已归档</span>' : '<span class="badge">未报价</span>';
  const people = (item.quoted_by || []).map((person) => person.display_name).filter(Boolean).join("、") || "—";
  return `<span class="badge good">已报价 · ${count} 份</span><br><small>${escapeHtml(people)}</small>`;
}

function renderInquirySummary(item) {
  const counts = { device: 0, tool: 0, accessory: 0 };
  (item.item_summary || []).forEach((part) => {
    const amount = part.item_type === "device_config" ? Number(part.item_count || 0) : Number(part.quantity || 0);
    if (part.item_type === "device_config") counts.device += amount;
    else if (part.item_type === "tool") counts.tool += amount;
    else if (part.item_type === "accessory") counts.accessory += amount;
  });
  if (!Object.values(counts).some((count) => count > 0) && Number(item.item_count || 0) > 0) counts.device = Number(item.item_count);
  return renderCommerceCountLines(counts);
}

function commerceItemType(item) {
  const explicit = item.item_type || item.itemType;
  if (["device_config", "tool", "accessory"].includes(explicit)) return explicit;
  if (item.kind === "tool") return "tool";
  if (item.kind === "accessory") return "accessory";
  return "device_config";
}

function normalizeCatalogCode(value) {
  const raw = String(value || "").trim().toUpperCase();
  const code = raw.replace(/\s+/g, "");
  const match = code.match(/^(BTE|BTK|BTC|BT)-?([A-Z0-9]+)$/);
  return match ? `${match[1]}-${match[2]}` : raw;
}

function catalogDisplayName(name, code) {
  let text = String(name || "").trim();
  const canonical = normalizeCatalogCode(code);
  const aliases = [String(code || "").trim(), canonical, canonical.replace(/-/g, "")].filter(Boolean).sort((a, b) => b.length - a.length);
  for (const alias of aliases) {
    const escaped = alias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const updated = text.replace(new RegExp(`^${escaped}(?=$|[\\s·:：/\\\\|_—–-])(?:[\\s·:：/\\\\|_—–-]+)?`, "i"), "").trim();
    if (updated !== text) { text = updated; break; }
  }
  return text;
}

function catalogIdentityHtml(code, name, fallback = "未命名项目") {
  const normalizedCode = normalizeCatalogCode(code);
  const cleanName = catalogDisplayName(name, normalizedCode);
  return `<span class="catalog-item-identity">${normalizedCode ? `<small>${escapeHtml(normalizedCode)}</small>` : ""}<strong>${escapeHtml(cleanName || fallback)}</strong></span>`;
}

function canonicalCommerceItems(items = []) {
  const typeOrder = { device_config: 0, tool: 1, accessory: 2 };
  return items.map((item, index) => ({ item, index })).sort((left, right) => {
    const leftType = commerceItemType(left.item); const rightType = commerceItemType(right.item);
    if (typeOrder[leftType] !== typeOrder[rightType]) return typeOrder[leftType] - typeOrder[rightType];
    if (leftType === "device_config") return left.index - right.index;
    const number = (entry) => Number(entry.catalog_category_sort_order ?? entry.category_sort_order ?? entry.snapshot?.category_sort_order ?? Number.MAX_SAFE_INTEGER);
    const order = (entry) => Number(entry.catalog_sort_order ?? entry.sort_order ?? entry.snapshot?.sort_order ?? Number.MAX_SAFE_INTEGER);
    return number(left.item) - number(right.item)
      || order(left.item) - order(right.item)
      || String(left.item.code || left.item.snapshot?.code || "").localeCompare(String(right.item.code || right.item.snapshot?.code || ""), "en", { numeric: true })
      || left.index - right.index;
  }).map(({ item }) => item);
}

function aggregateCommerceItems(items = []) {
  const ordered = canonicalCommerceItems(items);
  const groups = { devices: [], tools: [], accessories: [] };
  ordered.forEach((item) => {
    const type = commerceItemType(item);
    if (type === "tool") groups.tools.push(item);
    else if (type === "accessory") groups.accessories.push(item);
    else groups.devices.push(item);
  });
  return groups;
}

function inquirySourceSummary(item) {
  return item.source_type === "cart" ? "购物车" : item.source_type === "current_device" ? "设备页" : "--";
}

function inquiryAvailabilityLabel(status) {
  return { active: "当前可用", inactive: "已停用，保留历史", missing: "目录已删除，保留历史", snapshot_only: "选配规则已变化，使用历史快照" }[status] || "使用历史快照";
}

function inquiryTimingSummary(item) {
  const moments = [
    ["接手", item.assigned_at], ["联系", item.contacted_at],
    ["首报", item.first_quoted_at || item.quoted_at], ["更新报价", item.latest_quoted_at],
    ["关闭", item.closed_at]
  ].filter((entry) => entry[1]);
  return moments.length ? `<small class="inquiry-list-timeline">${moments.map(([label, value]) => `${escapeHtml(label)} ${escapeHtml(formatDateTime(value))}`).join(" · ")}</small>` : "";
}

function renderInquiries() {
  const target = $("#inquiries-table");
  if (!target) return;
  target.innerHTML = state.inquiries.map((item) => {
    const canTake = !item.assigned_to && item.status === "new";
    const stateClass = item.status === "quoted" ? "inquiry-converted" : ["cancelled", "closed"].includes(item.status) ? "off" : "warn";
    const quoteAction = item.status !== "cancelled"
      ? item.own_latest_quote_id
        ? `<button class="table-action" data-open-inquiry-quote="${escapeHtml(item.own_latest_quote_id)}">查看我的报价</button>`
        : `<button class="table-action" data-quote-inquiry="${escapeHtml(item.id)}">${Number(item.quote_count || 0) ? "再次报价" : "转报价"}</button>`
      : "";
    const actions = `<span class="table-actions"><button class="table-action" data-view-inquiry="${escapeHtml(item.id)}">查看</button>${canTake ? `<button class="table-action" data-take-inquiry="${escapeHtml(item.id)}">接手</button>` : ""}<details class="table-actions-menu"><summary aria-label="更多询价操作">更多</summary><div><button class="table-action" data-export-inquiry="${escapeHtml(item.id)}" data-inquiry-number="${escapeHtml(item.inquiry_number)}">导出 PDF</button>${quoteAction}</div></details></span>`;
    return `<tr><td><strong translate="no">${escapeHtml(item.inquiry_number)}</strong><small class="business-cell-meta">${escapeHtml(inquirySourceSummary(item))}</small></td><td>${renderCustomerLines(item.customer_name_snapshot || item.customer_display_name, item.customer_email_snapshot || item.customer_email_current, item.customer_phone_snapshot || item.customer_phone_current)}</td><td>${renderInquirySummary(item)}</td><td>${renderInquiryBusinessStatus(item)}</td><td>${escapeHtml(formatDateTime(item.created_at))}</td><td class="align-right">${actions}</td></tr>`;
  }).join("") || '<tr><td colspan="7" class="empty">暂无询价记录</td></tr>';
  const pages = Math.max(1, Math.ceil(state.inquiryTotal / state.inquiryPageSize));
  if ($("#inquiry-page-summary")) $("#inquiry-page-summary").textContent = `共 ${state.inquiryTotal} 条 · 第 ${state.inquiryPage}/${pages} 页`;
  if ($("#inquiry-page-prev")) $("#inquiry-page-prev").disabled = state.inquiryPage <= 1;
  if ($("#inquiry-page-next")) $("#inquiry-page-next").disabled = state.inquiryPage >= pages;
}

async function takeInquiry(button) {
  const inquiry = state.inquiries.find((item) => item.id === button.dataset.takeInquiry);
  if (!inquiry) return;
  try {
    await runButtonAction(button, "接手中…", async () => {
      await api(`/api/v1/staff/inquiries/${encodeURIComponent(inquiry.id)}`, { method: "PATCH", body: JSON.stringify({ version: inquiry.version, status: "assigned", assigned_to: state.user.id }) });
      showToast("询价已分配给当前账号");
      await loadInquiries();
    });
  } catch (failure) {
    if (failure.code === "INQUIRY_STATUS_CONFLICT") {
      await loadInquiries();
      showToast("询价状态已更新，请重新操作", "error");
    } else showToast(failure.message, "error");
  }
}

async function viewInquiry(inquiryId) {
  ensureInquiryDrawer();
  openInquiryDrawer();
  const body = $("[data-inquiry-drawer-body]", inquiryDrawerElement);
  const title = $("[data-inquiry-drawer-title]", inquiryDrawerElement);
  const footer = $("[data-inquiry-drawer-footer]", inquiryDrawerElement);
  title.textContent = "询价详情";
  body.innerHTML = '<div class="share-result-loading">正在加载询价详情…</div>';
  footer.innerHTML = '<button class="button button-secondary" type="button" data-inquiry-drawer-close>关闭</button>';
  try {
    const inquiry = await api(`/api/v1/staff/inquiries/${encodeURIComponent(inquiryId)}?lang=${state.catalogLanguage === "en" ? "en" : "zh"}`);
    const inquiryGroups = aggregateCommerceItems(inquiry.items || []);
    const isConfiguredValue = (value) => {
      const normalized = String(value || "").trim().toLocaleLowerCase();
      return Boolean(normalized) && !new Set(["未配置", "未选择", "无", "none", "not configured", "not selected", "n/a", "—", "-"]).has(normalized);
    };
    const devices = inquiryGroups.devices.map((entry, index) => {
      const snapshot = entry.snapshot || {};
      const categories = snapshot.categories || [];
      const singleValue = (id) => categories.find((category) => category.id === id)?.options?.map((option) => option.name).filter(isConfiguredValue).join(" / ") || "";
      const basics = [
        ["型号", snapshot.product?.name || ""], ["名称", snapshot.product?.title_name || ""],
        ["颜色", snapshot.color?.label || snapshot.color?.code || ""], ["电机", singleValue("motor")],
        ["电源", singleValue("voltage")], ["通道", singleValue("channel")]
      ].filter(([, value]) => isConfiguredValue(value)).map(([label, value]) => `<div><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
      const optionGroups = categories.filter((category) => !["motor", "voltage", "channel"].includes(category.id) && (category.options || []).length).map((category) => `<section class="share-detail-group"><header><span>${escapeHtml(category.name)}</span><small>${category.options.length} 项</small></header><ul>${category.options.map((option) => `<li>${catalogIdentityHtml(option.code, option.name, "未命名配置")}${plainDescription(option.description) ? `<span>${escapeHtml(plainDescription(option.description))}</span>` : ""}</li>`).join("")}</ul></section>`).join("");
      const availability = String(entry.availability || "snapshot_only");
      const availabilityNote = availability === "active" ? "" : `<em class="inquiry-availability ${escapeHtml(availability)}">${escapeHtml(inquiryAvailabilityLabel(availability))}</em>`;
      return `<article class="share-device-block inquiry-device-block"><h4>设备 ${index + 1} · ${escapeHtml(snapshot.product?.name || entry.display_name || "未填写")}${availabilityNote}</h4><section class="share-detail-group share-device-basics"><header><span>设备信息</span><small>型号与基本配置</small></header><div class="share-basic-list">${basics}</div></section><div class="share-detail-groups">${optionGroups || '<div class="empty">该设备未选择其他选配项目</div>'}</div></article>`;
    }).join("");
    const catalogSections = [[inquiryGroups.tools, "维修工具"], [inquiryGroups.accessories, "设备附件"]].map(([entries, label]) => {
      if (!entries.length) return "";
      const total = entries.reduce((sum, item) => sum + Number(item.quantity || 1), 0);
      const rows = entries.map((entry) => {
        const snapshot = entry.snapshot || {};
        const availability = String(entry.availability || "snapshot_only");
        const availabilityNote = availability === "active" ? "" : `<em class="inquiry-availability ${escapeHtml(availability)}">${escapeHtml(inquiryAvailabilityLabel(availability))}</em>`;
        return `<li>${catalogIdentityHtml(snapshot.code, snapshot.name || entry.display_name)}${availabilityNote}<span class="share-item-quantity">数量：${formatNumber(entry.quantity || snapshot.quantity || 1)}</span></li>`;
      }).join("");
      return `<article class="share-device-block share-catalog-block"><section class="share-detail-group"><header><span>${label}</span><small>共 ${formatNumber(total)} 件</small></header><ul>${rows}</ul></section></article>`;
    }).join("");
    const sources = (inquiry.sources || []).length
      ? inquiry.sources.map((source) => `<span class="inquiry-source-chip" translate="no">${escapeHtml(source.source_share_code || source.source_share_id || "历史分享")}</span>`).join("")
      : '<span class="inquiry-source-empty">无分享来源</span>';
    const quotedBy = (inquiry.quoted_by || []).map((person) => person.display_name).filter(Boolean).join("、");
    const timeline = [
      ["创建", inquiry.created_at], ["首次接手", inquiry.assigned_at], ["首次联系", inquiry.contacted_at], ["首次报价", inquiry.first_quoted_at || inquiry.quoted_at],
      ["最近报价", inquiry.latest_quoted_at], ["关闭", inquiry.closed_at]
    ].filter((entry) => entry[1]).map(([label, value]) => `<li><span>${label}</span><time>${escapeHtml(formatDateTime(value))}</time></li>`).join("");
    const quoteLinks = (inquiry.quote_links || []).map((quote) => `<button class="button button-secondary" type="button" data-open-inquiry-quote="${escapeHtml(quote.id)}">打开${quote.own ? "我的" : escapeHtml(quote.display_name || "关联")}报价</button>`).join("");
    title.innerHTML = `询价记录 <span translate="no">${escapeHtml(inquiry.inquiry_number)}</span>`;
    const inquiryCounts = { device: inquiryGroups.devices.length, tool: inquiryGroups.tools.reduce((sum, item) => sum + Number(item.quantity || 1), 0), accessory: inquiryGroups.accessories.reduce((sum, item) => sum + Number(item.quantity || 1), 0) };
    const summary = [[inquiryCounts.device, "台设备"], [inquiryCounts.tool, "件工具"], [inquiryCounts.accessory, "件附件"]].filter(([count]) => count > 0).map(([count, label]) => `${formatNumber(count)} ${label}`).join(" · ") || "未包含有效项目";
    const customer = renderCustomerLines(inquiry.customer_name_snapshot || inquiry.customer_display_name, inquiry.customer_email_snapshot || inquiry.customer_email_current, inquiry.customer_phone_snapshot || inquiry.customer_phone_current);
    const processing = `<strong>${escapeHtml(inquiryStatusLabel(inquiry.status))}</strong>${inquiry.assignee_name ? `<small>负责人：${escapeHtml(inquiry.assignee_name)}</small>` : ""}${quotedBy ? `<small>报价人：${escapeHtml(quotedBy)}</small>` : '<small>尚未报价</small>'}`;
    body.innerHTML = `<div class="inquiry-share-layout"><header class="share-result-header"><div><h3>${summary}</h3></div><span class="badge ${inquiry.status === "new" ? "good" : ""}">${escapeHtml(inquiryStatusLabel(inquiry.status))}</span></header><div class="share-device-summary"><div><span>询价客户</span>${customer}</div><div><span>处理状态</span>${processing}</div></div>${inquiry.message ? `<section class="inquiry-message-module"><span>客户备注</span><p>${escapeHtml(inquiry.message)}</p></section>` : ""}${devices}${catalogSections}${timeline ? `<section class="inquiry-timeline-section share-detail-group"><header><span>处理时间线</span><small>业务跟进记录</small></header><ol class="inquiry-timeline">${timeline}</ol></section>` : ""}</div>`;
    footer.innerHTML = `<div class="inquiry-linked-quotes">${quoteLinks}</div><button class="button button-secondary" type="button" data-inquiry-drawer-close>关闭</button>`;
  } catch (failure) {
    if (failure.code === "INQUIRY_STATUS_CONFLICT") {
      await loadInquiries();
      body.innerHTML = '<div class="share-result-loading share-result-error">询价状态已更新，请关闭后重新打开。</div>';
    } else body.innerHTML = `<div class="share-result-loading share-result-error">${escapeHtml(failure.message)}</div>`;
  }
}

function ensureInquiryDrawer() {
  if (inquiryDrawerElement && inquiryDrawerBackdrop) return;
  inquiryDrawerBackdrop = document.createElement("div");
  inquiryDrawerBackdrop.className = "share-drawer-backdrop inquiry-drawer-backdrop";
  inquiryDrawerElement = document.createElement("aside");
  inquiryDrawerElement.className = "share-drawer inquiry-drawer";
  inquiryDrawerElement.setAttribute("role", "dialog");
  inquiryDrawerElement.setAttribute("aria-modal", "true");
  inquiryDrawerElement.setAttribute("aria-labelledby", "inquiry-drawer-title");
  inquiryDrawerElement.setAttribute("aria-hidden", "true");
  inquiryDrawerElement.innerHTML = `<header class="share-drawer-header"><div><span class="eyebrow">CUSTOMER INQUIRY</span><h2 id="inquiry-drawer-title" data-inquiry-drawer-title>询价详情</h2></div><button class="icon-button" type="button" data-inquiry-drawer-close aria-label="关闭">×</button></header><div class="share-drawer-body" data-inquiry-drawer-body></div><footer class="share-drawer-footer" data-inquiry-drawer-footer><button class="button button-secondary" type="button" data-inquiry-drawer-close>关闭</button></footer>`;
  document.body.append(inquiryDrawerBackdrop, inquiryDrawerElement);
  inquiryDrawerBackdrop.addEventListener("click", closeInquiryDrawer);
  inquiryDrawerElement.addEventListener("click", (event) => { if (event.target.closest("[data-inquiry-drawer-close]")) closeInquiryDrawer(); });
  inquiryDrawerElement.addEventListener("keydown", (event) => {
    if (!inquiryDrawerElement.classList.contains("open") || document.querySelector("dialog[open]")) return;
    if (event.key === "Escape") { event.preventDefault(); closeInquiryDrawer(); return; }
    if (event.key !== "Tab") return;
    const focusable = $$('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])', inquiryDrawerElement).filter((item) => !item.hidden);
    if (!focusable.length) return;
    const first = focusable[0]; const last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
}

function openInquiryDrawer() {
  ensureInquiryDrawer();
  closeShareDrawer();
  previousInquiryFocus = document.activeElement;
  inquiryDrawerBackdrop.classList.add("open");
  inquiryDrawerElement.classList.add("open");
  inquiryDrawerElement.setAttribute("aria-hidden", "false");
  document.body.classList.add("share-drawer-open");
  requestAnimationFrame(() => $("[data-inquiry-drawer-close]", inquiryDrawerElement)?.focus());
}

function closeInquiryDrawer() {
  if (!inquiryDrawerElement) return;
  inquiryDrawerBackdrop.classList.remove("open");
  inquiryDrawerElement.classList.remove("open");
  inquiryDrawerElement.setAttribute("aria-hidden", "true");
  document.body.classList.remove("share-drawer-open");
  if (previousInquiryFocus?.isConnected) previousInquiryFocus.focus();
  previousInquiryFocus = null;
}

async function quoteInquiry(button) {
  const inquiry = state.inquiries.find((item) => item.id === button.dataset.quoteInquiry);
  if (!inquiry) return;
  if (Number(inquiry.quote_count || 0)) {
    const confirmed = await confirmAction(
      "该询价已有报价",
      `已有 ${Number(inquiry.quote_count)} 份有效报价。是否继续创建属于你的报价单？`,
      "继续报价"
    );
    if (!confirmed) return;
  }
  try {
    await runButtonAction(button, "创建中…", async () => {
      const result = await api(`/api/v1/staff/inquiries/${encodeURIComponent(inquiry.id)}/convert-to-quote`, { method: "POST", body: JSON.stringify({ version: inquiry.version, currency: "CNY", idempotency_key: crypto.randomUUID?.() || `${Date.now()}-inquiry-quote` }) });
      await loadData();
      const customer = quoteCustomerContext(result.quote, inquiry);
      openQuoteEditor({ quoteId: result.quote.id, quoteVersion: result.quote.version, sourceInquiryId: result.quote.source_inquiry_id || inquiry.id, sourceType: "inquiry", sourceDocumentVersion: result.quote.source_document_version || inquiry.document_version || 1, sourceDocumentId: inquiry.id, sourceCode: inquiry.inquiry_number, title: result.quote.title, items: result.quote.items, currency: result.quote.currency || "CNY", ...customer, language: result.quote.language || "zh" });
      showToast(result.reused ? "已打开你的现有报价" : "报价草稿已创建，请填写价格后保存或发送");
    });
  } catch (failure) {
    if (failure.code === "INQUIRY_STATUS_CONFLICT") {
      await loadInquiries();
      showToast("询价状态已更新，请重新操作", "error");
    } else showToast(failure.message, "error");
  }
}

function quoteCustomerContext(quote = {}, fallbackInquiry = null) {
  const inquiry = state.inquiries.find((item) =>
    item.id === quote.source_inquiry_id
    || item.id === quote.source_document_id
    || item.own_latest_quote_id === quote.id
  ) || fallbackInquiry;
  const recipientUserId = inquiry?.created_by || "";
  return {
    customerName: quote.customer_name ?? inquiry?.customer_name_snapshot ?? inquiry?.customer_display_name ?? "",
    customerEmail: quote.customer_email ?? inquiry?.customer_email_snapshot ?? inquiry?.customer_email_current ?? "",
    customerPhone: quote.customer_phone ?? inquiry?.customer_phone_snapshot ?? inquiry?.customer_phone_current ?? "",
    customerAddress: quote.customer_address || "",
    recipientUserId,
    recipientLabel: inquiry?.customer_name_snapshot || inquiry?.customer_display_name || inquiry?.customer_email_snapshot || (recipientUserId ? "客户账号" : "")
  };
}

async function openInquiryQuote(button) {
  try {
    await runButtonAction(button, "打开中…", async () => {
      const quote = await api(`/api/v1/quotes/${encodeURIComponent(button.dataset.openInquiryQuote)}`);
      const customer = quoteCustomerContext(quote);
      const sourceDialog = button.closest("dialog");
      if (sourceDialog?.open) sourceDialog.close();
      openQuoteEditor({
        quoteId: quote.id,
        quoteVersion: quote.version,
        configId: quote.config_id,
        title: quote.title,
        items: quote.items,
        currency: quote.currency || "CNY",
        sourceShareId: quote.source_share_id,
        sourceInquiryId: quote.source_inquiry_id,
        sourceType: quote.source_type,
        sourceDocumentVersion: quote.source_document_version,
        sourceDocumentId: quote.source_document_id,
        sourceCode: quote.source_code,
        customerName: customer.customerName,
        customerEmail: customer.customerEmail,
        customerPhone: customer.customerPhone, customerAddress: customer.customerAddress || "",
        language: quote.language || "zh",
        recipientUserId: customer.recipientUserId,
        recipientLabel: customer.recipientLabel,
      });
    });
  } catch (failure) { showToast(failure.message, "error"); }
}

let pdfExportPending = false;
function choosePdfLanguage() {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    const opener = document.activeElement;
    dialog.className = "pdf-language-dialog";
    dialog.setAttribute("aria-labelledby", "pdf-language-title");
    dialog.setAttribute("aria-describedby", "pdf-language-description");
    dialog.innerHTML = `<form method="dialog" class="pdf-language-card"><header><h2 id="pdf-language-title">导出 PDF</h2><button class="icon-button" value="cancel" aria-label="关闭">×</button></header><fieldset><legend>文件语言</legend><div class="pdf-language-options"><label><input type="radio" name="language" value="zh"><span>中文版</span></label><label><input type="radio" name="language" value="en"><span lang="en">English</span></label></div></fieldset><p id="pdf-language-description">仅影响本次文件，不改变原记录、币种或金额。</p><footer><button class="button button-secondary" value="cancel">取消</button><button class="button button-primary" value="export">导出</button></footer></form>`;
    dialog.querySelector(`input[value="${state.catalogLanguage === "en" ? "en" : "zh"}"]`).checked = true;
    document.body.appendChild(dialog);
    dialog.addEventListener("close", () => {
      const language = dialog.returnValue === "export" ? dialog.querySelector('input[name="language"]:checked').value : null;
      dialog.remove(); if (opener?.isConnected) opener.focus(); resolve(language);
    }, { once: true });
    dialog.showModal();
    dialog.querySelector('input:checked').focus();
  });
}

async function exportInquiryPdf(button) {
  if (pdfExportPending) return;
  pdfExportPending = true;
  const inquiryId = button.dataset.exportInquiry;
  const inquiryNumber = button.dataset.inquiryNumber || inquiryId.slice(0, 8);
  try {
    const language = await choosePdfLanguage();
    if (!language) return;
    await runButtonAction(button, "导出中…", async () => {
      const response = await fetch(`${API_BASE}/api/v1/staff/inquiries/${encodeURIComponent(inquiryId)}/pdf?lang=${language}`, { headers: { Authorization: `Bearer ${sessionStorage.getItem(TOKEN_KEY)}` } });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `PDF生成失败（${response.status}）`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = response.headers.get("Content-Disposition")?.match(/filename="([^"]+)"/)?.[1] || "BOTEN.pdf";
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      showToast("询价配置 PDF 已开始下载（不含价格）");
    });
  } catch (failure) { showToast(failure.message, "error"); }
  finally { pdfExportPending = false; }
}

function renderAudits() {
  const target = $("#audit-table"); if (!target) return;
  target.innerHTML = state.audits.map((item) => {
    const actor = item.display_name || item.email || item.phone || "已删除账号";
    const path = item.details?.path || `${item.entity_type}/${item.entity_id || ""}`;
    return `<tr><td>${escapeHtml(formatDateTime(item.created_at))}</td><td><strong>${escapeHtml(actor)}</strong><br><small>${escapeHtml(roleLabel(item.role || ""))}</small></td><td><span class="badge">${escapeHtml(item.action)}</span></td><td>${escapeHtml(path)}</td><td>${escapeHtml(item.details?.status || "成功")}</td></tr>`;
  }).join("") || '<tr><td colspan="5" class="empty">暂无操作记录</td></tr>';
}

function switchView(view, updateHistory = true) {
  const catalogViews = {
    "config-catalog": { rootId: "catalog-optional", title: "配置目录", eyebrow: "CONFIGURATION CATALOG", description: "维护设备可勾选的扩展配置；参考价格用于后续报价默认单价。" },
    "tool-catalog": { rootId: "catalog-tools", title: "工具目录", eyebrow: "TOOL CATALOG", description: "维护可独立加入购物车、分享和报价的维修工具。" },
    "accessory-catalog": { rootId: "catalog-accessories", title: "附件目录", eyebrow: "ACCESSORY CATALOG", description: "维护可独立加入购物车、分享和报价的设备附件。" }
  };
  const salesViews = ["dashboard", "products", ...Object.keys(catalogViews), "shares", "inquiries", "quotes"];
  if (state.user?.role === "sales" && !salesViews.includes(view)) view = "dashboard";
  const titles = { dashboard: "仪表盘", products: "设备目录", "config-catalog": "配置目录", "tool-catalog": "工具目录", "accessory-catalog": "附件目录", users: "账号管理", shares: "分享记录", inquiries: "询价列表", quotes: "报价管理", audit: "操作审计" };
  if (!titles[view]) view = "dashboard";
  const previousView = $(".view.active")?.dataset.viewPanel;
  if (view === "dashboard" && (previousView !== "dashboard" || !dashboardState.data)) void loadDashboard();
  const catalogView = catalogViews[view];
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  $$(".view").forEach((panel) => panel.classList.toggle("active", panel.dataset.viewPanel === (catalogView ? "config-catalog" : view)));
  const viewTitle = $("#view-title");
  if (viewTitle) viewTitle.textContent = titles[view];
  if (catalogView) {
    $("#catalog-view-eyebrow").textContent = catalogView.eyebrow;
    $("#catalog-view-title").textContent = catalogView.title;
    $("#catalog-view-description").textContent = catalogView.description;
    const catalogAction = $("#add-config-category");
    delete catalogAction.dataset.addCatalogCategory;
    delete catalogAction.dataset.addCatalogItem;
    catalogAction.hidden = false;
    catalogAction.textContent = "添加分类";
    catalogAction.dataset.addCatalogCategory = "";
    window.selectCatalogRootFromNavigation?.(catalogView.rootId);
  }
  if (updateHistory && window.location.hash !== `#${view}`) window.location.hash = view;
  if ($("#primary-action")) $("#primary-action").hidden = true;
  closeSidebar();
}

async function setUserStatus(button) {
  const enabled = button.dataset.enabled === "true";
  if (!await confirmAction(enabled ? "启用账号" : "禁用账号", enabled ? "确定恢复该账号的访问权限吗？" : "确定禁用该账号并撤销其当前会话吗？", enabled ? "确认启用" : "确认禁用")) return;
  try { await runButtonAction(button, "处理中…", async () => { const result = await api(`/api/v1/admin/users/${button.dataset.userStatus}/status`, { method: "PATCH", body: JSON.stringify({ enabled, version: Number(button.dataset.userVersion) }) }); applyUserMutation(result); showToast(enabled ? "账号已启用" : "账号已停用"); void refreshUsersAfterMutation(); }); }
  catch (failure) { showToast(failure.message, "error"); }
}

function findUser(userId) { return state.users.find((item) => item.id === userId); }
function clearAccountErrors(form) {
  $$('[aria-invalid="true"]', form).forEach((field) => field.removeAttribute("aria-invalid"));
  $$("[data-field-error]", form).forEach((error) => { error.hidden = true; error.textContent = ""; });
  const summary = $(".form-error", form); if (summary) { summary.hidden = true; summary.textContent = ""; }
}
function showAccountError(form, failure, fallbackField = "") {
  clearAccountErrors(form);
  const fieldName = failure.field || fallbackField;
  const field = fieldName ? form.elements[fieldName] : null;
  const inline = fieldName ? $(`[data-field-error="${fieldName}"]`, form) : null;
  if (field && inline) { field.setAttribute("aria-invalid", "true"); inline.textContent = failure.message; inline.hidden = false; field.focus(); return; }
  const summary = $(".form-error", form); if (summary) { summary.textContent = failure.requestId ? `${failure.message}（编号 ${failure.requestId}）` : failure.message; summary.hidden = false; }
}
function prepareAccountDialog(dialog, user, trigger) {
  dialog._returnFocus = trigger || document.activeElement;
  const target = $("[data-account-target]", dialog); if (target) target.textContent = `${user.display_name || "未命名用户"} · ${user.email || `${user.phone_calling_code || ""} ${user.phone || ""}`}`;
  clearAccountErrors($("form", dialog)); dialog.showModal();
  requestAnimationFrame(() => $("input:not([type=hidden]), select, textarea", dialog)?.focus());
}
function openUserEditor(user = null, trigger = null) {
  const dialog = $("#user-dialog");
  const form = $("#user-form");
  const editing = Boolean(user);
  form.reset();
  form.elements.user_id.value = user?.id || "";
  form.elements.version.value = user?.version || "";
  form.elements.display_name.value = user?.display_name || "";
  form.elements.role.value = user?.role || "sales";
  form.elements.email.value = user?.email || "";
  form.elements.phone.value = user?.phone || "";
  form.elements.phone_country.innerHTML = state.countries.map((country) => `<option value="${escapeHtml(country.code)}">${escapeHtml(country.name)}</option>`).join("");
  form.elements.phone_country.value = user?.phone_country || "CN";
  updateAdminPhoneCallingCode();
  form.elements.password.required = !editing;
  $$('[data-create-only]', form).forEach((element) => { element.hidden = editing; });
  $("#user-dialog-eyebrow").textContent = editing ? "EDIT PROFILE" : "NEW ACCOUNT";
  $("#user-dialog-title").textContent = editing ? "编辑账号资料" : "创建账号";
  $("#create-user-submit").textContent = editing ? "保存资料" : "创建账号";
  clearAccountErrors(form); form.dataset.initialSnapshot = JSON.stringify(Object.fromEntries(new FormData(form)));
  dialog._returnFocus = trigger || document.activeElement; dialog.showModal(); requestAnimationFrame(() => form.elements.display_name.focus());
}

function updateAdminPhoneCallingCode() {
  const country = state.countries.find((item) => item.code === $("#user-form [name='phone_country']")?.value);
  const output = $("#admin-phone-calling-code");
  if (output) output.textContent = country?.calling_code || "—";
}

async function createUser(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (event.submitter?.value === "cancel") { form.closest("dialog")?.close(); return; }
  const data = Object.fromEntries(new FormData(form));
  const userId = data.user_id;
  delete data.user_id;
  data.display_name = data.display_name.trim();
  data.email = data.email.trim() || null; data.phone = data.phone.trim() || null; data.phone_country = data.phone ? data.phone_country : null;
  clearAccountErrors(form);
  if (!data.display_name) { showAccountError(form, new ApiError("请填写显示名称", { field: "display_name" })); return; }
  if (!data.email && !data.phone) { showAccountError(form, new ApiError("邮箱和手机号至少填写一项", { field: "email" })); return; }
  if (!userId && (!data.password || data.password.length < 8)) { showAccountError(form, new ApiError("密码至少需要 8 个字符", { field: "password" })); return; }
  const original = userId ? findUser(userId) : null;
  const selfSensitive = userId === state.user?.id && original && (data.email !== original.email || data.phone !== original.phone || data.phone_country !== original.phone_country);
  if (userId) { delete data.role; delete data.password; }
  else delete data.version;
  const submit = event.submitter;
  try { await runButtonAction(submit, "正在保存…", async () => { const result = await api(userId ? `/api/v1/admin/users/${userId}` : "/api/v1/admin/users", { method: userId ? "PATCH" : "POST", body: JSON.stringify(data) }); applyUserMutation(result, { created: !userId }); $("#user-dialog").close(); form.reset(); showToast(selfSensitive ? "登录信息已更新，请重新登录" : userId ? "账号资料已保存" : "账号创建成功"); if (selfSensitive) setTimeout(logout, 900); else void refreshUsersAfterMutation(); }); }
  catch (failure) { showAccountError(form, failure); }
}

function openRoleEditor(user, trigger) { const dialog = $("#user-role-dialog"), form = $("#user-role-form"); form.reset(); form.elements.user_id.value = user.id; form.elements.version.value = user.version; form.elements.role.value = user.role; form.dataset.initialSnapshot = JSON.stringify(Object.fromEntries(new FormData(form))); prepareAccountDialog(dialog, user, trigger); }
function openPasswordEditor(user, trigger) { const dialog = $("#user-password-dialog"), form = $("#user-password-form"); form.reset(); form.elements.user_id.value = user.id; form.elements.version.value = user.version; form.dataset.initialSnapshot = JSON.stringify(Object.fromEntries(new FormData(form))); prepareAccountDialog(dialog, user, trigger); }
function openArchiveEditor(user, trigger) { const dialog = $("#user-archive-dialog"), form = $("#user-archive-form"); form.reset(); form.elements.user_id.value = user.id; form.elements.version.value = user.version; form.dataset.initialSnapshot = JSON.stringify(Object.fromEntries(new FormData(form))); prepareAccountDialog(dialog, user, trigger); }
async function submitRole(event) { event.preventDefault(); const form = event.currentTarget, submit = event.submitter; if (submit?.value === "cancel") return; clearAccountErrors(form); try { await runButtonAction(submit, "保存中…", async () => { const result = await api(`/api/v1/admin/users/${form.elements.user_id.value}/role`, { method: "PATCH", body: JSON.stringify({ role: form.elements.role.value, version: Number(form.elements.version.value) }) }); applyUserMutation(result); form.closest("dialog").close(); showToast("账号角色已更新"); void refreshUsersAfterMutation(); }); } catch (failure) { showAccountError(form, failure); } }
async function submitPassword(event) { event.preventDefault(); const form = event.currentTarget, submit = event.submitter; if (submit?.value === "cancel") return; clearAccountErrors(form); if (form.elements.password.value !== form.elements.password_confirmation.value) { showAccountError(form, new ApiError("两次输入的新密码不一致", { field: "password_confirmation" })); return; } try { await runButtonAction(submit, "重置中…", async () => { const result = await api(`/api/v1/admin/users/${form.elements.user_id.value}/password`, { method: "PATCH", body: JSON.stringify({ password: form.elements.password.value, version: Number(form.elements.version.value) }) }); applyUserMutation(result); form.closest("dialog").close(); showToast("密码已重置，原有登录状态已撤销"); void refreshUsersAfterMutation(); }); } catch (failure) { showAccountError(form, failure); } }
async function submitArchive(event) { event.preventDefault(); const form = event.currentTarget, submit = event.submitter; if (submit?.value === "cancel") return; clearAccountErrors(form); try { await runButtonAction(submit, "归档中…", async () => { const result = await api(`/api/v1/admin/users/${form.elements.user_id.value}/archive`, { method: "POST", body: JSON.stringify({ reason: form.elements.reason.value.trim(), version: Number(form.elements.version.value) }) }); applyUserMutation(result); form.closest("dialog").close(); showToast("账号已归档，历史数据仍保留"); void refreshUsersAfterMutation(); }); } catch (failure) { showAccountError(form, failure); } }
async function restoreUser(button) { const user = findUser(button.dataset.restoreUser); if (!user || !await confirmAction("恢复账号", "恢复后账号将重新启用，但用户仍需重新登录。", "确认恢复")) return; try { await runButtonAction(button, "恢复中…", async () => { const result = await api(`/api/v1/admin/users/${user.id}/restore`, { method: "POST", body: JSON.stringify({ version: user.version }) }); applyUserMutation(result); showToast("账号已恢复"); void refreshUsersAfterMutation(); }); } catch (failure) { showToast(failure.message, "error"); } }

async function closeShare(button) {
  if (!await confirmAction("关闭分享码", "确定关闭这个分享码吗？关闭后将无法再次查询。", "确认关闭")) return;
  try { await runButtonAction(button, "关闭中…", async () => { await api(`/api/v1/admin/shares/${button.dataset.closeShare}/status`, { method: "PATCH", body: JSON.stringify({ active: false }) }); showToast("分享码已关闭"); await loadShares(); }); }
  catch (failure) { showToast(failure.message); }
}

async function reopenShare(button) {
  try { await runButtonAction(button, "启用中…", async () => { await api(`/api/v1/admin/shares/${button.dataset.openShare}/status`, { method: "PATCH", body: JSON.stringify({ active: true }) }); showToast("分享码已重新启用"); await loadShares(); }); }
  catch (failure) { showToast(failure.message, "error"); }
}

async function deleteQuote(button) {
  if (!await confirmAction("删除报价单", "确定永久删除这份报价单吗？", "确认删除")) return;
  try { await runButtonAction(button, "删除中…", async () => { await api(`/api/v1/quotes/${button.dataset.deleteQuote}`, { method: "DELETE" }); showToast("报价单已删除"); await loadData(); }); } catch (failure) { showToast(failure.message); }
}

async function archiveQuote(button) {
  const quote = state.quotes.find((item) => item.id === button.dataset.archiveQuote);
  if (!quote || !await confirmAction("归档报价单", "归档后不可编辑或再次发送，历史版本与发送记录会完整保留。", "确认归档")) return;
  try {
    await runButtonAction(button, "归档中…", async () => {
      await api(`/api/v1/staff/quotes/${encodeURIComponent(quote.id)}/archive`, { method: "POST", body: JSON.stringify({ version: Number(quote.version || 1) }) });
      showToast("报价单已归档，可随时恢复");
      await loadData();
    });
  } catch (failure) { showToast(failure.message, "error"); }
}

async function restoreQuote(button) {
  const quote = state.quotes.find((item) => item.id === button.dataset.restoreQuote);
  if (!quote || !await confirmAction("恢复报价单", "恢复后可继续编辑。已有发送记录会继续保留。", "确认恢复")) return;
  try {
    await runButtonAction(button, "恢复中…", async () => {
      await api(`/api/v1/staff/quotes/${encodeURIComponent(quote.id)}/restore`, { method: "POST", body: JSON.stringify({ version: Number(quote.version || 1) }) });
      showToast("报价单已恢复");
      await loadData();
    });
  } catch (failure) { showToast(failure.message, "error"); }
}

async function viewQuoteHistory(quoteId) {
  try {
    const history = await api(`/api/v1/staff/quotes/${encodeURIComponent(quoteId)}/history`);
    const revisionRows = (history.revisions || []).map((item) => `<li><strong>版本 ${escapeHtml(item.revision_number)}</strong><small>${escapeHtml(formatDateTime(item.created_at))} · ${escapeHtml(item.created_by_name || "—")}</small></li>`).join("") || '<li class="empty">暂无已发送版本</li>';
    const deliveryRows = (history.deliveries || []).map((item) => {
      const state = item.status === "withdrawn" ? "已撤回" : item.notification_state === "read" ? "客户已查看" : "已发送未查看";
      const revision = item.revision_number ? `版本 ${item.revision_number}` : "旧版报价";
      return `<li><strong>${escapeHtml(item.recipient_name || "—")}</strong><small>${escapeHtml([revision, state, formatDateTime(item.delivered_at)].join(" · "))}</small></li>`;
    }).join("") || '<li class="empty">尚未发送给客户</li>';
    const dialog = document.createElement("dialog");
    dialog.className = "product-dialog quote-history-dialog";
    dialog.innerHTML = `<form method="dialog" class="dialog-card quote-history-card"><header><div><span class="eyebrow">QUOTATION HISTORY</span><h2>${escapeHtml(history.quote?.title || "报价历史")}</h2><p>${escapeHtml(history.quote?.quote_number || quoteId.slice(0, 8))}</p></div><button class="icon-button" value="close" aria-label="关闭">×</button></header><div class="quote-history-body"><section><h3>版本记录</h3><ul>${revisionRows}</ul></section><section><h3>发送记录</h3><ul>${deliveryRows}</ul></section></div><footer><button class="button button-secondary" value="close">关闭</button></footer></form>`;
    document.body.appendChild(dialog);
    dialog.addEventListener("close", () => dialog.remove(), { once: true });
    dialog.showModal();
  } catch (failure) { showToast(failure.message, "error"); }
}

async function exportQuote(quote) {
  if (!quote?.id) { showToast("报价已保存，但未取得报价编号，请在报价管理中重试导出"); return false; }
  if (pdfExportPending) return false;
  pdfExportPending = true;
  try {
    const language = await choosePdfLanguage();
    if (!language) return false;
    const response = await fetch(`${API_BASE}/api/v1/quotes/${encodeURIComponent(quote.id)}/pdf?lang=${language}`, { headers: { Authorization: `Bearer ${sessionStorage.getItem(TOKEN_KEY)}` } });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `PDF生成失败（${response.status}）`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = response.headers.get("Content-Disposition")?.match(/filename="([^"]+)"/)?.[1] || "BOTEN.pdf";
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return true;
  } catch (error) {
    showToast(error.message);
    return false;
  }
  finally { pdfExportPending = false; }
}

// Track the active section in either the desktop list or the compact dialog body.
function bindQuoteScrollContext(dialog) {
  const list = $(".quote-edit-list", dialog);
  const body = $(".quote-editor-body", dialog);
  const head = $(".quote-edit-head", dialog);
  const context = $(".quote-scroll-context", dialog);
  let frame = 0;
  let closed = false;
  const update = () => {
    frame = 0;
    if (closed || !dialog.open) return;
    list.style.setProperty("--quote-head-height", `${head.getBoundingClientRect().height}px`);
    const markers = $$('[data-quote-context]', list);
    context.hidden = !markers.length;
    if (!markers.length) return;
    const edge = context.getBoundingClientRect().bottom + 1;
    let active = markers[0];
    for (const marker of markers) {
      if (marker.getBoundingClientRect().top > edge) break;
      active = marker;
    }
    const label = active.dataset.quoteContext;
    if (context.firstElementChild.textContent !== label) {
      context.firstElementChild.textContent = label;
      context.title = label;
    }
  };
  const refresh = () => { if (!closed && !frame) frame = requestAnimationFrame(update); };
  list.addEventListener("scroll", refresh, { passive: true });
  body.addEventListener("scroll", refresh, { passive: true });
  const observer = new ResizeObserver(refresh);
  [list, body, head].forEach(element => observer.observe(element));
  dialog.addEventListener("close", () => {
    closed = true; cancelAnimationFrame(frame); observer.disconnect();
    list.removeEventListener("scroll", refresh); body.removeEventListener("scroll", refresh);
  }, { once: true });
  return refresh;
}

function openQuoteEditor({ quoteId = null, quoteVersion = null, configId = null, title, items, currency = "CNY", sourceShareId = null, sourceInquiryId = null, sourceType = "direct", sourceDocumentVersion = null, sourceDocumentId = null, sourceCode = "", customerName = "", customerEmail = "", customerPhone = "", customerAddress = "", language = "zh", recipientUserId = "", recipientLabel = "" }) {
  const opener = document.activeElement;
  let currentDeviceKey = null;
  let deviceSequence = 0;
  const normalizedItems = canonicalCommerceItems(items || []).map((item, index) => {
    const kind = item.kind || (commerceItemType(item) === "tool" ? "tool" : commerceItemType(item) === "accessory" ? "accessory" : "option");
    const lineId = item.line_id || `line-${crypto.randomUUID?.() || `${Date.now()}-${index}`}`;
    if (kind === "product") {
      deviceSequence = Number(item.device_sequence || deviceSequence + 1);
      currentDeviceKey = item.device_key || `device-${deviceSequence}-${lineId.slice(-8)}`;
    }
    return {
      ...item,
      kind,
      line_id: lineId,
      device_key: kind === "product" ? currentDeviceKey : item.device_key,
      parent_device_key: ["option", "surcharge"].includes(kind) ? (item.parent_device_key || currentDeviceKey) : null,
      device_sequence: ["product", "option", "surcharge"].includes(kind) ? Number(item.device_sequence || deviceSequence) : 0,
      availability: item.availability || "active",
      quantity: toPositiveInteger(item.quantity),
      price: Math.max(0, toFiniteNumber(item.quoted_price ?? item.price)),
      reference_price: Math.max(0, toFiniteNumber(item.reference_price ?? (currency === "USD" ? item.price_usd : item.price_cny) ?? item.price)),
      price_overridden: Boolean(item.price_overridden)
    };
  });
  const dialog = document.createElement("dialog");
  dialog.className = "product-dialog quote-editor-dialog";
  dialog.dataset.dynamic = "true";
  dialog.dataset.warnUnsaved = "true";
  dialog.innerHTML = `<form method="dialog" class="dialog-card quote-editor-card">
    <input type="hidden" name="quote_items_state" />
    <header><div><span class="eyebrow">QUOTATION</span><h2>${quoteId ? "修改报价" : "创建报价"}</h2></div><button class="icon-button" value="cancel" aria-label="关闭">×</button></header>
    <div class="quote-editor-body">
    <div class="quote-editor-meta">
      <div class="quote-primary-row">
        <label class="quote-title-field"><span>配置名称</span><input name="title" autocomplete="off" placeholder="例如：客户 A · CR1016 配置报价" value="${escapeHtml(title || "")}" required /></label>
        <div class="quote-currency-row"><label class="quote-currency-field"><span>报价货币</span><select name="currency" aria-label="报价货币"><option value="CNY" ${currency === "CNY" ? "selected" : ""}>CNY · 人民币</option><option value="USD" ${currency === "USD" ? "selected" : ""}>USD · 美元</option></select></label><button class="button button-secondary quote-auto-price" type="button">自动填价</button></div>
      </div>
      <div class="quote-customer-summary">
        <input name="customer_name" type="hidden" value="${escapeHtml(customerName)}" />
        <input name="customer_email" type="hidden" value="${escapeHtml(customerEmail)}" />
        <input name="customer_phone" type="hidden" value="${escapeHtml(customerPhone)}" />
        <input name="customer_address" type="hidden" value="${escapeHtml(customerAddress)}" />
        <select name="recipient_user_id" hidden><option value="${escapeHtml(recipientUserId)}" selected>${escapeHtml(recipientLabel || customerName || customerEmail || "未选择客户")}</option></select>
        <span class="quote-customer-summary-label">客户信息</span>
        <div class="quote-customer-summary-value"><strong>${escapeHtml(customerName || recipientLabel || "尚未选择客户")}</strong>${customerEmail ? `<small>${escapeHtml(customerEmail)}</small>` : ""}${customerPhone ? `<small>${escapeHtml(customerPhone)}</small>` : ""}</div>
        <button class="button button-secondary quote-customer-search" type="button">客户信息</button>
      </div>
    </div>
    <p class="quote-editor-error" role="alert" hidden></p>
    <div class="quote-add-toolbar" aria-label="添加报价项目">
      <label><span>添加类型</span><select name="quote_add_kind"><option value="option">设备可选配置</option><option value="tool">维修工具</option><option value="accessory">设备附件</option></select></label>
      <label class="quote-add-device-field"><span>所属设备</span><select name="quote_add_device"></select></label>
      <label class="quote-add-source-field"><span>选择项目</span><select name="quote_add_source"><option value="">正在读取目录…</option></select></label>
      <button class="button button-secondary quote-add-item" type="button">添加</button>
    </div>
    <div class="quote-edit-list">
      <div class="quote-edit-head"><span>产品 / 配置</span><span>数量</span><span>单价</span><span>操作</span></div>
      <div class="quote-scroll-context" aria-label="当前设备与分类" hidden><span></span></div>
      <div id="quote-edit-rows"></div>
    </div>
    <div class="quote-total-row"><span>合计</span><strong class="quote-total">0</strong></div>
    </div>
    <footer><button class="button button-quiet" value="cancel">取消</button><button class="button button-secondary" value="save">保存报价</button><button class="button button-secondary" value="saveAndExport">保存并导出 PDF</button><button class="button button-primary" value="saveAndDeliver">保存并发送给客户</button></footer>
  </form>`;
  document.body.appendChild(dialog);
  const quoteForm = $("form", dialog);
  quoteForm.dataset.initialSnapshot = JSON.stringify(Object.fromEntries(new FormData(quoteForm)));
  dialog.addEventListener("cancel", (event) => {
    const dirty = quoteForm.dataset.initialSnapshot !== JSON.stringify(Object.fromEntries(new FormData(quoteForm)));
    if (!dirty) return;
    event.preventDefault();
    confirmAction("放弃未保存修改", "当前报价尚未保存，确定关闭吗？", "放弃修改").then((confirmed) => {
      if (confirmed) { dialog.close(); dialog.remove(); }
    });
  });
  dialog.addEventListener("close", () => { if (opener?.isConnected) opener.focus(); }, { once: true });
  const refreshQuoteContext = bindQuoteScrollContext(dialog);
  const totalElement = $(".quote-total", dialog);
  const errorElement = $(".quote-editor-error", dialog);
  const setQuoteError = (message = "") => { errorElement.textContent = message; errorElement.hidden = !message; };
  const updateDeliveryAvailability = () => {
    const canDeliver = Boolean($("[name=recipient_user_id]", dialog).value);
    const button = $('button[value="saveAndDeliver"]', dialog);
    button.disabled = !canDeliver;
    button.title = canDeliver ? "" : "手动填写的客户未绑定系统账号，仅可保存或导出 PDF";
  };
  let referenceCatalog = null;
  let referenceReconciled = false;
  const itemStateInput = $("[name=quote_items_state]", dialog);
  const syncQuoteItemsFromInputs = () => {
    normalizedItems.forEach((item, index) => {
      const quantityInput = $(`[data-q="qty"][data-i="${index}"]`, dialog);
      const priceInput = $(`[data-q="price"][data-i="${index}"]`, dialog);
      if (quantityInput) item.quantity = toPositiveInteger(quantityInput.value);
      if (priceInput) {
        item.price = Math.max(0, toFiniteNumber(priceInput.value));
        item.quoted_price = item.price;
        item.price_overridden = Math.abs(item.price - toFiniteNumber(item.reference_price)) >= 0.005;
      }
    });
    itemStateInput.value = JSON.stringify(normalizedItems);
    return normalizedItems.map((item) => ({ ...item }));
  };
  const isLockedQuoteLine = (item) => item.kind === "product" || item.locked === true || item.configuration_role === "base_device" || item.configuration_role === "base_power" || String(item.source_id || "").startsWith("base-");
  const quoteDeviceSpecifications = (item) => (item.device_specifications || [])
    .filter((entry) => entry && (entry.value || entry.label))
    .map((entry) => `${entry.label || entry.key || "配置"}：${entry.value || "—"}`)
    .join(" · ");
  const quoteDeviceKey = (item) => item.parent_device_key || item.device_key || `sequence-${item.device_sequence || 0}`;
  const quoteCategory = (item) => {
    if (isLockedQuoteLine(item) || item.kind === "surcharge") return { key: "base", label: "基础配置" };
    const label = String(item.category_name || item.category_name_en || "").trim();
    return { key: item.category_id ? `category-${item.category_id}` : label ? `name-${label}` : "uncategorized", label: label || "未分类配置" };
  };
  const renderQuoteRows = () => {
    const rows = $("#quote-edit-rows", dialog);
    const list = $(".quote-edit-list", dialog);
    const body = $(".quote-editor-body", dialog);
    const scrollTop = list.scrollTop, bodyScrollTop = body.scrollTop;
    const devices = new Map(normalizedItems.filter(item => item.kind === "product").map(item => [quoteDeviceKey(item), item]));
    rows.innerHTML = normalizedItems.length ? normalizedItems.map((item, index) => {
      const type = commerceItemType(item);
      const previous = normalizedItems[index - 1];
      const startsGroup = !previous || commerceItemType(previous) !== type || (type === "device_config" && quoteDeviceKey(previous) !== quoteDeviceKey(item));
      const device = devices.get(quoteDeviceKey(item)) || item;
      const model = String((device.kind === "product" ? device.code : "") || device.device_label || device.device || "").replace(/^(?:设备|Device)\s*\d+\s*[·,，:：-]?\s*/i, "");
      const deviceLabel = `设备 ${device.device_sequence || item.device_sequence || 1}${model ? ` · ${model}` : ""}`;
      const groupLabel = type === "tool" ? "维修工具" : type === "accessory" ? "设备附件" : deviceLabel;
      const category = quoteCategory(item);
      const startsCategory = type === "device_config" && (startsGroup || quoteCategory(previous).key !== category.key);
      const context = type === "device_config" ? `${groupLabel} · ${category.label}` : groupLabel;
      const groupHeading = startsGroup ? `<div class="quote-commerce-group-title" role="heading" aria-level="3" data-quote-context="${escapeHtml(context)}">${escapeHtml(groupLabel)}</div>` : "";
      const categoryHeading = startsCategory ? `<div class="quote-category-title" role="heading" aria-level="4" data-quote-context="${escapeHtml(context)}">${escapeHtml(category.label)}</div>` : "";
      const availability = item.availability && item.availability !== "active" ? `<span class="quote-availability-warning">${item.availability === "inactive" ? "已停用" : item.availability === "missing" ? "已缺失" : "仅历史快照"}</span>` : "";
      const detail = item.kind === "product" ? quoteDeviceSpecifications(item) : "";
      const itemCode = normalizeCatalogCode(item.code);
      const itemName = catalogDisplayName(item.name, itemCode);
      const lineName = item.kind === "product" ? "设备基础价格" : itemName || "未命名项目";
      const deleteButton = isLockedQuoteLine(item) ? '<span class="quote-base-lock">基础配置</span>' : `<button class="table-action danger quote-line-delete" type="button" data-delete-quote-line="${index}" aria-label="删除 ${escapeHtml(item.name || "报价项目")}">删除</button>`;
      return `${groupHeading}${categoryHeading}<div class="quote-edit-row"><div class="quote-item-name">${availability ? `<small>${availability}</small>` : ""}${itemCode && item.kind !== "product" ? `<small class="catalog-code">${escapeHtml(itemCode)}</small>` : ""}<strong>${escapeHtml(lineName)}</strong>${detail ? `<span>${escapeHtml(detail)}</span>` : ""}</div><label class="quote-numeric-field"><span>数量</span><input class="quote-qty-input" data-q="qty" data-i="${index}" aria-label="数量" type="number" min="1" step="1" value="${item.quantity}"></label><label class="quote-numeric-field"><span>单价</span><input class="quote-price-input" data-q="price" data-i="${index}" aria-label="单价" type="number" min="0" step="0.01" value="${item.price}"></label><span class="quote-line-action">${deleteButton}</span></div>`;
    }).join("") : '<div class="quote-edit-empty">暂无可报价项目，请添加项目后保存。</div>';
    itemStateInput.value = JSON.stringify(normalizedItems);
    list.scrollTop = scrollTop; body.scrollTop = bodyScrollTop;
    refreshQuoteContext();
  };
  const productLines = () => normalizedItems.filter((item) => item.kind === "product");
  const updateAddSelectors = () => {
    const kind = $("[name=quote_add_kind]", dialog).value;
    const addToolbar = $(".quote-add-toolbar", dialog);
    const deviceField = $(".quote-add-device-field", dialog);
    const deviceSelect = $("[name=quote_add_device]", dialog);
    const sourceSelect = $("[name=quote_add_source]", dialog);
    const selectedSourceId = sourceSelect.value;
    const products = productLines();
    deviceField.hidden = kind !== "option";
    addToolbar.classList.toggle("has-device", kind === "option");
    deviceSelect.innerHTML = products.map((item) => `<option value="${escapeHtml(item.device_key)}">${escapeHtml(item.device_label || item.code || item.name || `设备 ${item.device_sequence}`)}</option>`).join("");
    if (!referenceCatalog) {
      sourceSelect.innerHTML = '<option value="">正在读取目录…</option>';
      return;
    }
    let candidates = referenceCatalog.options || [];
    if (kind === "option") {
      const target = products.find((item) => item.device_key === deviceSelect.value) || products[0];
      candidates = candidates.filter((item) => item.catalog_type === "optional" && !["motor", "voltage", "channel"].includes(item.category_id) && item.product_ids?.includes(target?.source_id));
    } else {
      candidates = candidates.filter((item) => item.catalog_type === (kind === "tool" ? "tools" : "accessories"));
    }
    sourceSelect.innerHTML = candidates.length
      ? `<option value="">请选择</option>${candidates.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml([item.code, language === "en" ? item.name_en || item.name : item.name].filter(Boolean).join(" · "))}</option>`).join("")}`
      : '<option value="">暂无可添加项目</option>';
    if (selectedSourceId && candidates.some((item) => String(item.id) === selectedSourceId)) sourceSelect.value = selectedSourceId;
  };
  const ensureReferenceCatalog = async () => {
    if (!referenceCatalog) referenceCatalog = await api("/api/v1/staff/reference-prices");
    if (!referenceReconciled) {
      syncQuoteItemsFromInputs();
      const productAvailability = referenceCatalog.product_availability || {};
      const optionAvailability = referenceCatalog.option_availability || {};
      normalizedItems.forEach((item) => {
        const sourceId = String(item.source_id || "");
        if (!sourceId) {
          item.availability = "snapshot_only";
          return;
        }
        const states = item.kind === "product" ? productAvailability : optionAvailability;
        item.availability = states[sourceId] || "missing";
      });
      referenceReconciled = true;
      renderQuoteRows();
    }
    updateAddSelectors();
    return referenceCatalog;
  };
  const loadRecipients = async (query = "") => {
    const result = await api(`/api/v1/staff/customers?query=${encodeURIComponent(query)}`);
    return result.items || [];
  };
  const openRecipientPicker = async () => {
    const picker = document.createElement("dialog");
    picker.className = "share-dialog quote-customer-picker";
    picker.setAttribute("aria-labelledby", "quote-customer-dialog-title");
    const fields = ["name", "phone", "email", "address"];
    let selectedId = $("[name=recipient_user_id]", dialog).value;
    let selectedLabel = $("[name=recipient_user_id]", dialog).selectedOptions[0]?.textContent || "";
    const initial = Object.fromEntries(fields.map((key) => [key, $(`[name=customer_${key}]`, dialog).value]));
    picker.innerHTML = `<form method="dialog" class="share-dialog-card quote-customer-picker-card"><header><div><span class="eyebrow">CUSTOMER</span><h2 id="quote-customer-dialog-title">客户信息</h2><p>选择客户自动填充；修改仅用于本次报价，不更改客户账户资料。</p></div><button class="icon-button" value="cancel" formnovalidate aria-label="关闭">×</button></header><div class="quote-customer-picker-body"><label class="quote-customer-picker-search"><span>搜索客户</span><input name="customer_query" type="search" autocomplete="off" placeholder="姓名、邮箱或手机号…" /></label><div class="quote-customer-picker-results" aria-live="polite"></div><div class="quote-customer-binding"><span class="quote-customer-binding-label"></span><button class="button button-secondary" type="button" data-manual-customer>手动填写</button></div><div class="quote-customer-manual-fields">${fields.map((key) => `<label><span>${({ name: "姓名", phone: "电话", email: "邮箱", address: "地址" })[key]}</span>${key === "address" ? `<textarea name="manual_address" maxlength="500" rows="2" autocomplete="street-address">${escapeHtml(initial[key])}</textarea>` : `<input name="manual_${key}" type="${key === "email" ? "email" : key === "phone" ? "tel" : "text"}" maxlength="${key === "name" ? 100 : key === "email" ? 254 : 100}" autocomplete="${key === "phone" ? "tel" : key}" ${key === "email" ? 'spellcheck="false"' : ""} value="${escapeHtml(initial[key])}" ${key === "name" ? "required" : ""} />`}</label>`).join("")}</div><p class="quote-customer-feedback" role="status" aria-live="polite"></p></div><footer><button class="button button-secondary" value="cancel" formnovalidate>取消</button><button class="button button-primary" value="apply">应用</button></footer></form>`;
    document.body.appendChild(picker);
    const input = $('[name="customer_query"]', picker);
    // Match the quote API limits; selecting an account does not relax them.
    for (const [key, limit] of Object.entries({ name: 200, email: 200, phone: 80, address: 500 })) {
      $(`[name=manual_${key}]`, picker).maxLength = limit;
    }
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") event.preventDefault();
    });
    const results = $(".quote-customer-picker-results", picker);
    const readDraft = () => Object.fromEntries(fields.map((key) => [key, $(`[name=manual_${key}]`, picker).value]));
    let baseline = JSON.stringify(readDraft());
    const updateBinding = () => { $(".quote-customer-binding-label", picker).textContent = selectedId ? `接收账号：${selectedLabel}` : "未绑定账号，仅可保存和导出 PDF"; };
    updateBinding();
    let records = [];
    let searchVersion = 0;
    let searchTimer;
    const renderResults = () => {
      results.innerHTML = records.length ? records.map((customer) => `<button type="button" class="quote-customer-result" data-customer-id="${escapeHtml(customer.id)}"><span><strong>${escapeHtml(customer.display_name || customer.email || customer.phone || "未命名客户")}</strong>${customer.email ? `<small>${escapeHtml(customer.email)}</small>` : ""}${customer.phone ? `<small>${escapeHtml(customer.phone)}</small>` : ""}</span><b aria-hidden="true">选择</b></button>`).join("") : '<div class="empty">没有找到匹配客户</div>';
    };
    const search = async () => {
      const version = ++searchVersion;
      results.innerHTML = '<div class="empty">正在搜索…</div>';
      try { const found = await loadRecipients(input.value.trim()); if (version !== searchVersion || !picker.open) return; records = found; renderResults(); }
      catch (error) { if (version === searchVersion && picker.open) results.innerHTML = `<div class="empty">${escapeHtml(error.message || "客户读取失败，请重新搜索")}</div>`; }
    };
    input.addEventListener("input", () => { ++searchVersion; records = []; results.innerHTML = '<div class="empty">正在搜索…</div>'; clearTimeout(searchTimer); searchTimer = setTimeout(search, 250); });
    results.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-customer-id]");
      if (!button) return;
      const customer = records.find((item) => String(item.id) === button.dataset.customerId);
      if (!customer) return;
      if (JSON.stringify(readDraft()) !== baseline && !await confirmAction("更换客户", "将替换当前填写的姓名、电话、邮箱和地址。", "替换")) return;
      if (!picker.open) return;
      selectedId = customer.id;
      selectedLabel = customer.display_name || customer.name || customer.email || customer.phone || "未命名客户";
      const values = { name: selectedLabel, phone: customer.phone || "", email: customer.email || "", address: customer.address || "" };
      fields.forEach((key) => { $(`[name=manual_${key}]`, picker).value = values[key]; });
      baseline = JSON.stringify(readDraft());
      updateBinding();
    });
    $('[data-manual-customer]', picker).addEventListener("click", () => { selectedId = ""; selectedLabel = ""; updateBinding(); });
    $("form", picker).addEventListener("submit", (event) => {
      if (event.submitter?.value !== "apply") return;
      event.preventDefault();
      const values = Object.fromEntries(Object.entries(readDraft()).map(([key, value]) => [key, value.trim()]));
      if (!values.name) { $(".quote-customer-feedback", picker).textContent = "请填写客户姓名。"; $('[name=manual_name]', picker).focus(); return; }
      fields.forEach((key) => { $(`[name=customer_${key}]`, dialog).value = values[key]; });
      $("[name=recipient_user_id]", dialog).innerHTML = `<option value="${escapeHtml(selectedId)}" selected>${escapeHtml(selectedLabel || "手动客户")}</option>`;
      $(".quote-customer-summary", dialog).classList.toggle("is-manual", !selectedId);
      $(".quote-customer-summary-value", dialog).innerHTML = `<strong>${escapeHtml(values.name)}</strong><small>${escapeHtml([values.phone, values.email].filter(Boolean).join(" · ") || "未填写联系方式")}</small>`;
      updateDeliveryAvailability(); setQuoteError(); picker.close("apply");
    });
    picker.addEventListener("close", () => { clearTimeout(searchTimer); ++searchVersion; picker.remove(); $(".quote-customer-search", dialog).focus(); }, { once: true });
    picker.showModal();
    if (window.matchMedia("(min-width: 701px)").matches) requestAnimationFrame(() => input.focus());
    await search();
  };
  const collectQuoteItems = () => syncQuoteItemsFromInputs();
  const updateTotal = () => {
    const total = collectQuoteItems().reduce((sum, item) => sum + item.price * item.quantity, 0);
    const selectedCurrency = $("[name=currency]", dialog).value;
    totalElement.textContent = `${selectedCurrency} ${formatNumber(total, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    return total;
  };
  dialog.addEventListener("input", () => { setQuoteError(); updateTotal(); });
  dialog.addEventListener("change", updateTotal);
  $("[name=quote_add_kind]", dialog).addEventListener("change", updateAddSelectors);
  $("[name=quote_add_device]", dialog).addEventListener("change", updateAddSelectors);
  $(".quote-add-item", dialog).addEventListener("click", async (event) => {
    const button = event.currentTarget;
    try {
      await runButtonAction(button, "添加中…", async () => {
        syncQuoteItemsFromInputs();
        const kind = $("[name=quote_add_kind]", dialog).value;
        const selectedSourceId = $("[name=quote_add_source]", dialog).value;
        const catalog = await ensureReferenceCatalog();
        const sourceId = selectedSourceId || $("[name=quote_add_source]", dialog).value;
        const record = (catalog.options || []).find((item) => item.id === sourceId);
        if (!record) { setQuoteError("请选择需要添加的有效目录项目。"); return; }
        const expectedCatalogType = kind === "tool" ? "tools" : kind === "accessory" ? "accessories" : "optional";
        if (record.catalog_type !== expectedCatalogType) { setQuoteError("所选项目与添加类型不一致，请重新选择。"); return; }
        const selectedCurrency = $("[name=currency]", dialog).value;
        const referencePrice = Math.max(0, toFiniteNumber(selectedCurrency === "USD" ? record.price_usd : record.price));
        const existing = normalizedItems.find((item) => item.kind === kind && item.source_id === record.id && (kind !== "option" || item.parent_device_key === $("[name=quote_add_device]", dialog).value));
        if (existing && ["tool", "accessory"].includes(kind)) {
          existing.quantity += 1;
          renderQuoteRows();
          updateTotal();
          showToast("该项目已存在，数量已增加 1");
          return;
        }
        if (existing) { setQuoteError("该设备已经包含这个配置。"); return; }
        const lineId = `line-${crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`}`;
        const name = language === "en" ? record.name_en || record.name : record.name;
        const newItem = {
          kind, line_id: lineId, source_id: record.id, code: record.code || "", name: name || record.code || "未命名项目",
          quantity: 1, price: referencePrice, quoted_price: referencePrice, reference_price: referencePrice,
          price_cny: Math.max(0, toFiniteNumber(record.price)), price_usd: Math.max(0, toFiniteNumber(record.price_usd)),
          price_overridden: false, availability: "active", category_id: record.category_id,
          category_name: language === "en" ? record.category_name_en || "" : record.category_name || "",
          category_name_en: record.category_name_en || "",
          category_sort_order: record.category_sort_order, sort_order: record.sort_order,
        };
        if (kind === "option") {
          const parentKey = $("[name=quote_add_device]", dialog).value;
          const parent = productLines().find((item) => item.device_key === parentKey);
          if (!parent) { setQuoteError("当前报价没有可关联的设备。"); return; }
          newItem.parent_device_key = parentKey;
          newItem.device_sequence = parent.device_sequence;
          newItem.device_label = parent.device_label || parent.code || parent.name;
          const lastInGroup = normalizedItems.reduce((position, item, index) => item.device_sequence === parent.device_sequence && ["product", "option", "surcharge"].includes(item.kind) ? index : position, -1);
          normalizedItems.splice(lastInGroup + 1, 0, newItem);
        } else {
          newItem.device_label = kind === "tool" ? "维修工具" : "设备附件";
          normalizedItems.push(newItem);
          const ordered = canonicalCommerceItems(normalizedItems);
          normalizedItems.splice(0, normalizedItems.length, ...ordered);
        }
        renderQuoteRows();
        updateAddSelectors();
        updateTotal();
        showToast("项目已添加，保存报价后生效");
      });
    } catch (error) { setQuoteError(error.message || "添加项目失败"); }
  });
  $("#quote-edit-rows", dialog).addEventListener("click", async (event) => {
    const button = event.target.closest("[data-delete-quote-line]");
    if (!button) return;
    syncQuoteItemsFromInputs();
    const index = Number(button.dataset.deleteQuoteLine);
    const item = normalizedItems[index];
    if (!item || isLockedQuoteLine(item)) return;
    if (!await confirmAction("删除报价项目", `确定从当前报价中删除“${item.name || item.code || "该项目"}”吗？`, "确认删除")) return;
    normalizedItems.splice(index, 1);
    renderQuoteRows();
    updateAddSelectors();
    updateTotal();
  });
  $("#quote-edit-rows", dialog).addEventListener("wheel", (event) => {
    if (!event.target.matches(".quote-price-input")) return;
    event.preventDefault();
    const list = $(".quote-edit-list", dialog);
    const scrollHost = getComputedStyle(list).overflowY === "visible" ? $(".quote-editor-body", dialog) : list;
    scrollHost.scrollTop += event.deltaY;
    scrollHost.scrollLeft += event.deltaX;
  }, { passive: false });
  $(".quote-customer-search", dialog).addEventListener("click", () => openRecipientPicker().catch((error) => setQuoteError(error.message)));
  $(".quote-auto-price", dialog).addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "读取中…";
    try {
      const prices = await ensureReferenceCatalog();
      const selectedCurrency = $("[name=currency]", dialog).value;
      const normalizeCode = (value) => String(value || "").replace(/[^a-z0-9]/gi, "").toUpperCase();
      const productMap = new Map((prices.products || []).flatMap((product) => [[normalizeCode(product.id), product], [normalizeCode(product.name), product]]));
      const optionMap = new Map((prices.options || []).flatMap((option) => [[normalizeCode(option.id), option], [normalizeCode(option.code), option]]));
      let matched = 0;
      normalizedItems.forEach((item, index) => {
        if (item.price_overridden) return;
        const hasSnapshotPrice = Object.prototype.hasOwnProperty.call(item, "price_cny") || Object.prototype.hasOwnProperty.call(item, "price_usd");
        const snapshotPrice = selectedCurrency === "USD" ? toFiniteNumber(item.price_usd) : toFiniteNumber(item.price_cny);
        if (hasSnapshotPrice) {
          item.reference_price = Math.max(0, snapshotPrice);
          item.price_overridden = false;
          $(`[data-q="price"][data-i="${index}"]`, dialog).value = Math.max(0, snapshotPrice);
          if (snapshotPrice > 0) matched += 1;
          return;
        }
        const keys = [item.source_id, item.code, item.name].map(normalizeCode).filter(Boolean);
        let record = null;
        if (item.kind === "product") record = keys.map((key) => productMap.get(key)).find(Boolean);
        else if (item.kind === "option") record = keys.map((key) => optionMap.get(key)).find(Boolean);
        else record = keys.map((key) => optionMap.get(key) || productMap.get(key)).find(Boolean);
        if (!record) return;
        const price = selectedCurrency === "USD" ? toFiniteNumber(record.price_usd) : toFiniteNumber(record.base_price ?? record.price ?? 0);
        if (price <= 0) return;
        item.reference_price = price;
        item.price_overridden = false;
        $(`[data-q="price"][data-i="${index}"]`, dialog).value = price;
        matched += 1;
      });
      updateTotal();
      showToast(`已填 ${matched} 项，${normalizedItems.length - matched} 项未设置价格`);
    } catch (error) { showToast(error.message); }
    finally { button.disabled = false; button.textContent = originalText; }
  });
  $("form", dialog).addEventListener("submit", async (event) => {
    const action = event.submitter?.value;
    if (action === "cancel") return;
    event.preventDefault();
    const finalItems = collectQuoteItems();
    const total = updateTotal();
    const quoteTitle = $("[name=title]", dialog).value.trim();
    if (!quoteTitle) { setQuoteError("请填写配置名称后再保存报价。"); $("[name=title]", dialog).focus(); return; }
    if (!finalItems.length) { setQuoteError("没有可保存的报价项目，请返回分享配置重新选择。"); return; }
    if (action === "saveAndDeliver") {
      const recipientSelect = $("[name=recipient_user_id]", dialog);
      if (!recipientSelect.value) { setQuoteError("请选择接收报价的客户账号。"); $(".quote-customer-search", dialog).focus(); return; }
      const recipient = recipientSelect.selectedOptions[0]?.textContent?.trim() || "所选客户";
      const email = $("[name=customer_email]", dialog).value.trim() || "未填写报价页头邮箱";
      const confirmed = await confirmAction("确认发送报价", `接收账号：${recipient}；客户邮箱：${email}；当前版本：${quoteVersion || "新报价"}。保存后将发送最新版本。`, "确认发送");
      if (!confirmed) return;
    }
    try { await runButtonAction(event.submitter, "正在保存…", async () => {
      const savedQuote = await api("/api/v1/quotes", { method: "POST", body: JSON.stringify({ quote_id: quoteId, version: quoteId ? quoteVersion : null, config_id: configId, title: quoteTitle, items: finalItems, total_price: total, currency: $("[name=currency]", dialog).value, source_share_id: sourceShareId, source_inquiry_id: sourceInquiryId, source_type: sourceType, source_document_version: sourceDocumentVersion, source_document_id: sourceDocumentId, source_code: sourceCode, customer_name: $("[name=customer_name]", dialog).value.trim(), customer_email: $("[name=customer_email]", dialog).value.trim(), customer_phone: $("[name=customer_phone]", dialog).value.trim(), customer_address: $("[name=customer_address]", dialog).value.trim(), language }) });
      const exported = action === "saveAndExport" ? await exportQuote(savedQuote) : false;
      if (action === "saveAndExport" && !exported) {
        quoteId = savedQuote.id; quoteVersion = savedQuote.version;
        quoteForm.dataset.initialSnapshot = JSON.stringify(Object.fromEntries(new FormData(quoteForm)));
        throw new Error("报价已保存，但 PDF 下载失败。请检查网络后再次点击导出。");
      }
      if (action === "saveAndDeliver") {
        try {
          const deliveryKey = dialog.dataset.deliveryKey || (dialog.dataset.deliveryKey = (crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`));
          await api(`/api/v1/staff/quotes/${encodeURIComponent(savedQuote.id)}/deliver`, { method: "POST", body: JSON.stringify({ recipient_user_id: $("[name=recipient_user_id]", dialog).value || null, source_share_id: sourceShareId, version: savedQuote.version, idempotency_key: deliveryKey }) });
        } catch (deliveryError) {
          throw new Error(`报价已保存，但发送失败：${deliveryError.message}`);
        }
      }
      dialog.close(); dialog.remove();
      showToast(action === "saveAndExport" ? (exported ? "报价单已保存并开始下载 PDF" : "报价单已保存，但 PDF 下载失败") : action === "saveAndDeliver" ? "报价单已保存并发送给客户" : (quoteId ? "报价单已更新" : "报价单已保存"));
      await loadData();
    }); } catch (error) { setQuoteError(error.message || "保存报价失败，请检查填写内容后重试。"); }
  });
  renderQuoteRows();
  updateAddSelectors();
  updateTotal();
  updateDeliveryAvailability();
  ensureReferenceCatalog().catch((error) => setQuoteError(`目录读取失败：${error.message}。历史项目仍可修改和保存。`));
  quoteForm.dataset.initialSnapshot = JSON.stringify(Object.fromEntries(new FormData(quoteForm)));
  dialog.showModal();
  refreshQuoteContext();
  requestAnimationFrame(() => $("[name=title]", dialog)?.focus());
}

async function editQuote(quote) {
  const customer = quoteCustomerContext(quote);
  openQuoteEditor({ quoteId: quote.id, quoteVersion: quote.version, configId: quote.config_id, title: quote.title, items: quote.items, currency: quote.currency || "CNY", sourceShareId: quote.source_share_id, sourceInquiryId: quote.source_inquiry_id, sourceType: quote.source_type, sourceDocumentVersion: quote.source_document_version, sourceDocumentId: quote.source_document_id, sourceCode: quote.source_code, customerName: customer.customerName, customerEmail: customer.customerEmail, customerPhone: customer.customerPhone, customerAddress: customer.customerAddress || "", language: quote.language || "zh", recipientUserId: customer.recipientUserId, recipientLabel: customer.recipientLabel });
}

function plainDescription(value) {
  return String(value || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function renderShareDetail(share) {
  const rawItems = share.items?.length ? share.items : [{ item_type: "device_config", snapshot: share.snapshot, display_name: share.name }];
  const groupedItems = aggregateCommerceItems(rawItems);
  const shareItems = [...groupedItems.devices, ...groupedItems.tools, ...groupedItems.accessories];
  const deviceItems = groupedItems.devices;
  const devices = deviceItems.map((shareItem, index) => {
    const snapshot = shareItem.snapshot || {};
    const categoryList = snapshot.categories || [];
    const baseCategoryIds = new Set(["motor", "voltage", "channel"]);
    const isConfiguredValue = (value) => {
      const normalized = String(value || "").trim().toLocaleLowerCase();
      return Boolean(normalized) && !new Set(["未配置", "未选择", "无", "none", "not configured", "not selected", "n/a", "—", "-"]).has(normalized);
    };
    const singleValue = (id) => {
      const category = categoryList.find((item) => item.id === id);
      return category?.options?.map((option) => String(option.name || "").trim()).filter(isConfiguredValue).join(" / ") || "";
    };
    const categories = categoryList.filter((category) => !baseCategoryIds.has(category.id)).map((category) => {
      const options = (category.options || []).map((option) => {
        const description = plainDescription(option.description);
        return `<li>${catalogIdentityHtml(option.code, option.name, "未命名配置")}${description ? `<span>${escapeHtml(description)}</span>` : ""}</li>`;
      }).join("");
      return `<section class="share-detail-group"><header><span>${escapeHtml(category.name)}</span><small>${category.options.length} 项</small></header><ul>${options}</ul></section>`;
    }).join("");
    const basics = [
      ["型号", snapshot.product?.name || ""],
      ["名称", snapshot.product?.title_name || ""],
      ["颜色", snapshot.color?.label || snapshot.color?.code || ""],
      ["电机", singleValue("motor")],
      ["电源", singleValue("voltage")],
      ["通道", singleValue("channel")]
    ].filter(([, value]) => isConfiguredValue(value)).map(([label, value]) => `<div><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
    return `<article class="share-device-block"><h4>设备 ${index + 1} · ${escapeHtml(snapshot.product?.name || "未填写")}</h4><section class="share-detail-group share-device-basics"><header><span>设备信息</span><small>型号与基本配置</small></header><div class="share-basic-list">${basics}</div></section><div class="share-detail-groups">${categories || '<div class="empty">该设备未选择其他选配项目</div>'}</div></article>`;
  }).join("");
  const catalogSections = [["tool", "维修工具"], ["accessory", "设备附件"]].map(([type, label]) => {
    const entries = type === "tool" ? groupedItems.tools : groupedItems.accessories;
    if (!entries.length) return "";
    const rows = entries.map((entry) => {
      const snapshot = entry.snapshot || {};
      return `<li>${catalogIdentityHtml(snapshot.code, snapshot.name || entry.display_name, "—")}<span class="share-item-quantity">数量：${Number(entry.quantity || snapshot.quantity || 1)}</span></li>`;
    }).join("");
    return `<article class="share-device-block share-catalog-block"><section class="share-detail-group"><header><span>${label}</span><small>${entries.length} 项</small></header><ul>${rows}</ul></section></article>`;
  }).join("");
  const senderDetails = renderCustomerLines(share.sender_name, share.sender_email, share.sender_phone);
  const quoteCount = Number(share.quote_count || 0);
  const quotePeople = (share.quoted_by || []).map((person) => person.display_name).filter(Boolean).join("、");
  const quoteState = quoteCount
    ? `<strong>已报价 · ${formatNumber(quoteCount)} 份</strong>${quotePeople ? `<small>${escapeHtml(quotePeople)}</small>` : ""}`
    : share.historical_quote_count
      ? '<strong>历史报价已归档</strong>'
      : '<strong>未报价</strong>';
  const summaryParts = [];
  if (deviceItems.length) summaryParts.push(`${deviceItems.length} 台设备`);
    const toolCount = shareItems.filter((item) => item.item_type === "tool").reduce((sum, item) => sum + Number(item.quantity || 1), 0);
    const accessoryCount = shareItems.filter((item) => item.item_type === "accessory").reduce((sum, item) => sum + Number(item.quantity || 1), 0);
    if (toolCount) summaryParts.push(`${toolCount} 件工具`);
    if (accessoryCount) summaryParts.push(`${accessoryCount} 件附件`);
  const shareNote = `<section class="share-note-block"><span>分享备注</span><p>${share.note ? escapeHtml(share.note) : "无备注"}</p></section>`;
  return `<header class="share-result-header"><div><h3>${escapeHtml(summaryParts.join(" · ") || "分享配置")}</h3></div><span class="badge good">有效至 ${formatDate(share.expires_at)}</span></header><div class="share-device-summary"><div><span>发送用户</span>${senderDetails}</div><div><span>报价状态</span>${quoteState}</div></div>${shareNote}${devices}${catalogSections}`;
}

function ensureShareDrawer() {
  if (shareDrawerElement && shareDrawerBackdrop) return;
  shareDrawerBackdrop = document.createElement("div");
  shareDrawerBackdrop.className = "share-drawer-backdrop";
  shareDrawerElement = document.createElement("aside");
  shareDrawerElement.className = "share-drawer";
  shareDrawerElement.setAttribute("role", "dialog");
  shareDrawerElement.setAttribute("aria-modal", "true");
  shareDrawerElement.setAttribute("aria-label", "分享配置详情");
  shareDrawerElement.setAttribute("aria-hidden", "true");
  shareDrawerElement.innerHTML = `<header class="share-drawer-header"><div><span class="eyebrow">SHARE PREVIEW</span><h2 data-share-drawer-title>分享记录</h2></div><button class="icon-button" type="button" data-share-drawer-close aria-label="关闭">×</button></header><div class="share-drawer-body" data-share-drawer-body></div><footer class="share-drawer-footer"><button class="button button-secondary" type="button" data-share-export disabled>导出 PDF</button><button class="button button-primary" type="button" data-share-quote disabled>报价</button></footer>`;
  document.body.append(shareDrawerBackdrop, shareDrawerElement);
  shareDrawerBackdrop.addEventListener("click", closeShareDrawer);
  shareDrawerElement.querySelector("[data-share-drawer-close]").addEventListener("click", closeShareDrawer);
  shareDrawerElement.querySelector("[data-share-export]").addEventListener("click", (event) => exportSharePdf(event.currentTarget.dataset.code));
  shareDrawerElement.querySelector("[data-share-quote]").addEventListener("click", (event) => quoteShare(event.currentTarget.dataset.code));
  document.addEventListener("keydown", (event) => {
    if (!shareDrawerElement?.classList.contains("open") || document.querySelector("dialog[open]")) return;
    if (event.key === "Escape") { event.preventDefault(); closeShareDrawer(); return; }
    if (event.key !== "Tab") return;
    const focusable = $$('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])', shareDrawerElement).filter((item) => !item.hidden);
    if (!focusable.length) return;
    const first = focusable[0]; const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
}

function setShareDrawerContent(code, content) {
  ensureShareDrawer();
  const body = $("[data-share-drawer-body]", shareDrawerElement);
  const title = $("[data-share-drawer-title]", shareDrawerElement);
  const exportButton = $("[data-share-export]", shareDrawerElement);
  const quoteButton = $("[data-share-quote]", shareDrawerElement);
  body.innerHTML = content;
  title.innerHTML = code ? `分享记录 <span translate="no">${escapeHtml(code)}</span>` : "分享记录";
  [exportButton, quoteButton].forEach((button) => { button.dataset.code = code || ""; button.disabled = !code; });
}

function openShareDrawer() {
  ensureShareDrawer();
  previousShareFocus = document.activeElement;
  shareDrawerBackdrop.classList.add("open");
  shareDrawerElement.classList.add("open");
  shareDrawerElement.setAttribute("aria-hidden", "false");
  const app = $("#admin-app");
  if (app) app.inert = true;
  document.body.classList.add("share-drawer-open");
  requestAnimationFrame(() => $("[data-share-drawer-close]", shareDrawerElement).focus());
}

function closeShareDrawer() {
  if (!shareDrawerElement) return;
  shareDrawerBackdrop.classList.remove("open");
  shareDrawerElement.classList.remove("open");
  shareDrawerElement.setAttribute("aria-hidden", "true");
  const app = $("#admin-app");
  if (app) app.inert = false;
  document.body.classList.remove("share-drawer-open");
  if (previousShareFocus?.focus) previousShareFocus.focus();
  previousShareFocus = null;
}

async function lookupShare(code) {
  if (!/^\d{6}$/.test(code)) { showToast("请输入6位数字分享码"); return; }
  setShareDrawerContent(code, '<div class="share-result-loading">正在读取配置…</div>');
  openShareDrawer();
  try {
    const share = await api(`/api/v1/staff/shares/${code}/preview?lang=${state.catalogLanguage === "en" ? "en" : "zh"}`);
    setShareDrawerContent(code, renderShareDetail(share));
  } catch (failure) {
    setShareDrawerContent("", `<div class="share-result-error"><strong>无法读取该配置</strong><span>${escapeHtml(failure.message)}</span></div>`);
  }
}

async function searchShare(event) {
  event.preventDefault();
  const input = $("#share-code");
  if (input) await lookupShare(input.value.trim());
}

function clearShareResult() {
  closeShareDrawer();
  const result = $("#share-result");
  if (result) { result.hidden = true; result.innerHTML = ""; }
  const input = $("#share-code");
  if (input) input.value = "";
}

async function exportSharePdf(code) {
  if (pdfExportPending) return;
  pdfExportPending = true;
  try {
    const language = await choosePdfLanguage();
    if (!language) return;
    const response = await fetch(`${API_BASE}/api/v1/shares/${encodeURIComponent(code)}/pdf?lang=${language}`, { headers: { Authorization: `Bearer ${sessionStorage.getItem(TOKEN_KEY)}` } });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `PDF生成失败（${response.status}）`);
    }
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = response.headers.get("Content-Disposition")?.match(/filename="([^"]+)"/)?.[1] || "BOTEN.pdf"; link.style.display = "none"; document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (failure) { showToast(failure.message); }
  finally { pdfExportPending = false; }
}

async function quoteShare(code) {
  const summary = state.shares.find((item) => item.code === code);
  if (summary?.own_latest_quote_id) {
    try {
      const quote = await api(`/api/v1/quotes/${encodeURIComponent(summary.own_latest_quote_id)}`);
      editQuote(quote);
    } catch (failure) { showToast(failure.message, "error"); }
    return;
  }
  if (Number(summary?.quote_count || 0)) {
    const confirmed = await confirmAction(
      "该分享已有报价",
      `已有 ${Number(summary.quote_count)} 份有效报价。是否继续创建属于你的报价单？`,
      "继续报价"
    );
    if (!confirmed) return;
  }
  try {
    const share = await api(`/api/v1/staff/shares/${code}/preview?lang=${state.catalogLanguage === "en" ? "en" : "zh"}`);
    const shareItems = share.items?.length ? share.items : [{ snapshot: share.snapshot }];
    const items = [];
    let deviceIndex = 0;
    shareItems.forEach((entry) => {
      const snapshot = entry.snapshot || {};
      const itemType = entry.item_type || "device_config";
      if (itemType !== "device_config") {
        const reference = entry.reference_price || {};
        const priceCny = toFiniteNumber(reference.CNY ?? snapshot.price_cny);
        const priceUsd = toFiniteNumber(reference.USD ?? snapshot.price_usd);
        items.push({ kind: itemType, source_id: snapshot.option_id || entry.source_id, name: snapshot.name || entry.display_name || "未命名项目", device_label: itemType === "tool" ? "维修工具" : "设备附件", code: snapshot.code || "", price: priceCny, price_cny: priceCny, price_usd: priceUsd, quantity: Number(entry.quantity || snapshot.quantity || 1) });
        return;
      }
      deviceIndex += 1;
      const pricing = entry.pricing_by_currency || {};
      const cnyPricing = pricing.CNY || {};
      const usdPricing = pricing.USD || {};
      const product = snapshot.product || {};
      const deviceLabel = `设备 ${deviceIndex} · ${product.name || product.id || "—"}`;
      const baseCny = toFiniteNumber(cnyPricing.base_price ?? product.base_price);
      const baseUsd = toFiniteNumber(usdPricing.base_price ?? product.price_usd);
      const deviceSpecifications = [];
      const color = snapshot.color || {};
      if (color.label || color.code) deviceSpecifications.push({ key: "color", label: state.catalogLanguage === "en" ? "Appearance" : "外观颜色", value: color.label || color.code });
      (snapshot.categories || []).filter((category) => ["motor", "channel", "voltage", "power"].includes(category.id)).forEach((category) => {
        const value = (category.options || []).map((option) => option.name || option.code).filter(Boolean).join(" / ");
        if (value) deviceSpecifications.push({ key: category.id, label: category.name || category.id, value });
      });
      items.push({ kind: "product", source_id: product.id, name: product.title_name || product.name || "设备", device_label: deviceLabel, code: product.name || product.id, price: baseCny, price_cny: baseCny, price_usd: baseUsd, reference_price: baseCny, quantity: 1, locked: true, configuration_role: "base_device", device_specifications: deviceSpecifications });

      const priceLines = (value) => new Map(((value || {}).lines || []).map((line) => [line.source_id, toFiniteNumber(line.amount)]));
      const cnyLines = priceLines(cnyPricing);
      const usdLines = priceLines(usdPricing);
      (snapshot.categories || []).forEach((category, categoryIndex) => (category.options || []).forEach((option, optionIndex) => {
        if (["motor", "voltage", "channel"].includes(category.id) && category.id !== "voltage") return;
        const priceCny = cnyLines.has(option.id) ? cnyLines.get(option.id) : toFiniteNumber(option.price_cny ?? option.price);
        const priceUsd = usdLines.has(option.id) ? usdLines.get(option.id) : toFiniteNumber(option.price_usd);
        const isPower = ["voltage", "power"].includes(category.id) || option.base_option_type === "power";
        items.push({ kind: isPower ? "surcharge" : "option", source_id: option.id, name: option.name, device_label: deviceLabel, code: option.code || "", price: priceCny, price_cny: priceCny, price_usd: priceUsd, reference_price: priceCny, quantity: 1, locked: isPower, configuration_role: isPower ? "base_power" : "optional", category_id: category.id, category_name: category.name || "", category_name_en: category.name_en || "", category_sort_order: isPower ? -1 : (category.sort_order ?? categoryIndex), sort_order: option.sort_order ?? optionIndex });
      }));
    });
    openQuoteEditor({ configId: share.config_id, title: `分享配置 ${code}`, items, currency: "CNY", sourceShareId: share.id, sourceType: "share", sourceDocumentVersion: share.document_version || 1, sourceDocumentId: share.id, sourceCode: share.code || code, customerName: share.customer_name || share.sender_name || "", customerEmail: share.customer_email || share.sender_email || "", customerPhone: share.customer_phone || share.sender_phone || "", language: state.catalogLanguage === "en" ? "en" : "zh", recipientUserId: share.created_by || "", recipientLabel: share.sender_name || share.customer_name || share.sender_email || "分享创建者" });
  } catch (failure) { showToast(failure.message); }
}

async function logout() {
  resetDashboard();
  try { await api("/api/v1/auth/logout", { method: "POST" }); } catch (_) {}
  sessionStorage.removeItem(TOKEN_KEY); state.user = null; $("#admin-app").hidden = true; $("#login-page").hidden = false;
}

function openSidebar() { $("#sidebar").classList.add("open"); $("#sidebar-backdrop").hidden = false; }
function closeSidebar() { $("#sidebar").classList.remove("open"); $("#sidebar-backdrop").hidden = true; }
function setSidebarCollapsed(collapsed, persist = true) {
  const app = $("#admin-app");
  const toggle = $("#sidebar-collapse-toggle");
  const isCollapsed = Boolean(collapsed);
  app?.classList.toggle("sidebar-collapsed", isCollapsed);
  if (toggle) {
    const label = isCollapsed ? "展开侧边栏" : "折叠侧边栏";
    toggle.setAttribute("aria-expanded", String(!isCollapsed));
    toggle.setAttribute("aria-label", label);
    toggle.title = label;
  }
  if (persist) localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(isCollapsed));
}
function setCategoryCollapsed(group, collapsed) {
  if (!group) return;
  const content = $(".catalog-group-content", group);
  const table = $(".config-catalog-table", group);
  const button = $("[data-collapse-category]", group);
  group.classList.toggle("collapsed", collapsed);
  // Remove the large table from layout completely. Relying on a class alone
  // can leave a stale grid/scroll extent after collapsing long categories.
  if (content) content.hidden = collapsed;
  if (table) table.hidden = collapsed;
  if (button?.classList.contains("catalog-collapse")) {
    button.textContent = collapsed ? "展开分类" : "折叠分类";
  }
  if (button) button.setAttribute("aria-expanded", String(!collapsed));
}

function restoreCollapsedCategories() {
  $$(".config-catalog-group").forEach((group) => {
    const id = group.dataset.catalogCategory || $("[data-collapse-category]", group)?.dataset.collapseCategory;
    setCategoryCollapsed(group, Boolean(id && state.collapsedCategories.has(id)));
  });
}

function bindEvents() {
  $("#login-form").addEventListener("submit", login);
  $("#logout-button").addEventListener("click", logout);
  $("#sidebar-collapse-toggle")?.addEventListener("click", () => setSidebarCollapsed(!$("#admin-app").classList.contains("sidebar-collapsed")));
  $$(".nav-item").forEach((item) => item.addEventListener("click", () => switchView(item.dataset.view)));
  $$('[data-go]').forEach((item) => item.addEventListener("click", () => switchView(item.dataset.go)));
  if ($("#primary-action")) $("#primary-action").addEventListener("click", () => openUserEditor());
  $("#add-user-button").addEventListener("click", () => openUserEditor());
  $("#user-role-filter")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-user-role]");
    if (!button) return;
    state.userRoleFilter = button.dataset.userRole;
    state.userPage = 1;
    $$("[data-user-role]", $("#user-role-filter")).forEach((item) => { const active = item === button; item.classList.toggle("active", active); item.setAttribute("aria-pressed", String(active)); });
    loadUsers().catch((failure) => showToast(failure.message, "error"));
  });
  let userSearchTimer;
  $("#user-search")?.addEventListener("input", (event) => { clearTimeout(userSearchTimer); userSearchTimer = setTimeout(() => { state.userQuery = event.target.value.trim(); state.userPage = 1; loadUsers().catch((failure) => showToast(failure.message, "error")); }, 300); });
  $("#user-filter-form")?.addEventListener("submit", (event) => { event.preventDefault(); clearTimeout(userSearchTimer); state.userQuery = $("#user-search").value.trim(); state.userPage = 1; loadUsers().catch((failure) => showToast(failure.message, "error")); });
  $("#user-status-filter")?.addEventListener("change", (event) => { state.userStatusFilter = event.target.value; state.userPage = 1; loadUsers().catch((failure) => showToast(failure.message, "error")); });
  $("#user-archived-filter")?.addEventListener("change", (event) => { state.userArchivedFilter = event.target.checked; state.userPage = 1; loadUsers().catch((failure) => showToast(failure.message, "error")); });
  $("#user-page-prev")?.addEventListener("click", () => { if (state.userPage > 1) { state.userPage -= 1; loadUsers().catch((failure) => showToast(failure.message, "error")); } });
  $("#user-page-next")?.addEventListener("click", () => { if (state.userPage * state.userPageSize < state.userTotal) { state.userPage += 1; loadUsers().catch((failure) => showToast(failure.message, "error")); } });
  $("#user-form").addEventListener("submit", createUser);
  $("#user-role-form").addEventListener("submit", submitRole);
  $("#user-password-form").addEventListener("submit", submitPassword);
  $("#user-archive-form").addEventListener("submit", submitArchive);
  $$(".account-dialog").forEach((dialog) => {
    dialog.addEventListener("close", () => { if (dialog._returnFocus?.isConnected) dialog._returnFocus.focus(); });
    dialog.addEventListener("cancel", (event) => { const form = $("form", dialog); const dirty = form?.dataset.initialSnapshot && form.dataset.initialSnapshot !== JSON.stringify(Object.fromEntries(new FormData(form))); if (!dirty) return; event.preventDefault(); confirmAction("放弃未保存修改", "当前修改尚未保存，确定关闭吗？", "放弃修改").then((confirmed) => { if (confirmed) dialog.close(); }); });
  });
  $("#user-form [name='phone_country']")?.addEventListener("change", updateAdminPhoneCallingCode);
  $("#product-form").addEventListener("submit", saveProduct);
  $("#config-option-form").addEventListener("submit", saveConfigOption);
  $("#delete-config-option").addEventListener("click", deleteCurrentConfigOption);
  $$(".editor-tab").forEach((button) => button.addEventListener("click", () => switchEditorTab(button.dataset.editorTab)));
  $(".editor-tabs")?.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const tabs = $$(".editor-tab", event.currentTarget); const current = tabs.indexOf(document.activeElement); if (current < 0) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    switchEditorTab(tabs[next].dataset.editorTab); tabs[next].focus();
  });
  $("#mapping-search")?.addEventListener("input", (event) => { if (!state.mappingEditor) return; state.mappingEditor.query = event.target.value; renderMappingEditor(); });
  $(".mapping-filters")?.addEventListener("click", (event) => { const button = event.target.closest("[data-mapping-filter]"); if (!button || !state.mappingEditor) return; state.mappingEditor.filter = button.dataset.mappingFilter; renderMappingEditor(); });
  $("#mapping-expand-all")?.addEventListener("click", () => { const editor = state.mappingEditor; if (!editor) return; editor.collapsed = editor.collapsed?.size ? new Set() : new Set(editor.categories.map((category) => category.id)); renderMappingEditor(); });
  $("#add-color-button").addEventListener("click", () => {
    $("#color-editor-list").insertAdjacentHTML("beforeend", colorEditorRow());
    const activeLanguage = $(".lang-toggle.active", $("#product-dialog"))?.dataset.lang || "zh";
    $$("[data-color-name-lang]", $("#color-editor-list").lastElementChild).forEach((label) => { label.hidden = label.dataset.colorNameLang !== activeLanguage; });
  });
  $("#code-search")?.addEventListener("submit", searchShare);
  $("#clear-share-result")?.addEventListener("click", clearShareResult);
  $("#share-filter-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    state.shareQuery = $("#share-query").value.trim(); state.shareStatus = $("#share-status-filter").value;
    state.shareProduct = ""; state.shareCreatedFrom = ""; state.shareCreatedTo = "";
    state.sharePage = 1; loadShares().catch((failure) => showToast(failure.message, "error"));
  });
  $("#share-filter-reset")?.addEventListener("click", () => {
    $("#share-filter-form").reset(); state.shareQuery = ""; state.shareStatus = "active"; state.shareProduct = ""; state.shareCreatedFrom = ""; state.shareCreatedTo = ""; state.sharePage = 1;
    loadShares().catch((failure) => showToast(failure.message, "error"));
  });
  $("#share-query")?.addEventListener("input", () => {
    clearTimeout(shareSearchTimer);
    shareSearchTimer = setTimeout(() => {
      state.shareQuery = $("#share-query").value.trim();
      state.sharePage = 1;
      loadShares().catch((failure) => showToast(failure.message, "error"));
    }, 350);
  });
  $("#share-status-filter")?.addEventListener("change", () => {
    state.shareStatus = $("#share-status-filter").value;
    state.sharePage = 1;
    loadShares().catch((failure) => showToast(failure.message, "error"));
  });
  $("#share-page-prev")?.addEventListener("click", () => { if (state.sharePage > 1) { state.sharePage -= 1; loadShares().catch((failure) => showToast(failure.message, "error")); } });
  $("#share-page-next")?.addEventListener("click", () => { if (state.sharePage * state.sharePageSize < state.shareTotal) { state.sharePage += 1; loadShares().catch((failure) => showToast(failure.message, "error")); } });
  let inquirySearchTimer;
  $("#inquiry-filter-form")?.addEventListener("submit", (event) => { event.preventDefault(); clearTimeout(inquirySearchTimer); state.inquiryQuery = $("#inquiry-query").value.trim(); state.inquiryStatus = $("#inquiry-status-filter").value; state.inquiryPage = 1; loadInquiries().catch((failure) => showToast(failure.message, "error")); });
  $("#inquiry-filter-reset")?.addEventListener("click", () => { $("#inquiry-filter-form").reset(); state.inquiryQuery = ""; state.inquiryStatus = "all"; state.inquiryQueue = "all"; state.inquiryPage = 1; loadInquiries().catch((failure) => showToast(failure.message, "error")); });
  $("#inquiry-query")?.addEventListener("input", () => { clearTimeout(inquirySearchTimer); inquirySearchTimer = setTimeout(() => { state.inquiryQuery = $("#inquiry-query").value.trim(); state.inquiryPage = 1; loadInquiries().catch((failure) => showToast(failure.message, "error")); }, 350); });
  $("#inquiry-status-filter")?.addEventListener("change", () => { state.inquiryStatus = $("#inquiry-status-filter").value; state.inquiryPage = 1; loadInquiries().catch((failure) => showToast(failure.message, "error")); });
  $("#inquiry-page-prev")?.addEventListener("click", () => { if (state.inquiryPage > 1) { state.inquiryPage -= 1; loadInquiries().catch((failure) => showToast(failure.message, "error")); } });
  $("#inquiry-page-next")?.addEventListener("click", () => { if (state.inquiryPage * state.inquiryPageSize < state.inquiryTotal) { state.inquiryPage += 1; loadInquiries().catch((failure) => showToast(failure.message, "error")); } });
  let quoteSearchTimer;
  $("#quote-filter-form")?.addEventListener("submit", (event) => { event.preventDefault(); clearTimeout(quoteSearchTimer); state.quoteQuery = $("#quote-query").value.trim(); state.quoteStatus = $("#quote-status-filter").value; loadQuotes().catch((failure) => showToast(failure.message, "error")); });
  $("#quote-query")?.addEventListener("input", () => { clearTimeout(quoteSearchTimer); quoteSearchTimer = setTimeout(() => { state.quoteQuery = $("#quote-query").value.trim(); loadQuotes().catch((failure) => showToast(failure.message, "error")); }, 350); });
  $("#quote-status-filter")?.addEventListener("change", () => { state.quoteStatus = $("#quote-status-filter").value; loadQuotes().catch((failure) => showToast(failure.message, "error")); });
  $("#quote-filter-reset")?.addEventListener("click", () => { clearTimeout(quoteSearchTimer); $("#quote-filter-form").reset(); state.quoteQuery = ""; state.quoteStatus = "all"; state.quoteDue = false; loadQuotes().catch((failure) => showToast(failure.message, "error")); });
  $("#refresh-audit")?.addEventListener("click", loadData);
  addLanguageToggles(); addProductButton(); addCatalogLanguageSwitches();
  $("#menu-button").addEventListener("click", openSidebar);
  $("#sidebar-backdrop").addEventListener("click", closeSidebar);
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".catalog-more")) document.querySelectorAll(".catalog-more[open]").forEach((menu) => { menu.removeAttribute("open"); });
    const tableMenuSummary = event.target.closest(".table-actions-menu > summary");
    if (tableMenuSummary) {
      const tableMenu = tableMenuSummary.parentElement;
      setTimeout(() => {
        if (!tableMenu.open) return;
        closeTableActionMenus(tableMenu);
        positionTableActionMenu(tableMenu);
      }, 0);
    } else if (!event.target.closest(".table-actions-menu")) {
      closeTableActionMenus();
    }
    const imageButton = event.target.closest("[data-pick-image]"); if (imageButton) { imageButton.closest(".image-path-control, .color-image-control")?.querySelector("[data-image-file]")?.click(); return; }
    const cancelButton = event.target.closest('button[value="cancel"]'); if (cancelButton) { const dialog = cancelButton.closest("dialog"); if (dialog) { if (dialog.classList.contains("confirm-dialog")) return; event.preventDefault(); const form = $("form", dialog); const shouldWarn = dialog.classList.contains("account-dialog") || dialog.dataset.warnUnsaved === "true"; const dirty = shouldWarn && form?.dataset.initialSnapshot && form.dataset.initialSnapshot !== JSON.stringify(Object.fromEntries(new FormData(form))); const closeAndRemove = () => { dialog.close(); if (dialog.dataset.dynamic === "true") dialog.remove(); }; if (dirty) { confirmAction("放弃未保存修改", "当前修改尚未保存，确定关闭吗？", "放弃修改").then((confirmed) => { if (confirmed) closeAndRemove(); }); } else closeAndRemove(); return; } }
    const userButton = event.target.closest("[data-user-status]"); if (userButton) setUserStatus(userButton);
    const editUserButton = event.target.closest("[data-edit-user]"); if (editUserButton) { const user = findUser(editUserButton.dataset.editUser); if (user) openUserEditor(user, editUserButton); }
    const roleButton = event.target.closest("[data-edit-user-role]"); if (roleButton) { const user = findUser(roleButton.dataset.editUserRole); if (user) openRoleEditor(user, roleButton); }
    const passwordButton = event.target.closest("[data-reset-user-password]"); if (passwordButton) { const user = findUser(passwordButton.dataset.resetUserPassword); if (user) openPasswordEditor(user, passwordButton); }
    const archiveButton = event.target.closest("[data-archive-user]"); if (archiveButton) { const user = findUser(archiveButton.dataset.archiveUser); if (user) openArchiveEditor(user, archiveButton); }
    const restoreButton = event.target.closest("[data-restore-user]"); if (restoreButton) restoreUser(restoreButton);
    const shareButton = event.target.closest("[data-close-share]"); if (shareButton) closeShare(shareButton);
    const reopenShareButton = event.target.closest("[data-open-share]"); if (reopenShareButton) reopenShare(reopenShareButton);
    const quoteButton = event.target.closest("[data-delete-quote]"); if (quoteButton) deleteQuote(quoteButton);
    const archiveQuoteButton = event.target.closest("[data-archive-quote]"); if (archiveQuoteButton) archiveQuote(archiveQuoteButton);
    const restoreQuoteButton = event.target.closest("[data-restore-quote]"); if (restoreQuoteButton) restoreQuote(restoreQuoteButton);
    const quoteHistoryButton = event.target.closest("[data-quote-history]"); if (quoteHistoryButton) viewQuoteHistory(quoteHistoryButton.dataset.quoteHistory);
    const exportQuoteButton = event.target.closest("[data-export-quote]"); if (exportQuoteButton) { const quote = state.quotes.find((item) => item.id === exportQuoteButton.dataset.exportQuote); if (quote) exportQuote(quote); }
    const editQuoteButton = event.target.closest("[data-edit-quote]"); if (editQuoteButton) { const quote = state.quotes.find((item) => item.id === editQuoteButton.dataset.editQuote); if (quote) editQuote(quote); }
    const lookupButton = event.target.closest("[data-lookup-share]");
    if (lookupButton) {
      const input = $("#share-code");
      if (input) input.value = lookupButton.dataset.lookupShare;
      lookupShare(lookupButton.dataset.lookupShare);
    }
    const exportButton = event.target.closest("[data-export-share]"); if (exportButton) exportSharePdf(exportButton.dataset.exportShare);
    const quoteActionButton = event.target.closest("[data-quote-share]"); if (quoteActionButton) quoteShare(quoteActionButton.dataset.quoteShare);
    const viewInquiryButton = event.target.closest("[data-view-inquiry]"); if (viewInquiryButton) viewInquiry(viewInquiryButton.dataset.viewInquiry);
    const exportInquiryButton = event.target.closest("[data-export-inquiry]"); if (exportInquiryButton) exportInquiryPdf(exportInquiryButton);
    const takeInquiryButton = event.target.closest("[data-take-inquiry]"); if (takeInquiryButton) takeInquiry(takeInquiryButton);
    const quoteInquiryButton = event.target.closest("[data-quote-inquiry]"); if (quoteInquiryButton) quoteInquiry(quoteInquiryButton);
    const openInquiryQuoteButton = event.target.closest("[data-open-inquiry-quote]"); if (openInquiryQuoteButton) openInquiryQuote(openInquiryQuoteButton);
    const productButton = event.target.closest("[data-edit-product]"); if (productButton) openProductEditor(productButton.dataset.editProduct);
    const mappingNoteButton = event.target.closest("[data-edit-mapping-note]"); if (mappingNoteButton) openMappingNoteEditor(mappingNoteButton.dataset.editMappingNote);
    const mappingGroupButton = event.target.closest("[data-mapping-category]");
    if (mappingGroupButton && state.mappingEditor) { const id = mappingGroupButton.dataset.mappingCategory; if (state.mappingEditor.collapsed.has(id)) state.mappingEditor.collapsed.delete(id); else state.mappingEditor.collapsed.add(id); renderMappingEditor(); }
    const optionButton = event.target.closest("[data-edit-option]"); if (optionButton) openConfigOptionEditor(JSON.parse(optionButton.dataset.editOption));
    const addOptionButton = event.target.closest("[data-add-option]"); if (addOptionButton) { addOptionButton.closest(".catalog-more")?.removeAttribute("open"); addConfigOption(addOptionButton.dataset.addOption); }
    const categoryButton = event.target.closest("[data-edit-category]"); if (categoryButton) { categoryButton.closest(".catalog-more")?.removeAttribute("open"); editConfigCategory(JSON.parse(categoryButton.dataset.editCategory)); }
    const collapseButton = event.target.closest("[data-collapse-category]");
    if (collapseButton) {
      const group = collapseButton.closest(".config-catalog-group");
      const collapsed = !group.classList.contains("collapsed");
      const id = collapseButton.dataset.collapseCategory;
      setCategoryCollapsed(group, collapsed);
      if (collapsed) state.collapsedCategories.add(id);
      else state.collapsedCategories.delete(id);
      localStorage.setItem("boten-admin-collapsed-categories", JSON.stringify(Array.from(state.collapsedCategories)));
    }
    const languageButton = event.target.closest(".lang-toggle"); if (languageButton) toggleDialogLanguage(languageButton);
    const catalogLanguageButton = event.target.closest("[data-catalog-lang]"); if (catalogLanguageButton) localStorage.setItem("boten-admin-language", catalogLanguageButton.dataset.catalogLang);
    const colorButton = event.target.closest("[data-remove-color]");
    if (colorButton) {
      const rows = $$(".color-editor-row", $("#color-editor-list"));
      if (rows.length <= 1) { showToast("每台设备至少保留一种外观颜色"); return; }
      const row = colorButton.closest(".color-editor-row");
      const wasDefault = $('[data-color-field="is_default"]', row).checked;
      row.remove();
      if (wasDefault) $('[data-color-field="is_default"]', $("#color-editor-list")).checked = true;
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeTableActionMenus();
    const target = event.target.closest?.("[data-collapse-category]");
    if (target && target.tagName !== "BUTTON" && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); target.click(); }
  });
  document.addEventListener("change", (event) => {
    const mappingCheckbox = event.target.closest('#mapping-editor input[type="checkbox"]');
    if (mappingCheckbox && state.mappingEditor) {
      if (mappingCheckbox.checked) state.mappingEditor.selected.add(mappingCheckbox.value);
      else state.mappingEditor.selected.delete(mappingCheckbox.value);
      renderMappingEditor();
      return;
    }
    const fileInput = event.target.closest("[data-image-file]");
    if (fileInput) uploadCatalogImage(fileInput.files?.[0], fileInput.closest(".image-path-control, .color-image-control"));
  });
  window.addEventListener("hashchange", () => { if (!$("#admin-app")?.hidden) switchView(window.location.hash.slice(1) || "dashboard", false); });
}

// Unified catalog editor cards.
function editorFieldControl(field) {
  if (field.type === "select") return `<select name="${escapeHtml(field.name)}">${field.options.map(([value, label]) => `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`).join("")}</select>`;
  if (field.name === "image_path") {
    return `<div class="image-path-control"><input name="image_path" value="${escapeHtml(field.value || "")}" placeholder="${escapeHtml(field.placeholder || "上传图片或填写现有路径")}"><button class="button button-secondary" type="button" data-pick-image>上传</button><input type="file" accept="image/png,image/jpeg,image/webp" data-image-file hidden></div>`;
  }
  if (field.type === "textarea") return `<textarea name="${field.name}" rows="3" placeholder="${escapeHtml(field.placeholder || "")}">${escapeHtml(field.value || "")}</textarea>`;
  return `<input name="${field.name}" type="${field.type || "text"}" value="${escapeHtml(field.value || "")}" placeholder="${escapeHtml(field.placeholder || "")}" ${field.required ? "required" : ""}>`;
}

function catalogEditorCard({ title, fields, onSave, onDelete = null, size = "medium" }) {
  const dialog = document.createElement("dialog"); dialog.className = `catalog-editor-dialog catalog-editor-dialog--${size}`;
  const titleId = `catalog-editor-title-${Date.now()}`;
  dialog.setAttribute("aria-labelledby", titleId);
  dialog.innerHTML = `<form method="dialog" class="dialog-card catalog-editor-card"><header><div><span class="eyebrow">CATALOG EDITOR</span><h2 id="${titleId}">${escapeHtml(title)}</h2></div><div class="dialog-actions"><div class="catalog-language dialog-language" role="group" aria-label="编辑语言"><button type="button" class="lang-toggle active" data-lang="zh" aria-pressed="true">中文</button><button type="button" class="lang-toggle" data-lang="en" aria-pressed="false">EN</button></div><button class="icon-button" value="cancel" aria-label="关闭">×</button></div></header><div class="catalog-editor-body"><div class="form-grid">${fields.map(f => `<label data-card-lang="${f.lang || "all"}"><span>${escapeHtml(f.label)}</span>${editorFieldControl(f)}</label>`).join("")}</div></div><footer>${onDelete ? '<button class="button button-danger" type="button" data-delete-card>删除</button>' : ""}<button class="button button-quiet" value="cancel">取消</button><button class="button button-primary" value="default">保存</button></footer></form>`;
  document.body.appendChild(dialog); const form = dialog.querySelector("form");
  const opener = document.activeElement;
  dialog.addEventListener("close", () => opener?.focus(), { once: true });
  const setLang = lang => { dialog.querySelectorAll("[data-card-lang]").forEach(row => row.hidden = !(["all", lang].includes(row.dataset.cardLang))); dialog.querySelectorAll(".lang-toggle").forEach(b => { const active = b.dataset.lang === lang; b.classList.toggle("active", active); b.setAttribute("aria-pressed", String(active)); }); };
  dialog.querySelectorAll(".lang-toggle").forEach(b => b.addEventListener("click", () => setLang(b.dataset.lang))); setLang(state.catalogLanguage || "zh");
  dialog.querySelector("[data-delete-card]")?.addEventListener("click", async event => { try { await runButtonAction(event.currentTarget, "删除中…", async () => { if (await onDelete()) { dialog.close(); dialog.remove(); await loadData(); } }); } catch (error) { showToast(error.message); } });
  form.addEventListener("submit", async event => { event.preventDefault(); if (event.submitter?.value === "cancel") { dialog.close(); dialog.remove(); return; } const data = Object.fromEntries(new FormData(form)); const missing = fields.find(field => field.required && !String(data[field.name] || "").trim()); if (missing) { showToast(`请填写${missing.label}`); form.querySelector(`[name="${missing.name}"]`)?.focus(); return; } try { await runButtonAction(event.submitter, "正在保存…", async () => { await onSave(data); dialog.close(); dialog.remove(); await loadData(); }); } catch (error) { showToast(error.message); } }); dialog.showModal(); dialog.querySelector("input, textarea, select")?.focus();
}

function categoryCard(category = null) { catalogEditorCard({ title: category ? "编辑配置分类" : "添加配置分类", size:"small", fields: [{name:"name",label:"分类标题",lang:"zh",value:category?.name,placeholder:"例如：CRI 共轨套件",required:true},{name:"description",label:"分类描述",lang:"zh",type:"textarea",value:category?.description,placeholder:"例如：适用于共轨喷油器测试"},{name:"name_en",label:"分类标题",lang:"en",value:category?.name_en,placeholder:"例如：CRI Common Rail Kits"},{name:"description_en",label:"分类描述",lang:"en",type:"textarea",value:category?.description_en,placeholder:"例如：Kits for common rail injector testing"}], onSave: data => api(category ? `/api/v1/admin/config-catalog/categories/${category.id}` : "/api/v1/admin/config-catalog/categories", {method:category?"PATCH":"POST",body:JSON.stringify({...data,multiple:true,...(category ? {version:category.version} : {})})}), onDelete: category ? () => deleteConfigCategory(category) : null }); }

async function addConfigOption(categoryId) { catalogEditorCard({ title:"添加配置", size:"medium", fields:[{name:"code",label:"配置编号",lang:"all",placeholder:"例如：BTK-1019",required:true},{name:"name",label:"配置名称",lang:"zh",placeholder:"例如：共轨喷油器测试套件",required:true},{name:"description",label:"配置描述",lang:"zh",type:"textarea",placeholder:"例如：适用于 Bosch CRIN4.2"},{name:"name_en",label:"配置名称",lang:"en",placeholder:"例如：Injector Test Kit"},{name:"description_en",label:"配置描述",lang:"en",type:"textarea",placeholder:"例如：For Bosch CRIN4.2"},{name:"image_path",label:"配置图片",lang:"all",placeholder:"上传图片或填写现有路径"},{name:"price",label:"人民币单价",lang:"all",type:"number",placeholder:"例如：1500"},{name:"price_usd",label:"美元单价",lang:"all",type:"number",placeholder:"例如：210"}], onSave:data=>api("/api/v1/admin/config-catalog/options",{method:"POST",body:JSON.stringify({...data,category_id:categoryId,price:Number(data.price||0),price_usd:Number(data.price_usd||0),enabled:true})}) }); }

// Unified bilingual add-device editor.
function addProductButton() {
  const panel = $("#product-catalog-actions");
  if (!panel || $("#add-product-button")) return;
  const button = document.createElement("button");
  button.id = "add-product-button"; button.className = "button button-secondary"; button.textContent = "添加设备";
  button.addEventListener("click", () => catalogEditorCard({ title:"添加设备", size:"large", fields:[
    {name:"id",label:"设备编号",lang:"all",placeholder:"例如：CR999",required:true},
    {name:"name",label:"设备名称",lang:"zh",placeholder:"例如：BOTEN CR999",required:true},
    {name:"title_name",label:"产品标题",lang:"zh",placeholder:"例如：共轨喷油器试验台",required:true},
    {name:"description",label:"设备概况",lang:"zh",type:"textarea",placeholder:"例如：适用于共轨喷油器测试"},
    {name:"name_en",label:"设备名称",lang:"en",placeholder:"例如：BOTEN CR999"},
    {name:"title_name_en",label:"产品标题",lang:"en",placeholder:"例如：Common Rail Test Bench"},
    {name:"description_en",label:"设备概况",lang:"en",type:"textarea",placeholder:"例如：Designed for common rail testing"},
    {name:"base_price",label:"人民币单价",lang:"all",type:"number",placeholder:"例如：158000"},
    {name:"price_usd",label:"美元单价",lang:"all",type:"number",placeholder:"例如：22000"}
  ], onSave:data => api("/api/v1/admin/products",{method:"POST",body:JSON.stringify({...data,base_price:Number(data.base_price||0),price_usd:Number(data.price_usd||0)})}) }));
  panel.appendChild(button);
}

async function saveConfigOption(event) {
  event.preventDefault(); const form=event.currentTarget; if(event.submitter?.value==="cancel"){form.closest("dialog")?.close();return;}
  const payload={code:form.elements.code.value.trim(),name:form.elements.name.value.trim(),name_en:form.elements.name_en.value.trim(),image_path:form.elements.image_path.value.trim()||null,description:form.elements.description.value.trim(),description_en:form.elements.description_en.value.trim(),notes:form.elements.notes.value.trim(),price:Number(form.elements.price.value||0),price_usd:Number(form.elements.price_usd?.value||0),enabled:form.elements.enabled.checked};
  payload.version = Number(form.dataset.optionVersion);
  try{await runButtonAction(event.submitter,"正在保存…",async()=>{await api(`/api/v1/admin/config-catalog/options/${form.elements.option_id.value}`,{method:"PATCH",body:JSON.stringify(payload)});$("#config-option-dialog").close();showToast("配置条目已保存");await loadData();});}catch(failure){const error=$("#config-option-error");error.textContent=failure.code === "CATALOG_VERSION_CONFLICT" ? "该配置已更新，请关闭编辑窗口并刷新目录后重新编辑；本次修改未保存。" : failure.message;error.hidden=false;}
}

document.addEventListener("DOMContentLoaded", async () => {
  bindDashboardEvents();
  setSidebarCollapsed(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true", false);
  restoreUserFilterState(); restoreBusinessFilterState(); bindEvents(); await checkApi(); await restoreSession();
});
document.addEventListener("click", (event) => {
  if (event.target.closest("[data-catalog-lang]")) setTimeout(renderProducts, 0);
});
