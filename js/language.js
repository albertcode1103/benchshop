(function () {
  const STORAGE_KEY = "boten-language";
  const copy = {
    zh: {
      account: "登录", device: "请选择", cart: "购物车", cartTitle: "我的购物车", clear: "清空购物车",
      share: "复制分享码", selected: "已选配置快捷导航", summary: "配置清单",
      summaryTitle: "当前选配", reset: "重置", model: "型号", empty: "尚未选择任何配置项",
      saveCart: "保存配置到购物车",
      viewSummary: "查看配置清单", closeSummary: "关闭配置清单", optionalFeatures: "设备可选配置",
      loginTitle: "登录账号", login: "登录", register: "注册", name: "姓名", nameHint: "请输入姓名",
      identifier: "邮箱或手机号", identifierHint: "邮箱 / 手机号", password: "密码", passwordHint: "至少 8 个字符",
      guest: "游客浏览", authHint: "登录后可保存配置。", user: "用户", customer: "客户", sales: "业务员",
      admin: "管理员", logout: "退出登录", shareTitle: "配置分享码", shareDesc: "将此 6 位代码发给业务员。",
      copyHint: "点击代码复制", expires: "有效期至", cartEmpty: "购物车为空", close: "关闭",
      closeCart: "关闭购物车", closeShare: "关闭分享", footer: "配置仅供参考，请联系销售报价。",
      selectAll: "全选", clearAll: "全不选", shareAction: "分享", deleteAction: "删除", overview: "设备概况",
      overviewDescription: "设备描述", overviewSpecifications: "参数表", specificationName: "参数", specificationValue: "数值",
      overviewExpand: "展开", overviewCollapse: "折叠",
      createAccount: "创建账号", registerContinue: "注册并继续", registering: "注册中…", signingIn: "登录中…",
      accountFallback: "账号", signInToSave: "登录后可保存配置", noSaved: "暂无配置", generating: "生成中…",
      copied: "已复制", copyCode: "复制分享码", confirmClear: "删除全部配置？", requestFailed: "请求失败",
      saveFailed: "保存失败", shareFailed: "分享失败", pdfFailed: "PDF 导出失败", removeFailed: "删除失败",
      removing: "删除中…", deviceNotFound: "未找到设备", configUnavailable: "该配置无法载入，请刷新后重试",
      email: "邮箱", phone: "手机号", loginMethod: "登录方式", countryCode: "国家区号", phoneNumber: "实际手机号",
      emailHint: "name@example.com", phoneHint: "1590000000", invalidPhone: "请选择国家并输入有效手机号",
      country: "国家", accountManage: "账号管理", currentPassword: "当前密码", newPassword: "新密码", confirmPassword: "确认新密码",
      saveRelogin: "保存并重新登录", changeRelogin: "修改密码并重新登录", back: "返回",
      contactInfo: "联系方式", changePassword: "修改密码", enterAdmin: "进入后台",
      currentPasswordRequired: "请输入当前密码", contactRequired: "请至少填写邮箱或手机号", newPasswordLength: "新密码至少 8 个字符", passwordMismatch: "两次输入的新密码不一致",
      appearance: "外观颜色", cartSelectAll: "全选", shareSelected: "分享所选", exportCombinedPdf: "导出 PDF", removeSelected: "删除所选",
      cancelEdit: "取消修改", saveChanges: "保存修改", saving: "保存中…", editingConfiguration: "正在修改", editAction: "修改", viewDetails: "查看详情",
      configurationDetails: "配置详情", selectConfiguration: "选择配置", configuration: "配置", cartSelectedCount: "已选择 {selected} / {total} 项",
      removeConfirmTitle: "删除所选配置", cancelAction: "取消", confirmRemoveAction: "确认删除", confirmRemoveOne: "确定从购物车删除这项配置？", confirmRemoveSelected: "确定从购物车删除 {count} 项配置？",
      unavailableSelectionConfirm: "该历史配置有 {count} 项内容已不可用。是否移除这些内容并继续修改？",
      pricePreview: "价格预览", cny: "人民币", basePrice: "设备基础价格", freePrice: "免费",
      pricePending: "价格待确认", unconfirmedPrice: "待确认", priceCalculating: "正在计算价格…",
      priceLoadFailed: "价格暂时无法计算", retry: "重试", referenceTotal: "参考合计",
      catalogMarketplace: "维修工具与设备附件", catalogMarketplaceDesc: "可独立选择数量并加入购物车，无需绑定设备。",
      serviceTools: "维修工具", accessories: "设备附件", search: "搜索", searchCatalogHint: "搜索编号或名称",
      allCategories: "全部", catalogEmpty: "暂无内容", addToCart: "加入购物车", addingToCart: "正在加入…",
      addedToCart: "已加入购物车", quantity: "数量", referencePrice: "参考价",
      requestQuote: "获取报价", contactSalesQuote: "请联系销售人员获取报价",
      catalogStandaloneDesc: "可独立选择数量并加入购物车，无需选择设备。",
      cartDevices: "设备配置", cartGroupCount: "{count} 项", inCart: "购物车中已有",
      selectCatalogGroup: "选择全部", catalogGroupSummary: "共 {count} 项", editCatalogGroup: "修改{type}",
      catalogGroupDetails: "{type}详情", undoDelete: "撤销删除",
      selectionRequiredTitle: "请先选择内容", selectionRequiredMessage: "请先勾选需要操作的设备配置、工具或附件。", understood: "知道了",
      decreaseQuantity: "减少数量", increaseQuantity: "增加数量", removeFromSelection: "从本次选择中移除",
      selectedItem: "已选择",
      deviceSequence: "设备 {number}", totalQuantity: "总数", quantityUnit: "件",
      openProductNavigation: "打开产品导航", closeProductNavigation: "关闭产品导航", productNavigation: "产品导航",
      testEquipment: "检测设备", backToProductCategories: "返回产品类别", noEnabledDevices: "暂无已启用设备",
      preparingToAdd: "本次准备添加", nothingInCartType: "购物车中暂无此类项目",
      nothingPreparing: "尚未设置待添加数量", addQuantity: "本次添加", inCartQuantity: "购物车中：{count}",
      toolSelection: "工具选择", accessorySelection: "附件选择", toolsInCart: "购物车中的工具",
      accessoriesInCart: "购物车中的附件", toolsToAdd: "本次添加的工具", accessoriesToAdd: "本次添加的附件",
      skipToContent: "跳到主要内容", home: "首页", languageSwitcher: "语言切换",
      cartCount: "购物车商品数量", configurationArea: "配置区域", gallery: "设备图片展示",
      carousel: "轮播图", previousImage: "上一张", nextImage: "下一张", image: "图片", slide: "第 {number} 张",
      appearanceSelection: "外观颜色", motorSelection: "电机选择", powerSelection: "供电选择",
      channelSelection: "通道选择", deviceConfiguration: "设备配置", categoryTabs: "配置分类",
      catalogTabs: "商品目录", catalogCategories: "目录分类", jumpTo: "跳转到", colorSwatch: "颜色"
    },
    en: {
      account: "Sign in", device: "Select", cart: "Cart", cartTitle: "My Cart", clear: "Clear Cart",
      share: "Copy Share Code", selected: "Selected Configuration", summary: "Configuration Summary",
      summaryTitle: "Selected Configuration", reset: "Reset", model: "Model", empty: "No Configuration Selected",
      saveCart: "Save Configuration to Cart",
      viewSummary: "View", closeSummary: "Close", optionalFeatures: "Optional Features",
      loginTitle: "Sign in", login: "Sign in", register: "Register", name: "Name", nameHint: "Your name",
      identifier: "Email or phone", identifierHint: "Email / phone", password: "Password", passwordHint: "8+ characters",
      guest: "Continue as guest", authHint: "Sign in to save configurations.", user: "User", customer: "Customer", sales: "Sales",
      admin: "Admin", logout: "Sign out", shareTitle: "Share Code", shareDesc: "Send this 6-digit code to sales.",
      copyHint: "Tap code to copy", expires: "Expires", cartEmpty: "Cart is empty", close: "Close",
      closeCart: "Close cart", closeShare: "Close share", footer: "For reference only. Contact sales for a quote.",
      selectAll: "Select all", clearAll: "Clear all", shareAction: "Share", deleteAction: "Delete", overview: "Overview",
      overviewDescription: "Description", overviewSpecifications: "Specifications", specificationName: "Specification", specificationValue: "Value",
      overviewExpand: "Expand", overviewCollapse: "Collapse",
      createAccount: "Create account", registerContinue: "Register", registering: "Registering…", signingIn: "Signing in…",
      accountFallback: "Account", signInToSave: "Sign in to save", noSaved: "No saved items", generating: "Generating…",
      copied: "Copied", copyCode: "Copy code", confirmClear: "Delete all items?", requestFailed: "Request failed",
      saveFailed: "Save failed", shareFailed: "Share failed", pdfFailed: "PDF export failed", removeFailed: "Remove failed",
      removing: "Removing…", deviceNotFound: "Device not found", configUnavailable: "This configuration could not be loaded. Refresh and try again",
      email: "Email", phone: "Phone", loginMethod: "Sign-in method", countryCode: "Country code", phoneNumber: "Phone number",
      emailHint: "name@example.com", phoneHint: "1590000000", invalidPhone: "Select a country and enter a valid phone number",
      country: "Country", accountManage: "Account management", currentPassword: "Current password", newPassword: "New password", confirmPassword: "Confirm password",
      saveRelogin: "Save and sign in again", changeRelogin: "Change password and sign in again", back: "Back",
      contactInfo: "Contact details", changePassword: "Change password", enterAdmin: "Open admin",
      currentPasswordRequired: "Enter your current password", contactRequired: "Enter an email or phone number", newPasswordLength: "New password must be at least 8 characters", passwordMismatch: "New passwords do not match",
      appearance: "Appearance", cartSelectAll: "Select All", shareSelected: "Share Selected", exportCombinedPdf: "Export PDF", removeSelected: "Remove Selected",
      cancelEdit: "Cancel Editing", saveChanges: "Save Changes", saving: "Saving…", editingConfiguration: "Editing", editAction: "Edit", viewDetails: "View Details",
      configurationDetails: "Configuration Details", selectConfiguration: "Select configuration", configuration: "Configuration", cartSelectedCount: "{selected} of {total} Selected",
      removeConfirmTitle: "Remove Selected Configurations", cancelAction: "Cancel", confirmRemoveAction: "Remove", confirmRemoveOne: "Remove this configuration from the cart?", confirmRemoveSelected: "Remove {count} selected configurations from the cart?",
      unavailableSelectionConfirm: "{count} saved selections are no longer available. Remove them and continue editing?",
      pricePreview: "Price Preview", cny: "CNY", basePrice: "Device Base Price", freePrice: "Included",
      pricePending: "Price Pending", unconfirmedPrice: "Unconfirmed", priceCalculating: "Calculating price…",
      priceLoadFailed: "Price is temporarily unavailable", retry: "Retry", referenceTotal: "Reference Total",
      catalogMarketplace: "Service Tools & Accessories", catalogMarketplaceDesc: "Choose quantities and add items without selecting a device.",
      serviceTools: "Service Tools", accessories: "Accessories", search: "Search", searchCatalogHint: "Search code or name",
      allCategories: "All", catalogEmpty: "No items", addToCart: "Add to Cart", addingToCart: "Adding…",
      addedToCart: "Added to cart", quantity: "Quantity", referencePrice: "Reference Price",
      requestQuote: "Request a Quote", contactSalesQuote: "Please contact our sales team for a quotation",
      catalogStandaloneDesc: "Choose quantities and add items without selecting a device.",
      cartDevices: "Device Configurations", cartGroupCount: "{count} items", inCart: "Already in Cart",
      selectCatalogGroup: "Select all", catalogGroupSummary: "{count} items", editCatalogGroup: "Edit {type}",
      catalogGroupDetails: "{type} Details", undoDelete: "Undo Delete",
      selectionRequiredTitle: "Select Items First", selectionRequiredMessage: "Select the device configurations, tools, or accessories you want to use.", understood: "OK",
      decreaseQuantity: "Decrease quantity", increaseQuantity: "Increase quantity", removeFromSelection: "Remove from current selection",
      selectedItem: "Selected",
      deviceSequence: "Device {number}", totalQuantity: "Total", quantityUnit: "items",
      openProductNavigation: "Open product navigation", closeProductNavigation: "Close product navigation", productNavigation: "Product Navigation",
      testEquipment: "Test Equipment", backToProductCategories: "Back to product categories", noEnabledDevices: "No enabled devices",
      preparingToAdd: "Preparing to Add", nothingInCartType: "No items of this type in the cart",
      nothingPreparing: "No quantities are being prepared", addQuantity: "Add Now", inCartQuantity: "In cart: {count}",
      toolSelection: "Tool Selection", accessorySelection: "Accessory Selection", toolsInCart: "Tools in Cart",
      accessoriesInCart: "Accessories in Cart", toolsToAdd: "Tools Being Added", accessoriesToAdd: "Accessories Being Added",
      skipToContent: "Skip to main content", home: "Home", languageSwitcher: "Language switcher",
      cartCount: "Items in cart", configurationArea: "Configuration area", gallery: "Device image gallery",
      carousel: "carousel", previousImage: "Previous image", nextImage: "Next image", image: "image", slide: "Slide {number}",
      appearanceSelection: "Appearance selection", motorSelection: "Motor selection", powerSelection: "Power supply selection",
      channelSelection: "Channel selection", deviceConfiguration: "Device configuration", categoryTabs: "Configuration categories",
      catalogTabs: "Product catalog", catalogCategories: "Catalog categories", jumpTo: "Jump to", colorSwatch: "color"
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
    const summaryToggle = document.getElementById("summary-toggle");
    const summaryClose = document.getElementById("summary-close");
    const optionalFeaturesTitle = document.getElementById("optional-features-title");
    const overview = document.querySelector(".device-overview");
    const overviewToggleLabel = document.getElementById("overview-toggle-label");
    const staticText = {
      "header-cart-label": "cart", "auth-title": "loginTitle", "auth-login-tab": "login",
      "auth-register-tab": "register", "auth-name-label": "name", "auth-identifier-label": "identifier",
      "auth-password-label": "password", "auth-submit": "login", "guest-continue": "guest",
      "auth-hint": "authHint", "account-name": "user", "account-role": "customer",
      "account-logout": "logout", "share-title": "shareTitle", "share-description": "shareDesc",
      "share-copy-status": "copyHint", "share-expiry-label": "expires", "cart-empty": "cartEmpty",
      "cart-select-all-label": "cartSelectAll", "cart-share-selected": "shareSelected",
      "cart-pdf-selected": "exportCombinedPdf", "cart-remove-selected": "removeSelected", "cancel-config-edit": "cancelEdit",
      "overview-title": "overview", "overview-description-title": "overviewDescription",
      "overview-specifications-title": "overviewSpecifications", "specification-name-heading": "specificationName",
      "specification-value-heading": "specificationValue", "pricing-preview-title": "requestQuote",
      "pricing-enquiry-message": "contactSalesQuote",
      "catalog-marketplace-title": "catalogMarketplace", "catalog-marketplace-description": "catalogMarketplaceDesc",
      "catalog-marketplace-search-label": "search", "catalog-marketplace-empty": "catalogEmpty"
    };
    if (account && !account.dataset.userName) account.textContent = text.account;
    if (deviceLabel) deviceLabel.textContent = text.device;
    if (cartTitle) cartTitle.textContent = text.cartTitle;
    if (cartClear) cartClear.textContent = text.clear;
    if (shareCopy) shareCopy.textContent = text.share;
    if (chips) chips.setAttribute("aria-label", text.selected);
    if (summaryPanel) summaryPanel.setAttribute("aria-label", text.summary);
    if (summaryTitle) summaryTitle.textContent = text.summaryTitle;
    if (reset) reset.textContent = text.reset;
    if (modelLabel) modelLabel.textContent = text.model;
    if (summaryEmpty) summaryEmpty.textContent = text.empty;
    if (saveCart) saveCart.textContent = text.saveCart;
    if (summaryToggle) {
      summaryToggle.setAttribute("aria-label", text.viewSummary);
      const label = summaryToggle.querySelector("span");
      if (label) label.textContent = text.viewSummary;
    }
    if (summaryClose) summaryClose.setAttribute("aria-label", text.closeSummary);
    if (optionalFeaturesTitle) optionalFeaturesTitle.textContent = text.optionalFeatures;
    if (overviewToggleLabel) overviewToggleLabel.textContent = overview?.open ? text.overviewCollapse : text.overviewExpand;
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
    const catalogSearch = document.getElementById("catalog-marketplace-search");
    if (catalogSearch) catalogSearch.placeholder = text.searchCatalogHint;
    const toolsTab = document.getElementById("catalog-tab-tools");
    const accessoriesTab = document.getElementById("catalog-tab-accessories");
    if (toolsTab) toolsTab.textContent = text.serviceTools;
    if (accessoriesTab) accessoriesTab.textContent = text.accessories;

    const skipLink = document.querySelector(".skip-link");
    const brand = document.querySelector(".brand");
    const languageSwitcher = document.getElementById("language-switcher");
    const cartCount = document.getElementById("cart-count");
    const configurationArea = document.querySelector(".config-stage");
    const gallery = document.querySelector(".gallery-viewport");
    const galleryPrevious = document.querySelector(".gallery-prev");
    const galleryNext = document.querySelector(".gallery-next");
    const colorSection = document.getElementById("color-section");
    const motorSection = document.getElementById("motor-section");
    const powerSection = document.getElementById("voltage-section");
    const channelSection = document.getElementById("channel-section");
    const configurationSection = document.getElementById("config-section");
    const categoryTabs = document.getElementById("category-tabs");
    const catalogTabs = document.getElementById("catalog-type-tabs");
    const catalogCategories = document.getElementById("catalog-category-filters");
    if (skipLink) skipLink.textContent = text.skipToContent;
    if (brand) brand.setAttribute("aria-label", text.home);
    if (languageSwitcher) languageSwitcher.setAttribute("aria-label", text.languageSwitcher);
    if (cartCount) cartCount.setAttribute("aria-label", text.cartCount);
    if (configurationArea) configurationArea.setAttribute("aria-label", text.configurationArea);
    if (gallery) {
      gallery.setAttribute("aria-label", text.gallery);
      gallery.setAttribute("aria-roledescription", text.carousel);
    }
    if (galleryPrevious) galleryPrevious.setAttribute("aria-label", text.previousImage);
    if (galleryNext) galleryNext.setAttribute("aria-label", text.nextImage);
    if (colorSection) colorSection.setAttribute("aria-label", text.appearanceSelection);
    if (motorSection) motorSection.setAttribute("aria-label", text.motorSelection);
    if (powerSection) powerSection.setAttribute("aria-label", text.powerSelection);
    if (channelSection) channelSection.setAttribute("aria-label", text.channelSelection);
    if (configurationSection) configurationSection.setAttribute("aria-label", text.deviceConfiguration);
    if (categoryTabs) categoryTabs.setAttribute("aria-label", text.categoryTabs);
    if (catalogTabs) catalogTabs.setAttribute("aria-label", text.catalogTabs);
    if (catalogCategories) catalogCategories.setAttribute("aria-label", text.catalogCategories);
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
    const overview = document.querySelector(".device-overview");
    if (overview) overview.addEventListener("toggle", function () { applyStaticLanguage(localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "zh"); });
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
