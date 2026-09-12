(function () {
  const text = (key, zh, en) => {
    const translated = window.botenI18n?.t(key);
    if (translated && translated !== key) return translated;
    return localStorage.getItem("boten-language") === "en" ? en : zh;
  };

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  }[character]));

  function initCatalogNavigationDrawer() {
    const toggle = document.getElementById("catalog-drawer-toggle");
    const stageToggle = document.getElementById("catalog-stage-toggle");
    const marketplaceToggle = document.getElementById("catalog-marketplace-toggle");
    const toggles = [toggle, stageToggle, marketplaceToggle].filter(Boolean);
    const drawer = document.getElementById("catalog-navigation-drawer");
    const modelDrawer = document.getElementById("catalog-model-drawer");
    const backdrop = document.getElementById("catalog-navigation-backdrop");
    const deviceEntry = document.getElementById("catalog-device-entry");
    const modelList = document.getElementById("catalog-model-list");
    const select = document.getElementById("device-select");
    if (!toggle || !drawer || !modelDrawer || !backdrop || !deviceEntry || !modelList || !select) return;

    let returnFocus = null;
    let thumbnailRequest = 0;
    const placeholder = "assets/images/placeholder-option.svg";
    const thumbnailMarkup = (source) => `<img class="catalog-navigation-thumbnail" src="${escapeHtml(source || placeholder)}" width="48" height="48" alt="" loading="lazy" decoding="async">`;
    const modelThumbnail = (model) => model
      ? (resolveDetailImages(model)[0] || model.colorImages?.[model.defaultColor || model.colors?.[0]] || placeholder)
      : placeholder;
    // Decorative images never replace the button's accessible text or click target.
    [drawer, modelDrawer].forEach((root) => root.addEventListener("error", (event) => {
      const image = event.target;
      if (!image.matches?.("img.catalog-navigation-thumbnail") || image.dataset.fallback) return;
      image.dataset.fallback = "true";
      image.src = placeholder;
    }, true));
    drawer.querySelectorAll(".catalog-drawer-item").forEach((button) => {
      button.insertAdjacentHTML("afterbegin", thumbnailMarkup());
    });
    const pageRegions = [document.querySelector(".site-header"), document.querySelector(".main"), document.querySelector(".site-footer")].filter(Boolean);
    const stackedDrawers = window.matchMedia("(max-width: 639px)");

    function focusModelDrawer() {
      (modelList.querySelector("button") || document.getElementById("catalog-model-close")).focus();
    }

    function syncDrawerFocus() {
      const open = drawer.classList.contains("open");
      const covered = open && modelDrawer.classList.contains("open") && stackedDrawers.matches;
      drawer.inert = covered;
      drawer.setAttribute("aria-hidden", String(!open || covered));
      modelDrawer.setAttribute("role", "dialog");
      modelDrawer.setAttribute("aria-modal", String(covered));
      if (covered && drawer.contains(document.activeElement)) focusModelDrawer();
      else if (open && !stackedDrawers.matches && document.activeElement.id === "catalog-model-back") focusModelDrawer();
    }
    stackedDrawers.addEventListener("change", syncDrawerFocus);

    function applyCopy() {
      document.getElementById("catalog-drawer-toggle-label").textContent = text("openProductNavigation", "打开产品导航", "Open product navigation");
      document.getElementById("catalog-stage-toggle-label").textContent = text("viewCatalog", "目录", "Catalog");
      document.getElementById("catalog-marketplace-toggle-label").textContent = text("marketplaceCatalog", "目录", "Catalog");
      document.getElementById("catalog-navigation-title").textContent = text("productNavigation", "产品导航", "Product Navigation");
      document.getElementById("catalog-model-title").textContent = text("testEquipment", "检测设备", "Test Equipment");
      deviceEntry.querySelector("span").textContent = text("testEquipment", "检测设备", "Test Equipment");
      const categoryButtons = drawer.querySelectorAll("[data-catalog-drawer-select]");
      categoryButtons[0].querySelector("span").textContent = text("serviceTools", "维修工具", "Service Tools");
      categoryButtons[1].querySelector("span").textContent = text("accessories", "设备附件", "Accessories");
      document.getElementById("catalog-drawer-close").setAttribute("aria-label", text("closeProductNavigation", "关闭产品导航", "Close product navigation"));
      document.getElementById("catalog-model-close").setAttribute("aria-label", text("closeProductNavigation", "关闭产品导航", "Close product navigation"));
      document.getElementById("catalog-model-back").setAttribute("aria-label", text("backToProductCategories", "返回产品类别", "Back to product categories"));
    }

    function renderModels() {
      const models = Array.isArray(window.configData?.models) ? window.configData.models : (typeof configData !== "undefined" ? configData.models : []);
      const current = select.value;
      const visibleModels = models.filter((model) => model.enabled !== false && model.navigationVisible !== false);
      const deviceImage = deviceEntry.querySelector("img");
      delete deviceImage.dataset.fallback;
      deviceImage.src = modelThumbnail(visibleModels[0]);
      modelList.innerHTML = visibleModels.map((model) => {
        const value = `device:${model.id}`;
        const active = current === value;
        const modelName = model.type || model.name || model.id;
        const productName = model.titleName || model.title_name || model.title || "";
        return `<button type="button" class="catalog-model-item${active ? " active" : ""}" data-catalog-drawer-select="${escapeHtml(value)}" aria-current="${active ? "true" : "false"}">
          ${thumbnailMarkup(modelThumbnail(model))}
          <span class="catalog-navigation-copy"><strong>${escapeHtml(modelName)}</strong>
          ${productName ? `<small>${escapeHtml(productName)}</small>` : ""}</span>
          ${active ? '<span class="catalog-model-check" aria-hidden="true">✓</span>' : ""}
        </button>`;
      }).join("") || `<p class="catalog-model-empty">${text("noEnabledDevices", "暂无已启用设备", "No enabled devices")}</p>`;
    }

    function loadDirectoryThumbnails() {
      const request = ++thumbnailRequest;
      const language = localStorage.getItem("boten-language") === "en" ? "en" : "zh";
      ["tools", "accessories"].forEach(async (type) => {
        const image = drawer.querySelector(`[data-catalog-drawer-select="catalog:${type}"] img`);
        try {
          // Same public, ordered and availability-filtered collection as the marketplace.
          const result = await catalogRequest(`/api/v1/catalog/items?type=${type}&lang=${language}`);
          if (request !== thumbnailRequest) return;
          delete image.dataset.fallback;
          image.src = window.botenAssetUrl(result.items?.[0]?.image_path) || placeholder;
        } catch (_) {
          if (request !== thumbnailRequest) return;
          image.src = placeholder;
        }
      });
    }

    function closeSecondLevel() {
      modelDrawer.classList.remove("open");
      modelDrawer.setAttribute("aria-hidden", "true");
      deviceEntry.setAttribute("aria-expanded", "false");
      syncDrawerFocus();
      deviceEntry.focus();
    }

    function closeDrawer() {
      drawer.classList.remove("open");
      modelDrawer.classList.remove("open");
      backdrop.classList.remove("open");
      drawer.setAttribute("aria-hidden", "true");
      modelDrawer.setAttribute("aria-hidden", "true");
      backdrop.setAttribute("aria-hidden", "true");
      deviceEntry.setAttribute("aria-expanded", "false");
      toggles.forEach((button) => button.setAttribute("aria-expanded", "false"));
      pageRegions.forEach((region) => { region.inert = false; });
      document.body.style.overflow = "";
      returnFocus?.focus?.();
      returnFocus = null;
      syncDrawerFocus();
    }

    function openDrawer() {
      applyCopy();
      renderModels();
      loadDirectoryThumbnails();
      returnFocus = document.activeElement;
      drawer.classList.add("open");
      backdrop.classList.add("open");
      drawer.setAttribute("aria-hidden", "false");
      backdrop.setAttribute("aria-hidden", "false");
      toggles.forEach((button) => button.setAttribute("aria-expanded", "true"));
      pageRegions.forEach((region) => { region.inert = true; });
      document.body.style.overflow = "hidden";
      syncDrawerFocus();
      requestAnimationFrame(() => deviceEntry.focus());
    }

    function openModels() {
      renderModels();
      modelDrawer.classList.add("open");
      modelDrawer.setAttribute("aria-hidden", "false");
      deviceEntry.setAttribute("aria-expanded", "true");
      syncDrawerFocus();
      requestAnimationFrame(() => { if (modelDrawer.classList.contains("open")) focusModelDrawer(); });
    }

    function activateSelection(value) {
      if (!value) return;
      select.value = value;
      closeDrawer();
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }

    toggles.forEach((button) => button.addEventListener("click", openDrawer));
    document.getElementById("catalog-drawer-close").addEventListener("click", closeDrawer);
    document.getElementById("catalog-model-close").addEventListener("click", closeDrawer);
    document.getElementById("catalog-model-back").addEventListener("click", closeSecondLevel);
    backdrop.addEventListener("click", closeDrawer);
    deviceEntry.addEventListener("click", openModels);
    drawer.addEventListener("click", (event) => {
      const button = event.target.closest("[data-catalog-drawer-select]");
      if (button) activateSelection(button.dataset.catalogDrawerSelect);
    });
    modelList.addEventListener("click", (event) => {
      const button = event.target.closest("[data-catalog-drawer-select]");
      if (button) activateSelection(button.dataset.catalogDrawerSelect);
    });
    document.addEventListener("keydown", (event) => {
      if (!drawer.classList.contains("open")) return;
      if (event.key === "Escape") { event.preventDefault(); closeDrawer(); return; }
      if (event.key !== "Tab") return;
      const roots = modelDrawer.classList.contains("open") ? (stackedDrawers.matches ? [modelDrawer] : [drawer, modelDrawer]) : [drawer];
      const focusable = roots.flatMap((root) => [...root.querySelectorAll('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])')]).filter((element) => !element.hidden && element.getClientRects().length);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!focusable.includes(document.activeElement)) { event.preventDefault(); (event.shiftKey ? last : first).focus(); }
      else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initCatalogNavigationDrawer, { once: true });
  else initCatalogNavigationDrawer();
})();
