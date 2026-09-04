const USER_TOKEN_KEY = "boten_user_token";
const ADMIN_TOKEN_KEY = "boten_admin_token";
let currentUser = null;
let authMode = "login";
let authIdentifierMode = "email";
let pendingAuthenticatedAction = null;
const authSubscribers = [];
let phoneCountries = [];
let authSubmitting = false;
const authText = (key, zh, en) => {
  const translated = window.botenI18n?.t(key);
  return translated && translated !== key ? translated : (localStorage.getItem("boten-language") === "en" ? en : zh);
};

function refreshAuthCopy() {
  const text = (key, zh, en) => authText(key, zh, en);
  document.querySelectorAll('[data-auth-text="name"]').forEach((item) => { item.textContent = text("name", "姓名", "Name"); });
  document.querySelectorAll('[data-auth-text="email"]').forEach((item) => { item.textContent = text("email", "邮箱", "Email"); });
  document.querySelectorAll('[data-auth-text="phone"]').forEach((item) => { item.textContent = text("phone", "手机号", "Phone"); });
  document.querySelectorAll('[data-auth-text="country"]').forEach((item) => { item.textContent = text("country", "国家", "Country"); });
  document.querySelectorAll(".auth-method-tab").forEach((tab) => { tab.textContent = text(tab.dataset.authIdentifier, tab.dataset.authIdentifier === "email" ? "邮箱" : "手机号", tab.dataset.authIdentifier === "email" ? "Email" : "Phone"); });
  document.querySelector(".auth-method-tabs")?.setAttribute("aria-label", text("loginMethod", "登录方式", "Sign-in method"));
  document.getElementById("auth-name")?.setAttribute("placeholder", text("nameHint", "请输入姓名", "Your name"));
  document.getElementById("auth-email")?.setAttribute("placeholder", text("emailHint", "name@example.com", "name@example.com"));
  document.getElementById("auth-country")?.setAttribute("aria-label", text("country", "国家", "Country"));
  document.getElementById("auth-phone")?.setAttribute("aria-label", text("phoneNumber", "实际手机号", "Phone number"));
  document.getElementById("auth-phone")?.setAttribute("placeholder", text("phoneHint", "1590000000", "1590000000"));
  document.getElementById("auth-password-label").textContent = text("password", "密码", "Password");
  document.getElementById("auth-password")?.setAttribute("placeholder", text("passwordHint", "至少 8 个字符", "8+ characters"));
  document.getElementById("auth-close")?.setAttribute("aria-label", text("close", "关闭", "Close"));
  const accountCopy = { email: ["邮箱", "Email"], phone: ["手机号", "Phone number"], currentPassword: ["当前密码", "Current password"], newPassword: ["新密码", "New password"], confirmPassword: ["确认新密码", "Confirm password"] };
  document.querySelectorAll("[data-account-copy]").forEach((item) => { const copy = accountCopy[item.dataset.accountCopy]; if (copy) item.textContent = text(item.dataset.accountCopy, copy[0], copy[1]); });
  document.querySelector('[data-account-section="contact"]')?.replaceChildren(document.createTextNode(text("contactInfo", "联系方式", "Contact details")));
  document.querySelector('[data-account-section="password"]')?.replaceChildren(document.createTextNode(text("changePassword", "修改密码", "Change password")));
  document.getElementById("account-manage").textContent = text("accountManage", "账号管理", "Account management");
  document.getElementById("account-logout").textContent = text("logout", "退出登录", "Sign out");
  document.getElementById("account-admin-entry").textContent = text("enterAdmin", "进入后台", "Open admin");
  document.getElementById("profile-contact-submit").textContent = text("saveRelogin", "保存并重新登录", "Save and sign in again");
  document.getElementById("profile-password-submit").textContent = text("changeRelogin", "修改密码并重新登录", "Change password and sign in again");
  document.getElementById("account-manage-back").textContent = text("back", "返回", "Back");
}

class AuthRequestError extends Error {
  constructor(message, { code = "REQUEST_FAILED", field = null, status = 0, requestId = "", retryAfter = 0 } = {}) {
    super(message); this.name = "AuthRequestError"; this.code = code; this.field = field; this.status = status; this.requestId = requestId; this.retryAfter = retryAfter;
  }
}

const AUTH_ERROR_COPY = {
  ACCOUNT_EMAIL_INVALID: ["请输入有效的邮箱地址。", "Enter a valid email address."],
  ACCOUNT_EMAIL_DUPLICATE: ["该邮箱已被其他账号使用。", "This email is already used by another account."],
  ACCOUNT_PHONE_INVALID: ["手机号格式或长度与所选国家不匹配。", "Enter a valid phone number for the selected country."],
  ACCOUNT_PHONE_DUPLICATE: ["该手机号已被其他账号使用。", "This phone number is already used by another account."],
  ACCOUNT_PHONE_COUNTRY_INVALID: ["请选择有效国家。", "Select a valid country."],
  ACCOUNT_CONTACT_REQUIRED: ["邮箱和手机号至少保留一项。", "Keep at least an email address or phone number."],
  ACCOUNT_NAME_REQUIRED: ["请填写姓名。", "Enter your name."],
  ACCOUNT_PASSWORD_TOO_SHORT: ["密码至少需要 8 个字符。", "The password must contain at least 8 characters."],
  ACCOUNT_PASSWORD_TOO_LONG: ["密码不能超过 128 个字符。", "The password cannot exceed 128 characters."],
  ACCOUNT_CURRENT_PASSWORD_INVALID: ["当前密码不正确，请重新输入。", "The current password is incorrect. Try again."],
  ACCOUNT_PASSWORD_CONFIRMATION_MISMATCH: ["两次输入的新密码不一致。", "The new passwords do not match."],
  ACCOUNT_IDENTIFIER_REQUIRED: ["请填写邮箱或手机号。", "Enter an email address or phone number."],
  ACCOUNT_CREDENTIALS_INVALID: ["账号或密码不正确，请重新输入。", "The account or password is incorrect. Try again."],
  ACCOUNT_SESSION_EXPIRED: ["登录状态已失效，请重新登录。", "Your session has expired. Sign in again."],
  ACCOUNT_PERMISSION_DENIED: ["当前账号没有执行此操作的权限。", "Your account does not have permission for this action."],
  ACCOUNT_RATE_LIMITED: ["尝试次数过多，请稍后再试。", "Too many attempts. Try again later."],
  ACCOUNT_VALIDATION_FAILED: ["请检查填写内容后重试。", "Check the entered information and try again."],
  SERVER_UNAVAILABLE: ["服务器暂时无法处理请求，请稍后重试。", "The server cannot complete the request right now. Try again later."],
  REQUEST_TIMEOUT: ["服务器响应超时，请确认网络后重试。", "The server took too long to respond. Check your connection and try again."],
  NETWORK_UNAVAILABLE: ["网络暂不可用，请检查连接或服务状态后重试。", "Network unavailable. Check your connection or service status and try again."]
};

function authErrorCopy(code) {
  const copy = AUTH_ERROR_COPY[code];
  return copy?.[localStorage.getItem("boten-language") === "en" ? 1 : 0];
}

async function authRequest(path, options = {}) {
  const token = sessionStorage.getItem(USER_TOKEN_KEY);
  const { timeout = 15000, ...requestOptions } = options;
  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(`${CATALOG_API_BASE}/api/v1${path}`, {
      ...requestOptions,
      headers: {
        "Content-Type": "application/json",
        "X-UI-Language": localStorage.getItem("boten-language") === "en" ? "en" : "zh-CN",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(requestOptions.headers || {})
      },
      signal: controller.signal
    });
    if (response.status === 204) return null;
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const code = body.error?.code || response.headers.get("X-Error-Code") || `HTTP_${response.status}`;
      const requestId = body.request_id || response.headers.get("X-Request-ID") || "";
      const message = response.status >= 500 ? authErrorCopy("SERVER_UNAVAILABLE") : (authErrorCopy(code) || body.detail || `${authText("requestFailed", "请求失败", "Request failed")} (${response.status})`);
      throw new AuthRequestError(message, { code, field: body.error?.field, status: response.status, requestId, retryAfter: Number(response.headers.get("Retry-After") || 0) });
    }
    return body;
  } catch (failure) {
    if (failure instanceof AuthRequestError) throw failure;
    if (failure?.name === "AbortError") throw new AuthRequestError(authErrorCopy("REQUEST_TIMEOUT"), { code: "REQUEST_TIMEOUT" });
    throw new AuthRequestError(authErrorCopy("NETWORK_UNAVAILABLE"), { code: "NETWORK_UNAVAILABLE" });
  } finally {
    clearTimeout(timeoutHandle);
  }
}

function isAuthenticated() {
  return Boolean(currentUser && currentUser.role !== "guest");
}

function subscribeAuth(listener) {
  authSubscribers.push(listener);
}

function notifyAuth() {
  renderAccountState();
  authSubscribers.forEach((listener) => listener(currentUser));
}

function setAuthMode(mode) {
  authMode = mode;
  refreshAuthCopy();
  document.querySelectorAll(".register-only").forEach((field) => { field.hidden = mode !== "register"; });
  document.getElementById("auth-name").required = mode === "register";
  document.getElementById("auth-title").textContent = mode === "register" ? authText("createAccount", "创建账号", "Create account") : authText("loginTitle", "登录账号", "Sign in");
  document.getElementById("auth-submit").textContent = mode === "register" ? authText("registerContinue", "注册并继续", "Register") : authText("login", "登录", "Sign in");
  document.getElementById("auth-password").autocomplete = mode === "register" ? "new-password" : "current-password";
  const isEnglish = localStorage.getItem("boten-language") === "en";
  document.getElementById("auth-mode-switch").innerHTML = mode === "register"
    ? `${isEnglish ? "Already have an account?" : "已有账号？"}<button class="auth-link" type="button" data-auth-mode="login">${authText("login", "登录", "Sign in")}</button>`
    : `${isEnglish ? "New here?" : "还没有账号？"}<button class="auth-link" type="button" data-auth-mode="register">${authText("register", "注册", "Register")}</button>`;
  refreshAuthIdentifierFields();
  document.getElementById("auth-error").hidden = true;
}

function setAuthIdentifierMode(mode) {
  authIdentifierMode = mode;
  refreshAuthIdentifierFields();
  document.getElementById("auth-error").hidden = true;
}

function refreshAuthIdentifierFields() {
  const isRegister = authMode === "register";
  const isEmail = authIdentifierMode === "email";
  document.querySelectorAll(".auth-method-tab").forEach((tab) => { const active = tab.dataset.authIdentifier === authIdentifierMode; tab.classList.toggle("active", active); tab.setAttribute("aria-selected", String(active)); tab.tabIndex = active ? 0 : -1; });
  document.querySelector(".auth-method-tabs").hidden = isRegister;
  document.getElementById("auth-email-field").hidden = !isRegister && !isEmail;
  document.getElementById("auth-phone-field").hidden = !isRegister && isEmail;
  document.getElementById("auth-email").required = isRegister || isEmail;
  document.getElementById("auth-phone").required = isRegister || !isEmail;
  document.getElementById("auth-country").required = isRegister || !isEmail;
}

function authPhone(prefix = "auth") {
  const country = document.getElementById(`${prefix}-country`).value;
  const phone = document.getElementById(`${prefix}-phone`).value.trim().replace(/\s+/g, "");
  if (!country || !/^\d{6,15}$/.test(phone)) throw new Error(authText("invalidPhone", "请选择国家并输入有效手机号", "Select a country and enter a valid phone number"));
  return { country, phone };
}

function authIdentifier() {
  return authIdentifierMode === "email" ? document.getElementById("auth-email").value.trim().toLowerCase() : "";
}

function updateCallingCode(prefix = "auth") {
  const country = phoneCountries.find((item) => item.code === document.getElementById(`${prefix}-country`)?.value);
  const output = document.getElementById(`${prefix}-calling-code`);
  if (output) output.textContent = country?.calling_code || "—";
}

async function loadPhoneCountries() {
  const language = localStorage.getItem("boten-language") === "en" ? "en" : "zh";
  try {
    const response = await fetch(`${CATALOG_API_BASE}/api/v1/auth/countries?lang=${language}`);
    if (!response.ok) throw new Error("country list failed");
    phoneCountries = (await response.json()).items || [];
  } catch (_) {
    phoneCountries = [{ code: "CN", name: language === "en" ? "China" : "中国", calling_code: "+86" }];
  }
  ["auth", "profile"].forEach((prefix) => {
    const select = document.getElementById(`${prefix}-country`);
    if (!select) return;
    const previous = select.value || localStorage.getItem("boten-phone-country") || "CN";
    select.innerHTML = `<option value="">${language === "en" ? "Select country" : "请选择国家"}</option>` + phoneCountries.map((item) => `<option value="${item.code}">${item.name}</option>`).join("");
    select.value = phoneCountries.some((item) => item.code === previous) ? previous : "";
    updateCallingCode(prefix);
  });
}

function openAuthDialog(mode = "login") {
  const dialog = document.getElementById("auth-dialog");
  if (isAuthenticated()) {
    document.getElementById("auth-form-view").hidden = true;
    document.getElementById("account-view").hidden = false;
    document.getElementById("account-manage-view").hidden = true;
    document.getElementById("auth-title").textContent = authText("account", "账号", "Account");
  } else {
    document.getElementById("auth-form-view").hidden = false;
    document.getElementById("account-view").hidden = true;
    document.getElementById("account-manage-view").hidden = true;
    setAuthMode(mode);
  }
  if (!dialog.open) dialog.showModal();
}

function requireLogin(action) {
  if (isAuthenticated()) {
    return Promise.resolve(action());
  }
  pendingAuthenticatedAction = action;
  openAuthDialog("login");
  return Promise.resolve(false);
}

function renderAccountState() {
  const label = document.getElementById("account-label");
  if (!label) return;
  const role = String(currentUser?.role || "").trim().toLowerCase();
  const canEnterAdmin = isAuthenticated() && (role === "admin" || role === "sales");
  const adminEntry = document.getElementById("account-admin-entry");
  adminEntry.toggleAttribute("hidden", !canEnterAdmin);
  adminEntry.setAttribute("aria-hidden", String(!canEnterAdmin));
  label.textContent = isAuthenticated() ? (currentUser.display_name || currentUser.email || currentUser.phone || authText("accountFallback", "账号", "Account")) : authText("login", "登录", "Sign in");
  if (isAuthenticated()) {
    const display = currentUser.display_name || `BOTEN ${authText("user", "用户", "User")}`;
    document.getElementById("account-avatar").textContent = display.charAt(0).toUpperCase();
    document.getElementById("account-name").textContent = display;
    document.getElementById("account-contact").textContent = currentUser.email || currentUser.phone || "";
    document.getElementById("account-role").textContent = { customer: authText("customer", "客户", "Customer"), sales: authText("sales", "业务员", "Sales"), admin: authText("admin", "管理员", "Admin") }[currentUser.role] || currentUser.role;
  }
}

function enterAdmin() {
  if (!isAuthenticated() || !["admin", "sales"].includes(currentUser.role)) return;
  const token = sessionStorage.getItem(USER_TOKEN_KEY);
  if (!token) return;
  sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
  // The new same-origin window receives a copy of this sessionStorage at open
  // time, allowing the admin page to validate the existing session normally.
  const adminWindow = window.open("./admin/", "boten-admin-workspace", "popup,width=1280,height=900");
  if (!adminWindow) return;
  adminWindow.focus();
}

async function submitAuth(event) {
  event.preventDefault();
  if (authSubmitting) return;
  authSubmitting = true;
  const error = document.getElementById("auth-error");
  const submit = document.getElementById("auth-submit");
  const password = document.getElementById("auth-password").value;
  error.hidden = true;
  document.querySelectorAll("#auth-form [aria-invalid]").forEach((field) => field.removeAttribute("aria-invalid"));
  submit.disabled = true;
  submit.setAttribute("aria-busy", "true");
  submit.textContent = authMode === "register" ? authText("registering", "注册中…", "Registering…") : authText("signingIn", "登录中…", "Signing in…");
  try {
    if (authMode === "register" && !document.getElementById("auth-name").value.trim()) throw new Error(authText("nameHint", "请输入姓名", "Enter your name"));
    if ((authMode === "register" || authIdentifierMode === "email") && !document.getElementById("auth-email").value.trim()) throw new Error(authText("emailHint", "请输入邮箱", "Enter your email"));
    if (!password) throw new Error(authText("passwordHint", "请输入密码", "Enter your password"));
    if (authMode === "register" && password.length < 8) throw new Error(authText("passwordHint", "密码至少 8 个字符", "Password must be at least 8 characters"));
    const payload = authMode === "register"
      ? {
          display_name: document.getElementById("auth-name").value.trim(),
          email: document.getElementById("auth-email").value.trim().toLowerCase(),
          password
        }
      : (authIdentifierMode === "email" ? { identifier: authIdentifier(), password } : { phone_country: authPhone().country, phone: authPhone().phone, password });
    if (authMode === "register") {
      const parsedPhone = authPhone();
      payload.phone_country = parsedPhone.country;
      payload.phone = parsedPhone.phone;
    }
    const result = await authRequest(`/auth/${authMode}`, { method: "POST", body: JSON.stringify(payload) });
    sessionStorage.setItem(USER_TOKEN_KEY, result.session.token);
    currentUser = result.user;
    notifyAuth();
    document.getElementById("auth-dialog").close();
    document.getElementById("auth-form").reset();
    const action = pendingAuthenticatedAction;
    pendingAuthenticatedAction = null;
    if (action) await action();
  } catch (failure) {
    error.textContent = formatAuthError(failure, authMode === "register" ? "register" : "login");
    error.hidden = false;
    const candidates = authMode === "register"
      ? [document.getElementById("auth-name"), document.getElementById("auth-email"), document.getElementById("auth-country"), document.getElementById("auth-phone"), document.getElementById("auth-password")]
      : [document.getElementById(authIdentifierMode === "email" ? "auth-email" : "auth-phone"), document.getElementById("auth-password")];
    const fieldMap = { display_name: "auth-name", email: "auth-email", phone_country: "auth-country", phone: "auth-phone", identifier: authIdentifierMode === "email" ? "auth-email" : "auth-phone", password: "auth-password" };
    const target = document.getElementById(fieldMap[failure.field]) || candidates.find((field) => field && !field.value.trim()) || (failure.code === "ACCOUNT_CREDENTIALS_INVALID" ? document.getElementById("auth-password") : candidates[0]);
    target?.setAttribute("aria-invalid", "true"); target?.focus();
  } finally {
    authSubmitting = false;
    submit.disabled = false;
    submit.removeAttribute("aria-busy");
    submit.textContent = authMode === "register" ? authText("registerContinue", "注册并继续", "Register") : authText("login", "登录", "Sign in");
  }
}

async function logoutUser() {
  try { await authRequest("/auth/logout", { method: "POST" }); } catch (_) {}
  sessionStorage.removeItem(USER_TOKEN_KEY);
  sessionStorage.removeItem(ADMIN_TOKEN_KEY);
  currentUser = null;
  pendingAuthenticatedAction = null;
  document.getElementById("auth-dialog").close();
  notifyAuth();
}

function openAccountManager() {
  if (!isAuthenticated()) return;
  document.getElementById("account-view").hidden = true;
  document.getElementById("account-manage-view").hidden = false;
  document.getElementById("auth-title").textContent = authText("accountManage", "账号管理", "Account management");
  document.getElementById("profile-email").value = currentUser.email || "";
  document.getElementById("profile-phone").value = currentUser.phone || "";
  document.getElementById("profile-country").value = currentUser.phone_country || "CN";
  updateCallingCode("profile");
}

async function saveContact(event) {
  event.preventDefault();
  const error = document.getElementById("profile-contact-error"); error.hidden = true;
  try {
    const country = document.getElementById("profile-country").value;
    const phone = document.getElementById("profile-phone").value.trim();
    const email = document.getElementById("profile-email").value.trim();
    const currentPassword = document.getElementById("profile-contact-password").value;
    if (!currentPassword) throw new Error(authText("currentPasswordRequired", "请输入当前密码", "Enter your current password"));
    if (!email && !phone) throw new Error(authText("contactRequired", "请至少填写邮箱或手机号", "Enter an email or phone number"));
    const payload = { current_password: currentPassword, email };
    if (phone) { const parsedPhone = authPhone("profile"); payload.phone_country = parsedPhone.country; payload.phone = parsedPhone.phone; }
    await authRequest("/auth/profile/contact", { method: "PATCH", body: JSON.stringify(payload) });
    if (country) localStorage.setItem("boten-phone-country", country);
    await logoutUser();
  } catch (failure) { error.textContent = formatAuthError(failure, "contact"); error.hidden = false; }
}

async function savePassword(event) {
  event.preventDefault();
  const error = document.getElementById("profile-password-error"); error.hidden = true;
  try {
    const currentPassword = document.getElementById("profile-current-password").value;
    const newPassword = document.getElementById("profile-new-password").value;
    const confirmPassword = document.getElementById("profile-confirm-password").value;
    if (!currentPassword) throw new Error(authText("currentPasswordRequired", "请输入当前密码", "Enter your current password"));
    if (newPassword.length < 8) throw new Error(authText("newPasswordLength", "新密码至少 8 个字符", "New password must be at least 8 characters"));
    if (newPassword !== confirmPassword) throw new Error(authText("passwordMismatch", "两次输入的新密码不一致", "New passwords do not match"));
    await authRequest("/auth/change-password", { method: "POST", body: JSON.stringify({ current_password: currentPassword, new_password: newPassword, confirm_password: confirmPassword }) });
    await logoutUser();
  } catch (failure) { error.textContent = formatAuthError(failure, "password"); error.hidden = false; }
}

function formatAuthError(error, context = "login") {
  const lang = localStorage.getItem("boten-language") === "en";
  const translated = authErrorCopy(error?.code);
  if (translated) {
    if (error.code === "ACCOUNT_RATE_LIMITED" && error.retryAfter) return lang ? `${translated} Retry in about ${error.retryAfter} seconds.` : `${translated} 约 ${error.retryAfter} 秒后可重试。`;
    if (error.code === "SERVER_UNAVAILABLE" && error.requestId) return lang ? `${translated} Reference: ${error.requestId}` : `${translated} 问题编号：${error.requestId}`;
    return translated;
  }
  if (context === "password") return lang ? "Password change failed. Check your current password and requirements." : "修改密码失败，请检查当前密码和新密码要求。";
  if (context === "contact") return lang ? "Account details could not be saved. Check the fields and current password." : "账号信息保存失败，请检查填写内容和当前密码。";
  return error?.message || (lang ? "Unable to complete the request." : "操作未完成，请稍后重试。");
}

async function initAuth() {
  document.getElementById("account-toggle")?.addEventListener("click", () => openAuthDialog());
  document.getElementById("auth-close")?.addEventListener("click", () => document.getElementById("auth-dialog").close());
  document.getElementById("account-logout")?.addEventListener("click", logoutUser);
  document.getElementById("account-manage")?.addEventListener("click", openAccountManager);
  document.getElementById("account-manage-back")?.addEventListener("click", () => { document.getElementById("account-manage-view").hidden = true; document.getElementById("account-view").hidden = false; document.getElementById("auth-title").textContent = authText("account", "账号", "Account"); });
  document.getElementById("account-contact-form")?.addEventListener("submit", saveContact);
  document.getElementById("account-password-form")?.addEventListener("submit", savePassword);
  ["auth", "profile"].forEach((prefix) => document.getElementById(`${prefix}-country`)?.addEventListener("change", () => { localStorage.setItem("boten-phone-country", document.getElementById(`${prefix}-country`).value); updateCallingCode(prefix); }));
  document.getElementById("account-admin-entry")?.addEventListener("click", enterAdmin);
  document.getElementById("auth-form")?.addEventListener("submit", submitAuth);
  document.getElementById("auth-form")?.addEventListener("input", (event) => {
    event.target.removeAttribute?.("aria-invalid");
    const error = document.getElementById("auth-error"); if (error) error.hidden = true;
  });
  document.getElementById("auth-mode-switch")?.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-auth-mode]");
    if (trigger) setAuthMode(trigger.dataset.authMode);
  });
  document.querySelectorAll(".auth-method-tab").forEach((tab) => tab.addEventListener("click", () => setAuthIdentifierMode(tab.dataset.authIdentifier)));
  document.querySelector(".auth-method-tabs")?.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const tabs = Array.from(event.currentTarget.querySelectorAll(".auth-method-tab")); const current = tabs.indexOf(document.activeElement); if (current < 0) return;
    event.preventDefault(); const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    setAuthIdentifierMode(tabs[next].dataset.authIdentifier); tabs[next].focus();
  });
  await loadPhoneCountries();
  refreshAuthCopy();
  setAuthIdentifierMode(authIdentifierMode);

  const token = sessionStorage.getItem(USER_TOKEN_KEY);
  if (token) {
    try { currentUser = await authRequest("/auth/me"); }
    catch (_) { sessionStorage.removeItem(USER_TOKEN_KEY); currentUser = null; }
  }
  notifyAuth();
}
