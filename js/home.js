(function () {
  const en = localStorage.getItem("boten-language") === "en";
  const copy = en ? {
    title: "Test Equipment & Service Tools", description: "Explore equipment, choose configurations, and find the tools and accessories you need.",
    browse: "Browse Equipment", tools: "Service Tools", accessories: "Accessories", toolsAction: "Browse Tools", accessoriesAction: "Browse Accessories",
    loading: "Loading…", empty: "No products available", error: "Unable to load catalog. Please retry.", retry: "Retry"
  } : {
    title: "检测设备与维修工具", description: "浏览设备，选择配置，找到所需工具与附件。",
    browse: "浏览设备", tools: "维修工具", accessories: "设备附件", toolsAction: "浏览工具", accessoriesAction: "浏览附件",
    loading: "正在加载…", empty: "暂无可用产品", error: "目录加载失败，请重试。", retry: "重试"
  };
  const placeholder = "assets/images/placeholder-option.svg";
  let deviceModel = null;
  let deviceModels = [];
  let deviceIndex = 0;
  let applicationReady = false;
  const byId = id => document.getElementById(id);
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  let timer = null, hovering = false, touching = false;
  function syncAutoplay() {
    clearTimeout(timer);
    const carousel = document.querySelector(".home-carousel");
    const paused = reducedMotion.matches;
    const focused = carousel.contains(document.activeElement);
    const running = !paused && !hovering && !touching && !focused && !document.hidden &&
      document.body.dataset.selectionView === "home" && !byId("main-content").inert &&
      !document.querySelector("dialog[open]") && deviceModels.length > 1;
    if (running) timer = setTimeout(() => showDevice(deviceIndex + 1), 5000);
  }
  function deviceStatus(status) {
    applicationReady = status === "ready";
    deviceModels = applicationReady ? configData.models.filter(model => model.enabled !== false && model.navigationVisible !== false) : [];
    deviceIndex = 0;
    showDevice(0);
    byId("home-device-status").textContent = status === "error" ? copy.error : applicationReady ? (deviceModel ? "" : copy.empty) : copy.loading;
    byId("home-retry").hidden = status !== "error";
    byId("home-browse").disabled = !deviceModel;
    document.querySelectorAll("[data-home-catalog]").forEach(button => { button.disabled = !applicationReady; });
  }
  function showDevice(index) {
    deviceIndex = deviceModels.length ? (index + deviceModels.length) % deviceModels.length : 0;
    deviceModel = deviceModels[deviceIndex] || null;
    byId("home-device").disabled = !deviceModel;
    byId("home-device-model").textContent = deviceModel?.type || "";
    byId("home-device-name").textContent = deviceModel?.titleName || "";
    byId("home-device-image").src = deviceModel ? (resolveDetailImages(deviceModel)[0] || deviceModel.colorImages?.[deviceModel.defaultColor] || placeholder) : placeholder;
    byId("home-carousel-arrows").hidden = deviceModels.length < 2;
    syncAutoplay();
  }
  async function loadDirectory(type) {
    const card = document.querySelector(`[data-home-type="${type}"]`);
    const status = card.querySelector(".home-status");
    const retry = card.querySelector("[data-home-retry]");
    status.textContent = copy.loading;
    retry.hidden = true;
    try {
      const result = await catalogRequest(`/api/v1/catalog/items?type=${type}&lang=${en ? "en" : "zh"}`);
      card.querySelector("img").src = window.botenAssetUrl(result.items?.[0]?.image_path) || placeholder;
      status.textContent = result.items?.length ? "" : copy.empty;
    } catch (_) {
      status.textContent = copy.error;
      retry.hidden = false;
    }
  }
  function init() {
    const carousel = document.querySelector(".home-carousel");
    carousel.addEventListener("mouseenter", () => { hovering = true; syncAutoplay(); });
    carousel.addEventListener("mouseleave", () => { hovering = false; syncAutoplay(); });
    carousel.addEventListener("focusin", syncAutoplay);
    carousel.addEventListener("focusout", () => queueMicrotask(syncAutoplay));
    document.addEventListener("visibilitychange", syncAutoplay);
    reducedMotion.addEventListener("change", syncAutoplay);
    const viewObserver = new MutationObserver(syncAutoplay);
    viewObserver.observe(document.body, { attributes: true, subtree: true, attributeFilter: ["data-selection-view", "open"] });
    viewObserver.observe(byId("main-content"), { attributes: true, attributeFilter: ["inert"] });
    window.addEventListener("pagehide", () => clearTimeout(timer));
    window.addEventListener("pageshow", syncAutoplay);
    carousel.setAttribute("aria-label", en ? "Device Catalog" : "设备目录");
    document.querySelector(".home-carousel").setAttribute("aria-roledescription", en ? "carousel" : "轮播图");
    byId("home-device-prev").setAttribute("aria-label", en ? "Previous device" : "上一台设备");
    byId("home-device-next").setAttribute("aria-label", en ? "Next device" : "下一台设备");
    byId("home-device-prev").addEventListener("click", () => showDevice(deviceIndex - 1));
    byId("home-device-next").addEventListener("click", () => showDevice(deviceIndex + 1));
    document.querySelector(".home-carousel").addEventListener("keydown", event => {
      if (deviceModels.length < 2 || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      showDevice(deviceIndex + (event.key === "ArrowRight" ? 1 : -1));
    });
    let touchStart = null;
    let suppressClickUntil = 0;
    byId("home-device").addEventListener("touchstart", event => {
      touching = true; syncAutoplay();
      touchStart = event.touches.length === 1 ? { x: event.touches[0].clientX, y: event.touches[0].clientY } : null;
    }, { passive: true });
    byId("home-device").addEventListener("touchcancel", () => { touchStart = null; touching = false; syncAutoplay(); });
    byId("home-device").addEventListener("touchend", event => {
      touching = event.touches.length > 0; syncAutoplay();
      if (!touchStart || !event.changedTouches.length) return;
      const dx = event.changedTouches[0].clientX - touchStart.x;
      const dy = event.changedTouches[0].clientY - touchStart.y;
      touchStart = null;
      if (deviceModels.length > 1 && Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.5) {
        suppressClickUntil = Date.now() + 500;
        showDevice(deviceIndex + (dx < 0 ? 1 : -1));
      }
    }, { passive: true });
    byId("home-title").textContent = copy.title;
    byId("home-title").tabIndex = -1;
    byId("home-description").textContent = copy.description;
    byId("home-browse").textContent = copy.browse;
    byId("home-retry").textContent = copy.retry;
    byId("home-retry").addEventListener("click", () => location.reload());
    byId("home-browse").addEventListener("click", () => window.botenOpenEquipment?.());
    byId("home-device").addEventListener("click", () => {
      if (Date.now() < suppressClickUntil) return;
      if (deviceModel) window.botenNavigateCatalog?.(`device:${deviceModel.id}`);
    });
    byId("home-page").addEventListener("error", event => {
      const image = event.target;
      if (image.tagName === "IMG" && !image.src.endsWith(placeholder)) image.src = placeholder;
    }, true);
    for (const type of ["tools", "accessories"]) {
      const card = document.querySelector(`[data-home-type="${type}"]`);
      card.querySelector("h2").textContent = copy[type];
      card.querySelector("[data-home-catalog]").textContent = copy[type + "Action"];
      card.querySelector("[data-home-catalog]").addEventListener("click", () => window.botenNavigateCatalog?.(`catalog:${type}`));
      const retry = card.querySelector("[data-home-retry]");
      retry.textContent = copy.retry;
      retry.addEventListener("click", () => loadDirectory(type));
      loadDirectory(type);
    }
    window.botenHomeDeviceStatus = deviceStatus;
    deviceStatus(window.catalogSource === "api" ? "ready" : window.catalogSource === "error" ? "error" : "loading");
    applySelectionView(restoredSelectionView());
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
