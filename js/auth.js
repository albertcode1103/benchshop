const USER_TOKEN_KEY = "boten_user_token";
const ADMIN_TOKEN_KEY = "boten_admin_token";
let currentUser = null;
let authMode = "login";
let authIdentifierMode = "email";
let pendingAuthenticatedAction = null;
const authSubscribers = [];
const authText = (key, zh, en) => window.botenI18n?.t(key) || (localStorage.getItem("boten-language") === "en" ? en : zh);

function refreshAuthCopy() {
  const text = (key, zh, en) => authText(key, zh, en);
  document.querySelectorAll('[data-auth-text="name"]').forEach((item) => { item.textContent = text("name", "姓名", "Name"); });
  document.querySelectorAll('[data-auth-text="email"]').forEach((item) => { item.textContent = text("email", "邮箱", "Email"); });
  document.querySelectorAll('[data-auth-text="phone"]').forEach((item) => { item.textContent = text("phone", "手机号", "Phone"); });
  document.querySelectorAll(".auth-method-tab").forEach((tab) => { tab.textContent = text(tab.dataset.authIdentifier, tab.dataset.authIdentifier === "email" ? "邮箱" : "手机号", tab.dataset.authIdentifier === "email" ? "Email" : "Phone"); });
  document.querySelector(".auth-method-tabs")?.setAttribute("aria-label", text("loginMethod", "登录方式", "Sign-in method"));
  document.getElementById("auth-name")?.setAttribute("placeholder", text("nameHint", "请输入姓名", "Your name"));
  document.getElementById("auth-email")?.setAttribute("placeholder", text("emailHint", "name@example.com", "name@example.com"));
  document.getElementById("auth-country-code")?.setAttribute("aria-label", text("countryCode", "国家区号", "Country code"));
  document.getElementById("auth-phone")?.setAttribute("aria-label", text("phoneNumber", "实际手机号", "Phone number"));
  document.getElementById("auth-phone")?.setAttribute("placeholder", text("phoneHint", "1590000000", "1590000000"));
  document.getElementById("auth-password-label").textContent = text("password", "密码", "Password");
  document.getElementById("auth-password")?.setAttribute("placeholder", text("passwordHint", "至少 8 个字符", "8+ characters"));
  document.getElementById("auth-close")?.setAttribute("aria-label", text("close", "关闭", "Close"));
}

async function authRequest(path, options = {}) {
  const token = sessionStorage.getItem(USER_TOKEN_KEY);
  const response = await fetch(`${CATALOG_API_BASE}/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  });
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `${authText("requestFailed", "请求失败", "Request failed")} (${response.status})`);
  return body;
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
  document.getElementById("auth-country-code").required = isRegister || !isEmail;
}

function authPhone() {
  const countryCode = document.getElementById("auth-country-code").value.trim().replace(/\s+/g, "");
  const phone = document.getElementById("auth-phone").value.trim().replace(/\s+/g, "");
  if (!/^\+[1-9]\d{0,3}$/.test(countryCode) || !/^\d{7,15}$/.test(phone)) throw new Error(authText("invalidPhone", "请输入国家区号和7至15位手机号", "Enter a country code and a 7–15 digit phone number"));
  return `${countryCode}${phone}`;
}

function authIdentifier() {
  return authIdentifierMode === "email" ? document.getElementById("auth-email").value.trim().toLowerCase() : authPhone();
}

function openAuthDialog(mode = "login") {
  const dialog = document.getElementById("auth-dialog");
  if (isAuthenticated()) {
    document.getElementById("auth-form-view").hidden = true;
    document.getElementById("account-view").hidden = false;
  } else {
    document.getElementById("auth-form-view").hidden = false;
    document.getElementById("account-view").hidden = true;
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
  const canEnterAdmin = isAuthenticated() && ["admin", "sales"].includes(currentUser.role);
  document.getElementById("account-admin-entry").hidden = !canEnterAdmin;
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
  window.location.assign("./admin/");
}

async function submitAuth(event) {
  event.preventDefault();
  const error = document.getElementById("auth-error");
  const submit = document.getElementById("auth-submit");
  const password = document.getElementById("auth-password").value;
  error.hidden = true;
  document.querySelectorAll("#auth-form [aria-invalid]").forEach((field) => field.removeAttribute("aria-invalid"));
  submit.disabled = true;
  submit.textContent = authMode === "register" ? authText("registering", "注册中…", "Registering…") : authText("signingIn", "登录中…", "Signing in…");
  try {
    const payload = authMode === "register"
      ? {
          display_name: document.getElementById("auth-name").value.trim(),
          email: document.getElementById("auth-email").value.trim().toLowerCase(),
          phone: authPhone(),
          password
        }
      : { identifier: authIdentifier(), password };
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
    error.textContent = failure.message;
    error.hidden = false;
    const candidates = authMode === "register"
      ? [document.getElementById("auth-name"), document.getElementById("auth-email"), document.getElementById("auth-country-code"), document.getElementById("auth-phone"), document.getElementById("auth-password")]
      : [document.getElementById(authIdentifierMode === "email" ? "auth-email" : "auth-phone"), document.getElementById("auth-password")];
    const target = candidates.find((field) => field && !field.value.trim()) || candidates[0];
    target?.setAttribute("aria-invalid", "true"); target?.focus();
  } finally {
    submit.disabled = false;
    submit.textContent = authMode === "register" ? authText("registerContinue", "注册并继续", "Register") : authText("login", "登录", "Sign in");
  }
}

async function logoutUser() {
  try { await authRequest("/auth/logout", { method: "POST" }); } catch (_) {}
  sessionStorage.removeItem(USER_TOKEN_KEY);
  currentUser = null;
  pendingAuthenticatedAction = null;
  document.getElementById("auth-dialog").close();
  notifyAuth();
}

async function initAuth() {
  document.getElementById("account-toggle")?.addEventListener("click", () => openAuthDialog());
  document.getElementById("auth-close")?.addEventListener("click", () => document.getElementById("auth-dialog").close());
  document.getElementById("account-logout")?.addEventListener("click", logoutUser);
  document.getElementById("account-admin-entry")?.addEventListener("click", enterAdmin);
  document.getElementById("auth-form")?.addEventListener("submit", submitAuth);
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
  refreshAuthCopy();
  setAuthIdentifierMode(authIdentifierMode);

  const token = sessionStorage.getItem(USER_TOKEN_KEY);
  if (token) {
    try { currentUser = await authRequest("/auth/me"); }
    catch (_) { sessionStorage.removeItem(USER_TOKEN_KEY); currentUser = null; }
  }
  notifyAuth();
}
