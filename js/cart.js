let serverCart = [];
let editingConfig = null;

const cartText = (key, zh, en) => {
  const translated = window.botenI18n?.t(key);
  if (translated && translated !== key) return translated;
  return localStorage.getItem("boten-language") === "en" ? en : zh;
};
const cartLanguage = () => localStorage.getItem("boten-language") === "en" ? "en" : "zh";

function setCartStatus(message = "", kind = "") {
  const status = document.getElementById("cart-operation-status");
  if (!status) return;
  status.textContent = message;
  status.className = `cart-operation-status${kind ? ` ${kind}` : ""}`;
  status.hidden = !message;
}

function setConfigSaveStatus(message = "", kind = "") {
  const status = document.getElementById("config-save-status");
  if (!status) return;
  status.textContent = message;
  status.className = `cart-operation-status${kind ? ` ${kind}` : ""}`;
  status.hidden = !message;
}

function escapeCartHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

function descriptionText(value) {
  return String(value || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function savedConfigToCartItem(saved) {
  const snapshot = saved.snapshot;
  const colorName = snapshot.color.label || snapshot.color.code;
  const groups = [{ id: "color", type: "single", category: cartText("appearance", "外观颜色", "Appearance"), value: colorName }];
  snapshot.categories.forEach((category) => {
    const values = category.options.map((option) => {
      const details = [option.description, option.special_note].map(descriptionText).filter(Boolean);
      return details.length ? `${option.name} | ${details.join(" | ")}` : getSpecLabel(category.id, option.name);
    });
    if (!values.length) return;
    groups.push(category.multiple
      ? { id: category.id, type: "multi", category: category.name, value: values, count: values.length }
      : { id: category.id, type: "single", category: category.name, value: values[0], count: 1 });
  });
  return {
    itemType: "device_config",
    id: saved.id, version: Number(saved.version || 1), savedAt: saved.created_at, updatedAt: saved.updated_at,
    modelName: snapshot.product.name, titleName: saved.name || snapshot.product.title_name,
    productTitle: snapshot.product.title_name, colorName, snapshot, groups,
  };
}

function savedCatalogToCartItem(saved) {
  return {
    itemType: saved.catalog_type === "tools" ? "tool" : "accessory",
    id: saved.id,
    version: Number(saved.version || 1),
    optionId: saved.option_id,
    catalogType: saved.catalog_type,
    code: saved.code || "",
    name: saved.name || "",
    description: saved.description || "",
    note: saved.note || "",
    imagePath: saved.image_path || "",
    quantity: Number(saved.quantity || 1),
    categorySortOrder: Number.isFinite(Number(saved.catalog_category_sort_order)) ? Number(saved.catalog_category_sort_order) : Number.MAX_SAFE_INTEGER,
    sortOrder: Number.isFinite(Number(saved.catalog_sort_order)) ? Number(saved.catalog_sort_order) : Number.MAX_SAFE_INTEGER,
    savedAt: saved.created_at,
    updatedAt: saved.updated_at,
    snapshot: saved.snapshot || {}
  };
}

function compareCartChronology(left, right) {
  const byCreated = String(left.savedAt || "").localeCompare(String(right.savedAt || ""));
  return byCreated || String(left.id || "").localeCompare(String(right.id || ""));
}

function compareCatalogSystemOrder(left, right) {
  const byCategory = Number(left.categorySortOrder) - Number(right.categorySortOrder);
  if (byCategory) return byCategory;
  const byOrder = Number(left.sortOrder) - Number(right.sortOrder);
  if (byOrder) return byOrder;
  const byCode = String(left.code || "").localeCompare(String(right.code || ""), undefined, { numeric: true });
  return byCode || String(left.id || "").localeCompare(String(right.id || ""));
}

function orderCartItems(items) {
  return [
    ...items.filter((item) => item.itemType === "device_config").sort(compareCartChronology),
    ...items.filter((item) => item.catalogType === "tools").sort(compareCatalogSystemOrder),
    ...items.filter((item) => item.catalogType === "accessories").sort(compareCatalogSystemOrder),
  ];
}

window.getCatalogCartSnapshot = function getCatalogCartSnapshot(type) {
  return serverCart
    .filter((item) => item.catalogType === type)
    .sort(compareCatalogSystemOrder)
    .map((item) => ({ ...item }));
};

function notifyCatalogCartUpdated() {
  window.dispatchEvent(new CustomEvent("boten:cart-updated"));
}

async function refreshServerCart() {
  if (!isAuthenticated()) {
    serverCart = []; renderCartCount(); renderCartPanel(); notifyCatalogCartUpdated(); return;
  }
  try {
    const [configs, catalogItems] = await Promise.all([
      authRequest(`/configs?lang=${cartLanguage()}`),
      authRequest(`/cart/catalog-items?lang=${cartLanguage()}`)
    ]);
    serverCart = orderCartItems([
      ...configs.items.map(savedConfigToCartItem),
      ...catalogItems.items.map(savedCatalogToCartItem)
    ]);
  } catch (error) {
    console.error("Failed to load cart", error);
    serverCart = [];
  }
  renderCartCount(); renderCartPanel(); notifyCatalogCartUpdated();
}

window.refreshCatalogCartOnly = async function refreshCatalogCartOnly() {
  if (!isAuthenticated()) return refreshServerCart();
  const catalogItems = await authRequest(`/cart/catalog-items?lang=${cartLanguage()}`);
  const deviceItems = serverCart.filter((item) => item.itemType === "device_config");
  serverCart = orderCartItems([
    ...deviceItems,
    ...catalogItems.items.map(savedCatalogToCartItem)
  ]);
  renderCartCount();
  renderCartPanel();
  notifyCatalogCartUpdated();
};

function renderCartCount() {
  const badge = document.getElementById("cart-count");
  if (!badge) return;
  badge.textContent = serverCart.length;
  badge.hidden = serverCart.length === 0;
}

function renderCartActions() {
  const hasItems = serverCart.length > 0 && isAuthenticated();
  const headerActions = [
    ["cart-pdf", "exportCombinedPdf", "导出 PDF", "Export PDF"],
    ["cart-share", "shareSelected", "分享", "Share"],
    ["cart-close", "closeCart", "关闭", "Close"],
  ];
  headerActions.forEach(([id, key, zh, en]) => {
    const button = document.getElementById(id);
    if (!button) return;
    const label = cartText(key, zh, en);
    button.setAttribute("aria-label", label);
    const text = button.querySelector(".cart-action-label");
    if (text) text.textContent = label;
    if (id !== "cart-close") button.disabled = !hasItems;
  });
  const inquiry = document.getElementById("cart-inquiry");
  if (inquiry) {
    inquiry.disabled = serverCart.length === 0;
    inquiry.textContent = isAuthenticated()
      ? cartText("cartContactSales", "联系销售获取报价", "Contact Sales for a Quote")
      : cartText("loginToContactSales", "登录后联系销售", "Sign in to Contact Sales");
  }
}

function renderDeviceCartCard(item, deviceIndex) {
  const coreHtml = item.groups.filter((group) => ["color", "motor", "voltage", "channel"].includes(group.id)).map((group) =>
    `<div class="cart-item-core-row"><span>${escapeCartHtml(group.category)}</span><strong>${escapeCartHtml(Array.isArray(group.value) ? group.value.join("、") : group.value)}</strong></div>`).join("");
  const summaryHtml = item.groups.filter((group) => !["color", "motor", "voltage", "channel"].includes(group.id)).map((group) => {
    const optionCount = group.count || (Array.isArray(group.value) ? group.value.length : 1);
    return `<div class="cart-item-summary-row"><span>${escapeCartHtml(group.category)}</span><strong>${optionCount}</strong></div>`;
  }).join("");
  return `<article class="cart-item">
    <header class="cart-item-toolbar">
      <div class="cart-item-toolbar-label"><span class="cart-item-kind-title">${cartText("deviceSequence", "设备 {number}", "Device {number}").replace("{number}", deviceIndex)}</span></div>
      <div class="cart-item-actions"><button class="btn btn-secondary btn-sm cart-item-details" type="button" data-id="${escapeCartHtml(item.id)}">${cartText("cartView", "详情", "View")}</button><button class="btn btn-secondary btn-sm cart-item-edit" type="button" data-id="${escapeCartHtml(item.id)}">${cartText("editAction", "修改", "Edit")}</button><button class="btn btn-danger btn-sm cart-item-delete" type="button" data-id="${escapeCartHtml(item.id)}">${cartText("deleteAction", "删除", "Delete")}</button></div>
    </header>
    <div class="cart-item-heading"><div class="cart-item-model">${escapeCartHtml(item.modelName)}</div><div class="cart-item-title">${escapeCartHtml(item.productTitle || item.titleName)}</div></div>
    <div class="cart-item-core">${coreHtml}</div>${summaryHtml ? `<div class="cart-item-summary">${summaryHtml}</div>` : ""}
  </article>`;
}

function catalogCartItems(type) {
  return serverCart.filter((item) => item.catalogType === type).sort(compareCatalogSystemOrder);
}

function renderCatalogCartGroup(type, items) {
  const toolMode = type === "tools";
  const title = toolMode ? cartText("serviceTools", "维修工具", "Service Tools") : cartText("accessories", "设备附件", "Accessories");
  const totalQuantity = items.reduce((total, item) => total + Number(item.quantity || 1), 0);
  const rows = items.map((item) => `<div class="cart-catalog-group-row"><span><strong>${escapeCartHtml(item.name || "--")}</strong><small>${escapeCartHtml(item.code || "--")}</small></span><b>× ${item.quantity}</b></div>`).join("");
  return `<article class="cart-item cart-catalog-group-card" data-catalog-cart-group="${type}">
    <header class="cart-item-toolbar">
      <div class="cart-item-toolbar-label"><span class="cart-item-kind-title">${escapeCartHtml(title)}</span></div>
      <div class="cart-item-actions"><button class="btn btn-secondary btn-sm" type="button" data-edit-catalog-group="${type}">${cartText("editAction", "修改", "Edit")}</button><button class="btn btn-danger btn-sm" type="button" data-delete-catalog-group="${type}">${cartText("deleteAction", "删除", "Delete")}</button></div>
    </header>
    <div class="cart-catalog-group-list">${rows}</div>
    <footer class="cart-catalog-group-total"><span>${cartText("totalQuantity", "总数", "Total")}</span><strong>${totalQuantity} ${cartText("quantityUnit", "件", "items")}</strong></footer>
  </article>`;
}

function renderCartPanel() {
  const itemsEl = document.getElementById("cart-items");
  const emptyEl = document.getElementById("cart-empty");
  if (!itemsEl || !emptyEl) return;
  if (!isAuthenticated()) {
    itemsEl.innerHTML = ""; emptyEl.hidden = false;
    emptyEl.textContent = cartText("signInToSave", "登录后可保存配置", "Sign in to save");
    renderCartActions(); return;
  }
  if (serverCart.length === 0) {
    itemsEl.innerHTML = ""; emptyEl.hidden = false;
    emptyEl.textContent = cartText("noSaved", "暂无已保存配置", "No saved configurations");
    renderCartActions(); return;
  }
  emptyEl.hidden = true;
  const displayUnits = serverCart.filter((item) => item.itemType === "device_config").map((item) => ({ kind: "device", item }));
  ["tools", "accessories"].forEach((type) => {
    const items = catalogCartItems(type);
    if (items.length) displayUnits.push({ kind: "catalog", type, items });
  });
  let deviceIndex = 0;
  itemsEl.innerHTML = displayUnits.map((unit) => unit.kind === "device" ? renderDeviceCartCard(unit.item, ++deviceIndex) : renderCatalogCartGroup(unit.type, unit.items)).join("");
  itemsEl.querySelectorAll(".cart-item-edit").forEach((button) => button.addEventListener("click", () => beginConfigEdit(button.dataset.id)));
  itemsEl.querySelectorAll(".cart-item-details").forEach((button) => button.addEventListener("click", () => showCartDetails(button.dataset.id)));
  itemsEl.querySelectorAll(".cart-item-delete").forEach((button) => button.addEventListener("click", () => removeDeviceCartItem(button.dataset.id, button)));
  itemsEl.querySelectorAll("[data-edit-catalog-group]").forEach((button) => button.addEventListener("click", () => showCatalogGroupDialog(button.dataset.editCatalogGroup)));
  itemsEl.querySelectorAll("[data-delete-catalog-group]").forEach((button) => button.addEventListener("click", () => removeCatalogCartGroup(button.dataset.deleteCatalogGroup, button)));
  renderCartActions();
}

function showCatalogGroupDialog(type) {
  const items = catalogCartItems(type);
  if (!items.length) return;
  const toolMode = type === "tools";
  const typeLabel = toolMode ? cartText("serviceTools", "维修工具", "Service Tools") : cartText("accessories", "设备附件", "Accessories");
  const title = cartText("editCatalogGroup", "修改{type}", "Edit {type}").replace("{type}", typeLabel);
  const dialog = document.createElement("dialog");
  dialog.className = "share-dialog cart-detail-dialog catalog-group-dialog is-editing";
  dialog.setAttribute("aria-labelledby", "catalog-group-dialog-title");
  const rows = items.map((item) => `<article class="catalog-cart-dialog-row" data-catalog-dialog-item="${escapeCartHtml(item.id)}" data-version="${item.version}" data-original-quantity="${item.quantity}">
    <div class="catalog-cart-dialog-copy"><strong>${escapeCartHtml(item.name || "--")}</strong><small>${escapeCartHtml(item.code || "--")}</small></div>
    <div class="catalog-cart-dialog-quantity"><span class="catalog-dialog-stepper"><button type="button" data-catalog-quantity-step="-1" aria-label="${cartText("decreaseQuantity", "减少数量", "Decrease quantity")}">−</button><input type="number" min="1" max="999" step="1" value="${item.quantity}" inputmode="numeric" aria-label="${cartText("quantity", "数量", "Quantity")}：${escapeCartHtml(item.name || item.code || "")}"><button type="button" data-catalog-quantity-step="1" aria-label="${cartText("increaseQuantity", "增加数量", "Increase quantity")}">+</button></span></div>
    <button class="btn btn-secondary btn-sm catalog-dialog-delete" type="button" data-mark-catalog-delete aria-pressed="false">${cartText("deleteAction", "删除", "Delete")}</button>
  </article>`).join("");
  dialog.innerHTML = `<form method="dialog" class="share-dialog-card catalog-group-dialog-card">
    <header class="share-dialog-header"><div><span class="auth-kicker">${escapeCartHtml(typeLabel)}</span><h2 id="catalog-group-dialog-title">${escapeCartHtml(title)}</h2><p class="cart-detail-model">${cartText("catalogGroupSummary", "共 {count} 项", "{count} items").replace("{count}", items.length)}</p></div><button class="btn btn-text btn-sm" type="submit" value="cancel" aria-label="${cartText("close", "关闭", "Close")}">✕</button></header>
    <div class="cart-detail-content catalog-group-dialog-list">${rows}</div>
    <div class="cart-operation-status catalog-group-dialog-status" role="alert" tabindex="-1" hidden></div>
    <footer class="catalog-group-dialog-footer"><button class="btn btn-secondary" type="submit" value="cancel">${cartText("cancelAction", "取消", "Cancel")}</button><button class="btn btn-primary" type="submit" value="save">${cartText("saveChanges", "保存修改", "Save Changes")}</button></footer>
  </form>`;
  document.body.appendChild(dialog);
  const returnFocus = document.activeElement;

  dialog.querySelectorAll("[data-catalog-quantity-step]").forEach((button) => button.addEventListener("click", () => {
    const input = button.closest(".catalog-dialog-stepper")?.querySelector("input");
    if (!input || input.disabled) return;
    input.value = String(Math.max(1, Math.min(999, Number(input.value || 1) + Number(button.dataset.catalogQuantityStep))));
  }));

  dialog.querySelectorAll("[data-mark-catalog-delete]").forEach((button) => button.addEventListener("click", () => {
    const row = button.closest("[data-catalog-dialog-item]");
    const marked = !row.classList.contains("marked-for-delete");
    row.classList.toggle("marked-for-delete", marked);
    row.querySelector("input").disabled = marked;
    button.setAttribute("aria-pressed", String(marked));
    button.textContent = marked ? cartText("undoDelete", "撤销删除", "Undo Delete") : cartText("deleteAction", "删除", "Delete");
  }));

  dialog.querySelector("form").addEventListener("submit", async (event) => {
    if (event.submitter?.value !== "save") return;
    event.preventDefault();
    const saveButton = event.submitter;
    const original = saveButton.textContent;
    const status = dialog.querySelector(".catalog-group-dialog-status");
    saveButton.disabled = true;
    saveButton.textContent = cartText("saving", "保存中…", "Saving…");
    status.hidden = true;
    try {
      const rows = [...dialog.querySelectorAll("[data-catalog-dialog-item]")];
      const removed = rows.filter((row) => row.classList.contains("marked-for-delete"));
      for (const row of rows.filter((candidate) => !candidate.classList.contains("marked-for-delete"))) {
        const quantity = Math.max(1, Math.min(999, Number(row.querySelector("input").value || 1)));
        if (quantity === Number(row.dataset.originalQuantity)) continue;
        await authRequest(`/cart/catalog-items/${encodeURIComponent(row.dataset.catalogDialogItem)}`, {
          method: "PATCH",
          body: JSON.stringify({ version: Number(row.dataset.version), quantity, lang: cartLanguage() })
        });
      }
      if (removed.length) {
        await authRequest("/cart/batch-archive", {
          method: "POST",
          body: JSON.stringify({ items: removed.map((row) => ({ item_type: toolMode ? "tool" : "accessory", id: row.dataset.catalogDialogItem })), lang: cartLanguage() })
        });
      }
      await refreshServerCart();
      dialog.close();
    } catch (error) {
      status.textContent = `${cartText("saveFailed", "保存失败", "Save failed")}：${error.message}`;
      status.hidden = false;
      status.focus();
      saveButton.disabled = false;
      saveButton.textContent = original;
    }
  });
  dialog.addEventListener("close", () => { dialog.remove(); returnFocus?.focus?.(); }, { once: true });
  dialog.showModal();
}

function showCartDetails(id) {
  const item = serverCart.find((candidate) => candidate.id === id);
  if (!item) return;
  if (item.itemType !== "device_config") {
    const dialog = document.createElement("dialog");
    const typeLabel = item.itemType === "tool" ? cartText("serviceTools", "维修工具", "Service Tools") : cartText("accessories", "设备附件", "Accessories");
    dialog.className = "share-dialog cart-detail-dialog";
    dialog.setAttribute("aria-labelledby", "cart-detail-title");
    dialog.innerHTML = `<div class="share-dialog-card"><header class="share-dialog-header"><div><span class="auth-kicker">${escapeCartHtml(typeLabel)}</span><h2 id="cart-detail-title">${escapeCartHtml(item.name)}</h2><p class="cart-detail-model">${escapeCartHtml(item.code || "--")}</p></div><button class="btn btn-text btn-sm" type="button" aria-label="${cartText("close", "关闭", "Close")}">✕</button></header><div class="cart-detail-content"><section class="cart-item-group"><div class="cart-item-group-header"><span>${cartText("quantity", "数量", "Quantity")}</span><strong>${item.quantity}</strong></div>${item.description ? `<p>${escapeCartHtml(item.description)}</p>` : ""}${item.note ? `<p>${escapeCartHtml(item.note)}</p>` : ""}</section></div></div>`;
    document.body.appendChild(dialog);
    dialog.querySelector("button")?.addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => dialog.remove(), { once: true });
    dialog.showModal();
    return;
  }
  const groupsHtml = item.groups.map((group) => group.type === "multi"
    ? `<section class="cart-item-group"><div class="cart-item-group-header"><span>${escapeCartHtml(group.category)}</span><span class="cart-item-count">${group.count}</span></div><ul>${group.value.map((name) => `<li>${escapeCartHtml(name)}</li>`).join("")}</ul></section>`
    : `<section class="cart-item-group"><div class="cart-item-group-header"><span class="cart-item-category">${escapeCartHtml(group.category)}</span></div><div class="cart-item-value">${escapeCartHtml(group.value)}</div></section>`).join("");
  const dialog = document.createElement("dialog");
  dialog.className = "share-dialog cart-detail-dialog";
  dialog.setAttribute("aria-labelledby", "cart-detail-title");
  dialog.innerHTML = `<div class="share-dialog-card"><header class="share-dialog-header"><div><span class="auth-kicker">${cartText("configurationDetails", "配置详情", "CONFIGURATION DETAILS")}</span><h2 id="cart-detail-title">${escapeCartHtml(item.modelName)}</h2><p class="cart-detail-model">${escapeCartHtml(item.productTitle)} · ${escapeCartHtml(item.colorName)}</p></div><button class="btn btn-text btn-sm" type="button" aria-label="${cartText("close", "关闭", "Close")}">✕</button></header><div class="cart-detail-content">${groupsHtml}</div></div>`;
  document.body.appendChild(dialog);
  dialog.querySelector("button")?.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => dialog.remove(), { once: true });
  dialog.showModal();
}

async function updateCatalogCartQuantity(id, button) {
  const item = serverCart.find((candidate) => candidate.id === id && candidate.itemType !== "device_config");
  const input = document.querySelector(`[data-catalog-cart-quantity="${CSS.escape(id)}"]`);
  if (!item || !input) return;
  const quantity = Math.max(1, Math.min(999, Number(input.value || 1)));
  const original = button.textContent;
  button.disabled = true;
  button.textContent = cartText("saving", "保存中…", "Saving…");
  try {
    setCartStatus();
    await authRequest(`/cart/catalog-items/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ version: item.version, quantity, lang: cartLanguage() })
    });
    await refreshServerCart();
  } catch (error) {
    setCartStatus(`${cartText("saveFailed", "保存失败", "Save failed")}：${error.message}`, "error");
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

function currentConfigPayload() {
  const snapshot = state.getSnapshot();
  const model = configData.models.find((item) => item.id === snapshot.currentModelId);
  if (!model) throw new Error(cartText("deviceNotFound", "未找到设备", "Device not found"));
  return { model, payload: { name: `${model.name} ${cartText("configuration", "配置", "Configuration")}`, product_id: snapshot.currentModelId, color: snapshot.currentColor, selections: snapshot.selections, lang: cartLanguage() } };
}

async function saveCurrentConfigToServer() {
  const button = document.getElementById("save-cart");
  if (button) { button.disabled = true; button.textContent = cartText("saving", "保存中…", "Saving…"); }
  try {
    setConfigSaveStatus();
    const { payload } = currentConfigPayload();
    if (editingConfig) {
      await authRequest(`/configs/${encodeURIComponent(editingConfig.id)}`, { method: "PUT", body: JSON.stringify({ ...payload, version: editingConfig.version }) });
      cancelConfigEdit(false);
    } else {
      await authRequest("/configs", { method: "POST", body: JSON.stringify(payload) });
    }
    await refreshServerCart(); openCartPanel();
  } catch (error) {
    setConfigSaveStatus(`${cartText("saveFailed", "保存失败", "Save failed")}: ${error.message}`, "error");
  } finally {
    if (button) button.disabled = false;
    updateEditStatus();
  }
}

function addCurrentConfigToCart() { requireLogin(saveCurrentConfigToServer); }

function beginConfigEdit(id) {
  const item = serverCart.find((candidate) => candidate.id === id);
  if (!item) {
    setCartStatus(cartText("configUnavailable", "该配置无法载入，请刷新后重试", "This configuration could not be loaded. Refresh and try again"), "error");
    return;
  }
  const loadResult = state.loadSnapshot(item.snapshot);
  if (!loadResult.loaded && loadResult.missingCount) {
    const warning = cartText("unavailableSelectionConfirm", "该历史配置有 {count} 项内容已不可用。是否移除这些内容并继续修改？", "{count} saved selections are no longer available. Remove them and continue editing?").replace("{count}", loadResult.missingCount);
    if (!window.confirm(warning)) return;
    state.loadSnapshot(item.snapshot, true);
  } else if (!loadResult.loaded) {
    setCartStatus(cartText("configUnavailable", "该配置无法载入，请刷新后重试", "This configuration could not be loaded. Refresh and try again"), "error");
    return;
  }
  setCartStatus();
  editingConfig = { id: item.id, version: item.version, modelName: item.modelName };
  const loadedModelId = state.getSnapshot().currentModelId;
  const deviceShown = window.botenShowDeviceSelection?.(loadedModelId);
  if (!deviceShown) {
    editingConfig = null;
    setCartStatus(cartText("configUnavailable", "该配置无法载入，请刷新后重试", "This configuration could not be loaded. Refresh and try again"), "error");
    updateEditStatus();
    return;
  }
  closeCartPanel();
  updateEditStatus();
  requestAnimationFrame(() => document.querySelector(".stage-header")?.scrollIntoView({ behavior: "smooth", block: "start" }));
}

function cancelConfigEdit(reset = true) {
  editingConfig = null;
  if (reset && state?.reset) state.reset();
  updateEditStatus();
}

function updateEditStatus() {
  const status = document.getElementById("config-edit-status");
  const label = document.getElementById("config-edit-label");
  const button = document.getElementById("save-cart");
  if (status) status.hidden = !editingConfig;
  if (label && editingConfig) label.textContent = `${cartText("editingConfiguration", "正在修改", "Editing")}: ${editingConfig.modelName}`;
  if (button) button.textContent = editingConfig ? cartText("saveChanges", "保存修改", "Save Changes") : cartText("saveCart", "保存配置到购物车", "Save Configuration to Cart");
}

function allCartItems() {
  return serverCart.map((item) => ({ item_type: item.itemType || "device_config", id: item.id }));
}

function formatShareExpiry(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value || "--") : new Intl.DateTimeFormat(cartLanguage() === "en" ? "en" : "zh-CN", { dateStyle: "medium", timeStyle: "short", hour12: false }).format(date);
}

function showShareResult(share) {
  const dialog = document.getElementById("share-dialog");
  dialog.dataset.code = share.code;
  document.getElementById("share-code").textContent = share.code;
  document.getElementById("share-expires-at").textContent = formatShareExpiry(share.expires_at);
  document.getElementById("share-copy-status").textContent = cartText("copyHint", "点击代码复制", "Select the code to copy");
  closeCartPanel();
  if (!dialog.open) dialog.showModal();
}

async function copyShareCode() {
  const code = document.getElementById("share-dialog")?.dataset.code;
  if (!code) return;
  try {
    await navigator.clipboard.writeText(code);
    document.getElementById("share-copy-status").textContent = `${cartText("copied", "已复制", "Copied")} ${code}`;
  } catch (_) { window.prompt(cartText("copyCode", "复制分享码", "Copy Code"), code); }
}

async function shareCart() {
  const items = allCartItems();
  if (!items.length) return;
  const button = document.getElementById("cart-share"); const original = button.textContent;
  button.disabled = true; button.textContent = cartText("generating", "生成中…", "Generating…");
  try {
    setCartStatus();
    const share = await authRequest("/cart/share", { method: "POST", body: JSON.stringify({ items, lang: cartLanguage() }) });
    showShareResult(share);
  } catch (error) { setCartStatus(`${cartText("shareFailed", "分享失败", "Share failed")}: ${error.message}`, "error"); }
  finally { button.textContent = original; renderCartActions(); }
}

async function exportCartPdf() {
  const items = allCartItems();
  if (!items.length) return;
  const button = document.getElementById("cart-pdf"); const original = button.textContent;
  button.disabled = true; button.textContent = cartText("generating", "生成中…", "Generating…");
  try {
    setCartStatus();
    const response = await fetch(`${CATALOG_API_BASE}/api/v1/cart/export/pdf`, {
      method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${sessionStorage.getItem(USER_TOKEN_KEY)}` },
      body: JSON.stringify({ items, lang: cartLanguage() }),
    });
    if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `PDF (${response.status})`); }
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = "BOTEN-configurations.pdf"; document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { setCartStatus(`${cartText("pdfFailed", "PDF 导出失败", "PDF export failed")}: ${error.message}`, "error"); }
  finally { button.textContent = original; renderCartActions(); }
}

async function archiveCartItems(items, button, message, title) {
  if (!items.length) return;
  const confirmed = await confirmCartRemoval(message, title);
  if (!confirmed) return;
  const original = button.textContent;
  button.disabled = true; button.textContent = cartText("removing", "删除中…", "Removing…");
  try {
    setCartStatus();
    await authRequest("/cart/batch-archive", { method: "POST", body: JSON.stringify({ items, lang: cartLanguage() }) });
    await refreshServerCart();
  } catch (error) { setCartStatus(`${cartText("removeFailed", "删除失败", "Remove failed")}: ${error.message}`, "error"); }
  finally { button.textContent = original; renderCartActions(); }
}

function removeDeviceCartItem(id, button) {
  const item = serverCart.find((candidate) => candidate.id === id && candidate.itemType === "device_config");
  if (!item) return;
  const message = cartText("confirmRemoveOne", "确定从购物车删除这台设备配置？", "Remove this device configuration from the cart?");
  void archiveCartItems([{ item_type: "device_config", id }], button, message, cartText("removeDevice", "删除设备配置", "Remove Device Configuration"));
}

function removeCatalogCartGroup(type, button) {
  const items = catalogCartItems(type);
  if (!items.length) return;
  const typeLabel = type === "tools" ? cartText("serviceTools", "维修工具", "Service Tools") : cartText("accessories", "设备附件", "Accessories");
  const quantity = items.reduce((total, item) => total + Number(item.quantity || 0), 0);
  const message = cartText("confirmRemoveCatalogGroup", "确定从购物车移除全部 {type}（{count} 个项目，共 {quantity} 件）吗？", "Remove all {type} ({count} items, {quantity} total) from the cart?")
    .replace("{type}", typeLabel).replace("{count}", items.length).replace("{quantity}", quantity);
  void archiveCartItems(items.map((item) => ({ item_type: item.itemType, id: item.id })), button, message, cartText("removeCatalogGroup", "删除{type}", "Remove {type}").replace("{type}", typeLabel));
}

function inquiryIdempotencyKey(sourceType) {
  const suffix = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  return `inquiry-${sourceType}-${suffix}`;
}

function inquirySummary(sourceType) {
  if (sourceType === "cart") {
    const devices = serverCart.filter((item) => item.itemType === "device_config");
    const tools = catalogCartItems("tools");
    const accessories = catalogCartItems("accessories");
    const totalToolQuantity = tools.reduce((total, item) => total + Number(item.quantity || 0), 0);
    const totalAccessoryQuantity = accessories.reduce((total, item) => total + Number(item.quantity || 0), 0);
    return [
      devices.length ? `${cartText("devices", "设备", "Devices")} · ${devices.length}` : "",
      tools.length ? `${cartText("serviceTools", "维修工具", "Service Tools")} · ${totalToolQuantity}` : "",
      accessories.length ? `${cartText("accessories", "设备附件", "Accessories")} · ${totalAccessoryQuantity}` : "",
    ].filter(Boolean);
  }
  const { model, payload } = currentConfigPayload();
  const snapshot = state.getSnapshot();
  const groups = buildSummaryGroups(model, snapshot);
  return [
    `${model.name || "--"} · ${model.title_name || ""}`,
    ...groups.map((group) => `${group.category}: ${Array.isArray(group.value) ? group.value.join("、") : group.value}`),
  ].filter(Boolean).map((value) => String(value));
}

function openInquiryDialog(sourceType) {
  if (sourceType === "cart" && !serverCart.length) {
    setCartStatus(cartText("inquiryCartEmpty", "购物车为空，暂时无法提交询价。", "Your cart is empty, so an inquiry cannot be submitted."), "error");
    return;
  }
  let summary;
  let currentPayload = null;
  try {
    if (sourceType === "current_device") currentPayload = currentConfigPayload().payload;
    summary = inquirySummary(sourceType);
  } catch (error) {
    setConfigSaveStatus(`${cartText("inquiryConfigInvalid", "当前设备选配不完整，请检查后再询价。", "Complete the current device configuration before requesting a quote.")}`, "error");
    return;
  }
  const returnFocus = document.activeElement;
  const isCart = sourceType === "cart";
  const dialog = document.createElement("dialog");
  dialog.className = "share-dialog cart-confirm-dialog inquiry-dialog";
  dialog.setAttribute("aria-labelledby", "inquiry-dialog-title");
  dialog.innerHTML = `<form method="dialog" class="share-dialog-card cart-confirm-card inquiry-dialog-card">
    <header class="share-dialog-header">
      <div><span class="auth-kicker">${isCart ? "CART INQUIRY" : "CONFIGURATION INQUIRY"}</span><h2 id="inquiry-dialog-title">${cartText("inquiryTitle", "联系销售获取报价", "Contact Sales for a Quote")}</h2></div>
      <button class="btn btn-text btn-sm" type="submit" value="cancel" aria-label="${cartText("close", "关闭", "Close")}">✕</button>
    </header>
    <p class="cart-confirm-message">${cartText("inquiryConfirmCopy", "请确认需要提交给销售人员的内容。提交后，销售人员将基于此配置与您联系。", "Review the content for sales. After submission, a sales representative will contact you about this request.")}</p>
    <ul class="inquiry-summary-list">${summary.map((line) => `<li>${escapeCartHtml(line)}</li>`).join("")}</ul>
    <label class="inquiry-message-field"><span>${cartText("inquiryMessage", "补充说明（选填）", "Additional notes (optional)")}</span><textarea name="message" maxlength="1000" rows="3" placeholder="${cartText("inquiryMessageHint", "例如：请通过邮箱联系我", "For example: please contact me by email")}"></textarea></label>
    <p class="cart-operation-status inquiry-dialog-status" role="alert" tabindex="-1" hidden></p>
    <footer class="cart-confirm-actions"><button class="btn btn-secondary" type="submit" value="cancel">${cartText("cancelAction", "取消", "Cancel")}</button><button class="btn btn-primary" type="submit" value="submit">${cartText("submitInquiry", "提交询价", "Submit Inquiry")}</button></footer>
  </form>`;
  document.body.appendChild(dialog);
  const idempotencyKey = inquiryIdempotencyKey(sourceType);
  dialog.querySelector("form").addEventListener("submit", async (event) => {
    if (event.submitter?.value !== "submit") return;
    event.preventDefault();
    const submit = event.submitter;
    const status = dialog.querySelector(".inquiry-dialog-status");
    submit.disabled = true;
    const original = submit.textContent;
    submit.textContent = cartText("submitting", "提交中…", "Submitting…");
    status.hidden = true;
    try {
      const message = dialog.querySelector("[name=message]").value.trim();
      const endpoint = isCart ? "/customer/inquiries/cart" : "/customer/inquiries/current-configuration";
      const body = isCart
        ? { lang: cartLanguage(), message, idempotency_key: idempotencyKey }
        : { ...currentPayload, message, idempotency_key: idempotencyKey };
      const inquiry = await authRequest(endpoint, { method: "POST", body: JSON.stringify(body) });
      status.textContent = `${cartText("inquirySubmitted", "询价已提交，销售人员将与您联系。询价编号：", "Inquiry submitted. Sales will contact you. Inquiry number: ")}${inquiry.inquiry_number}`;
      status.classList.remove("error");
      status.hidden = false;
      submit.hidden = true;
      dialog.querySelector('[value="cancel"]').textContent = cartText("close", "关闭", "Close");
      dialog.querySelector('[value="cancel"]').focus();
    } catch (error) {
      status.textContent = `${cartText("inquiryFailed", "询价提交失败", "Inquiry submission failed")}: ${error.message}`;
      status.classList.add("error");
      status.hidden = false;
      status.focus();
      submit.disabled = false;
      submit.textContent = original;
    }
  });
  dialog.addEventListener("close", () => { dialog.remove(); returnFocus?.focus?.(); }, { once: true });
  dialog.showModal();
}

function requestCurrentInquiry() {
  requireLogin(() => openInquiryDialog("current_device"));
}

function requestCartInquiry() {
  requireLogin(() => openInquiryDialog("cart"));
}

window.openCurrentInquiryDialog = requestCurrentInquiry;

function confirmCartRemoval(message, title = cartText("removeConfirmTitle", "删除所选配置", "Remove Selected Configurations")) {
  return new Promise((resolve) => {
    const returnFocus = document.activeElement;
    const dialog = document.createElement("dialog");
    dialog.className = "share-dialog cart-confirm-dialog";
    dialog.setAttribute("aria-labelledby", "cart-confirm-title");
    dialog.setAttribute("aria-describedby", "cart-confirm-message");
    dialog.innerHTML = `<form method="dialog" class="share-dialog-card cart-confirm-card">
      <header class="share-dialog-header">
        <div><span class="auth-kicker">${cartText("cart", "购物车", "CART")}</span><h2 id="cart-confirm-title">${escapeCartHtml(title)}</h2></div>
        <button class="btn btn-text btn-sm" type="submit" value="cancel" aria-label="${cartText("close", "关闭", "Close")}">✕</button>
      </header>
      <p id="cart-confirm-message" class="cart-confirm-message">${escapeCartHtml(message)}</p>
      <div class="cart-confirm-actions">
        <button class="btn btn-secondary" type="submit" value="cancel">${cartText("cancelAction", "取消", "Cancel")}</button>
        <button class="btn btn-danger" type="submit" value="confirm">${cartText("confirmRemoveAction", "确认删除", "Remove")}</button>
      </div>
    </form>`;
    document.body.appendChild(dialog);
    dialog.addEventListener("close", () => {
      const confirmed = dialog.returnValue === "confirm";
      dialog.remove();
      if (!confirmed && returnFocus instanceof HTMLElement) returnFocus.focus();
      resolve(confirmed);
    }, { once: true });
    dialog.showModal();
  });
}

window.confirmCartRemoval = confirmCartRemoval;

function openCartPanel() {
  const panel = document.getElementById("cart-panel"); const backdrop = document.getElementById("cart-backdrop");
  if (!panel || !backdrop) return;
  panel._returnFocus = document.activeElement;
  panel.classList.add("open"); backdrop.classList.add("open"); panel.setAttribute("aria-hidden", "false"); backdrop.setAttribute("aria-hidden", "false");
  [document.querySelector(".site-header"), document.querySelector(".main"), document.querySelector(".site-footer")].filter(Boolean).forEach((region) => { region.inert = true; });
  document.body.style.overflow = "hidden";
  requestAnimationFrame(() => document.getElementById("cart-close")?.focus());
}

function closeCartPanel() {
  const panel = document.getElementById("cart-panel"); const backdrop = document.getElementById("cart-backdrop");
  if (!panel || !backdrop) return;
  panel.classList.remove("open"); backdrop.classList.remove("open"); panel.setAttribute("aria-hidden", "true"); backdrop.setAttribute("aria-hidden", "true");
  [document.querySelector(".site-header"), document.querySelector(".main"), document.querySelector(".site-footer")].filter(Boolean).forEach((region) => { region.inert = false; });
  document.body.style.overflow = "";
  panel._returnFocus?.focus(); panel._returnFocus = null;
}

function trapCartFocus(event) {
  const panel = document.getElementById("cart-panel");
  if (event.key !== "Tab" || !panel?.classList.contains("open") || document.querySelector("dialog[open]")) return;
  const items = Array.from(panel.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')).filter((item) => !item.hidden);
  if (!items.length) return;
  const first = items[0]; const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}

function initCart() {
  renderCartCount(); renderCartPanel(); updateEditStatus();
  subscribeAuth(() => refreshServerCart());
  if (isAuthenticated()) refreshServerCart();
  document.getElementById("save-cart")?.addEventListener("click", addCurrentConfigToCart);
  document.getElementById("cancel-config-edit")?.addEventListener("click", () => cancelConfigEdit(true));
  document.getElementById("share-close")?.addEventListener("click", () => document.getElementById("share-dialog").close());
  document.getElementById("share-copy")?.addEventListener("click", copyShareCode);
  document.getElementById("share-code")?.addEventListener("click", copyShareCode);
  document.getElementById("cart-toggle")?.addEventListener("click", () => isAuthenticated() ? openCartPanel() : requireLogin(openCartPanel));
  document.getElementById("cart-close")?.addEventListener("click", closeCartPanel);
  document.getElementById("cart-backdrop")?.addEventListener("click", closeCartPanel);
  document.getElementById("cart-share")?.addEventListener("click", () => requireLogin(shareCart));
  document.getElementById("cart-pdf")?.addEventListener("click", () => requireLogin(exportCartPdf));
  document.getElementById("cart-inquiry")?.addEventListener("click", requestCartInquiry);
  window.addEventListener("beforeunload", (event) => { if (editingConfig) { event.preventDefault(); event.returnValue = ""; } });
  document.addEventListener("keydown", (event) => {
    const panel = document.getElementById("cart-panel");
    if (event.key === "Escape" && panel?.classList.contains("open") && !document.querySelector("dialog[open]")) closeCartPanel();
    trapCartFocus(event);
  });
}
