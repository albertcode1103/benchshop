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
  const groups = [{ type: "single", category: localStorage.getItem("boten-language") === "en" ? "Appearance" : "外观颜色", value: getColorLabel(snapshot.color.code) }];
  snapshot.categories.forEach((category) => {
    const values = category.options.map((option) => {
      if (category.id !== "cri" || !option.description) return getSpecLabel(category.id, option.name);
      return `${option.name} | ${descriptionText(option.description)}`;
    });
    if (!values.length) return;
    groups.push(category.multiple
      ? { type: "multi", category: category.name, value: values, count: values.length }
      : { type: "single", category: category.name, value: values[0] });
  });
  return {
    id: saved.id,
    savedAt: saved.created_at,
    modelName: snapshot.product.name,
    titleName: saved.name || snapshot.product.title_name,
    colorName: getColorLabel(snapshot.color.code),
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
    const result = await authRequest("/configs");
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
    const groupsHtml = item.groups.map((group) => group.type === "multi"
      ? `<div class="cart-item-group"><div class="cart-item-group-header"><span>${escapeCartHtml(group.category)}</span><span class="cart-item-count">${group.count}</span></div><ul>${group.value.map((name) => `<li>${escapeCartHtml(name)}</li>`).join("")}</ul></div>`
      : `<div class="cart-item-group"><div class="cart-item-group-header"><span class="cart-item-category">${escapeCartHtml(group.category)}</span></div><div class="cart-item-value">${escapeCartHtml(group.value)}</div></div>`).join("");
    return `<article class="cart-item"><header class="cart-item-header"><div><div class="cart-item-model">${escapeCartHtml(item.modelName)}</div><div class="cart-item-title">${escapeCartHtml(item.titleName)} · ${escapeCartHtml(item.colorName)}</div></div><div class="cart-item-actions"><button class="btn btn-secondary btn-sm cart-item-share" type="button" data-id="${escapeCartHtml(item.id)}">${cartText("shareAction", "分享", "Share")}</button><button class="btn btn-text btn-sm cart-item-remove" type="button" data-id="${escapeCartHtml(item.id)}">${cartText("deleteAction", "删除", "Delete")}</button></div></header><div class="cart-item-body">${groupsHtml}</div></article>`;
  }).join("");
  itemsEl.querySelectorAll(".cart-item-share").forEach((button) => button.addEventListener("click", () => shareSavedConfig(button.dataset.id, button)));
  itemsEl.querySelectorAll(".cart-item-remove").forEach((button) => button.addEventListener("click", () => removeCartItem(button.dataset.id)));
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
  panel.classList.add("open"); backdrop.classList.add("open"); panel.setAttribute("aria-hidden", "false"); backdrop.setAttribute("aria-hidden", "false"); document.body.style.overflow = "hidden";
}

function closeCartPanel() {
  const panel = document.getElementById("cart-panel"); const backdrop = document.getElementById("cart-backdrop");
  if (!panel || !backdrop) return;
  panel.classList.remove("open"); backdrop.classList.remove("open"); panel.setAttribute("aria-hidden", "true"); backdrop.setAttribute("aria-hidden", "true"); document.body.style.overflow = "";
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
  });
}
