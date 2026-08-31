const USER_TOKEN_KEY = "boten_user_token";
let currentUser = null;
let authMode = "login";
let pendingAuthenticatedAction = null;
const authSubscribers = [];
const authText = (key, zh, en) => window.botenI18n?.t(key) || (localStorage.getItem("boten-language") === "en" ? en : zh);

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
  document.querySelectorAll(".auth-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.authMode === mode));
  document.querySelectorAll(".register-only").forEach((field) => { field.hidden = mode !== "register"; });
  document.getElementById("auth-title").textContent = mode === "register" ? authText("createAccount", "创建账号", "Create account") : authText("loginTitle", "登录账号", "Sign in");
  document.getElementById("auth-submit").textContent = mode === "register" ? authText("registerContinue", "注册并继续", "Register") : authText("login", "登录", "Sign in");
  document.getElementById("auth-password").autocomplete = mode === "register" ? "new-password" : "current-password";
  document.getElementById("auth-error").hidden = true;
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
  label.textContent = isAuthenticated() ? (currentUser.display_name || currentUser.email || currentUser.phone || authText("accountFallback", "账号", "Account")) : authText("login", "登录", "Sign in");
  if (isAuthenticated()) {
    const display = currentUser.display_name || `BOTEN ${authText("user", "用户", "User")}`;
    document.getElementById("account-avatar").textContent = display.charAt(0).toUpperCase();
    document.getElementById("account-name").textContent = display;
    document.getElementById("account-contact").textContent = currentUser.email || currentUser.phone || "";
    document.getElementById("account-role").textContent = { customer: authText("customer", "客户", "Customer"), sales: authText("sales", "业务员", "Sales"), admin: authText("admin", "管理员", "Admin") }[currentUser.role] || currentUser.role;
  }
}

async function submitAuth(event) {
  event.preventDefault();
  const error = document.getElementById("auth-error");
  const submit = document.getElementById("auth-submit");
  const identifier = document.getElementById("auth-identifier").value.trim();
  const password = document.getElementById("auth-password").value;
  error.hidden = true;
  submit.disabled = true;
  submit.textContent = authMode === "register" ? authText("registering", "注册中…", "Registering…") : authText("signingIn", "登录中…", "Signing in…");
  try {
    const payload = authMode === "register"
      ? {
          ...(identifier.includes("@") ? { email: identifier } : { phone: identifier }),
          password,
          display_name: document.getElementById("auth-name").value.trim()
        }
      : { identifier, password };
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
  document.getElementById("guest-continue")?.addEventListener("click", () => {
    pendingAuthenticatedAction = null;
    document.getElementById("auth-dialog").close();
  });
  document.getElementById("account-logout")?.addEventListener("click", logoutUser);
  document.getElementById("auth-form")?.addEventListener("submit", submitAuth);
  document.querySelectorAll(".auth-tab").forEach((tab) => tab.addEventListener("click", () => setAuthMode(tab.dataset.authMode)));

  const token = sessionStorage.getItem(USER_TOKEN_KEY);
  if (token) {
    try { currentUser = await authRequest("/auth/me"); }
    catch (_) { sessionStorage.removeItem(USER_TOKEN_KEY); currentUser = null; }
  }
  notifyAuth();
}
