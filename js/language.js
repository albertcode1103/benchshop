(function () {
  const STORAGE_KEY = "boten-language";
  const copy = {
    zh: {
      account: "登录", device: "选择设备型号", cart: "我的购物车", clear: "清空购物车",
      share: "复制分享码", selected: "已选配置快捷导航", summary: "配置清单",
      summaryTitle: "当前选配", reset: "重置", model: "型号", empty: "尚未选择任何配置项",
      saveCart: "保存当前配置到购物车", shareCurrent: "分享当前配置", exportPdf: "导出 PDF",
      viewSummary: "查看配置清单", closeSummary: "关闭配置清单", optionalFeatures: "设备可选配置",
      loginTitle: "登录账号", login: "登录", register: "注册", name: "姓名", nameHint: "请输入姓名",
      identifier: "邮箱或手机号", identifierHint: "邮箱 / 手机号", password: "密码", passwordHint: "至少 8 个字符",
      guest: "游客浏览", authHint: "登录后可保存配置。", user: "用户", customer: "客户", sales: "业务员",
      admin: "管理员", logout: "退出登录", shareTitle: "配置分享码", shareDesc: "将此 6 位代码发给业务员。",
      copyHint: "点击代码复制", expires: "有效期至", cartEmpty: "购物车为空", close: "关闭",
      closeCart: "关闭购物车", closeShare: "关闭分享", footer: "配置仅供参考，请联系销售报价。",
      selectAll: "全选", clearAll: "全不选", shareAction: "分享", deleteAction: "删除",
      createAccount: "创建账号", registerContinue: "注册并继续", registering: "注册中…", signingIn: "登录中…",
      accountFallback: "账号", signInToSave: "登录后可保存配置", noSaved: "暂无配置", generating: "生成中…",
      copied: "已复制", copyCode: "复制分享码", confirmClear: "删除全部配置？", requestFailed: "请求失败",
      email: "邮箱", phone: "手机号", loginMethod: "登录方式", countryCode: "国家区号", phoneNumber: "实际手机号",
      emailHint: "name@example.com", phoneHint: "1590000000", invalidPhone: "请输入国家区号和7至15位手机号"
    },
    en: {
      account: "Sign in", device: "Select Test Bench", cart: "Cart", clear: "Clear Cart",
      share: "Copy Share Code", selected: "Selected Configuration", summary: "Configuration Summary",
      summaryTitle: "Selected Configuration", reset: "Reset", model: "Model", empty: "No Configuration Selected",
      saveCart: "Add to Cart", shareCurrent: "Share Configuration", exportPdf: "Export PDF",
      viewSummary: "View", closeSummary: "Close", optionalFeatures: "Optional Features",
      loginTitle: "Sign in", login: "Sign in", register: "Register", name: "Name", nameHint: "Your name",
      identifier: "Email or phone", identifierHint: "Email / phone", password: "Password", passwordHint: "8+ characters",
      guest: "Continue as guest", authHint: "Sign in to save configurations.", user: "User", customer: "Customer", sales: "Sales",
      admin: "Admin", logout: "Sign out", shareTitle: "Share Code", shareDesc: "Send this 6-digit code to sales.",
      copyHint: "Tap code to copy", expires: "Expires", cartEmpty: "Cart is empty", close: "Close",
      closeCart: "Close cart", closeShare: "Close share", footer: "For reference only. Contact sales for a quote.",
      selectAll: "Select all", clearAll: "Clear all", shareAction: "Share", deleteAction: "Delete",
      createAccount: "Create account", registerContinue: "Register", registering: "Registering…", signingIn: "Signing in…",
      accountFallback: "Account", signInToSave: "Sign in to save", noSaved: "No saved items", generating: "Generating…",
      copied: "Copied", copyCode: "Copy code", confirmClear: "Delete all items?", requestFailed: "Request failed",
      email: "Email", phone: "Phone", loginMethod: "Sign-in method", countryCode: "Country code", phoneNumber: "Phone number",
      emailHint: "name@example.com", phoneHint: "1590000000", invalidPhone: "Enter a country code and a 7–15 digit phone number"
    }
  };

  function applyStaticLanguage(lang) {
    const text = copy[lang] || copy.zh;
    document.documentElement.lang = lang === "en" ? "en" : "zh-CN";
    const account = document.getElementById("account-label");
    const deviceLabel = document.querySelector('label[for="device-select"]');
    const cartTitle = document.getElementById("cart-title");
    const cartClear = document.getElementById("cart-clear");
    const shareCopy = document.getElementById("share-copy");
    const chips = document.getElementById("spec-chips");
    const summaryPanel = document.getElementById("summary-panel");
    const summaryTitle = document.getElementById("summary-title");
    const reset = document.getElementById("reset-config");
    const modelLabel = document.getElementById("summary-model-label");
    const summaryEmpty = document.getElementById("summary-empty");
    const saveCart = document.getElementById("save-cart");
    const shareCurrent = document.getElementById("share-current");
    const exportPdf = document.getElementById("export-print");
    const summaryToggle = document.getElementById("summary-toggle");
    const summaryClose = document.getElementById("summary-close");
    const optionalFeaturesTitle = document.getElementById("optional-features-title");
    const staticText = {
      "header-cart-label": "cart", "auth-title": "loginTitle", "auth-login-tab": "login",
      "auth-register-tab": "register", "auth-name-label": "name", "auth-identifier-label": "identifier",
      "auth-password-label": "password", "auth-submit": "login", "guest-continue": "guest",
      "auth-hint": "authHint", "account-name": "user", "account-role": "customer",
      "account-logout": "logout", "share-title": "shareTitle", "share-description": "shareDesc",
      "share-copy-status": "copyHint", "share-expiry-label": "expires", "cart-empty": "cartEmpty"
    };
    if (account && !account.dataset.userName) account.textContent = text.account;
    if (deviceLabel) deviceLabel.textContent = text.device;
    if (cartTitle) cartTitle.textContent = text.cart;
    if (cartClear) cartClear.textContent = text.clear;
    if (shareCopy) shareCopy.textContent = text.share;
    if (chips) chips.setAttribute("aria-label", text.selected);
    if (summaryPanel) summaryPanel.setAttribute("aria-label", text.summary);
    if (summaryTitle) summaryTitle.textContent = text.summaryTitle;
    if (reset) reset.textContent = text.reset;
    if (modelLabel) modelLabel.textContent = text.model;
    if (summaryEmpty) summaryEmpty.textContent = text.empty;
    if (saveCart) saveCart.textContent = text.saveCart;
    if (shareCurrent) shareCurrent.textContent = text.shareCurrent;
    if (exportPdf) exportPdf.textContent = text.exportPdf;
    if (summaryToggle) {
      summaryToggle.setAttribute("aria-label", text.viewSummary);
      const label = summaryToggle.querySelector("span");
      if (label) label.textContent = text.viewSummary;
    }
    if (summaryClose) summaryClose.setAttribute("aria-label", text.closeSummary);
    if (optionalFeaturesTitle) optionalFeaturesTitle.textContent = text.optionalFeatures;
    Object.entries(staticText).forEach(function ([id, key]) {
      const element = document.getElementById(id);
      if (element) element.textContent = text[key];
    });
    const nameInput = document.getElementById("auth-name");
    const identifierInput = document.getElementById("auth-identifier");
    const passwordInput = document.getElementById("auth-password");
    const authClose = document.getElementById("auth-close");
    const shareClose = document.getElementById("share-close");
    const cartClose = document.getElementById("cart-close");
    const footer = document.getElementById("site-footer-copy");
    if (nameInput) nameInput.placeholder = text.nameHint;
    if (identifierInput) identifierInput.placeholder = text.identifierHint;
    if (passwordInput) passwordInput.placeholder = text.passwordHint;
    if (authClose) authClose.setAttribute("aria-label", text.close);
    if (shareClose) shareClose.setAttribute("aria-label", text.closeShare);
    if (cartClose) cartClose.setAttribute("aria-label", text.closeCart);
    if (footer) footer.innerHTML = `&copy; 2026 BOTEN DIESEL TEST BENCH. ${text.footer}`;
  }

  window.botenI18n = {
    get lang() { return localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "zh"; },
    t(key) { const lang = this.lang; return (copy[lang] && copy[lang][key]) || copy.zh[key] || key; }
  };

  document.addEventListener("DOMContentLoaded", function () {
    const switcher = document.getElementById("language-switcher");
    if (!switcher) return;
    const lang = localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "zh";
    switcher.querySelectorAll("[data-language]").forEach(function (button) {
      button.classList.toggle("active", button.dataset.language === lang);
      button.setAttribute("aria-pressed", button.dataset.language === lang ? "true" : "false");
    });
    applyStaticLanguage(lang);
    switcher.addEventListener("click", function (event) {
      const button = event.target.closest("[data-language]");
      if (!button) return;
      let nextLanguage = button.dataset.language === "en" ? "en" : "zh";
      if (nextLanguage === lang) {
        if (!window.matchMedia("(max-width: 639px)").matches) return;
        nextLanguage = lang === "en" ? "zh" : "en";
      }
      if (typeof state !== "undefined" && state?.getSnapshot) {
        sessionStorage.setItem("boten-language-config", JSON.stringify(state.getSnapshot()));
      }
      localStorage.setItem(STORAGE_KEY, nextLanguage);
      window.location.reload();
    });
  });
})();
