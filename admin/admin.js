// An empty runtime base is deliberate for the NAS Nginx same-origin proxy.
const API_BASE = typeof window.BOTEN_API_BASE === "string"
  ? window.BOTEN_API_BASE
  : (window.location.port === "8001" ? "" : `${window.location.protocol}//${window.location.hostname || "127.0.0.1"}:8001`);
const TOKEN_KEY = "boten_admin_token";
const CUSTOMER_TOKEN_KEY = "boten_user_token";

function getStoredCollapsedCategories() { try { const value = JSON.parse(localStorage.getItem("boten-admin-collapsed-categories") || "[]"); return Array.isArray(value) ? value : []; } catch (_) { return []; } }
const state = { user: null, products: [], users: [], userTotal: 0, userPage: 1, userPageSize: 20, userQuery: "", userRoleFilter: "all", userStatusFilter: "all", userArchivedFilter: false, shares: [], shareTotal: 0, sharePage: 1, sharePageSize: 20, shareQuery: "", shareStatus: "all", shareProduct: "", shareCreatedFrom: "", shareCreatedTo: "", shareActiveTotal: 0, shareViewTotal: 0, quotes: [], audits: [], countries: [], editingProduct: null, mappingEditor: null, catalogLanguage: localStorage.getItem("boten-admin-language") || "zh", configCatalog: [], collapsedCategories: new Set(getStoredCollapsedCategories()) };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
let shareDrawerElement = null;
let shareDrawerBackdrop = null;
let shareSearchTimer = null;
let previousShareFocus = null;

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
  ACCOUNT_RATE_LIMITED: "操作过于频繁，请稍后再试", ACCOUNT_VALIDATION_FAILED: "请检查填写内容", SERVER_UNAVAILABLE: "服务器处理失败，请稍后重试"
};
const ACCOUNT_ERROR_TEXT_EN = {
  ACCOUNT_NOT_FOUND: "The account no longer exists", ACCOUNT_EMAIL_INVALID: "Enter a valid email address", ACCOUNT_EMAIL_DUPLICATE: "This email is already used by another account",
  ACCOUNT_PHONE_INVALID: "Enter a valid phone number for the selected country", ACCOUNT_PHONE_DUPLICATE: "This phone number is already used by another account", ACCOUNT_PHONE_COUNTRY_INVALID: "Select a valid country",
  ACCOUNT_CONTACT_REQUIRED: "Keep at least an email address or phone number", ACCOUNT_NAME_REQUIRED: "Enter a display name", ACCOUNT_NAME_TOO_LONG: "The display name cannot exceed 100 characters",
  ACCOUNT_PASSWORD_TOO_SHORT: "The password must contain at least 8 characters", ACCOUNT_PASSWORD_TOO_LONG: "The password cannot exceed 128 characters", ACCOUNT_PASSWORD_CONFIRMATION_MISMATCH: "The new passwords do not match",
  ACCOUNT_ROLE_INVALID: "Select a supported account role", ACCOUNT_SELF_DISABLE_FORBIDDEN: "You cannot disable your current account", ACCOUNT_SELF_ROLE_CHANGE_FORBIDDEN: "You cannot remove your own administrator access",
  ACCOUNT_SELF_ARCHIVE_FORBIDDEN: "You cannot archive your current account", ACCOUNT_LAST_ADMIN_REQUIRED: "At least one enabled administrator account is required", ACCOUNT_VERSION_CONFLICT: "This account was changed by another administrator. Reload it and try again",
  ACCOUNT_ARCHIVED: "This account is archived", ACCOUNT_NOT_ARCHIVED: "This account is not archived", ACCOUNT_SESSION_EXPIRED: "Your session has expired. Sign in again", ACCOUNT_PERMISSION_DENIED: "You do not have permission to perform this action", ACCOUNT_CURRENT_PASSWORD_INVALID: "The current password is incorrect", ACCOUNT_IDENTIFIER_REQUIRED: "Enter an email address or phone number", ACCOUNT_CREDENTIALS_INVALID: "The email, phone number, or password is incorrect",
  ACCOUNT_RATE_LIMITED: "Too many requests. Try again later", ACCOUNT_VALIDATION_FAILED: "Check the entered information", SERVER_UNAVAILABLE: "The server could not complete the request. Try again later"
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
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", { hour12: false });
}

function roleLabel(role) {
  return { admin: "管理员", sales: "业务员", customer: "客户", guest: "游客" }[role] || role;
}

async function checkApi() {
  const status = $("#api-status");
  try {
    await api("/api/v1/health");
    status.textContent = "服务连接正常";
    status.style.color = "var(--green)";
    return true;
  } catch (_) {
    status.textContent = "无法连接后端，请先启动 8001 端口的 API 服务";
    status.style.color = "var(--red)";
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
  $(".sidebar-brand span").textContent = isAdmin ? "管理后台" : "业务员工作台";
  await loadData();
  const requestedView = window.location.hash.slice(1);
  const catalogViews = ["config-catalog", "tool-catalog", "accessory-catalog"];
  const allowed = isAdmin ? ["dashboard", "products", ...catalogViews, "shares", "quotes", "audit", "users"] : ["products", ...catalogViews, "shares", "quotes"];
  switchView(allowed.includes(requestedView) ? requestedView : (isAdmin ? "dashboard" : "products"), false);
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
  renderShares(); renderDashboard();
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
  const requests = {
    shares: api(shareListPath()),
    quotes: api("/api/v1/quotes"),
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
  const quotes = value("quotes");
  const products = value("products");
  const configCatalog = value("configCatalog");
  const countries = value("countries");
  const users = isAdmin ? value("users") : null;
  const audits = isAdmin ? value("audits") : null;

  state.shares = shares?.items || [];
  state.shareTotal = Number(shares?.total || state.shares.length);
  state.shareActiveTotal = Number(shares?.active_total || 0);
  state.shareViewTotal = Number(shares?.view_total || 0);
  state.quotes = quotes?.items || [];
  state.products = products?.items || [];
  state.configCatalog = configCatalog?.items || [];
  state.countries = countries?.items || [];
  state.users = users?.items || [];
  state.userTotal = Number(users?.total || 0);
  state.audits = audits?.items || [];

  renderConfigCatalog(state.configCatalog);
  renderAll();
  setTimeout(() => {
    addCatalogLanguageSwitches();
    applyCatalogLanguage(state.catalogLanguage);
    restoreCollapsedCategories();
  }, 0);

  const errorTargets = {
    shares: ["#shares-table", 7], quotes: ["#quotes-table", 5], products: ["#products-table", 4],
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
  $("#metric-products").textContent = state.products.length;
  $("#metric-users").textContent = state.userTotal;
  $("#metric-shares").textContent = state.shareActiveTotal;
  $("#metric-views").textContent = state.shareViewTotal;
    renderProducts(); renderUsers(); renderShares(); renderQuotes(); renderAudits(); renderDashboard();
}

function renderDashboard() {
  $("#dashboard-products").innerHTML = state.products.slice(0, 5).map((product) => `
    <div class="mini-row"><div><strong>${escapeHtml(product.name)}</strong><span>${escapeHtml(product.title_name)}</span></div><div class="model-mark">${escapeHtml(product.id.toUpperCase())}</div></div>
  `).join("") || '<div class="empty">暂无产品数据</div>';
  $("#dashboard-shares").innerHTML = state.shares.slice(0, 5).map((share) => `
    <div class="mini-row"><div><strong>${escapeHtml(share.code)}</strong><span>${escapeHtml(share.name)}</span></div><span class="badge ${share.active ? "good" : "off"}">${share.active ? "有效" : "已关闭"}</span></div>
  `).join("") || '<div class="empty">暂无分享记录</div>';
}

function renderProducts() {
  const english = state.catalogLanguage === "en";
  const priceLabel = $("[data-view-panel=\"products\"] thead th:nth-child(3)");
  if (priceLabel) priceLabel.textContent = english ? "价格 / USD" : "价格 / 人民币";
  $("#products-table").innerHTML = state.products.map((product) => `
    <tr><td><strong>${escapeHtml(english ? (product.name_en || product.name) : product.name)}</strong></td><td>${escapeHtml(english ? (product.title_name_en || product.title_name) : product.title_name)}</td><td>${english ? "$" + Number(product.price_usd || 0).toLocaleString("en-US") : "¥" + Number(product.base_price || 0).toLocaleString("zh-CN")}</td><td><span class="badge ${product.enabled ? "good" : "off"}">${product.enabled ? "已启用" : "已下架"}</span></td><td class="align-right"><button class="table-action" data-edit-product="${product.id}">编辑</button></td></tr>
  `).join("") || '<tr><td colspan="5" class="empty">暂无产品数据</td></tr>';
}

function renderConfigCatalog(categories) {
  const target = $("#config-catalog-list"); if (!target) return;
  target.innerHTML = categories.map((category) => `<section class="config-catalog-group"><header><div class="catalog-collapse-target" data-collapse-category="${escapeHtml(category.id)}" role="button" tabindex="0" aria-expanded="true"><h3>${escapeHtml(category.name)}</h3><p>${escapeHtml(category.description || "")}</p></div><div><span>${category.options.length} 项</span><button class="text-button" data-add-option="${escapeHtml(category.id)}">添加配置</button><details class="catalog-more"><summary>更多</summary><div><button class="text-button" data-edit-category='${escapeHtml(JSON.stringify(category))}'>编辑分类</button></div></details></div></header><div class="config-catalog-table"><table><thead><tr><th>编号</th><th>名称</th><th>图片</th><th>参考价格</th><th>状态</th><th></th></tr></thead><tbody>${category.options.map((option) => `<tr><td><strong>${escapeHtml(option.code)}</strong></td><td>${escapeHtml(option.name)}<br><small>${escapeHtml(option.description || "")}</small></td><td class="config-image-cell">${renderCatalogThumbnail(option)}</td><td>¥${Number(option.price || 0).toLocaleString("zh-CN")}</td><td><span class="badge ${option.enabled ? "good" : "off"}">${option.enabled ? "启用" : "停用"}</span></td><td class="align-right"><button class="table-action" data-edit-option='${escapeHtml(JSON.stringify(option))}'>编辑</button></td></tr>`).join("")}</tbody></table></div></section>`).join("") || '<div class="empty">暂无配置目录</div>';
}

async function addConfigCategory() { categoryCard(); }
async function editConfigCategory(category) { categoryCard(category); }

function addLanguageToggles() { ["#product-dialog", "#config-option-dialog"].forEach((selector) => { const dialog = $(selector); const header = $(".dialog-card > header", dialog); if (!header || $(".lang-toggle", header)) return; const box = document.createElement("div"); box.className = "catalog-language dialog-language"; box.innerHTML = '<button type="button" class="lang-toggle active" data-lang="zh" aria-pressed="true">中文</button><button type="button" class="lang-toggle" data-lang="en" aria-pressed="false">EN</button>'; box.addEventListener("click", (event) => { const button = event.target.closest(".lang-toggle"); if (!button) return; event.stopPropagation(); toggleDialogLanguage(button); }); header.appendChild(box); }); const examples={name:"例如：CR318C",name_en:"例如：CR318C",title_name:"例如：共轨喷油器试验台",title_name_en:"例如：Common Rail Test Bench",description:"例如：适用于多种喷油器测试",description_en:"例如：Designed for common rail injector testing",code:"例如：BTK-1019",price:"例如：1500"}; Object.entries(examples).forEach(([name,placeholder])=>$$(`[name="${name}"]`).forEach(el=>{if(!el.placeholder)el.placeholder=placeholder;})); }
function toggleDialogLanguage(button) { const dialog = button.closest("dialog"); const lang = button.dataset.lang; $$(".lang-toggle", dialog).forEach((item) => { const active = item === button; item.classList.toggle("active", active); item.setAttribute("aria-pressed", String(active)); }); $$('[name$="_en"]', dialog).forEach((field) => { const label = field.closest("label"); if (label) label.hidden = lang !== "en"; }); $$('[name="name"],[name="title_name"],[name="description"]', dialog).forEach((field) => { const label = field.closest("label"); if (label) label.hidden = lang === "en"; }); $$('[data-color-name-lang]', dialog).forEach((label) => { label.hidden = label.dataset.colorNameLang !== lang; }); if (dialog.id === "product-dialog") { state.catalogLanguage = lang; localStorage.setItem("boten-admin-language", lang); renderMappingEditor(); } }
function applyCatalogLanguage(lang) { state.catalogLanguage=lang; $$(".catalog-language button").forEach(b=>b.classList.toggle("active",b.dataset.catalogLang===lang)); $$("#products-table tr").forEach((row,i)=>{const p=state.products[i];if(!p)return;const cells=row.children;cells[0].querySelector("strong").textContent=lang==="en"?(p.name_en||p.name):p.name;cells[1].textContent=lang==="en"?(p.title_name_en||p.title_name):p.title_name;}); $$(".config-catalog-group").forEach((group,i)=>{const c=state.configCatalog[i];if(!c)return;group.querySelector("h3").textContent=lang==="en"?(c.name_en||c.name):c.name;const p=group.querySelector("header p");if(p)p.textContent=lang==="en"?(c.description_en||c.description||""):(c.description||"");$$('tbody tr',group).forEach((row,n)=>{const o=c.options[n];if(!o)return;const cell=row.children[1];cell.childNodes[0].textContent=lang==="en"?(o.name_en||o.name):o.name;const small=cell.querySelector("small");if(small)small.textContent=lang==="en"?(o.description_en||o.description||""):(o.description||"");});}); }
function addCatalogLanguageSwitches(){[["products","设备目录"],["config-catalog","配置目录"]].forEach(([view])=>{const header=$(`[data-view-panel="${view}"] .panel-header`);if(!header||$(".catalog-language",header))return;const box=document.createElement("div");box.className="catalog-language";box.innerHTML='<button type="button" class="active" data-catalog-lang="zh">中文</button><button type="button" data-catalog-lang="en">EN</button>';header.appendChild(box);box.addEventListener("click",e=>{const b=e.target.closest("[data-catalog-lang]");if(b)applyCatalogLanguage(b.dataset.catalogLang);});});}
function openConfigOptionEditor(option) {
  const form = $("#config-option-form");
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
    const sender = share.sender_name || share.sender_email || share.sender_phone || "未填写";
    const contact = share.sender_email || share.sender_phone || "—";
    const canReopen = isAdmin && !share.active && new Date(share.expires_at) > new Date();
    const actions = valid ? `<span class="table-actions"><button class="table-action" data-lookup-share="${escapeHtml(share.code)}">查看</button><details class="table-actions-menu"><summary aria-label="更多分享操作">更多</summary><div><button class="table-action" data-export-share="${escapeHtml(share.code)}">导出 PDF</button><button class="table-action" data-quote-share="${escapeHtml(share.code)}">报价</button>${isAdmin ? `<button class="table-action danger" data-close-share="${share.id}">关闭</button>` : ""}</div></details></span>` : canReopen ? `<button class="table-action" data-open-share="${share.id}">重新启用</button>` : "—";
    const itemCount = Number(share.item_count || 1);
    const itemCountLabel = share.document_version === 2 ? `${itemCount} 项` : `${itemCount} 台设备`;
    const statusText = !share.active ? "已关闭" : valid ? "有效" : "已过期";
    return `<tr><td><button class="share-code-button" data-lookup-share="${escapeHtml(share.code)}" ${valid ? "" : "disabled"}>${escapeHtml(share.code)}</button><br><small>${escapeHtml(formatDateTime(share.created_at))}</small></td><td>${escapeHtml(share.name)}<br><small>${escapeHtml(itemCountLabel)} · ${escapeHtml((share.product_summary || share.product_id || "").toUpperCase())}</small></td><td><strong>${escapeHtml(sender)}</strong><br><small>${escapeHtml(contact)}</small></td><td>${share.view_count} 次<br><small>${share.last_viewed_at ? escapeHtml(formatDateTime(share.last_viewed_at)) : "尚未查看"}</small></td><td>${formatDate(share.expires_at)}</td><td><span class="badge ${valid ? "good" : "off"}">${statusText}</span></td><td class="align-right">${actions}</td></tr>`;
  }).join("") || '<tr><td colspan="7" class="empty">暂无分享记录</td></tr>';
  const pages = Math.max(1, Math.ceil(state.shareTotal / state.sharePageSize));
  if ($("#share-page-summary")) $("#share-page-summary").textContent = `共 ${state.shareTotal} 条 · 第 ${state.sharePage}/${pages} 页`;
  if ($("#share-page-prev")) $("#share-page-prev").disabled = state.sharePage <= 1;
  if ($("#share-page-next")) $("#share-page-next").disabled = state.sharePage >= pages;
}

function renderQuotes() {
  const target = $("#quotes-table"); if (!target) return;
  target.innerHTML = state.quotes.map((quote) => { const symbol = quote.currency === "USD" ? "$" : "¥"; return `<tr><td><strong>${escapeHtml(quote.title)}</strong><br><small>${escapeHtml(quote.id.slice(0, 8))}</small></td><td>${escapeHtml(quote.display_name || quote.email || quote.phone || "—")}</td><td>${symbol}${Number(quote.total_price || 0).toLocaleString("zh-CN")}</td><td>${formatDate(quote.updated_at)}</td><td class="align-right"><button class="table-action" data-edit-quote="${escapeHtml(quote.id)}">编辑</button> <button class="table-action" data-export-quote="${escapeHtml(quote.id)}">导出PDF</button> <button class="table-action danger" data-delete-quote="${escapeHtml(quote.id)}">删除</button></td></tr>`; }).join("") || '<tr><td colspan="5" class="empty">暂无报价单</td></tr>';
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
  const salesViews = ["products", ...Object.keys(catalogViews), "shares", "quotes"];
  if (state.user?.role === "sales" && !salesViews.includes(view)) view = "products";
  const titles = { dashboard: "管理概览", products: "设备目录", "config-catalog": "配置目录", "tool-catalog": "工具目录", "accessory-catalog": "附件目录", users: "账号管理", shares: "分享记录", quotes: "报价管理", audit: "操作审计" };
  if (!titles[view]) view = state.user?.role === "admin" ? "dashboard" : "products";
  const catalogView = catalogViews[view];
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  $$(".view").forEach((panel) => panel.classList.toggle("active", panel.dataset.viewPanel === (catalogView ? "config-catalog" : view)));
  $("#view-title").textContent = titles[view];
  if (catalogView) {
    $("#catalog-view-eyebrow").textContent = catalogView.eyebrow;
    $("#catalog-view-title").textContent = catalogView.title;
    $("#catalog-view-description").textContent = catalogView.description;
    const catalogAction = $("#add-config-category");
    delete catalogAction.dataset.addCatalogCategory;
    delete catalogAction.dataset.addCatalogItem;
    catalogAction.hidden = false;
    if (catalogView.rootId === "catalog-optional") {
      catalogAction.textContent = "添加分类";
      catalogAction.dataset.addCatalogCategory = "";
    } else {
      catalogAction.textContent = catalogView.rootId === "catalog-tools" ? "添加工具" : "添加附件";
      catalogAction.dataset.addCatalogItem = catalogView.rootId;
    }
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
async function exportQuote(quote) {
  if (!quote?.id) { showToast("报价已保存，但未取得报价编号，请在报价管理中重试导出"); return false; }
  try {
    const response = await fetch(`${API_BASE}/api/v1/quotes/${encodeURIComponent(quote.id)}/pdf`, { headers: { Authorization: `Bearer ${sessionStorage.getItem(TOKEN_KEY)}` } });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `PDF生成失败（${response.status}）`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `quote-${quote.id.slice(0, 8)}.pdf`;
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
}

function openQuoteEditor({ quoteId = null, configId = null, title, items, currency = "CNY", sourceShareId = null, customerName = "", customerEmail = "", language = "zh" }) {
  const normalizedItems = (items || []).map((item) => ({
    ...item,
    quantity: toPositiveInteger(item.quantity),
    price: Math.max(0, toFiniteNumber(item.price))
  }));
  const dialog = document.createElement("dialog");
  dialog.className = "product-dialog quote-editor-dialog";
  dialog.dataset.dynamic = "true";
  dialog.innerHTML = `<form method="dialog" class="dialog-card quote-editor-card">
    <header><div><span class="eyebrow">QUOTATION</span><h2>${quoteId ? "修改报价" : "创建报价"}</h2></div><button class="icon-button" value="cancel" aria-label="关闭">×</button></header>
    <div class="quote-editor-meta">
      <label class="quote-title-field"><span>配置名称</span><input name="title" autocomplete="off" placeholder="例如：客户 A · CR1016 配置报价" value="${escapeHtml(title || "")}" required /></label>
      <div class="quote-currency-row"><label class="quote-currency-field"><span>报价货币</span><select name="currency" aria-label="报价货币"><option value="CNY" ${currency === "CNY" ? "selected" : ""}>CNY · 人民币</option><option value="USD" ${currency === "USD" ? "selected" : ""}>USD · 美元</option></select></label><button class="button button-secondary quote-auto-price" type="button">自动填价</button></div>
      <div class="quote-customer-row"><label><span>客户名称</span><input name="customer_name" autocomplete="organization" placeholder="填写客户或公司名称" value="${escapeHtml(customerName)}" /></label><label><span>客户邮箱</span><input name="customer_email" autocomplete="email" spellcheck="false" placeholder="用于报价单页头" value="${escapeHtml(customerEmail)}" /></label></div>
    </div>
    <p class="quote-editor-error" role="alert" hidden></p>
    <div class="quote-edit-list">
      <div class="quote-edit-head"><span>产品 / 配置</span><span>数量</span><span>单价</span></div>
      ${normalizedItems.length ? normalizedItems.map((item, index) => {
        const context = item.device_label || item.device || item.code || (item.kind === "product" ? "设备" : "可选配置");
        return `<div class="quote-edit-row"><div class="quote-item-name"><small>${escapeHtml(context)}</small><strong>${escapeHtml(item.name || "未命名项目")}</strong></div><input class="quote-qty-input" data-q="qty" data-i="${index}" aria-label="数量" type="number" min="1" step="1" value="${item.quantity}"><input class="quote-price-input" data-q="price" data-i="${index}" aria-label="单价" type="number" min="0" step="0.01" value="${item.price}"></div>`;
      }).join("") : '<div class="quote-edit-empty">暂无可报价项目，请返回分享配置重新选择。</div>'}
    </div>
    <div class="quote-total-row"><span>合计</span><strong class="quote-total">0</strong></div>
    <footer><button class="button button-quiet" value="cancel">取消</button><button class="button button-secondary" value="save">保存报价</button><button class="button button-primary" value="saveAndExport">保存并导出 PDF</button></footer>
  </form>`;
  document.body.appendChild(dialog);
  const totalElement = $(".quote-total", dialog);
  const errorElement = $(".quote-editor-error", dialog);
  const setQuoteError = (message = "") => { errorElement.textContent = message; errorElement.hidden = !message; };
  const collectQuoteItems = () => normalizedItems.map((item, index) => ({
    ...item,
    quantity: toPositiveInteger($(`[data-q="qty"][data-i="${index}"]`, dialog).value),
    price: Math.max(0, toFiniteNumber($(`[data-q="price"][data-i="${index}"]`, dialog).value))
  }));
  const updateTotal = () => {
    const total = collectQuoteItems().reduce((sum, item) => sum + item.price * item.quantity, 0);
    const selectedCurrency = $("[name=currency]", dialog).value;
    totalElement.textContent = `${selectedCurrency} ${total.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    return total;
  };
  dialog.addEventListener("input", () => { setQuoteError(); updateTotal(); });
  dialog.addEventListener("change", updateTotal);
  $(".quote-auto-price", dialog).addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "读取中…";
    try {
      const prices = await api("/api/v1/staff/reference-prices");
      const selectedCurrency = $("[name=currency]", dialog).value;
      const normalizeCode = (value) => String(value || "").replace(/[^a-z0-9]/gi, "").toUpperCase();
      const productMap = new Map((prices.products || []).flatMap((product) => [[normalizeCode(product.id), product], [normalizeCode(product.name), product]]));
      const optionMap = new Map((prices.options || []).flatMap((option) => [[normalizeCode(option.id), option], [normalizeCode(option.code), option]]));
      let matched = 0;
      normalizedItems.forEach((item, index) => {
        const hasSnapshotPrice = Object.prototype.hasOwnProperty.call(item, "price_cny") || Object.prototype.hasOwnProperty.call(item, "price_usd");
        const snapshotPrice = selectedCurrency === "USD" ? toFiniteNumber(item.price_usd) : toFiniteNumber(item.price_cny);
        if (hasSnapshotPrice) {
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
    try { await runButtonAction(event.submitter, "正在保存…", async () => {
      const savedQuote = await api("/api/v1/quotes", { method: "POST", body: JSON.stringify({ quote_id: quoteId, config_id: configId, title: quoteTitle, items: finalItems, total_price: total, currency: $("[name=currency]", dialog).value, source_share_id: sourceShareId, customer_name: $("[name=customer_name]", dialog).value.trim(), customer_email: $("[name=customer_email]", dialog).value.trim(), language }) });
      const exported = action === "saveAndExport" ? await exportQuote(savedQuote) : false;
      dialog.close(); dialog.remove();
      showToast(action === "saveAndExport" ? (exported ? "报价单已保存并开始下载 PDF" : "报价单已保存，但 PDF 下载失败") : (quoteId ? "报价单已更新" : "报价单已保存"));
      await loadData();
    }); } catch (error) { setQuoteError(error.message || "保存报价失败，请检查填写内容后重试。"); }
  });
  updateTotal();
  dialog.showModal();
}

async function editQuote(quote) {
  openQuoteEditor({ quoteId: quote.id, configId: quote.config_id, title: quote.title, items: quote.items, currency: quote.currency || "CNY", sourceShareId: quote.source_share_id, customerName: quote.customer_name, customerEmail: quote.customer_email, language: quote.language || "zh" });
}

function plainDescription(value) {
  return String(value || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function renderShareDetail(share) {
  const shareItems = share.items?.length ? share.items : [{ snapshot: share.snapshot, display_name: share.name }];
  const deviceItems = shareItems.filter((item) => (item.item_type || "device_config") === "device_config");
  const devices = deviceItems.map((shareItem, index) => {
    const snapshot = shareItem.snapshot || {};
    const categoryList = snapshot.categories || [];
    const baseCategoryIds = new Set(["motor", "voltage", "channel"]);
    const singleValue = (id) => {
      const category = categoryList.find((item) => item.id === id);
      return category?.options?.[0]?.name || "未选择";
    };
    const categories = categoryList.filter((category) => !baseCategoryIds.has(category.id)).map((category) => {
      const options = (category.options || []).map((option) => {
        const description = plainDescription(option.description);
        return `<li><strong>${escapeHtml(option.name)}</strong>${description ? `<span>${escapeHtml(description)}</span>` : ""}</li>`;
      }).join("");
      return `<section class="share-detail-group"><header><span>${escapeHtml(category.name)}</span><small>${category.options.length} 项</small></header><ul>${options}</ul></section>`;
    }).join("");
    const basics = [
      ["型号", snapshot.product?.name || "未填写"],
      ["名称", snapshot.product?.title_name || "未填写"],
      ["颜色", snapshot.color?.label || snapshot.color?.code || "未选择"],
      ["电机", singleValue("motor")],
      ["电源", singleValue("voltage")],
      ["通道", categoryList.some((item) => item.id === "channel") ? singleValue("channel") : "未配置"]
    ].map(([label, value]) => `<div><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
    return `<article class="share-device-block"><h4>设备 ${index + 1} · ${escapeHtml(snapshot.product?.name || "未填写")}</h4><section class="share-detail-group share-device-basics"><header><span>设备信息</span><small>型号与基本配置</small></header><div class="share-basic-list">${basics}</div></section><div class="share-detail-groups">${categories || '<div class="empty">该设备未选择其他选配项目</div>'}</div></article>`;
  }).join("");
  const catalogSections = [["tool", "维修工具"], ["accessory", "设备附件"]].map(([type, label]) => {
    const entries = shareItems.filter((item) => item.item_type === type);
    if (!entries.length) return "";
    const rows = entries.map((entry) => {
      const snapshot = entry.snapshot || {};
      return `<li><strong>${escapeHtml([snapshot.code, snapshot.name || entry.display_name].filter(Boolean).join(" · ") || "—")}</strong><span>数量：${Number(entry.quantity || snapshot.quantity || 1)}</span></li>`;
    }).join("");
    return `<article class="share-device-block share-catalog-block"><h4>${label}</h4><section class="share-detail-group"><header><span>${label}</span><small>${entries.length} 项</small></header><ul>${rows}</ul></section></article>`;
  }).join("");
  const sender = share.sender_name || "未填写姓名";
  const contact = share.sender_email || share.sender_phone || "未填写联系方式";
  const summaryParts = [];
  if (deviceItems.length) summaryParts.push(`${deviceItems.length} 台设备`);
  const catalogCount = shareItems.length - deviceItems.length;
  if (catalogCount) summaryParts.push(`${catalogCount} 项工具或附件`);
  return `<header class="share-result-header"><div><span class="eyebrow">CONFIGURATION ${escapeHtml(share.code)}</span><h3>${escapeHtml(summaryParts.join(" · ") || "分享配置")}</h3></div><span class="badge good">有效至 ${formatDate(share.expires_at)}</span></header><div class="share-device-summary"><div><span>发送用户</span><strong>${escapeHtml(sender)}</strong><small>${escapeHtml(contact)}</small></div></div>${devices}${catalogSections}`;
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
  shareDrawerElement.innerHTML = `<header class="share-drawer-header"><div><span class="eyebrow">SHARE PREVIEW</span><h2>分享详情</h2></div><button class="icon-button" type="button" data-share-drawer-close aria-label="关闭">×</button></header><div class="share-drawer-body" data-share-drawer-body></div><footer class="share-drawer-footer"><button class="button button-secondary" type="button" data-share-export disabled>导出 PDF</button><button class="button button-primary" type="button" data-share-quote disabled>报价</button></footer>`;
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
  const exportButton = $("[data-share-export]", shareDrawerElement);
  const quoteButton = $("[data-share-quote]", shareDrawerElement);
  body.innerHTML = content;
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
  try {
    const response = await fetch(`${API_BASE}/api/v1/shares/${encodeURIComponent(code)}/pdf`, { headers: { Authorization: `Bearer ${sessionStorage.getItem(TOKEN_KEY)}` } });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `PDF生成失败（${response.status}）`);
    }
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = `shared-configuration-${code}.pdf`; link.style.display = "none"; document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (failure) { showToast(failure.message); }
}

async function quoteShare(code) {
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
      items.push({ kind: "product", source_id: product.id, name: product.title_name || product.name || "设备", device_label: deviceLabel, code: product.name || product.id, price: baseCny, price_cny: baseCny, price_usd: baseUsd, quantity: 1 });

      const priceLines = (value) => new Map(((value || {}).lines || []).map((line) => [line.source_id, toFiniteNumber(line.amount)]));
      const cnyLines = priceLines(cnyPricing);
      const usdLines = priceLines(usdPricing);
      (snapshot.categories || []).forEach((category) => (category.options || []).forEach((option) => {
        if (["motor", "voltage", "channel"].includes(category.id) && category.id !== "voltage") return;
        const priceCny = cnyLines.has(option.id) ? cnyLines.get(option.id) : toFiniteNumber(option.price_cny ?? option.price);
        const priceUsd = usdLines.has(option.id) ? usdLines.get(option.id) : toFiniteNumber(option.price_usd);
        items.push({ kind: category.id === "voltage" ? "surcharge" : "option", source_id: option.id, name: option.name, device_label: deviceLabel, code: option.code || "", price: priceCny, price_cny: priceCny, price_usd: priceUsd, quantity: 1 });
      }));
    });
    openQuoteEditor({ configId: share.config_id, title: `分享配置 ${code}`, items, currency: "CNY", sourceShareId: share.id, customerName: share.customer_name || share.sender_name || "", customerEmail: share.customer_email || share.sender_email || "", language: state.catalogLanguage === "en" ? "en" : "zh" });
  } catch (failure) { showToast(failure.message); }
}

async function logout() {
  try { await api("/api/v1/auth/logout", { method: "POST" }); } catch (_) {}
  sessionStorage.removeItem(TOKEN_KEY); state.user = null; $("#admin-app").hidden = true; $("#login-page").hidden = false;
}

function openSidebar() { $("#sidebar").classList.add("open"); $("#sidebar-backdrop").hidden = false; }
function closeSidebar() { $("#sidebar").classList.remove("open"); $("#sidebar-backdrop").hidden = true; }
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
    $("#share-filter-form").reset(); state.shareQuery = ""; state.shareStatus = "all"; state.shareProduct = ""; state.shareCreatedFrom = ""; state.shareCreatedTo = ""; state.sharePage = 1;
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
  $("#refresh-audit")?.addEventListener("click", loadData);
  addLanguageToggles(); addProductButton(); addCatalogLanguageSwitches();
  $("#menu-button").addEventListener("click", openSidebar);
  $("#sidebar-backdrop").addEventListener("click", closeSidebar);
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".catalog-more")) document.querySelectorAll(".catalog-more[open]").forEach((menu) => { menu.removeAttribute("open"); });
    const imageButton = event.target.closest("[data-pick-image]"); if (imageButton) { imageButton.closest(".image-path-control, .color-image-control")?.querySelector("[data-image-file]")?.click(); return; }
    const cancelButton = event.target.closest('button[value="cancel"]'); if (cancelButton) { const dialog = cancelButton.closest("dialog"); if (dialog) { if (dialog.classList.contains("confirm-dialog")) return; event.preventDefault(); const form = $("form", dialog); const dirty = dialog.classList.contains("account-dialog") && form?.dataset.initialSnapshot && form.dataset.initialSnapshot !== JSON.stringify(Object.fromEntries(new FormData(form))); if (dirty) { confirmAction("放弃未保存修改", "当前修改尚未保存，确定关闭吗？", "放弃修改").then((confirmed) => { if (confirmed) dialog.close(); }); } else dialog.close(); if (dialog.dataset.dynamic === "true") dialog.remove(); return; } }
    const userButton = event.target.closest("[data-user-status]"); if (userButton) setUserStatus(userButton);
    const editUserButton = event.target.closest("[data-edit-user]"); if (editUserButton) { const user = findUser(editUserButton.dataset.editUser); if (user) openUserEditor(user, editUserButton); }
    const roleButton = event.target.closest("[data-edit-user-role]"); if (roleButton) { const user = findUser(roleButton.dataset.editUserRole); if (user) openRoleEditor(user, roleButton); }
    const passwordButton = event.target.closest("[data-reset-user-password]"); if (passwordButton) { const user = findUser(passwordButton.dataset.resetUserPassword); if (user) openPasswordEditor(user, passwordButton); }
    const archiveButton = event.target.closest("[data-archive-user]"); if (archiveButton) { const user = findUser(archiveButton.dataset.archiveUser); if (user) openArchiveEditor(user, archiveButton); }
    const restoreButton = event.target.closest("[data-restore-user]"); if (restoreButton) restoreUser(restoreButton);
    const shareButton = event.target.closest("[data-close-share]"); if (shareButton) closeShare(shareButton);
    const reopenShareButton = event.target.closest("[data-open-share]"); if (reopenShareButton) reopenShare(reopenShareButton);
    const quoteButton = event.target.closest("[data-delete-quote]"); if (quoteButton) deleteQuote(quoteButton);
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

function categoryCard(category = null) { catalogEditorCard({ title: category ? "编辑配置分类" : "添加配置分类", size:"small", fields: [{name:"name",label:"分类标题",lang:"zh",value:category?.name,placeholder:"例如：CRI 共轨套件",required:true},{name:"description",label:"分类描述",lang:"zh",type:"textarea",value:category?.description,placeholder:"例如：适用于共轨喷油器测试"},{name:"name_en",label:"分类标题",lang:"en",value:category?.name_en,placeholder:"例如：CRI Common Rail Kits"},{name:"description_en",label:"分类描述",lang:"en",type:"textarea",value:category?.description_en,placeholder:"例如：Kits for common rail injector testing"}], onSave: data => api(category ? `/api/v1/admin/config-catalog/categories/${category.id}` : "/api/v1/admin/config-catalog/categories", {method:category?"PATCH":"POST",body:JSON.stringify({...data,multiple:true})}), onDelete: category ? () => deleteConfigCategory(category) : null }); }

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
  try{await runButtonAction(event.submitter,"正在保存…",async()=>{await api(`/api/v1/admin/config-catalog/options/${form.elements.option_id.value}`,{method:"PATCH",body:JSON.stringify(payload)});$("#config-option-dialog").close();showToast("配置条目已保存");await loadData();});}catch(failure){const error=$("#config-option-error");error.textContent=failure.message;error.hidden=false;}
}

document.addEventListener("DOMContentLoaded", async () => {
  restoreUserFilterState(); bindEvents(); await checkApi(); await restoreSession();
});
document.addEventListener("click", (event) => {
  if (event.target.closest("[data-catalog-lang]")) setTimeout(renderProducts, 0);
});
