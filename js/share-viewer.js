let customerSharePreview = null;
let customerShareImportKey = "";

function customerShareText(key, zh, en) {
  const translated = window.botenI18n?.t(key);
  return translated && translated !== key ? translated : (localStorage.getItem("boten-language") === "en" ? en : zh);
}

function escapeCustomerShare(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  }[char]));
}

function customerShareItemTitle(item) {
  const snapshot = item.snapshot || {};
  if (item.item_type === "device_config") {
    const product = snapshot.product || {};
    return [product.name, product.title_name].filter(Boolean).join(" ") || item.display_name || "--";
  }
  return window.catalogDisplayName(snapshot.name || item.display_name, snapshot.code) || window.normalizeCatalogCode(snapshot.code) || "--";
}

function customerShareItemCode(item) {
  return item.item_type === "device_config" ? "" : window.normalizeCatalogCode(item.snapshot?.code);
}

function customerShareConfigured(value) {
  const normalized = String(value || "").trim().toLocaleLowerCase();
  return Boolean(normalized) && !new Set(["未配置", "未选择", "无", "none", "not configured", "not selected", "n/a", "—", "-"]).has(normalized);
}

function customerShareCatalogIdentity(code, name, fallback) {
  const normalizedCode = window.normalizeCatalogCode(code);
  const displayName = window.catalogDisplayName(name, normalizedCode) || fallback;
  return `${normalizedCode ? `<small class="customer-share-option-code">${escapeCustomerShare(normalizedCode)}</small>` : ""}<strong>${escapeCustomerShare(displayName)}</strong>`;
}

function renderCustomerShareDevice(item, index) {
  const snapshot = item.snapshot || {};
  const product = snapshot.product || {};
  const categories = snapshot.categories || [];
  const baseIds = new Set(["motor", "voltage", "channel"]);
  const singleValue = (id) => categories.find((category) => category.id === id)?.options?.map((option) => option.name || option.code).filter(customerShareConfigured).join(" / ") || "";
  const basics = [
    [customerShareText("model", "型号", "Model"), product.name],
    [customerShareText("productName", "名称", "Name"), product.title_name],
    [customerShareText("appearance", "外观颜色", "Appearance"), snapshot.color?.label || snapshot.color?.code],
    [customerShareText("motor", "电机", "Motor"), singleValue("motor")],
    [customerShareText("powerSupply", "电源", "Power Supply"), singleValue("voltage")],
    [customerShareText("channels", "通道", "Channels"), singleValue("channel")]
  ].filter(([, value]) => customerShareConfigured(value)).map(([label, value]) => `<div><span>${escapeCustomerShare(label)}</span><strong>${escapeCustomerShare(value)}</strong></div>`).join("");
  const optionGroups = categories.filter((category) => !baseIds.has(category.id) && (category.options || []).length).map((category) => `
    <section class="customer-share-option-group">
      <header><strong>${escapeCustomerShare(category.name)}</strong><small>${category.options.length} ${customerShareText("items", "项", "items")}</small></header>
      <ul>${category.options.map((option) => `<li><span>${customerShareCatalogIdentity(option.code, option.name, customerShareText("unnamedOption", "未命名配置", "Unnamed option"))}${option.description ? `<em>${escapeCustomerShare(String(option.description).replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim())}</em>` : ""}</span><b>× 1</b></li>`).join("")}</ul>
    </section>`).join("");
  const warning = item.available || !item.missing?.length ? "" : `<p class="customer-share-device-warning">${customerShareText("missingContent", "缺失或已停用", "Missing or disabled")}：${item.missing.map(escapeCustomerShare).join("、")}</p>`;
  return `<article class="customer-share-device${item.available ? "" : " is-unavailable"}">
    <h4>${customerShareText("sharedDeviceNumber", "设备", "Device")} ${index + 1} · ${escapeCustomerShare(product.name || item.display_name || "--")}<span>× ${Number(item.quantity || 1)}</span></h4>
    ${warning}<section class="customer-share-device-basics"><header><strong>${customerShareText("deviceInformation", "设备信息", "Device Information")}</strong><small>${customerShareText("modelAndBaseConfiguration", "型号与基本配置", "Model and base configuration")}</small></header><div>${basics}</div></section>
    <div class="customer-share-option-groups">${optionGroups || `<p class="customer-share-device-empty">${customerShareText("noOptionalConfiguration", "该设备未选择其他选配项目", "No optional configuration selected.")}</p>`}</div>
  </article>`;
}

function renderCustomerSharePreview(preview) {
  const content = document.getElementById("customer-share-content");
  const importButton = document.getElementById("customer-share-import");
  const note = document.getElementById("customer-share-note");
  const groups = [
    ["device_config", customerShareText("cartDevices", "设备配置", "Device Configurations")],
    ["tool", customerShareText("serviceTools", "维修工具", "Service Tools")],
    ["accessory", customerShareText("accessories", "设备附件", "Accessories")]
  ];
  note.hidden = !preview.note;
  document.getElementById("customer-share-note-label").textContent = customerShareText("shareNote", "分享备注", "Share note");
  document.getElementById("customer-share-note-text").textContent = preview.note || "";
  content.innerHTML = groups.map(([type, title]) => {
    const items = preview.items.filter((item) => item.item_type === type);
    if (!items.length) return "";
    if (type === "device_config") return `<section class="customer-share-group customer-share-device-group"><h3>${escapeCustomerShare(title)}</h3><div class="customer-share-devices">${items.map(renderCustomerShareDevice).join("")}</div></section>`;
    return `<section class="customer-share-group"><h3>${escapeCustomerShare(title)}</h3><div class="customer-share-items customer-share-catalog-card">${items.map((item) => `
      <article class="customer-share-item${item.available ? "" : " is-unavailable"}">
        <div class="customer-share-item-main">${customerShareItemCode(item) ? `<small>${escapeCustomerShare(customerShareItemCode(item))}</small>` : ""}<strong>${escapeCustomerShare(customerShareItemTitle(item))}</strong><span>${customerShareText("quantity", "数量", "Quantity")} ${Number(item.quantity || 1)}</span></div>
        <div class="customer-share-item-meta"><span class="customer-share-item-quantity">× ${Number(item.quantity || 1)}</span><span class="customer-share-availability">${item.available ? customerShareText("shareAvailable", "可加入", "Available") : customerShareText("shareUnavailable", "当前不可用", "Unavailable")}</span></div>
        ${item.available || !item.missing?.length ? "" : `<p>${customerShareText("missingContent", "缺失或已停用", "Missing or disabled")}：${item.missing.map(escapeCustomerShare).join("、")}</p>`}
      </article>`).join("")}</div></section>`;
  }).join("");
  content.hidden = false;
  importButton.hidden = preview.available_count < 1;
  importButton.disabled = false;
  importButton.textContent = preview.available_count === preview.item_count
    ? customerShareText("addAllToCart", "全部加入购物车", "Add All to Cart")
    : customerShareText("addAvailableToCart", "加入可用内容", "Add Available Items");
}

async function searchCustomerShare(event) {
  event.preventDefault();
  const codeInput = document.getElementById("customer-share-code");
  const status = document.getElementById("customer-share-status");
  const button = document.getElementById("customer-share-search");
  const code = codeInput.value.replace(/\D/g, "").slice(0, 6);
  codeInput.value = code;
  customerSharePreview = null;
  document.getElementById("customer-share-note").hidden = true;
  document.getElementById("customer-share-content").hidden = true;
  document.getElementById("customer-share-import").hidden = true;
  if (!/^\d{6}$/.test(code)) {
    status.textContent = customerShareText("shareCodeInvalid", "请输入 6 位数字分享码。", "Enter a 6-digit share code.");
    status.className = "customer-share-status is-error";
    codeInput.setAttribute("aria-invalid", "true");
    codeInput.focus();
    return;
  }
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  status.textContent = customerShareText("loadingShare", "正在读取分享内容…", "Loading shared items…");
  status.className = "customer-share-status";
  try {
    const lang = localStorage.getItem("boten-language") === "en" ? "en" : "zh";
    customerSharePreview = await authRequest(`/customer/shares/${code}?lang=${lang}`);
    customerShareImportKey = crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    renderCustomerSharePreview(customerSharePreview);
    const unavailable = customerSharePreview.item_count - customerSharePreview.available_count;
    status.textContent = unavailable
      ? (lang === "en" ? `${unavailable} item(s) are unavailable and are marked below.` : `有 ${unavailable} 项内容已失效，已在下方标注。`)
      : (lang === "en" ? `${customerSharePreview.item_count} item(s) can be added.` : `共 ${customerSharePreview.item_count} 项内容可以加入购物车。`);
    status.className = `customer-share-status${unavailable ? " is-warning" : " is-success"}`;
  } catch (error) {
    status.textContent = formatAuthError(error, "share");
    status.className = "customer-share-status is-error";
  } finally {
    button.disabled = false;
    button.removeAttribute("aria-busy");
  }
}

async function importCustomerShare() {
  if (!customerSharePreview || !customerShareImportKey) return;
  const button = document.getElementById("customer-share-import");
  const status = document.getElementById("customer-share-status");
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  try {
    const lang = localStorage.getItem("boten-language") === "en" ? "en" : "zh";
    const result = await authRequest(`/customer/shares/${customerSharePreview.code}/import`, {
      method: "POST",
      body: JSON.stringify({ idempotency_key: customerShareImportKey, lang })
    });
    if (typeof refreshServerCart === "function") await refreshServerCart();
    const resultMessage = result.skipped_count
      ? customerShareText("shareImportPartial", "可用内容已加入，失效内容未处理。", "Available items were added. Unavailable items were skipped.")
      : customerShareText("shareImportSuccess", "已加入购物车。", "Added to cart.");
    const quantityWarning = result.warnings?.length
      ? customerShareText("shareQuantityAdjusted", "部分数量已达到购物车上限。", "Some quantities reached the cart limit.")
      : "";
    status.textContent = [resultMessage, quantityWarning].filter(Boolean).join(" ");
    status.className = `customer-share-status${result.skipped_count || quantityWarning ? " is-warning" : " is-success"}`;
    button.hidden = true;
  } catch (error) {
    status.textContent = formatAuthError(error, "share");
    status.className = "customer-share-status is-error";
    button.disabled = false;
  } finally {
    button.removeAttribute("aria-busy");
  }
}

window.openCustomerShareDialog = function openCustomerShareDialog() {
  if (!isAuthenticated()) { openAuthDialog("login"); return; }
  const dialog = document.getElementById("customer-share-dialog");
  customerSharePreview = null;
  customerShareImportKey = "";
  document.getElementById("customer-share-form").reset();
  document.getElementById("customer-share-note").hidden = true;
  document.getElementById("customer-share-content").hidden = true;
  document.getElementById("customer-share-import").hidden = true;
  const status = document.getElementById("customer-share-status");
  status.textContent = "";
  status.className = "customer-share-status";
  if (!dialog.open) dialog.showModal();
  requestAnimationFrame(() => document.getElementById("customer-share-code").focus());
};

function initCustomerShareViewer() {
  const dialog = document.getElementById("customer-share-dialog");
  if (!dialog) return;
  document.getElementById("customer-share-close")?.addEventListener("click", () => dialog.close());
  document.getElementById("customer-share-form")?.addEventListener("submit", searchCustomerShare);
  document.getElementById("customer-share-import")?.addEventListener("click", importCustomerShare);
  document.getElementById("customer-share-code")?.addEventListener("input", (event) => {
    event.target.value = event.target.value.replace(/\D/g, "").slice(0, 6);
    event.target.removeAttribute("aria-invalid");
  });
}
