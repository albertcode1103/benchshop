
  const rendererElements = {
    deviceSelect: document.getElementById("device-select"),
    pageTitle: document.getElementById("page-title"),
    pageSubtitle: document.getElementById("page-subtitle"),
    pageDesc: document.getElementById("page-desc"),
    previewArea: document.getElementById("preview-area"),
    colorSection: document.getElementById("color-section"),
    colorTitle: document.getElementById("color-title"),
    colorOptions: document.getElementById("color-options"),
    motorSection: document.getElementById("motor-section"),
    motorTitle: document.getElementById("motor-title"),
    motorOptions: document.getElementById("motor-options"),
    voltageSection: document.getElementById("voltage-section"),
    voltageTitle: document.getElementById("voltage-title"),
    voltageOptions: document.getElementById("voltage-options"),
    categoryTabs: document.getElementById("category-tabs"),
    specChips: document.getElementById("spec-chips"),
    optionsPanel: document.getElementById("options-panel"),
    summaryModelName: document.getElementById("summary-model-name"),
    summaryList: document.getElementById("summary-list"),
    summaryEmpty: document.getElementById("summary-empty"),
    summaryToggle: document.getElementById("summary-toggle"),
    summaryClose: document.getElementById("summary-close"),
    drawerBackdrop: document.getElementById("drawer-backdrop"),
    summaryPanel: document.getElementById("summary-panel")
  };

  const sectionTitles = {
    zh: {
      color: "外观颜色",
      motor: "电机配置",
      voltage: "供电配置"
    },
    en: {
      color: "Appearance",
      motor: "Motor",
      voltage: "Power Supply"
    }
  };

  function getSectionTitle(sectionId) {
    const language = localStorage.getItem("boten-language") === "en" ? "en" : "zh";
    return sectionTitles[language][sectionId];
  }

  let rendererStateRef = null;

  function bindRenderer(state) {
    rendererStateRef = state;
    state.subscribe(render);
    bindDeviceSelect();
    bindDrawerEvents();
    bindStickyHeader();
    render(state.getSnapshot());
  }

  function bindDeviceSelect() {
    if (!rendererElements.deviceSelect) return;
    rendererElements.deviceSelect.addEventListener("change", (e) => {
      rendererStateRef.setModel(e.target.value);
    });
  }

  function render(snapshot) {
    const model = configData.models.find((m) => m.id === snapshot.currentModelId);
    if (!model) return;

    renderDeviceSelect(model);
    renderHeader(model);
    renderGallery(model, snapshot.currentColor);
    renderColorSection(model, snapshot.currentColor);
    renderSpecSection(model, "motor", rendererElements.motorSection, rendererElements.motorOptions, rendererElements.motorTitle);
    renderSpecSection(model, "voltage", rendererElements.voltageSection, rendererElements.voltageOptions, rendererElements.voltageTitle);
    renderCategoryTabs(model, snapshot.currentCategoryId);
    renderSpecChips(model, snapshot);
    renderOptions(model, snapshot.currentCategoryId, snapshot.selections);
    renderSummary(model, snapshot);
  }

  function renderDeviceSelect(currentModel) {
    if (!rendererElements.deviceSelect) return;

    rendererElements.deviceSelect.innerHTML = configData.models
      .map(
        (m) =>
          `<option value="${m.id}" ${m.id === currentModel.id ? "selected" : ""}>${m.type}</option>`
      )
      .join("");
  }

  function renderHeader(model) {
    if (rendererElements.pageTitle) rendererElements.pageTitle.textContent = model.type;
    if (rendererElements.pageSubtitle) rendererElements.pageSubtitle.textContent = model.titleName;
    if (rendererElements.pageDesc) rendererElements.pageDesc.textContent = model.description;
  }

  let galleryState = {
    currentIndex: 0,
    urls: [],
    startX: 0,
    startY: 0,
    isDragging: false
  };

  function renderGallery(model, color) {
    if (!rendererElements.previewArea) return;

    const viewport = rendererElements.previewArea.querySelector(".gallery-viewport");
    if (!viewport) return;

    const urls = resolveGalleryImages(model, color || getDefaultColor(model));
    galleryState.urls = urls;
    galleryState.currentIndex = 0;

    const track = viewport.querySelector(".gallery-track");
    const dots = viewport.querySelector(".gallery-dots");

    track.innerHTML = urls
      .map(
        (url, idx) => `
          <div class="gallery-slide" data-index="${idx}">
            <img src="${url}" alt="${model.name} 图片 ${idx + 1}" loading="${idx === 0 ? "eager" : "lazy"}"
                 onerror="this.src='assets/images/placeholder-option.svg'" />
          </div>
        `
      )
      .join("");

    dots.innerHTML = urls
      .map(
        (_, idx) =>
          `<button type="button" class="gallery-dot ${idx === 0 ? "active" : ""}" data-index="${idx}" aria-label="第 ${idx + 1} 张"></button>`
      )
      .join("");

    updateGalleryPosition(viewport);
    bindGalleryEvents(viewport);
  }

  function updateGalleryPosition(viewport) {
    const track = viewport.querySelector(".gallery-track");
    if (!track) return;
    track.style.transform = `translateX(-${galleryState.currentIndex * 100}%)`;

    viewport.querySelectorAll(".gallery-dot").forEach((dot, idx) => {
      dot.classList.toggle("active", idx === galleryState.currentIndex);
    });
  }

  function goToGallerySlide(viewport, index) {
    if (galleryState.urls.length === 0) return;
    galleryState.currentIndex = Math.max(0, Math.min(index, galleryState.urls.length - 1));
    updateGalleryPosition(viewport);
  }

  function moveGallery(viewport, delta) {
    goToGallerySlide(viewport, galleryState.currentIndex + delta);
  }

  function bindGalleryEvents(viewport) {
    const prevBtn = viewport.querySelector(".gallery-prev");
    const nextBtn = viewport.querySelector(".gallery-next");

    if (prevBtn) {
      prevBtn.onclick = () => moveGallery(viewport, -1);
    }
    if (nextBtn) {
      nextBtn.onclick = () => moveGallery(viewport, 1);
    }

    viewport.querySelectorAll(".gallery-dot").forEach((dot) => {
      dot.onclick = () => goToGallerySlide(viewport, parseInt(dot.dataset.index, 10));
    });

    // Touch swipe
    viewport.ontouchstart = (e) => {
      galleryState.startX = e.touches[0].clientX;
      galleryState.startY = e.touches[0].clientY;
      galleryState.isDragging = true;
    };

    viewport.ontouchmove = (e) => {
      if (!galleryState.isDragging) return;
      const x = e.touches[0].clientX;
      const y = e.touches[0].clientY;
      const dx = galleryState.startX - x;
      const dy = galleryState.startY - y;

      // Prevent vertical scroll only when horizontal drag is dominant
      if (Math.abs(dx) > Math.abs(dy)) {
        e.preventDefault();
      }
    };

    viewport.ontouchend = (e) => {
      if (!galleryState.isDragging) return;
      galleryState.isDragging = false;
      const endX = e.changedTouches[0].clientX;
      const endY = e.changedTouches[0].clientY;
      const dx = galleryState.startX - endX;
      const dy = galleryState.startY - endY;

      if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 50) {
        moveGallery(viewport, dx > 0 ? 1 : -1);
      }
    };

    // Mouse drag
    viewport.onmousedown = (e) => {
      galleryState.startX = e.clientX;
      galleryState.isDragging = true;
      viewport.style.cursor = "grabbing";
    };

    viewport.onmousemove = (e) => {
      if (!galleryState.isDragging) return;
      e.preventDefault();
    };

    viewport.onmouseup = (e) => {
      if (!galleryState.isDragging) return;
      galleryState.isDragging = false;
      viewport.style.cursor = "";
      const dx = galleryState.startX - e.clientX;
      if (Math.abs(dx) > 50) {
        moveGallery(viewport, dx > 0 ? 1 : -1);
      }
    };

    viewport.onmouseleave = () => {
      galleryState.isDragging = false;
      viewport.style.cursor = "";
    };

    // Keyboard arrows
    viewport.setAttribute("tabindex", "0");
    viewport.onkeydown = (e) => {
      if (e.key === "ArrowLeft") {
        moveGallery(viewport, -1);
      } else if (e.key === "ArrowRight") {
        moveGallery(viewport, 1);
      }
    };
  }

  function renderColorSection(model, currentColor) {
    if (!rendererElements.colorSection || !rendererElements.colorOptions) return;

    if (rendererElements.colorTitle) {
      rendererElements.colorTitle.textContent = getSectionTitle("color");
    }

    const activeColor = currentColor || getDefaultColor(model);
    const colorClassMap = {
      Red: "color-red",
      Green: "color-green"
    };

    const gridHtml = model.colors
      .map((color) => {
        const isActive = activeColor === color;
        const colorClass = colorClassMap[color] || "";
        return `
          <div class="option-card option-card-color ${colorClass} ${isActive ? "active" : ""}"
               data-color="${color}" role="radio" aria-checked="${isActive}" tabindex="0">
            <div class="option-check" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3">
                <polyline points="5 12 10 17 19 8"/>
              </svg>
            </div>
            <div class="option-name">${getColorLabel(color)}</div>
          </div>
        `;
      })
      .join("");

    rendererElements.colorOptions.innerHTML = `<div class="options-grid color-options-grid compact-options">${gridHtml}</div>`;

    rendererElements.colorOptions.querySelectorAll(".option-card").forEach((card) => {
      const color = card.dataset.color;
      const activate = () => rendererStateRef.setColor(color);
      card.addEventListener("click", activate);
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          activate();
        }
      });
    });
  }

  function renderSpecSection(model, categoryId, sectionEl, optionsEl, titleEl) {
    if (!sectionEl || !optionsEl) return;

    const category = model.categories.find((c) => c.id === categoryId);
    if (!category) {
      sectionEl.hidden = true;
      return;
    }
    sectionEl.hidden = false;

    if (titleEl) {
      // Motor and power titles are catalog data and must follow the language
      // selected when the API was loaded, instead of a stale UI translation.
      titleEl.textContent = category.name || getSectionTitle(categoryId);
    }

    const selected = rendererStateRef.selections[categoryId];
    const isTextOnly = categoryId === "voltage" || categoryId === "motor";

    const gridClass = "options-grid compact-options text-options";

    const gridHtml = category.options
      .map((opt) => {
        const isActive = selected === opt.id;
        const media = isTextOnly
          ? ""
          : `<div class="option-media">
               <img src="${opt.image || "assets/images/placeholder-option.svg"}" alt="" loading="lazy" onerror="this.src='assets/images/placeholder-option.svg'" />
             </div>`;
        const label = opt.name;
        return `
          <div class="option-card ${isTextOnly ? "option-card-text" : ""} ${isActive ? "active" : ""}" data-option="${opt.id}" role="radio"
               aria-checked="${isActive}" tabindex="0">
            <div class="option-check" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3">
                <polyline points="5 12 10 17 19 8"/>
              </svg>
            </div>
            ${media}
            <div class="option-name">${label}</div>
          </div>
        `;
      })
      .join("");

    optionsEl.innerHTML = `<div class="${gridClass}">${gridHtml}</div>`;

    optionsEl.querySelectorAll(".option-card").forEach((card) => {
      const optionId = card.dataset.option;
      const activate = () => rendererStateRef.selectOption(categoryId, optionId, false);
      card.addEventListener("click", activate);
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          activate();
        }
      });
    });
  }

  function renderCategoryTabs(model, currentCategoryId) {
    rendererElements.categoryTabs.innerHTML = model.categories
      .filter((c) => c.id !== "motor" && c.id !== "voltage")
      .map(
        (cat) => `
          <button type="button" class="tab-btn ${cat.id === currentCategoryId ? "active" : ""}"
                  data-category="${cat.id}" role="tab" aria-selected="${cat.id === currentCategoryId}">
            ${cat.name}
          </button>
        `
      )
      .join("");

    rendererElements.categoryTabs.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => rendererStateRef.setCategory(btn.dataset.category));
    });
  }

  function renderSpecChips(model, snapshot) {
    if (!rendererElements.specChips) return;

    const motorCat = model.categories.find((c) => c.id === "motor");
    const voltageCat = model.categories.find((c) => c.id === "voltage");
    const motorOpt = motorCat?.options.find((o) => o.id === snapshot.selections.motor);
    const voltageOpt = voltageCat?.options.find((o) => o.id === snapshot.selections.voltage);
    const color = snapshot.currentColor || getDefaultColor(model);

    const chips = [
      { id: "model-chip", label: model.type, target: "device-select" },
      { id: "color-chip", label: getColorLabel(color), target: "color-section" },
      { id: "motor-chip", label: motorOpt?.name || "--", target: "motor-section" },
      { id: "voltage-chip", label: voltageOpt?.name || "--", target: "voltage-section" }
    ];

    rendererElements.specChips.innerHTML = chips
      .map(
        (chip) => `
          <button type="button" class="spec-chip" data-target="${chip.target}" aria-label="跳转到${chip.label}">
            <span class="spec-chip-label">${chip.label}</span>
          </button>
        `
      )
      .join("");

    rendererElements.specChips.querySelectorAll(".spec-chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetId = btn.dataset.target;
        const target = document.getElementById(targetId);
        if (!target) return;
        const headerHeight = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--header-height"), 10) || 64;
        const top = target.getBoundingClientRect().top + window.scrollY - headerHeight - 8;
        window.scrollTo({ top, behavior: "smooth" });
      });
    });
  }

  function renderOptions(model, currentCategoryId, selections) {
    const category = model.categories.find((c) => c.id === currentCategoryId);
    if (!category || category.id === "motor" || category.id === "voltage") {
      rendererElements.optionsPanel.innerHTML = "";
      return;
    }

    const selected = selections[category.id];
    const isMulti = category.multiple;
    const allSelected = isMulti && category.options.length > 0 && selected?.length === category.options.length;

    const headerHtml = `
      <div class="options-header">
        <div class="options-header-title">
          <h3>${category.name}</h3>
          ${isMulti ? `<button type="button" class="btn btn-secondary btn-sm select-all-toggle">${allSelected ? (window.botenI18n?.t("clearAll") || "全不选") : (window.botenI18n?.t("selectAll") || "全选")}</button>` : ""}
        </div>
        <p>${category.description}</p>
      </div>
    `;

    const gridHtml = category.options
      .map((opt) => {
        const isActive = isMulti
          ? selected?.includes(opt.id)
          : selected === opt.id;
        const media = opt.color
          ? `<div class="option-color" style="background-color: ${opt.color};" aria-label="${opt.name} 颜色"></div>`
          : `<img src="${opt.image || "assets/images/placeholder-option.svg"}" alt="" loading="lazy" onerror="this.src='assets/images/placeholder-option.svg'" />`;

        return `
          <div class="option-card option-card-config ${isActive ? "active" : ""}" data-option="${opt.id}" role="${isMulti ? "checkbox" : "radio"}"
               aria-checked="${isActive}" tabindex="0">
            <div class="option-check" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3">
                <polyline points="5 12 10 17 19 8"/>
              </svg>
            </div>
            <div class="option-media option-media-2by1">${media}</div>
            <div class="option-name">${opt.name}</div>
            ${opt.description ? `<div class="option-desc">${opt.description}</div>` : ""}
          </div>
        `;
      })
      .join("");

    rendererElements.optionsPanel.innerHTML = headerHtml + `<div class="options-grid config-options-grid">${gridHtml}</div>`;

    const selectAllToggle = rendererElements.optionsPanel.querySelector(".select-all-toggle");
    if (selectAllToggle) {
      selectAllToggle.addEventListener("click", () => {
        const optionIds = allSelected ? [] : category.options.map((option) => option.id);
        rendererStateRef.setAllOptions(category.id, optionIds);
      });
    }

    rendererElements.optionsPanel.querySelectorAll(".option-card").forEach((card) => {
      const optionId = card.dataset.option;
      const activate = () => rendererStateRef.selectOption(category.id, optionId, isMulti);
      card.addEventListener("click", activate);
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          activate();
        }
      });
    });
  }

  function renderSummary(model, snapshot) {
    const groups = buildSummaryGroups(model, snapshot);

    const modelHeading = [model.name, model.titleName]
      .filter((value, index, values) => value && values.indexOf(value) === index)
      .join(" · ");
    rendererElements.summaryModelName.textContent = modelHeading;

    if (groups.length === 0) {
      rendererElements.summaryList.innerHTML = "";
      rendererElements.summaryList.hidden = true;
      rendererElements.summaryEmpty.hidden = false;
      return;
    }

    rendererElements.summaryList.hidden = false;
    rendererElements.summaryEmpty.hidden = true;

    rendererElements.summaryList.innerHTML = groups
      .map((group) => {
        if (group.type === "multi") {
          const itemsHtml = group.value
            .map((name) => `<li class="summary-subitem">${name}</li>`)
            .join("");
          return `
            <li class="summary-group">
              <div class="summary-group-header">
                <span class="summary-group-name">${group.category}</span>
                <span class="summary-group-count">${group.count}</span>
              </div>
              <ul class="summary-sublist">${itemsHtml}</ul>
            </li>
          `;
        }
        return `
          <li class="summary-item">
            <div class="summary-item-name">
              <span class="summary-item-category">${group.category}</span>
              ${group.value}
            </div>
          </li>
        `;
      })
      .join("");
  }

  function bindDrawerEvents() {
    const toggle = rendererElements.summaryToggle;
    const panel = rendererElements.summaryPanel;
    const backdrop = rendererElements.drawerBackdrop;

    if (!toggle || !panel || !backdrop) return;

    const openDrawer = () => {
      panel.classList.add("open");
      backdrop.classList.add("open");
      toggle.setAttribute("aria-expanded", "true");
      document.body.style.overflow = "hidden";
    };

    const closeDrawer = () => {
      panel.classList.remove("open");
      backdrop.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
      document.body.style.overflow = "";
    };

    toggle.addEventListener("click", openDrawer);
    if (rendererElements.summaryClose) {
      rendererElements.summaryClose.addEventListener("click", closeDrawer);
    }
    backdrop.addEventListener("click", closeDrawer);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && panel.classList.contains("open")) {
        closeDrawer();
      }
    });
  }

  function bindStickyHeader() {
    const voltageSection = document.getElementById("voltage-section");
    const header = document.getElementById("config-sticky-header");
    if (!voltageSection || !header) return;

    const update = () => {
      const headerHeight =
        parseInt(getComputedStyle(document.documentElement).getPropertyValue("--header-height"), 10) || 64;
      const voltageRect = voltageSection.getBoundingClientRect();
      // 供电配置完全滚过顶部导航后，再显示已选配置快捷导航。
      header.classList.toggle("is-sticky", voltageRect.bottom <= headerHeight);
    };

    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update, { passive: true });
    update();
  }
