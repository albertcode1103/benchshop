const catalogMarketplaceState = {
  type: "tools",
  items: [],
  category: "all",
  query: "",
  loading: false,
  pendingQuantities: new Map(),
  quantityTimers: new Map(),
  quantitySaving: new Set()
};

const marketplaceText = (key, zh, en) => window.botenI18n?.t(key)
  || (localStorage.getItem("boten-language") === "en" ? en : zh);

function marketplaceLanguage() {
  return localStorage.getItem("boten-language") === "en" ? "en" : "zh";
}

function escapeMarketplaceHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  }[char]));
}

function setMarketplaceStatus(message = "", kind = "") {
  const status = document.getElementById("catalog-marketplace-status");
  if (!status) return;
  status.textContent = message;
  status.className = `catalog-marketplace-status${kind ? ` ${kind}` : ""}`;
  status.hidden = !message;
}

function renderMarketplaceCategories() {
  const container = document.getElementById("catalog-category-filters");
  if (!container) return;
  const categories = [...new Map(catalogMarketplaceState.items.map((item) => [item.category_id, item.category_name])).entries()];
  const entries = [["all", marketplaceText("allCategories", "全部", "All")], ...categories];
  if (!entries.some(([id]) => id === catalogMarketplaceState.category)) catalogMarketplaceState.category = "all";
  container.innerHTML = entries.map(([id, name]) => `
    <button type="button" class="catalog-filter-chip ${catalogMarketplaceState.category === id ? "active" : ""}"
      data-catalog-category="${escapeMarketplaceHtml(id)}" aria-pressed="${catalogMarketplaceState.category === id}">
      ${escapeMarketplaceHtml(name || "--")}
    </button>`).join("");
  container.querySelectorAll("[data-catalog-category]").forEach((button) => {
    button.addEventListener("click", () => {
      catalogMarketplaceState.category = button.dataset.catalogCategory;
      renderCatalogMarketplace();
    });
  });
}

function filteredMarketplaceItems() {
  const query = catalogMarketplaceState.query.trim().toLocaleLowerCase();
  return catalogMarketplaceState.items.filter((item) => {
    if (catalogMarketplaceState.category !== "all" && item.category_id !== catalogMarketplaceState.category) return false;
    if (!query) return true;
    return [item.code, item.name, item.description, item.note, item.category_name]
      .some((value) => String(value || "").toLocaleLowerCase().includes(query));
  });
}

function currentMarketplaceCart() {
  return typeof window.getCatalogCartSnapshot === "function"
    ? window.getCatalogCartSnapshot(catalogMarketplaceState.type)
    : [];
}

function aggregateMarketplaceCart() {
  const aggregated = new Map();
  currentMarketplaceCart().forEach((item) => {
    const key = item.optionId || item.id;
    const current = aggregated.get(key) || { optionId: key, code: item.code, name: item.name, quantity: 0 };
    current.quantity += Number(item.quantity || 1);
    aggregated.set(key, current);
  });
  catalogMarketplaceState.pendingQuantities.forEach((quantity, optionId) => {
    const catalogItem = catalogMarketplaceState.items.find((item) => item.id === optionId);
    const current = aggregated.get(optionId);
    if (!catalogItem && !current) return;
    if (quantity <= 0) {
      aggregated.delete(optionId);
      return;
    }
    aggregated.set(optionId, {
      optionId,
      code: current?.code || catalogItem?.code,
      name: current?.name || catalogItem?.name,
      quantity
    });
  });
  return aggregated;
}

function scheduleMarketplaceQuantitySave(optionId, quantity, delay = 150) {
  const target = Math.max(0, Math.min(999, Number(quantity || 0)));
  catalogMarketplaceState.pendingQuantities.set(optionId, target);
  const previousTimer = catalogMarketplaceState.quantityTimers.get(optionId);
  if (previousTimer) clearTimeout(previousTimer);
  const timer = setTimeout(() => persistMarketplaceQuantity(optionId), delay);
  catalogMarketplaceState.quantityTimers.set(optionId, timer);
  renderCatalogMarketplace();
}

async function persistMarketplaceQuantity(optionId) {
  catalogMarketplaceState.quantityTimers.delete(optionId);
  if (catalogMarketplaceState.quantitySaving.has(optionId)) return;
  const submittedQuantity = catalogMarketplaceState.pendingQuantities.get(optionId);
  if (submittedQuantity === undefined) return;
  catalogMarketplaceState.quantitySaving.add(optionId);
  try {
    setMarketplaceStatus();
    await authRequest(`/cart/catalog-options/${encodeURIComponent(optionId)}`, {
      method: "PUT",
      body: JSON.stringify({ quantity: submittedQuantity, lang: marketplaceLanguage() })
    });
    if (catalogMarketplaceState.pendingQuantities.get(optionId) === submittedQuantity) {
      catalogMarketplaceState.pendingQuantities.delete(optionId);
      if (typeof window.refreshCatalogCartOnly === "function") await window.refreshCatalogCartOnly();
      else if (typeof refreshServerCart === "function") await refreshServerCart();
    }
  } catch (error) {
    if (catalogMarketplaceState.pendingQuantities.get(optionId) === submittedQuantity) {
      catalogMarketplaceState.pendingQuantities.delete(optionId);
    }
    setMarketplaceStatus(`${marketplaceText("requestFailed", "操作失败", "Request failed")}：${error.message}`, "error");
    if (typeof window.refreshCatalogCartOnly === "function") await window.refreshCatalogCartOnly().catch(() => {});
  } finally {
    catalogMarketplaceState.quantitySaving.delete(optionId);
    const latestQuantity = catalogMarketplaceState.pendingQuantities.get(optionId);
    if (latestQuantity !== undefined && latestQuantity !== submittedQuantity) {
      scheduleMarketplaceQuantitySave(optionId, latestQuantity, 0);
    } else {
      renderCatalogMarketplace();
    }
  }
}

async function changeMarketplaceCartQuantity(optionId, quantity, delta) {
  if (!optionId || ![-1, 1].includes(delta)) return;
  if (delta > 0 && quantity >= 999) return;
  const item = catalogMarketplaceState.items.find((candidate) => candidate.id === optionId);
  if (delta < 0 && quantity === 1) {
    const message = marketplaceText(
      "confirmRemoveCatalogItem",
      "确定从购物车中移除“{name}”吗？",
      "Remove “{name}” from the cart?"
    ).replace("{name}", item?.name || "--");
    const title = marketplaceText("removeCartItemTitle", "移除购物车项目", "Remove Cart Item");
    const confirmed = await window.confirmCartRemoval?.(message, title);
    if (!confirmed) return;
  }
  scheduleMarketplaceQuantitySave(optionId, quantity + delta);
}

function marketplaceSummaryRow(item) {
  return `<div class="catalog-summary-row"><span><strong>${escapeMarketplaceHtml(item.code || "--")}</strong><small>${escapeMarketplaceHtml(item.name || "--")}</small></span><b>× ${Number(item.quantity || 1)}</b></div>`;
}

function renderMarketplaceSummary() {
  const toolMode = catalogMarketplaceState.type === "tools";
  const cartTitle = document.getElementById("catalog-cart-summary-title");
  const cartList = document.getElementById("catalog-cart-summary-list");
  const cartCount = document.getElementById("catalog-cart-summary-count");
  const toggle = document.getElementById("catalog-summary-toggle");
  const toggleLabel = document.getElementById("catalog-summary-toggle-label");
  const toggleCount = document.getElementById("catalog-summary-toggle-count");
  const closeButton = document.getElementById("catalog-summary-close");
  if (!cartList) return;

  if (cartTitle) cartTitle.textContent = toolMode
    ? marketplaceText("toolsInCart", "购物车中的工具", "Tools in Cart")
    : marketplaceText("accessoriesInCart", "购物车中的附件", "Accessories in Cart");
  const cartItems = [...aggregateMarketplaceCart().values()];
  cartList.innerHTML = cartItems.length
    ? cartItems.map(marketplaceSummaryRow).join("")
    : `<p class="catalog-summary-empty">${marketplaceText("nothingInCartType", "购物车中暂无此类项目", "No items of this type in the cart")}</p>`;
  const countText = (count) => marketplaceText("cartGroupCount", "{count} 项", "{count} items").replace("{count}", count);
  if (cartCount) cartCount.textContent = countText(cartItems.length);
  const cartLabel = toolMode
    ? marketplaceText("toolsInCart", "购物车中的工具", "Tools in Cart")
    : marketplaceText("accessoriesInCart", "购物车中的附件", "Accessories in Cart");
  if (toggleLabel) toggleLabel.textContent = cartLabel;
  if (toggleCount) toggleCount.textContent = String(cartItems.length);
  if (toggle) toggle.setAttribute("aria-label", `${cartLabel}，${countText(cartItems.length)}`);
  if (closeButton) closeButton.setAttribute("aria-label", marketplaceText("close", "关闭已选项目", "Close selected items"));
}

function bindCatalogSummaryDrawer() {
  const toggle = document.getElementById("catalog-summary-toggle");
  const panel = document.getElementById("catalog-summary-panel");
  const closeButton = document.getElementById("catalog-summary-close");
  const backdrop = document.getElementById("drawer-backdrop");
  if (!toggle || !panel || !closeButton || !backdrop) return;

  let previousFocus = null;
  const pageRegions = [document.querySelector(".site-header"), document.querySelector(".config-stage"), document.querySelector(".site-footer")].filter(Boolean);
  const focusable = () => Array.from(panel.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')).filter((item) => !item.hidden);
  const closeDrawer = (restoreFocus = true) => {
    if (!panel.classList.contains("open")) return;
    panel.classList.remove("open");
    backdrop.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
    panel.removeAttribute("aria-modal");
    pageRegions.forEach((region) => { region.inert = false; });
    document.body.style.overflow = "";
    if (restoreFocus && !toggle.hidden) previousFocus?.focus?.();
    previousFocus = null;
  };
  const openDrawer = () => {
    if (window.matchMedia("(min-width: 1024px)").matches) return;
    previousFocus = document.activeElement;
    panel.classList.add("open");
    backdrop.classList.add("open");
    toggle.setAttribute("aria-expanded", "true");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    pageRegions.forEach((region) => { region.inert = true; });
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => closeButton.focus());
  };

  window.botenCloseCatalogSummary = closeDrawer;
  toggle.addEventListener("click", openDrawer);
  closeButton.addEventListener("click", () => closeDrawer());
  backdrop.addEventListener("click", () => closeDrawer());
  window.matchMedia("(min-width: 1024px)").addEventListener("change", (event) => { if (event.matches) closeDrawer(false); });
  document.addEventListener("keydown", (event) => {
    if (!panel.classList.contains("open")) return;
    if (event.key === "Escape") { event.preventDefault(); closeDrawer(); return; }
    if (event.key !== "Tab") return;
    const items = focusable();
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
}

function renderCatalogMarketplace() {
  const grid = document.getElementById("catalog-product-grid");
  const empty = document.getElementById("catalog-marketplace-empty");
  const panel = document.getElementById("catalog-marketplace-panel");
  if (!grid || !empty || !panel) return;
  renderMarketplaceCategories();
  const items = filteredMarketplaceItems();
  const cartQuantities = aggregateMarketplaceCart();
  panel.setAttribute("aria-labelledby", `catalog-tab-${catalogMarketplaceState.type}`);
  empty.hidden = items.length > 0 || catalogMarketplaceState.loading;
  grid.innerHTML = items.map((item) => {
    const image = window.botenAssetUrl(item.image_path) || "assets/images/placeholder-option.svg";
    const imageWidth = Number(item.image_width) || 640;
    const imageHeight = Number(item.image_height) || 320;
    const description = item.description || item.note || "";
    const inCartQuantity = cartQuantities.get(item.id)?.quantity || 0;
    const selected = inCartQuantity > 0;
    return `<article class="catalog-product-card${selected ? " selected" : ""}" data-catalog-item="${escapeMarketplaceHtml(item.id)}">
      <span class="catalog-product-selected-mark" ${selected ? "" : "hidden"} aria-label="${marketplaceText("selectedItem", "已选择", "Selected")}"><span aria-hidden="true">✓</span></span>
      <div class="catalog-product-media">
        <img src="${escapeMarketplaceHtml(image)}" alt="" width="${imageWidth}" height="${imageHeight}" loading="lazy" onerror="this.src='assets/images/placeholder-option.svg'" />
      </div>
      <div class="catalog-product-body">
        <div class="catalog-product-code">${escapeMarketplaceHtml(item.code || "--")}</div>
        <h3>${escapeMarketplaceHtml(item.name || "--")}</h3>
        ${description ? `<p>${escapeMarketplaceHtml(description)}</p>` : ""}
        ${inCartQuantity ? `<div class="catalog-product-in-cart">${marketplaceText("inCartQuantity", "购物车中：{count}", "In cart: {count}").replace("{count}", inCartQuantity)}</div>` : ""}
      </div>
      <footer class="catalog-product-actions">
        <label class="catalog-quantity-field"><span>${marketplaceText("quantity", "数量", "Quantity")}</span>
          <span class="catalog-quantity-control">
            <button type="button" data-quantity-step="-1" aria-label="${marketplaceLanguage() === "en" ? "Decrease quantity" : "减少数量"}">−</button>
            <input type="number" min="1" max="999" step="1" value="${inCartQuantity || 1}" inputmode="numeric" aria-label="${marketplaceText("quantity", "数量", "Quantity")}" ${selected ? "readonly" : ""} />
            <button type="button" data-quantity-step="1" aria-label="${marketplaceLanguage() === "en" ? "Increase quantity" : "增加数量"}">+</button>
          </span>
        </label>
        <button type="button" class="btn btn-primary catalog-add-button" data-add-catalog="${escapeMarketplaceHtml(item.id)}" ${selected ? "disabled" : ""}>${selected ? marketplaceText("addedToCart", "已加入购物车", "Added to Cart") : marketplaceText("addToCart", "加入购物车", "Add to Cart")}</button>
      </footer>
    </article>`;
  }).join("");

  grid.querySelectorAll("[data-quantity-step]").forEach((button) => {
    button.addEventListener("click", async () => {
      const input = button.parentElement?.querySelector("input");
      if (!input) return;
      const optionId = button.closest("[data-catalog-item]")?.dataset.catalogItem;
      const selected = optionId && aggregateMarketplaceCart().has(optionId);
      const step = Number(button.dataset.quantityStep);
      if (selected) {
        await changeMarketplaceCartQuantity(optionId, Number(input.value || 1), step);
        return;
      }
      const next = Math.max(1, Math.min(999, Number(input.value || 1) + step));
      input.value = String(next);
    });
  });
  grid.querySelectorAll('.catalog-quantity-control input').forEach((input) => {
    input.addEventListener("change", () => {
      input.value = String(Math.max(1, Math.min(999, Number(input.value || 1))));
    });
  });
  grid.querySelectorAll("[data-add-catalog]").forEach((button) => {
    button.addEventListener("click", () => addMarketplaceItem(button.dataset.addCatalog, button));
  });
  renderMarketplaceSummary();
}

async function addMarketplaceItem(optionId, button) {
  const card = button.closest("[data-catalog-item]");
  const input = card?.querySelector('input[type="number"]');
  const quantity = Math.max(1, Math.min(999, Number(input?.value || 1)));
  requireLogin(() => {
    setMarketplaceStatus();
    scheduleMarketplaceQuantitySave(optionId, quantity, 0);
  });
}

async function loadMarketplaceItems() {
  catalogMarketplaceState.loading = true;
  setMarketplaceStatus(marketplaceLanguage() === "en" ? "Loading…" : "正在加载…");
  renderCatalogMarketplace();
  try {
    const result = await catalogRequest(`/api/v1/catalog/items?type=${encodeURIComponent(catalogMarketplaceState.type)}&lang=${marketplaceLanguage()}`);
    catalogMarketplaceState.items = Array.isArray(result.items) ? result.items : [];
    catalogMarketplaceState.category = "all";
    setMarketplaceStatus();
  } catch (error) {
    catalogMarketplaceState.items = [];
    setMarketplaceStatus(`${marketplaceText("requestFailed", "加载失败", "Load failed")}：${error.message}`, "error");
  } finally {
    catalogMarketplaceState.loading = false;
    renderCatalogMarketplace();
  }
}

function selectMarketplaceType(button) {
  const type = button.dataset.catalogType;
  if (!type || type === catalogMarketplaceState.type) return;
  catalogMarketplaceState.type = type;
  document.querySelectorAll("[data-catalog-type]").forEach((tab) => {
    const active = tab.dataset.catalogType === type;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  loadMarketplaceItems();
}

window.selectMarketplaceCatalog = function selectMarketplaceCatalog(type) {
  if (!["tools", "accessories"].includes(type)) return;
  catalogMarketplaceState.type = type;
  document.querySelectorAll("[data-catalog-type]").forEach((tab) => {
    const active = tab.dataset.catalogType === type;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  const title = document.getElementById("catalog-marketplace-title");
  const description = document.getElementById("catalog-marketplace-description");
  if (title) title.textContent = type === "tools"
    ? marketplaceText("serviceTools", "维修工具", "Service Tools")
    : marketplaceText("accessories", "设备附件", "Accessories");
  if (description) description.textContent = marketplaceText(
    "catalogStandaloneDesc",
    "可独立选择数量并加入购物车，无需选择设备。",
    "Choose quantities and add items without selecting a device."
  );
  loadMarketplaceItems();
};

function initCatalogMarketplace() {
  const tabs = document.getElementById("catalog-type-tabs");
  const search = document.getElementById("catalog-marketplace-search");
  if (!tabs || !search) return;
  tabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-catalog-type]");
    if (button) selectMarketplaceType(button);
  });
  tabs.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const buttons = Array.from(tabs.querySelectorAll("[data-catalog-type]"));
    const current = buttons.indexOf(document.activeElement);
    if (current < 0) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1
      : (current + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next].focus();
    selectMarketplaceType(buttons[next]);
  });
  search.addEventListener("input", () => {
    catalogMarketplaceState.query = search.value;
    renderCatalogMarketplace();
  });
  bindCatalogSummaryDrawer();
  window.addEventListener("boten:cart-updated", renderCatalogMarketplace);
  renderMarketplaceSummary();
}
