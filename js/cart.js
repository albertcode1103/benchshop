let serverCart = [];
const cartText = (key, zh, en) => window.botenI18n?.t(key) || (localStorage.getItem("boten-language") === "en" ? en : zh);
const cartLocale = (zh, en) => localStorage.getItem("boten-language") === "en" ? en : zh;

function escapeCartHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

function descriptionText(value) {
  return String(value || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function savedConfigToCartItem(saved) {
  const snapshot = saved.snapshot;
  const colorName = snapshot.color.label || snapshot.color.code;
  const groups = [{ id: "color", type: "single", category: localStorage.getItem("boten-language") === "en" ? "Appearance" : "外观颜色", value: colorName }];
  snapshot.categories.forEach((category) => {
    const values = category.options.map((option) => {
      const details = [option.description, option.special_note].map(descriptionText).filter(Boolean);
      if (!details.length) return getSpecLabel(category.id, option.name);
      return `${option.name} | ${details.join(" | ")}`;
    });
    if (!values.length) return;
    groups.push(category.multiple
      ? { id: category.id, type: "multi", category: category.name, value: values, count: values.length }
      : { id: category.id, type: "single", category: category.name, value: values[0], count: 1 });
  });
  return {
    id: saved.id,
    savedAt: saved.created_at,
    modelName: snapshot.product.name,
    titleName: saved.name || snapshot.product.title_name,
    colorName,
    groups
  };
}

async function refreshServerCart() {
  if (!isAuthenticated()) {
    serverCart = [];
    renderCartCount(); renderCartPanel();
    return;
  }
  try {
    const language = localStorage.getItem("boten-language") === "en" ? "en" : "zh";
    const result = await authRequest(`/configs?lang=${language}`);
    serverCart = result.items.map(savedConfigToCartItem);
  } catch (error) {
    console.error("Failed to load saved configurations", error);
    serverCart = [];
  }
  renderCartCount(); renderCartPanel();
}

function renderCartCount() {
  const badge = document.getElementById("cart-count");
  if (!badge) return;
  badge.textContent = serverCart.length;
  badge.hidden = serverCart.length === 0;
}

function renderCartPanel() {
  const itemsEl = document.getElementById("cart-items");
  const emptyEl = document.getElementById("cart-empty");
  if (!itemsEl || !emptyEl) return;
  if (!isAuthenticated()) {
    itemsEl.innerHTML = ""; emptyEl.hidden = false;
    emptyEl.textContent = cartText("signInToSave", "登录后可保存配置", "Sign in to save");
    return;
  }
  if (serverCart.length === 0) {
    itemsEl.innerHTML = ""; emptyEl.hidden = false; emptyEl.textContent = cartText("noSaved", "暂无配置", "No saved items");
    return;
  }
  emptyEl.hidden = true;
  itemsEl.innerHTML = serverCart.map((item) => {
    const coreHtml = item.groups.filter((group) => ["color", "motor", "voltage"].includes(group.id)).map((group) =>
      `<div class="cart-item-core-row"><span>${escapeCartHtml(group.category)}</span><strong>${escapeCartHtml(Array.isArray(group.value) ? group.value.join("、") : group.value)}</strong></div>`).join("");
    const summaryHtml = item.groups.filter((group) => !["color", "motor", "voltage"].includes(group.id)).map((group) => {
      const count = group.count || (Array.isArray(group.value) ? group.value.length : 1);
      return `<div class="cart-item-summary-row"><span>${escapeCartHtml(group.category)}</span><strong>${count}</strong></div>`;
    }).join("");
    return `<article class="cart-item"><header class="cart-item-header"><div class="cart-item-heading"><div class="cart-item-model">${escapeCartHtml(item.titleName || item.modelName)}</div></div><div class="cart-item-actions"><button class="btn btn-secondary btn-sm cart-item-share" type="button" data-id="${escapeCartHtml(item.id)}">${cartText("shareAction", "分享", "Share")}</button><button class="btn btn-text btn-sm cart-item-remove" type="button" data-id="${escapeCartHtml(item.id)}">${cartText("deleteAction", "删除", "Delete")}</button></div></header><div class="cart-item-core">${coreHtml}</div>${summaryHtml ? `<div class="cart-item-summary">${summaryHtml}</div>` : ""}<button class="btn btn-secondary btn-sm cart-item-details" type="button" data-id="${escapeCartHtml(item.id)}">${cartLocale("查看详情", "View details")}</button></article>`;
  }).join("");
  itemsEl.querySelectorAll(".cart-item-share").forEach((button) => button.addEventListener("click", () => shareSavedConfig(button.dataset.id, button)));
  itemsEl.querySelectorAll(".cart-item-remove").forEach((button) => button.addEventListener("click", () => removeCartItem(button.dataset.id)));
  itemsEl.querySelectorAll(".cart-item-details").forEach((button) => button.addEventListener("click", () => showCartDetails(button.dataset.id)));
}

function showCartDetails(id) {
  const item = serverCart.find((candidate) => candidate.id === id);
  if (!item) return;
  const groupsHtml = item.groups.map((group) => group.type === "multi"
    ? `<section class="cart-item-group"><div class="cart-item-group-header"><span>${escapeCartHtml(group.category)}</span><span class="cart-item-count">${group.count}</span></div><ul>${group.value.map((name) => `<li>${escapeCartHtml(name)}</li>`).join("")}</ul></section>`
    : `<section class="cart-item-group"><div class="cart-item-group-header"><span class="cart-item-category">${escapeCartHtml(group.category)}</span></div><div class="cart-item-value">${escapeCartHtml(group.value)}</div></section>`).join("");
  const dialog = document.createElement("dialog");
  dialog.className = "share-dialog cart-detail-dialog";
  dialog.setAttribute("aria-labelledby", "cart-detail-title");
  dialog.innerHTML = `<div class="share-dialog-card"><header class="share-dialog-header"><div><span class="auth-kicker">${cartLocale("配置详情", "CONFIGURATION DETAILS")}</span><h2 id="cart-detail-title">${escapeCartHtml(item.titleName)}</h2><p class="cart-detail-model">${escapeCartHtml(item.modelName)} · ${escapeCartHtml(item.colorName)}</p></div><button class="btn btn-text btn-sm" type="button" aria-label="${cartLocale("关闭", "Close")}">✕</button></header><div class="cart-detail-content">${groupsHtml}</div></div>`;
  document.body.appendChild(dialog);
  dialog.querySelector("button")?.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => dialog.remove(), { once: true });
  dialog.showModal();
}

async function createCurrentSavedConfig() {
  const snapshot = state.getSnapshot();
  const model = configData.models.find((item) => item.id === snapshot.currentModelId);
  if (!model) throw new Error(cartLocale("未找到设备", "Device not found"));
  return authRequest("/configs", {
    method: "POST",
    body: JSON.stringify({ name: `${model.name} ${cartLocale("配置", "Configuration")}`, product_id: snapshot.currentModelId, color: snapshot.currentColor, selections: snapshot.selections, lang: localStorage.getItem("boten-language") === "en" ? "en" : "zh" })
  });
}

async function saveCurrentConfigToServer() {
  try {
    await createCurrentSavedConfig();
    await refreshServerCart(); openCartPanel();
  } catch (error) { alert(`${cartLocale("保存失败", "Save failed")}: ${error.message}`); }
}

function addCurrentConfigToCart() { requireLogin(saveCurrentConfigToServer); }

function formatShareExpiry(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value || "--") : date.toLocaleString(cartLocale("zh-CN", "en"), { hour12: false });
}

function showShareResult(share) {
  const dialog = document.getElementById("share-dialog");
  dialog.dataset.code = share.code;
  document.getElementById("share-code").textContent = share.code;
  document.getElementById("share-expires-at").textContent = formatShareExpiry(share.expires_at);
  document.getElementById("share-copy-status").textContent = cartText("copyHint", "点击代码复制", "Tap code to copy");
  if (!dialog.open) dialog.showModal();
}

async function copyShareCode() {
  const code = document.getElementById("share-dialog")?.dataset.code;
  if (!code) return;
  try {
    await navigator.clipboard.writeText(code);
    document.getElementById("share-copy-status").textContent = `${cartText("copied", "已复制", "Copied")} ${code}`;
  } catch (_) {
    window.prompt(cartText("copyCode", "复制分享码", "Copy code"), code);
  }
}

async function shareSavedConfig(id, button) {
  if (!id) return;
  const originalText = button?.textContent;
  if (button) { button.disabled = true; button.textContent = cartText("generating", "生成中…", "Generating…"); }
  try {
    const share = await authRequest(`/configs/${encodeURIComponent(id)}/share`, { method: "POST" });
    showShareResult(share);
  } catch (error) {
    alert(`${cartLocale("分享失败", "Share failed")}: ${error.message}`);
  } finally {
    if (button) { button.disabled = false; button.textContent = originalText; }
  }
}

async function shareCurrentConfig() {
  const button = document.getElementById("share-current");
  button.disabled = true; button.textContent = cartText("generating", "生成中…", "Generating…");
  try {
    const saved = await createCurrentSavedConfig();
    const share = await authRequest(`/configs/${encodeURIComponent(saved.id)}/share`, { method: "POST" });
    await refreshServerCart();
    showShareResult(share);
  } catch (error) {
    alert(`${cartLocale("分享失败", "Share failed")}: ${error.message}`);
  } finally {
    button.disabled = false; button.textContent = cartText("shareCurrent", "分享当前配置", "Share configuration");
  }
}

async function removeCartItem(id) {
  try { await authRequest(`/configs/${encodeURIComponent(id)}`, { method: "DELETE" }); await refreshServerCart(); }
  catch (error) { alert(`${cartLocale("删除失败", "Delete failed")}: ${error.message}`); }
}

async function clearCart() {
  if (!serverCart.length || !confirm(cartText("confirmClear", "删除全部配置？", "Delete all items?"))) return;
  try {
    await Promise.all(serverCart.map((item) => authRequest(`/configs/${encodeURIComponent(item.id)}`, { method: "DELETE" })));
    await refreshServerCart();
  } catch (error) { alert(`${cartLocale("清空失败", "Clear failed")}: ${error.message}`); }
}

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
  if (event.key !== "Tab" || !panel?.classList.contains("open")) return;
  const items = Array.from(panel.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')).filter((item) => !item.hidden);
  if (!items.length) return;
  const first = items[0]; const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}

function initCart() {
  renderCartCount(); renderCartPanel();
  subscribeAuth(() => refreshServerCart());
  if (isAuthenticated()) refreshServerCart();
  document.getElementById("save-cart")?.addEventListener("click", addCurrentConfigToCart);
  document.getElementById("share-current")?.addEventListener("click", () => requireLogin(shareCurrentConfig));
  document.getElementById("share-close")?.addEventListener("click", () => document.getElementById("share-dialog").close());
  document.getElementById("share-copy")?.addEventListener("click", copyShareCode);
  document.getElementById("share-code")?.addEventListener("click", copyShareCode);
  document.getElementById("cart-toggle")?.addEventListener("click", () => isAuthenticated() ? openCartPanel() : requireLogin(openCartPanel));
  document.getElementById("cart-close")?.addEventListener("click", closeCartPanel);
  document.getElementById("cart-backdrop")?.addEventListener("click", closeCartPanel);
  document.getElementById("cart-clear")?.addEventListener("click", clearCart);
  document.addEventListener("keydown", (event) => {
    const panel = document.getElementById("cart-panel");
    if (event.key === "Escape" && panel?.classList.contains("open")) closeCartPanel();
    trapCartFocus(event);
  });
}
