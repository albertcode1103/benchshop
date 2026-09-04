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
    const drawer = document.getElementById("catalog-navigation-drawer");
    const modelDrawer = document.getElementById("catalog-model-drawer");
    const backdrop = document.getElementById("catalog-navigation-backdrop");
    const deviceEntry = document.getElementById("catalog-device-entry");
    const modelList = document.getElementById("catalog-model-list");
    const select = document.getElementById("device-select");
    if (!toggle || !drawer || !modelDrawer || !backdrop || !deviceEntry || !modelList || !select) return;

    let returnFocus = null;
    const pageRegions = [document.querySelector(".site-header"), document.querySelector(".main"), document.querySelector(".site-footer")].filter(Boolean);

    function applyCopy() {
      document.getElementById("catalog-drawer-toggle-label").textContent = text("openProductNavigation", "打开产品导航", "Open product navigation");
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
      modelList.innerHTML = models.filter((model) => model.enabled !== false).map((model) => {
        const value = `device:${model.id}`;
        const active = current === value;
        return `<button type="button" class="catalog-model-item${active ? " active" : ""}" data-catalog-drawer-select="${escapeHtml(value)}" aria-current="${active ? "true" : "false"}">
          <strong>${escapeHtml(model.type || model.name || model.id)}</strong>
          <small>${escapeHtml(model.title_name || model.title || "")}</small>
          ${active ? '<span class="catalog-model-check" aria-hidden="true">✓</span>' : ""}
        </button>`;
      }).join("") || `<p class="catalog-model-empty">${text("noEnabledDevices", "暂无已启用设备", "No enabled devices")}</p>`;
    }

    function closeSecondLevel() {
      modelDrawer.classList.remove("open");
      modelDrawer.setAttribute("aria-hidden", "true");
      deviceEntry.setAttribute("aria-expanded", "false");
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
      toggle.setAttribute("aria-expanded", "false");
      pageRegions.forEach((region) => { region.inert = false; });
      document.body.style.overflow = "";
      returnFocus?.focus?.();
      returnFocus = null;
    }

    function openDrawer() {
      applyCopy();
      renderModels();
      returnFocus = document.activeElement;
      drawer.classList.add("open");
      backdrop.classList.add("open");
      drawer.setAttribute("aria-hidden", "false");
      backdrop.setAttribute("aria-hidden", "false");
      toggle.setAttribute("aria-expanded", "true");
      pageRegions.forEach((region) => { region.inert = true; });
      document.body.style.overflow = "hidden";
      requestAnimationFrame(() => deviceEntry.focus());
    }

    function openModels() {
      renderModels();
      modelDrawer.classList.add("open");
      modelDrawer.setAttribute("aria-hidden", "false");
      deviceEntry.setAttribute("aria-expanded", "true");
      requestAnimationFrame(() => modelList.querySelector("button")?.focus());
    }

    function activateSelection(value) {
      if (!value) return;
      select.value = value;
      closeDrawer();
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }

    toggle.addEventListener("click", openDrawer);
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
      const roots = modelDrawer.classList.contains("open") ? [drawer, modelDrawer] : [drawer];
      const focusable = roots.flatMap((root) => [...root.querySelectorAll('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])')]).filter((element) => !element.hidden);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
  }

  document.addEventListener("DOMContentLoaded", initCatalogNavigationDrawer);
})();
