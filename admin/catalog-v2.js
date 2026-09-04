/* Device and catalog editor V2. Loaded after admin.js so existing account,
   share and quote workflows remain unchanged while catalog screens migrate. */
(function () {
  document.documentElement.dataset.catalogEditorVersion = "2";
  const ROOT_IDS = {
    optional: "catalog-optional",
    tools: "catalog-tools",
    accessories: "catalog-accessories"
  };
  const GROUP_LABELS = { motor: "电机", power: "电源", channel: "通道" };
  const TEXT_COLOR_PRESETS = [
    ["#dc2626", "红色"],
    ["#15803d", "绿色"],
    ["#2563eb", "蓝色"],
    ["#a16207", "黄色"],
    ["#111827", "黑色"],
    ["#6b7280", "灰色"]
  ];

  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function editorLanguage() { return state.productEditorLanguage || state.catalogLanguage || "zh"; }
  function temporaryId(prefix) {
    const random = globalThis.crypto?.randomUUID?.().replaceAll("-", "") || `${Date.now()}${Math.random().toString(16).slice(2)}`;
    return `${prefix}-${random}`;
  }
  function majorToMinor(value) { return Math.max(0, Math.round(toFiniteNumber(value) * 100)); }
  function minorToMajor(value) { return (Number(value || 0) / 100).toFixed(2); }
  function localized(zh, en, language = state.catalogLanguage) {
    const value = language === "en" ? en : zh;
    return String(value || "").trim() || (language === "en" ? "[English pending]" : "—");
  }
  function optionalCategories() {
    const root = state.configCatalog.find((item) => item.id === ROOT_IDS.optional);
    return root?.children || [];
  }

  function textColorOptions(value) {
    const current = String(value || "#111827").toLowerCase();
    const options = TEXT_COLOR_PRESETS.slice();
    if (!options.some(([color]) => color === current)) options.unshift([current, `当前颜色（${current}）`]);
    return options.map(([color, label]) => `<option value="${escapeHtml(color)}" ${color === current ? "selected" : ""}>${escapeHtml(label)}</option>`).join("");
  }

  window.renderProducts = function renderProductsV2() {
    const english = state.catalogLanguage === "en";
    $("#products-table").innerHTML = state.products.map((product) => `
      <tr>
        <td><strong>${escapeHtml(english ? (product.name_en || product.name) : product.name)}</strong></td>
        <td>${escapeHtml(localized(product.title_name, product.title_name_en))}</td>
        <td><span class="badge ${product.enabled ? "good" : "off"}">${product.enabled ? "已启用" : "已下架"}</span></td>
        <td class="align-right"><button class="table-action" type="button" data-edit-product="${escapeHtml(product.id)}">编辑</button></td>
      </tr>
    `).join("") || '<tr><td colspan="4" class="empty">暂无产品数据</td></tr>';
  };

  function captureSpecifications() {
    if (!state.editingProduct) return;
    const lang = editorLanguage();
    const current = new Map((state.editingProduct.specifications || []).map((item) => [item.id, item]));
    state.editingProduct.specifications = $$(".specification-row", $("#product-specifications-editor")).map((row, index) => {
      const id = row.dataset.id || temporaryId("spec");
      const item = { ...(current.get(id) || {}), id, sort_order: index };
      item[lang === "en" ? "label_en" : "label"] = $('[data-spec-field="label"]', row).value.trim();
      item[lang === "en" ? "value_en" : "value"] = $('[data-spec-field="value"]', row).value.trim();
      return item;
    });
  }

  function renderSpecifications() {
    const lang = editorLanguage();
    const labelKey = lang === "en" ? "label_en" : "label";
    const valueKey = lang === "en" ? "value_en" : "value";
    const items = state.editingProduct?.specifications || [];
    $("#product-specifications-editor").innerHTML = items.map((item, index) => `
      <div class="specification-row" data-id="${escapeHtml(item.id || temporaryId("spec"))}">
        <label><span>参数项目</span><input data-spec-field="label" value="${escapeHtml(item[labelKey] || "")}" placeholder="${lang === "en" ? "e.g. Maximum speed" : "例如：最大转速"}"></label>
        <label><span>参数数据</span><input data-spec-field="value" value="${escapeHtml(item[valueKey] || "")}" placeholder="例如：3000 rpm"></label>
        <div class="row-actions"><button type="button" class="icon-button" data-move-spec="${index}" data-direction="-1" aria-label="上移" ${index ? "" : "disabled"}>↑</button><button type="button" class="icon-button" data-move-spec="${index}" data-direction="1" aria-label="下移" ${index === items.length - 1 ? "disabled" : ""}>↓</button><button type="button" class="button button-quiet" data-remove-spec="${index}">删除</button></div>
      </div>
    `).join("") || '<div class="editor-empty">暂未填写参数，点击“添加参数”创建项目。</div>';
  }

  window.colorEditorRow = function colorEditorRowV2(color = {}) {
    const id = color.id || color.code || temporaryId("color");
    const displayColor = color.display_color || "#111827";
    const source = color.image_path ? catalogAssetUrl(color.image_path) : "";
    const preview = source
      ? `<img src="${escapeHtml(source)}" alt="颜色图片缩略图" width="152" height="92">`
      : "<span>暂无图片</span>";
    return `<div class="color-editor-row" data-color-id="${escapeHtml(id)}" data-translation-status="${escapeHtml(color.translation_status || "machine_draft")}">
      <label class="color-name-field language-value-field"><span>颜色名称</span><input data-color-field="name_zh" data-content-lang="zh" value="${escapeHtml(color.name_zh || color.label || "")}" placeholder="例如：绿色"><input data-color-field="name_en" data-content-lang="en" value="${escapeHtml(color.name_en || color.label_en || "")}" placeholder="e.g. Green" hidden></label>
      <label class="color-value-field"><span>文字颜色</span><span class="color-value-control"><select data-color-field="display_color" aria-label="选择前端显示的文字颜色" title="${escapeHtml(displayColor)}">${textColorOptions(displayColor)}</select></span></label>
      <label class="color-image-field"><span>颜色图片</span><div class="color-image-control"><input data-color-field="image_path" type="hidden" value="${escapeHtml(color.image_path || "")}"><input data-color-field="image_width" type="hidden" value="${escapeHtml(color.image_width || "")}"><input data-color-field="image_height" type="hidden" value="${escapeHtml(color.image_height || "")}"><div class="color-image-preview" data-color-image-preview>${preview}</div><button class="button button-secondary" type="button" data-pick-image>上传图片</button><input type="file" accept="image/png,image/jpeg,image/webp" data-image-file hidden></div></label>
      <div class="color-state-controls"><label class="compact-check"><input data-color-field="enabled" type="checkbox" ${color.enabled !== false ? "checked" : ""}><span>启用</span></label><label class="compact-check"><input data-color-field="is_default" type="radio" name="default-color" ${color.is_default ? "checked" : ""}><span>默认</span></label></div>
      <button class="icon-button" data-remove-color type="button" aria-label="删除颜色">✕</button>
    </div>`;
  };

  window.renderColorEditor = function renderColorEditorV2(colors) {
    $("#color-editor-list").innerHTML = (colors || []).map((color) => window.colorEditorRow(color)).join("");
    showProductLanguageFields();
  };

  window.collectColors = function collectColorsV2() {
    return $$(".color-editor-row", $("#color-editor-list")).map((row, index) => ({
      id: row.dataset.colorId,
      name_zh: $('[data-color-field="name_zh"]', row).value.trim(),
      name_en: $('[data-color-field="name_en"]', row).value.trim(),
      display_color: $('[data-color-field="display_color"]', row).value,
      image_path: $('[data-color-field="image_path"]', row).value.trim() || null,
      image_width: toPositiveInteger($('[data-color-field="image_width"]', row).value, 0) || null,
      image_height: toPositiveInteger($('[data-color-field="image_height"]', row).value, 0) || null,
      is_default: $('[data-color-field="is_default"]', row).checked,
      enabled: $('[data-color-field="enabled"]', row).checked,
      sort_order: index,
      translation_status: row.dataset.translationStatus || "machine_draft"
    }));
  };

  function ensureGroup(type) {
    let group = state.editingProduct.base_option_groups.find((item) => item.option_type === type);
    if (!group) {
      group = {
        id: `base-${state.editingProduct.id}-${type}`,
        option_type: type,
        required: type !== "channel",
        enabled: type !== "channel",
        sort_order: type === "motor" ? 0 : type === "power" ? 1 : 2,
        options: []
      };
      state.editingProduct.base_option_groups.push(group);
    }
    return group;
  }

  function captureBaseOptions() {
    if (!state.editingProduct || !$("#base-options-editor").children.length) return;
    const lang = editorLanguage();
    const original = new Map(state.editingProduct.base_option_groups.map((group) => [group.option_type, group]));
    state.editingProduct.base_option_groups = $$("[data-base-group]", $("#base-options-editor")).map((section, groupIndex) => {
      const type = section.dataset.baseGroup;
      const previous = original.get(type) || {};
      return {
        ...previous,
        id: section.dataset.groupId || previous.id || `base-${state.editingProduct.id}-${type}`,
        option_type: type,
        required: type !== "channel",
        enabled: $('[data-group-enabled]', section)?.checked ?? true,
        sort_order: groupIndex,
        options: $$("[data-base-option]", section).map((row, optionIndex) => {
          const id = row.dataset.baseOption;
          const old = (previous.options || []).find((item) => item.id === id) || {};
          const result = {
            ...old,
            id,
            enabled: $('[data-base-enabled]', row).checked,
            sort_order: optionIndex,
            translation_status: row.dataset.translationStatus || old.translation_status || "machine_draft"
          };
          result[lang === "en" ? "name_en" : "name_zh"] = $('[data-base-name]', row).value.trim();
          if (type === "power") {
            result.is_free = $('[data-base-free]', row).checked;
            result.price_cny_minor = result.is_free ? 0 : majorToMinor($('[data-base-price-cny]', row).value);
            result.price_usd_minor = result.is_free ? 0 : majorToMinor($('[data-base-price-usd]', row).value);
            result.price_confirmed = result.is_free || Boolean(old.price_confirmed);
          } else {
            result.is_free = false;
            result.price_cny_minor = 0;
            result.price_usd_minor = 0;
            result.price_confirmed = false;
          }
          return result;
        })
      };
    });
  }

  function renderBaseOptions() {
    const lang = editorLanguage();
    state.collapsedBaseGroups ||= new Set();
    ["motor", "power", "channel"].forEach(ensureGroup);
    $("#base-options-editor").innerHTML = state.editingProduct.base_option_groups
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((group) => `
        <section class="base-option-group ${state.collapsedBaseGroups.has(group.option_type) ? "collapsed" : ""}" data-base-group="${group.option_type}" data-group-id="${escapeHtml(group.id)}">
          <header><button type="button" class="base-option-heading" data-toggle-base-group="${group.option_type}" aria-expanded="${String(!state.collapsedBaseGroups.has(group.option_type))}"><span class="disclosure-chevron" aria-hidden="true"></span><span><strong>${GROUP_LABELS[group.option_type]}</strong><small>${group.option_type === "motor" ? "单选；参与基础价格组合" : group.option_type === "power" ? "单选；价格作为附加费" : "单选；启用后参与基础价格组合"}</small></span></button><div class="base-group-actions">${group.option_type === "channel" ? `<label class="compact-check"><input type="checkbox" data-group-enabled ${group.enabled ? "checked" : ""}><span>启用通道</span></label>` : `<input type="checkbox" data-group-enabled checked hidden>`}<button type="button" class="button button-secondary" data-add-base-option="${group.option_type}">添加选项</button></div></header>
          <div class="base-option-list" ${state.collapsedBaseGroups.has(group.option_type) ? "hidden" : ""}>${(group.options || []).map((option, optionIndex) => {
            const power = group.option_type === "power";
            const free = Boolean(option.is_free);
            return `<article class="base-option-row ${power ? "base-option-row-power" : "base-option-row-simple"}" data-base-option="${escapeHtml(option.id)}" data-translation-status="${escapeHtml(option.translation_status || "machine_draft")}">
              <label class="base-option-name"><span>选项名称</span><input data-base-name value="${escapeHtml(lang === "en" ? option.name_en : option.name_zh)}" placeholder="${lang === "en" ? "English option name" : "中文选项名称"}"></label>
              ${power ? `<label class="base-option-price"><span>人民币附加费</span><input data-base-price-cny type="number" min="0" step="0.01" value="${minorToMajor(option.price_cny_minor)}" ${free ? "disabled" : ""}></label><label class="base-option-price"><span>美元附加费</span><input data-base-price-usd type="number" min="0" step="0.01" value="${minorToMajor(option.price_usd_minor)}" ${free ? "disabled" : ""}></label><div class="base-option-status"><label class="compact-check"><input data-base-free type="checkbox" ${free ? "checked" : ""}><span>免费</span></label><label class="compact-check"><input data-base-enabled type="checkbox" ${option.enabled !== false ? "checked" : ""}><span>启用</span></label></div>` : `<label class="compact-check"><input data-base-enabled type="checkbox" ${option.enabled !== false ? "checked" : ""}><span>启用</span></label>`}
              <div class="base-option-actions"><button type="button" class="icon-button" data-move-base-option="${escapeHtml(option.id)}" data-direction="-1" aria-label="上移" ${optionIndex ? "" : "disabled"}>↑</button><button type="button" class="icon-button" data-move-base-option="${escapeHtml(option.id)}" data-direction="1" aria-label="下移" ${optionIndex === group.options.length - 1 ? "disabled" : ""}>↓</button><button type="button" class="button button-quiet" data-remove-base-option="${escapeHtml(option.id)}">删除</button></div>
            </article>`;
          }).join("") || '<div class="editor-empty">尚未添加选项。</div>'}</div>
        </section>
      `).join("");
  }

  function capturePriceVariants() {
    if (!state.editingProduct || !$("#price-variant-editor").children.length) return;
    const current = new Map((state.editingProduct.price_variants || []).map((item) => [item.id, item]));
    state.editingProduct.price_variants = $$("[data-price-variant]", $("#price-variant-editor")).map((row) => {
      const id = row.dataset.priceVariant;
      return {
        ...(current.get(id) || {}),
        id,
        motor_option_id: row.dataset.motorId || null,
        channel_option_id: row.dataset.channelId || null,
        price_cny_minor: majorToMinor($('[data-variant-cny]', row).value),
        price_usd_minor: majorToMinor($('[data-variant-usd]', row).value),
        enabled: true
      };
    });
  }

  function expectedPriceVariants() {
    const motorGroup = ensureGroup("motor");
    const channelGroup = ensureGroup("channel");
    const motors = motorGroup.enabled ? motorGroup.options.filter((item) => item.enabled !== false) : [];
    const channels = channelGroup.enabled ? channelGroup.options.filter((item) => item.enabled !== false) : [];
    const enabledCurrent = (state.editingProduct.price_variants || []).filter((item) => item.enabled !== false);
    const pricesByMotor = enabledCurrent.length ? enabledCurrent.some((item) => item.motor_option_id) : motors.length > 0;
    const pricesByChannel = enabledCurrent.length ? enabledCurrent.some((item) => item.channel_option_id) : channels.length > 0;
    const combinations = pricesByMotor && pricesByChannel
      ? motors.flatMap((motor) => channels.map((channel) => [motor, channel]))
      : pricesByMotor
        ? motors.map((motor) => [motor, null])
        : pricesByChannel
          ? channels.map((channel) => [null, channel])
          : [];
    const current = new Map((state.editingProduct.price_variants || []).map((item) => [`${item.motor_option_id || ""}|${item.channel_option_id || ""}`, item]));
    return combinations.map(([motor, channel]) => ({
      ...(current.get(`${motor?.id || ""}|${channel?.id || ""}`) || {
        id: temporaryId("price"),
        price_cny_minor: 0,
        price_usd_minor: 0,
        price_confirmed: false
      }),
      motor_option_id: motor?.id || null,
      channel_option_id: channel?.id || null,
      enabled: true
    }));
  }

  function renderPriceVariants() {
    captureBaseOptions();
    state.editingProduct.price_variants = expectedPriceVariants();
    const lang = editorLanguage();
    const names = new Map(state.editingProduct.base_option_groups.flatMap((group) => group.options.map((item) => [item.id, lang === "en" ? item.name_en : item.name_zh])));
    const variants = state.editingProduct.price_variants;
    $("#price-variant-editor").innerHTML = variants.length ? `<div class="price-variant-table"><div class="price-variant-head"><span>定价配置</span><span>人民币基础价</span><span>美元基础价</span></div>${variants.map((item) => `
      <div class="price-variant-row" data-price-variant="${escapeHtml(item.id)}" data-motor-id="${escapeHtml(item.motor_option_id || "")}" data-channel-id="${escapeHtml(item.channel_option_id || "")}">
        <strong>${escapeHtml([names.get(item.motor_option_id), names.get(item.channel_option_id)].filter(Boolean).join(" / "))}</strong>
        <label><span class="sr-only">人民币基础价</span><input data-variant-cny type="number" min="0" step="0.01" value="${minorToMajor(item.price_cny_minor)}"></label>
        <label><span class="sr-only">美元基础价</span><input data-variant-usd type="number" min="0" step="0.01" value="${minorToMajor(item.price_usd_minor)}"></label>
      </div>`).join("")}</div>` : '<div class="editor-empty editor-empty-warning">请先在“基本配置”中至少添加并启用一个电机选项。</div>';
  }

  window.renderMappingEditor = function renderMappingEditorV2() {
    const editor = state.mappingEditor;
    if (!editor) return;
    const lang = editorLanguage();
    const query = (editor.query || "").trim().toLowerCase();
    const groups = editor.categories.map((category) => {
      const options = (category.options || []).filter((option) => {
        const selected = editor.selected.has(option.id);
        const matchesFilter = editor.filter === "selected" ? selected : editor.filter === "unselected" ? !selected : true;
        const note = editor.notes.get(option.id);
        const text = [option.code, option.name, option.name_en, note?.zh, note?.en].join(" ").toLowerCase();
        return matchesFilter && (!query || text.includes(query));
      });
      if (!options.length) return "";
      const collapsed = editor.collapsed.has(category.id);
      return `<section class="mapping-group ${collapsed ? "collapsed" : ""}"><header><button type="button" class="mapping-group-toggle" data-mapping-category="${escapeHtml(category.id)}" aria-expanded="${String(!collapsed)}"><span class="disclosure-chevron" aria-hidden="true"></span><span class="mapping-group-title"><strong>${escapeHtml(localized(category.name, category.name_en, lang))}</strong><small>${category.options.filter((option) => editor.selected.has(option.id)).length} / ${category.options.length} 已选择</small></span></button></header><div class="mapping-options" ${collapsed ? "hidden" : ""}>${options.map((option) => {
        const note = editor.notes.get(option.id)?.[lang] || "";
        const name = localized(option.name, option.name_en, lang);
        return `<div class="mapping-option ${!option.enabled ? "disabled" : ""}"><label class="mapping-option-select"><input type="checkbox" value="${escapeHtml(option.id)}" aria-label="${escapeHtml(`选择 ${option.code} ${name}`)}" ${editor.selected.has(option.id) ? "checked" : ""} ${option.enabled ? "" : "disabled"}><span class="mapping-option-copy"><small class="mapping-option-code" translate="no">${escapeHtml(option.code)}</small><strong>${escapeHtml(name)}</strong>${note ? `<b class="mapping-special-note">${escapeHtml(note)}</b>` : ""}</span></label><button type="button" class="button button-quiet mapping-note-button" data-edit-mapping-note="${escapeHtml(option.id)}">标注</button></div>`;
      }).join("")}</div></section>`;
    }).join("");
    $("#mapping-editor").innerHTML = groups || `<div class="editor-empty">${lang === "en" ? "No matching configurations" : "没有符合条件的可选配置"}</div>`;
    $$('[data-mapping-filter]').forEach((button) => button.classList.toggle("active", button.dataset.mappingFilter === editor.filter));
    const expand = $("#mapping-expand-all");
    if (expand) expand.textContent = editor.collapsed.size ? "展开全部" : "全部折叠";
  };

  window.reconcileMappingEditor = function reconcileMappingEditorV2() {
    const editor = state.mappingEditor;
    if (!editor) return [];
    const valid = new Set(editor.categories.flatMap((category) => category.options.filter((option) => option.enabled).map((option) => option.id)));
    const stale = Array.from(editor.selected).filter((id) => !valid.has(id));
    stale.forEach((id) => editor.selected.delete(id));
    Array.from(editor.notes.keys()).filter((id) => !valid.has(id)).forEach((id) => editor.notes.delete(id));
    return stale;
  };

  function showProductLanguageFields() {
    const lang = editorLanguage();
    $$('[data-content-lang]', $("#product-dialog")).forEach((field) => { field.hidden = field.dataset.contentLang !== lang; });
    $$(".lang-toggle", $("#product-dialog")).forEach((button) => {
      const active = button.dataset.lang === lang;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }

  function captureProductEditor() {
    if (!state.editingProduct) return;
    const form = $("#product-form");
    state.editingProduct.model = form.elements.model.value.trim();
    state.editingProduct.product_name_zh = form.elements.product_name_zh.value.trim();
    state.editingProduct.product_name_en = form.elements.product_name_en.value.trim();
    state.editingProduct.overview_zh = form.elements.overview_zh.value.trim();
    state.editingProduct.overview_en = form.elements.overview_en.value.trim();
    state.editingProduct.translation_status = form.elements.translation_status.value;
    state.editingProduct.enabled = form.elements.enabled.checked;
    state.editingProduct.colors = window.collectColors();
    captureSpecifications();
    captureBaseOptions();
    capturePriceVariants();
  }

  function productEditorSnapshot() {
    captureProductEditor();
    const editor = state.mappingEditor;
    const mappings = editor ? {
      selected: Array.from(editor.selected || []).sort(),
      notes: Array.from(editor.notes || [])
        .map(([id, note]) => [id, { zh: note?.zh || "", en: note?.en || "" }])
        .sort(([left], [right]) => left.localeCompare(right))
    } : { selected: [], notes: [] };
    return JSON.stringify({ product: state.editingProduct, mappings });
  }

  window.hasUnsavedProductChanges = function hasUnsavedProductChanges() {
    const dialog = $("#product-dialog");
    if (!dialog?.open || !state.editingProduct || !state.productEditorInitialSnapshot) return false;
    return productEditorSnapshot() !== state.productEditorInitialSnapshot;
  };

  window.toggleDialogLanguage = function toggleDialogLanguageV2(button) {
    const dialog = button.closest("dialog");
    const lang = button.dataset.lang;
    if (dialog?.classList.contains("catalog-v2-dialog")) {
      setCatalogDialogLanguage(dialog, lang);
      return;
    }
    if (dialog?.id === "product-dialog") {
      captureProductEditor();
      state.productEditorLanguage = lang;
      state.catalogLanguage = lang;
      localStorage.setItem("boten-admin-language", lang);
      showProductLanguageFields();
      renderSpecifications();
      window.renderColorEditor(state.editingProduct.colors);
      renderBaseOptions();
      renderPriceVariants();
      window.renderMappingEditor();
      window.renderProducts();
      window.renderConfigCatalog(state.configCatalog);
      return;
    }
    $$(".lang-toggle", dialog).forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    $$('[name$="_en"]', dialog).forEach((field) => { const label = field.closest("label"); if (label) label.hidden = lang !== "en"; });
    $$('[name="name"],[name="title_name"],[name="description"]', dialog).forEach((field) => { const label = field.closest("label"); if (label) label.hidden = lang === "en"; });
  };

  window.applyCatalogLanguage = function applyCatalogLanguageV2(lang) {
    state.catalogLanguage = lang === "en" ? "en" : "zh";
    localStorage.setItem("boten-admin-language", state.catalogLanguage);
    $$('[data-catalog-lang]').forEach((button) => {
      const active = button.dataset.catalogLang === state.catalogLanguage;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    window.renderProducts();
    window.renderConfigCatalog(state.configCatalog);
  };

  window.switchEditorTab = function switchEditorTabV2(tab) {
    if (state.editingProduct) {
      if (tab === "pricing") renderPriceVariants();
      else if (tab !== "basic") captureProductEditor();
    }
    $$(".editor-tab").forEach((button) => {
      const active = button.dataset.editorTab === tab;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    });
    $$(".editor-panel").forEach((panel) => {
      const active = panel.dataset.editorPanel === tab;
      panel.classList.toggle("active", active);
      panel.hidden = !active;
    });
  };

  window.openProductEditor = async function openProductEditorV2(productId) {
    try {
      const product = await api(`/api/v1/admin/products/${encodeURIComponent(productId)}/editor`);
      state.editingProduct = clone(product);
      state.productEditorLanguage = state.catalogLanguage || "zh";
      state.editingProduct.base_option_groups ||= [];
      state.editingProduct.price_variants ||= [];
      state.editingProduct.specifications ||= [];
      state.collapsedBaseGroups = new Set();
      const form = $("#product-form");
      form.elements.product_id.value = product.id;
      form.elements.version.value = product.version;
      form.elements.model.value = product.model || "";
      form.elements.product_name_zh.value = product.product_name_zh || "";
      form.elements.product_name_en.value = product.product_name_en || "";
      form.elements.overview_zh.value = product.overview_zh || "";
      form.elements.overview_en.value = product.overview_en || "";
      form.elements.translation_status.value = product.translation_status || "machine_draft";
      form.elements.enabled.checked = Boolean(product.enabled);
      $("#product-dialog-title").textContent = `编辑 ${product.model}`;
      const status = $("#product-editor-status");
      status.textContent = product.enabled ? "已启用" : "已下架";
      status.className = `badge ${product.enabled ? "good" : "off"}`;
      window.renderColorEditor(product.colors || []);
      renderSpecifications();
      renderBaseOptions();
      renderPriceVariants();
      state.mappingEditor = {
        categories: optionalCategories(),
        selected: new Set(product.optional_config_ids || []),
        notes: new Map(optionalCategories().flatMap((category) => category.options.map((option) => {
          const override = product.optional_config_overrides?.[option.id] || {};
          return [option.id, {
            zh: override.description_override || "",
            en: override.description_override_en || "",
            mapped: (product.optional_config_ids || []).includes(option.id),
            dirty: false
          }];
        }))),
        query: "",
        filter: "all",
        collapsed: new Set(optionalCategories().map((category) => category.id))
      };
      $("#mapping-search").value = "";
      window.renderMappingEditor();
      showProductLanguageFields();
      window.switchEditorTab("basic");
      $("#product-error").hidden = true;
      $$('[data-product-field-error]').forEach((field) => { field.hidden = true; field.textContent = ""; });
      $$('[data-product-module-error]').forEach((field) => { field.hidden = true; field.textContent = ""; });
      state.productEditorInitialSnapshot = productEditorSnapshot();
      $("#product-dialog").showModal();
    } catch (failure) {
      showToast(failure.message, "error");
    }
  };

  function productErrorTab(field) {
    if (!field) return null;
    if (field.startsWith("colors")) return "colors";
    if (field.startsWith("base_option")) return "base-options";
    if (field.startsWith("price_variant")) return "pricing";
    if (field.startsWith("optional")) return "options";
    return "basic";
  }

  window.saveProduct = async function saveProductV2(event) {
    event.preventDefault();
    const form = event.currentTarget;
    if (event.submitter?.value === "cancel") { form.closest("dialog")?.close(); return; }
    const submit = $("#save-product-button");
    const errorBox = $("#product-error");
    errorBox.hidden = true;
    $$('[data-product-field-error]').forEach((field) => { field.hidden = true; field.textContent = ""; });
    $$('[data-product-module-error]').forEach((field) => { field.hidden = true; field.textContent = ""; });
    try {
      await runButtonAction(submit, "正在保存…", async () => {
        captureProductEditor();
        const product = state.editingProduct;
        const colors = product.colors || [];
        if (!product.model || !product.product_name_zh || !product.product_name_en) throw new ApiError("请完整填写设备型号和中英文产品名称", { field: "product" });
        if (!colors.some((color) => color.enabled)) throw new ApiError("设备至少需要保留一个启用的外观颜色", { field: "colors" });
        if (colors.filter((color) => color.enabled && color.is_default).length !== 1) throw new ApiError("启用的外观颜色必须且只能设置一个默认项", { field: "colors" });
        const stale = window.reconcileMappingEditor();
        if (stale.length) {
          window.renderMappingEditor();
          throw new ApiError("配置目录已变化，失效选项已取消，请确认后再次保存", { field: "optional_config_ids" });
        }
        product.price_variants = expectedPriceVariants().map((item) => ({ ...item, enabled: true }));
        const payload = {
          version: Number(form.elements.version.value),
          model: product.model,
          product_name_zh: product.product_name_zh,
          product_name_en: product.product_name_en,
          overview_zh: product.overview_zh,
          overview_en: product.overview_en,
          translation_status: product.translation_status || "machine_draft",
          enabled: product.enabled,
          colors,
          specifications: product.specifications || [],
          base_option_groups: product.base_option_groups.map((group) => ({
            id: group.id,
            option_type: group.option_type,
            required: group.option_type !== "channel",
            sort_order: group.sort_order,
            enabled: group.enabled,
            options: group.options.map((item) => ({
              id: item.id,
              name_zh: item.name_zh || "",
              name_en: item.name_en || "",
              price_cny_minor: item.price_cny_minor || 0,
              price_usd_minor: item.price_usd_minor || 0,
              price_confirmed: Boolean(item.price_confirmed),
              is_free: Boolean(item.is_free),
              sort_order: item.sort_order,
              enabled: item.enabled !== false,
              translation_status: item.translation_status || "machine_draft"
            }))
          })),
          price_variants: product.price_variants.map((item) => ({
            id: item.id,
            motor_option_id: item.motor_option_id || null,
            channel_option_id: item.channel_option_id || null,
            price_cny_minor: item.price_cny_minor || 0,
            price_usd_minor: item.price_usd_minor || 0,
            price_confirmed: Boolean(item.price_confirmed),
            enabled: true
          })),
          optional_config_ids: Array.from(state.mappingEditor.selected),
          optional_config_overrides: Object.fromEntries(Array.from(state.mappingEditor.notes)
            .filter(([optionId, note]) => state.mappingEditor.selected.has(optionId) || note.zh || note.en)
            .map(([optionId, note]) => [optionId, {
              description_override: note.zh || null,
              description_override_en: note.en || null
            }]))
        };
        const result = await api(`/api/v1/admin/products/${encodeURIComponent(product.id)}/editor`, { method: "PUT", body: JSON.stringify(payload) });
        state.editingProduct = result;
        $("#product-dialog").close();
        showToast("设备资料和配置已保存");
        await loadData();
      });
    } catch (failure) {
      const tab = productErrorTab(failure.field) || "basic";
      window.switchEditorTab(tab);
      const directField = failure.field === "model" ? "model" : failure.field === "product" || failure.field === "translation_status" ? "product_name" : failure.field?.startsWith("overview") ? "overview" : null;
      const fieldError = directField ? $(`[data-product-field-error="${directField}"]`) : null;
      if (fieldError) { fieldError.textContent = failure.message; fieldError.hidden = false; fieldError.previousElementSibling?.focus?.(); }
      const moduleError = $(`[data-product-module-error="${tab}"]`);
      if (moduleError) { moduleError.textContent = failure.message; moduleError.hidden = false; moduleError.focus(); }
      else { errorBox.textContent = failure.message; errorBox.hidden = false; errorBox.focus?.(); }
    }
  };

  window.addProductButton = function addProductButtonV2() {
    const panel = $("#product-catalog-actions");
    if (!panel || $("#add-product-button")) return;
    const button = document.createElement("button");
    button.id = "add-product-button";
    button.className = "button button-secondary";
    button.type = "button";
    button.textContent = "添加设备";
    button.addEventListener("click", () => catalogEditorCard({
      title: "添加设备",
      size: "medium",
      fields: [
        { name: "id", label: "设备内部编号", placeholder: "例如：cr999", required: true },
        { name: "model", label: "设备型号", placeholder: "例如：BOTEN CR999", required: true },
        { name: "product_name_zh", label: "产品名称", lang: "zh", placeholder: "中文产品名称", required: true },
        { name: "product_name_en", label: "产品名称", lang: "en", placeholder: "English product name", required: true }
      ],
      onSave: async (data) => {
        await api("/api/v1/admin/products", { method: "POST", body: JSON.stringify({
          id: data.id,
          name: data.model,
          name_en: data.model,
          title_name: data.product_name_zh,
          title_name_en: data.product_name_en,
          base_price: 0,
          price_usd: 0
        }) });
        showToast("设备已创建，请继续编辑基本配置和价格");
      }
    }));
    panel.appendChild(button);
  };

  async function generateProductTranslation(button) {
    captureProductEditor();
    const product = state.editingProduct;
    if (!product) return;
    const descriptors = [];
    const add = (key, source, apply, skip = false) => {
      if (!skip && String(source || "").trim()) descriptors.push({ key, source: String(source).trim(), apply });
    };
    const productReviewed = product.translation_status === "reviewed";
    add("product_name", product.product_name_zh, (value) => { product.product_name_en = value; }, productReviewed);
    add("product_overview", product.overview_zh, (value) => { product.overview_en = value; }, productReviewed);
    (product.colors || []).forEach((color, index) => add(`color_${index}`, color.name_zh, (value) => { color.name_en = value; color.translation_status = "machine_draft"; }, color.translation_status === "reviewed"));
    (product.base_option_groups || []).forEach((group) => (group.options || []).forEach((option, index) => add(`base_${group.option_type}_${index}`, option.name_zh, (value) => { option.name_en = value; option.translation_status = "machine_draft"; }, option.translation_status === "reviewed")));
    (product.specifications || []).forEach((spec, index) => {
      add(`spec_label_${index}`, spec.label, (value) => { spec.label_en = value; }, Boolean(spec.label_en));
      add(`spec_value_${index}`, spec.value, (value) => { spec.value_en = value; }, Boolean(spec.value_en));
    });
    if (!descriptors.length) { showToast("没有需要生成的英文草稿"); return; }
    await runButtonAction(button, "生成中…", async () => {
      const results = await requestTranslationDrafts(Object.fromEntries(descriptors.map((item) => [item.key, item.source])));
      let completed = 0;
      descriptors.forEach((descriptor) => {
        const result = results[descriptor.key];
        if (result?.complete && result.draft) { descriptor.apply(result.draft); completed += 1; }
      });
      const productDescriptors = descriptors.filter((item) => item.key.startsWith("product_"));
      if (!productReviewed && productDescriptors.length) {
        product.translation_status = productDescriptors.every((item) => results[item.key]?.complete && results[item.key]?.draft) ? "machine_draft" : "missing";
      }
      const form = $("#product-form");
      form.elements.product_name_en.value = product.product_name_en || "";
      form.elements.overview_en.value = product.overview_en || "";
      form.elements.translation_status.value = product.translation_status || "machine_draft";
      state.productEditorLanguage = "en";
      state.catalogLanguage = "en";
      localStorage.setItem("boten-admin-language", "en");
      renderSpecifications();
      window.renderColorEditor(product.colors || []);
      renderBaseOptions();
      renderPriceVariants();
      window.renderMappingEditor();
      showProductLanguageFields();
      showToast(completed === descriptors.length ? "英文草稿已生成，请校对后保存" : `已生成 ${completed} 项；其余内容需要人工填写`, completed === descriptors.length ? "status" : "error");
    });
  }

  function catalogRoots() {
    return state.configCatalog.filter((root) => ROOT_IDS[root.catalog_type] === root.id);
  }

  function catalogLeaves() {
    return catalogRoots().flatMap((root) => root.children?.length ? root.children : [root]);
  }

  function countCatalogItems(node) {
    return (node.options || []).length + (node.children || []).reduce((sum, child) => sum + countCatalogItems(child), 0);
  }

  function currentCatalogRootId() {
    const urlValue = new URL(window.location.href).searchParams.get("catalog");
    const requested = state.catalogRootId || urlValue;
    return catalogRoots().some((root) => root.id === requested) ? requested : ROOT_IDS.optional;
  }

  function renderCatalogItems(category) {
    const language = state.catalogLanguage;
    const items = category.options || [];
    if (!items.length) return '<div class="catalog-empty">该分类暂未添加配置项目。</div>';
    return `<div class="config-catalog-table"><table class="catalog-v2-table">
      <colgroup><col class="catalog-col-code"><col class="catalog-col-name"><col class="catalog-col-image"><col class="catalog-col-price"><col class="catalog-col-status"><col class="catalog-col-actions"></colgroup>
      <thead><tr><th>编号</th><th>名称与描述</th><th>图片</th><th>参考价格</th><th>状态</th><th class="align-right">操作</th></tr></thead>
      <tbody>${items.map((item, itemIndex) => `<tr>
        <td><strong>${escapeHtml(item.code)}</strong></td>
        <td class="catalog-item-copy"><strong>${escapeHtml(localized(item.name, item.name_en, language))}</strong>${localized(item.description, item.description_en, language) !== "—" && localized(item.description, item.description_en, language) !== "[English pending]" ? `<small>${escapeHtml(localized(item.description, item.description_en, language))}</small>` : ""}</td>
        <td class="config-image-cell">${renderCatalogThumbnail(item)}</td>
        <td class="catalog-price-cell"><span class="catalog-price-values"><span><span class="catalog-currency-mark" aria-hidden="true">¥</span><strong>${Number(item.price || 0).toLocaleString("zh-CN")}</strong></span><span><span class="catalog-currency-mark" aria-hidden="true">$</span><strong>${Number(item.price_usd || 0).toLocaleString("en-US")}</strong></span></span></td>
        <td><span class="badge ${item.enabled ? "good" : "off"}">${item.enabled ? "启用" : "停用"}</span></td>
        <td class="align-right"><span class="catalog-row-actions"><button class="icon-button" type="button" data-move-catalog-item="${escapeHtml(item.id)}" data-category-id="${escapeHtml(category.id)}" data-direction="-1" aria-label="上移 ${escapeHtml(item.name)}" ${itemIndex === 0 ? "disabled" : ""}>↑</button><button class="icon-button" type="button" data-move-catalog-item="${escapeHtml(item.id)}" data-category-id="${escapeHtml(category.id)}" data-direction="1" aria-label="下移 ${escapeHtml(item.name)}" ${itemIndex === items.length - 1 ? "disabled" : ""}>↓</button><button class="table-action" type="button" data-edit-catalog-item="${escapeHtml(item.id)}">编辑</button></span></td>
      </tr>`).join("")}</tbody>
    </table></div>`;
  }

  function renderCatalogCategory(category, { root = false } = {}) {
    const collapsed = state.collapsedCategories.has(category.id);
    const name = localized(category.name, category.name_en);
    const description = localized(category.description, category.description_en);
    return `<section class="config-catalog-group catalog-v2-group ${collapsed ? "collapsed" : ""}" data-catalog-category="${escapeHtml(category.id)}">
      <header>
        <button type="button" class="catalog-collapse-target" data-collapse-category="${escapeHtml(category.id)}" aria-expanded="${String(!collapsed)}">
          <span class="disclosure-chevron" aria-hidden="true"></span>
          <div><h3>${escapeHtml(name)}</h3>${description !== "—" && description !== "[English pending]" ? `<p>${escapeHtml(description)}</p>` : ""}</div>
        </button>
        <div class="catalog-group-actions">
          <span>${category.options?.length || 0} 项</span>
          <button class="button button-secondary" type="button" data-add-catalog-item="${escapeHtml(category.id)}">添加项目</button>
          ${root ? "" : `<details class="catalog-more"><summary>更多</summary><div><button class="text-button" type="button" data-edit-catalog-category="${escapeHtml(category.id)}">编辑分类</button><button class="text-button danger-text" type="button" data-delete-catalog-category="${escapeHtml(category.id)}">删除分类</button></div></details>`}
        </div>
      </header>
      <div class="catalog-group-content" ${collapsed ? "hidden" : ""}>${renderCatalogItems(category)}</div>
    </section>`;
  }

  window.renderConfigCatalog = function renderConfigCatalogV2() {
    const target = $("#config-catalog-list");
    if (!target) return;
    const roots = catalogRoots();
    const activeId = currentCatalogRootId();
    state.catalogRootId = activeId;
    const active = roots.find((root) => root.id === activeId);
    if (!active) {
      target.innerHTML = '<div class="empty">配置目录尚未完成数据迁移。</div>';
      return;
    }
    const hasCategories = Boolean(active.children?.length);
    const content = hasCategories
      ? active.children.map((child) => renderCatalogCategory(child)).join("")
      : `<div class="catalog-flat-list"><div class="catalog-flat-meta" aria-live="polite">共 ${active.options?.length || 0} 项</div>${renderCatalogItems(active)}</div>`;
    target.innerHTML = `<div class="catalog-root-content ${hasCategories ? "catalog-category-content" : "catalog-flat-content"}">${content}</div>`;
  };

  function findCatalogCategory(categoryId) {
    return catalogRoots().flatMap((root) => [root, ...(root.children || [])]).find((item) => item.id === categoryId) || null;
  }

  function findCatalogItem(optionId) {
    for (const category of catalogLeaves()) {
      const item = (category.options || []).find((option) => option.id === optionId);
      if (item) return item;
    }
    return null;
  }

  async function moveCatalogItem(optionId, categoryId, direction, button) {
    const category = findCatalogCategory(categoryId);
    if (!category) return;
    const items = category.options || [];
    const from = items.findIndex((item) => item.id === optionId);
    const to = from + Number(direction);
    if (from < 0 || to < 0 || to >= items.length) return;
    const reordered = [...items];
    [reordered[from], reordered[to]] = [reordered[to], reordered[from]];
    const group = button.closest("[data-catalog-category]");
    group?.querySelectorAll("[data-move-catalog-item]").forEach((control) => { control.disabled = true; });
    try {
      await api("/api/v1/admin/catalog/items-order", {
        method: "PUT",
        body: JSON.stringify({ category_id: categoryId, items: reordered.map((item) => ({ id: item.id, version: item.version })) })
      });
      showToast("配置顺序已更新");
      await loadData();
    } catch (failure) {
      showToast(failure.message || "排序保存失败，请刷新后重试", "error");
      window.renderConfigCatalog();
    }
  }

  function catalogImageControl(item = {}) {
    const source = item.image_path ? catalogAssetUrl(item.image_path) : "";
    const preview = source
      ? `<img src="${escapeHtml(source)}" alt="配置图片缩略图" width="152" height="92">`
      : "<span>暂无图片</span>";
    return `<div class="image-path-control catalog-image-control">
      <input name="image_path" type="hidden" value="${escapeHtml(item.image_path || "")}">
      <input name="image_width" type="hidden" value="${escapeHtml(item.image_width || "")}">
      <input name="image_height" type="hidden" value="${escapeHtml(item.image_height || "")}">
      <div class="catalog-image-preview" data-catalog-image-preview>${preview}</div>
      <button class="button button-secondary" type="button" data-pick-image data-idle-label="上传图片">上传图片</button>
      <input type="file" accept="image/png,image/jpeg,image/webp" data-image-file hidden>
    </div>`;
  }

  function setCatalogDialogLanguage(dialog, language) {
    dialog.dataset.contentLanguage = language;
    $$('[data-content-lang]', dialog).forEach((field) => { field.hidden = field.dataset.contentLang !== language; });
    $$('.lang-toggle', dialog).forEach((button) => {
      const active = button.dataset.lang === language;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }

  async function requestTranslationDrafts(values) {
    const entries = Object.entries(values);
    const results = {};
    for (let index = 0; index < entries.length; index += 20) {
      const batch = Object.fromEntries(entries.slice(index, index + 20));
      const response = await api("/api/v1/admin/catalog/translation-draft", { method: "POST", body: JSON.stringify({ values: batch }) });
      Object.assign(results, response.items || {});
    }
    return results;
  }

  async function generateCatalogDraft(form, button) {
    const pairs = [
      ["name_zh", "name_en"],
      ["description_zh", "description_en"],
      ["note_zh", "note_en"]
    ].filter(([source]) => form.elements[source]);
    const values = Object.fromEntries(pairs.map(([source]) => [source, form.elements[source].value.trim()]));
    await runButtonAction(button, "生成中…", async () => {
      const items = await requestTranslationDrafts(values);
      let complete = true;
      pairs.forEach(([source, target]) => {
        const result = items[source];
        if (result?.complete && result.draft) form.elements[target].value = result.draft;
        else if (values[source]) complete = false;
      });
      if (form.elements.translation_status) form.elements.translation_status.value = complete ? "machine_draft" : "missing";
      setCatalogDialogLanguage(form.closest("dialog"), "en");
      showToast(complete ? "英文草稿已生成，请校对后保存" : "部分内容无法可靠翻译，请人工填写英文", complete ? "status" : "error");
    });
  }

  function openCatalogDialog({ title, subtitle = "", body, footerControl = "", onSave, onDelete = null, initialLanguage = state.catalogLanguage || "zh", dialogClass = "" }) {
    const dialog = document.createElement("dialog");
    dialog.className = `catalog-editor-dialog catalog-v2-dialog ${dialogClass}`.trim();
    dialog.dataset.dynamic = "true";
    dialog.innerHTML = `<form method="dialog" class="dialog-card catalog-editor-card" novalidate>
      <header><div class="catalog-dialog-heading"><span class="eyebrow">CATALOG EDITOR</span><h2>${escapeHtml(title)}</h2>${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ""}</div><div class="dialog-actions"><div class="catalog-language dialog-language" role="group" aria-label="编辑内容语言"><button type="button" class="lang-toggle" data-lang="zh" aria-pressed="false">中文</button><button type="button" class="lang-toggle" data-lang="en" aria-pressed="false">EN</button></div><button class="icon-button" value="cancel" aria-label="关闭">×</button></div></header>
      <div class="catalog-editor-body">${body}<div class="form-error" role="alert" tabindex="-1" hidden></div></div>
      <footer class="catalog-dialog-footer"><div class="catalog-dialog-danger">${onDelete ? '<button class="button button-danger catalog-delete-action" type="button">删除</button>' : ""}</div><div class="catalog-dialog-footer-actions">${footerControl}<button class="button button-quiet" value="cancel">取消</button><button class="button button-primary" value="default">保存</button></div></footer>
    </form>`;
    document.body.appendChild(dialog);
    const form = $("form", dialog);
    const opener = document.activeElement;
    setCatalogDialogLanguage(dialog, initialLanguage);
    $$('.lang-toggle', dialog).forEach((button) => button.addEventListener("click", () => setCatalogDialogLanguage(dialog, button.dataset.lang)));
    $('.catalog-delete-action', dialog)?.addEventListener("click", async (event) => {
      try {
        await runButtonAction(event.currentTarget, "处理中…", async () => {
          if (await onDelete()) { dialog.close(); await loadData(); }
        });
      } catch (failure) { const error = $('.form-error', dialog); error.textContent = failure.message; error.hidden = false; error.focus(); }
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (event.submitter?.value === "cancel") { dialog.close(); return; }
      const error = $('.form-error', dialog);
      error.hidden = true;
      try {
        await runButtonAction(event.submitter, "正在保存…", async () => {
          await onSave(form);
          dialog.close();
          showToast("配置目录已保存");
          await loadData();
        });
      } catch (failure) {
        error.textContent = failure.message;
        error.hidden = false;
        error.focus();
        if (failure.field) form.elements[failure.field]?.focus?.();
      }
    });
    dialog.addEventListener("close", () => { dialog.remove(); opener?.focus?.(); }, { once: true });
    dialog.addEventListener("cancel", (event) => {
      const current = JSON.stringify(Object.fromEntries(new FormData(form)));
      if (!form.dataset.initialSnapshot || current === form.dataset.initialSnapshot) return;
      event.preventDefault();
      confirmAction("放弃未保存修改", "当前配置目录内容尚未保存，确定关闭编辑窗口吗？", "放弃修改").then((confirmed) => { if (confirmed) dialog.close(); });
    });
    dialog.showModal();
    queueMicrotask(() => { form.dataset.initialSnapshot = JSON.stringify(Object.fromEntries(new FormData(form))); });
    $('input:not([type="hidden"]), select, textarea', dialog)?.focus();
    return dialog;
  }

  function translationFields(values = {}, { includeNote = false, nameLabel = "配置名称", descriptionLabel = "配置描述" } = {}) {
    return `<section class="catalog-form-section catalog-copy-section"><div class="catalog-form-heading"><div><h3>中英文内容</h3><p>字段标题保持中文，右上角切换当前编辑的内容语言。</p></div></div><div class="catalog-field-list">
      <label class="catalog-field language-value-field"><span>${escapeHtml(nameLabel)}</span><input name="name_zh" data-content-lang="zh" maxlength="300" required value="${escapeHtml(values.name || values.name_zh || "")}" placeholder="填写中文名称"><input name="name_en" data-content-lang="en" maxlength="300" required value="${escapeHtml(values.name_en || "")}" placeholder="Enter the English name"></label>
      <label class="catalog-field language-value-field"><span>${escapeHtml(descriptionLabel)}</span><textarea name="description_zh" data-content-lang="zh" rows="1" maxlength="10000" placeholder="填写中文描述">${escapeHtml(values.description || values.description_zh || "")}</textarea><textarea name="description_en" data-content-lang="en" rows="1" maxlength="10000" placeholder="Enter the English description">${escapeHtml(values.description_en || "")}</textarea></label>
      ${includeNote ? `<label class="catalog-field language-value-field"><span>备注</span><textarea name="note_zh" data-content-lang="zh" rows="1" maxlength="5000" placeholder="填写中文备注">${escapeHtml(values.notes || values.note_zh || "")}</textarea><textarea name="note_en" data-content-lang="en" rows="1" maxlength="5000" placeholder="Enter the English note">${escapeHtml(values.note_en || "")}</textarea></label>` : ""}
    </div></section>`;
  }

  function openCatalogCategoryEditor(category = null) {
    const editing = Boolean(category);
    const dialog = openCatalogDialog({
      title: editing ? "编辑配置分类" : "添加配置分类",
      subtitle: "维护配置目录的二级分类及中英文显示内容",
      dialogClass: "catalog-category-editor-dialog",
      body: `<input type="hidden" name="version" value="${escapeHtml(category?.version || 1)}">
        ${translationFields(category || {}, { nameLabel: "分类名称" })}
        <input type="hidden" name="translation_status" value="${escapeHtml(category?.translation_status || "machine_draft")}"><section class="catalog-form-section catalog-settings-section"><div class="catalog-form-heading"><div><h3>显示设置</h3><p>排序值越小越靠前，也可在目录列表中使用上下箭头调整。</p></div></div><div class="catalog-field-list"><label class="catalog-field"><span>排序</span><input name="sort_order" type="number" step="1" value="${escapeHtml(category?.sort_order || 0)}"></label></div></section>`,
      footerControl: `<label class="compact-check catalog-footer-enabled"><input name="enabled" type="checkbox" ${category?.enabled !== false ? "checked" : ""}><span>启用分类</span></label>`,
      onSave: async (form) => {
        const payload = {
          parent_id: ROOT_IDS.optional,
          name_zh: form.elements.name_zh.value.trim(),
          name_en: form.elements.name_en.value.trim(),
          description_zh: form.elements.description_zh.value.trim(),
          description_en: form.elements.description_en.value.trim(),
          enabled: form.elements.enabled.checked,
          sort_order: Number(form.elements.sort_order.value || 0),
          translation_status: form.elements.translation_status.value
        };
        if (!payload.name_zh || (payload.enabled && !payload.name_en)) throw new ApiError("启用分类前必须填写中英文分类名称", { field: payload.name_zh ? "name_en" : "name_zh" });
        if (editing) payload.version = Number(form.elements.version.value);
        await api(editing ? `/api/v1/admin/catalog/categories/${encodeURIComponent(category.id)}` : "/api/v1/admin/catalog/categories", { method: editing ? "PATCH" : "POST", body: JSON.stringify(payload) });
      },
      onDelete: editing ? async () => {
        if (!await confirmAction("删除配置分类", `确定删除“${category.name}”吗？分类中仍有项目时系统会阻止删除。`, "删除分类")) return false;
        await api(`/api/v1/admin/catalog/categories/${encodeURIComponent(category.id)}`, { method: "DELETE" });
        showToast("配置分类已删除");
        return true;
      } : null
    });
    const status = $("[name=translation_status]", dialog);
    if (status) status.value = category?.translation_status || "machine_draft";
    return dialog;
  }

  function catalogRootForCategory(categoryId) {
    return catalogRoots().find((root) => root.id === categoryId || root.children?.some((category) => category.id === categoryId)) || null;
  }

  function itemCategoryOptions(selectedId, catalogType) {
    return catalogLeaves().filter((category) => category.enabled && category.catalog_type === catalogType).map((category) => `<option value="${escapeHtml(category.id)}" ${category.id === selectedId ? "selected" : ""}>${escapeHtml(category.name)}</option>`).join("");
  }

  function openCatalogItemEditor(item = null, categoryId = null) {
    const editing = Boolean(item);
    const selectedCategoryId = item?.category_id || categoryId || catalogLeaves()[0]?.id || "";
    const root = catalogRootForCategory(selectedCategoryId);
    const catalogType = root?.catalog_type || "optional";
    const labels = catalogType === "tools"
      ? { singular: "工具", directory: "工具目录" }
      : catalogType === "accessories"
        ? { singular: "附件", directory: "附件目录" }
        : { singular: "配置", directory: "配置目录" };
    const categoryField = catalogType === "optional"
      ? `<label class="catalog-field"><span>所属分类</span><select name="category_id" required>${itemCategoryOptions(selectedCategoryId, catalogType)}</select></label>`
      : `<div class="catalog-field catalog-readonly-field"><span>所属目录</span><strong>${labels.directory}</strong><input name="category_id" type="hidden" value="${escapeHtml(selectedCategoryId)}"></div>`;
    const dialog = openCatalogDialog({
      title: editing ? `编辑${labels.singular} ${item.code}` : `添加${labels.singular}`,
      subtitle: `维护${labels.singular}的编号、中英文内容、图片和参考价格`,
      dialogClass: "catalog-item-editor-dialog",
      body: `<input type="hidden" name="version" value="${escapeHtml(item?.version || 1)}">
        <section class="catalog-form-section catalog-form-basics"><div class="catalog-form-heading"><div><h3>基本资料</h3><p>编号用于数据匹配，保存后建议保持不变。</p></div></div><div class="catalog-field-list">${categoryField}<label class="catalog-field"><span>${labels.singular}编号</span><input name="code" maxlength="200" required value="${escapeHtml(item?.code || "")}" placeholder="例如：BTK-1019" spellcheck="false" autocomplete="off"></label><div class="catalog-field catalog-image-field"><span>${labels.singular}图片</span>${catalogImageControl(item || {})}</div></div></section>
        ${translationFields(item || {}, { includeNote: true, nameLabel: `${labels.singular}名称`, descriptionLabel: `${labels.singular}描述` })}
        <section class="catalog-form-section catalog-price-section"><div class="catalog-form-heading"><div><h3>参考价格</h3><p>作为后台报价的默认单价，用户端不显示价格。</p></div></div><div class="catalog-field-list"><label class="catalog-field"><span>人民币参考价格</span><input name="price_cny" type="number" min="0" step="1" inputmode="decimal" value="${escapeHtml(item?.price || 0)}"></label><label class="catalog-field"><span>美元参考价格</span><input name="price_usd" type="number" min="0" step="1" inputmode="decimal" value="${escapeHtml(item?.price_usd || 0)}"></label></div></section>
        <input type="hidden" name="translation_status" value="${escapeHtml(item?.translation_status || "machine_draft")}"><section class="catalog-form-section catalog-settings-section"><div class="catalog-form-heading"><div><h3>显示设置</h3><p>排序值越小越靠前，也可在目录列表中使用上下箭头调整。</p></div></div><div class="catalog-field-list"><label class="catalog-field"><span>排序</span><input name="sort_order" type="number" step="1" value="${escapeHtml(item?.sort_order || 0)}"></label></div></section>`,
      footerControl: `<label class="compact-check catalog-footer-enabled"><input name="enabled" type="checkbox" ${item?.enabled !== false ? "checked" : ""}><span>启用${labels.singular}</span></label>`,
      onSave: async (form) => {
        const payload = {
          category_id: form.elements.category_id.value,
          code: form.elements.code.value.trim(),
          name_zh: form.elements.name_zh.value.trim(),
          name_en: form.elements.name_en.value.trim(),
          description_zh: form.elements.description_zh.value.trim(),
          description_en: form.elements.description_en.value.trim(),
          note_zh: form.elements.note_zh.value.trim(),
          note_en: form.elements.note_en.value.trim(),
          image_path: form.elements.image_path.value || null,
          image_width: Number(form.elements.image_width.value) || null,
          image_height: Number(form.elements.image_height.value) || null,
          price_cny: Math.max(0, Math.round(Number(form.elements.price_cny.value || 0))),
          price_usd: Math.max(0, Math.round(Number(form.elements.price_usd.value || 0))),
          enabled: form.elements.enabled.checked,
          sort_order: Number(form.elements.sort_order.value || 0),
          translation_status: form.elements.translation_status.value
        };
        if (!payload.code) throw new ApiError("请填写配置编号", { field: "code" });
        if (!payload.name_zh || (payload.enabled && !payload.name_en)) throw new ApiError("启用项目前必须填写中英文配置名称", { field: payload.name_zh ? "name_en" : "name_zh" });
        if (editing) payload.version = Number(form.elements.version.value);
        await api(editing ? `/api/v1/admin/catalog/items/${encodeURIComponent(item.id)}` : "/api/v1/admin/catalog/items", { method: editing ? "PATCH" : "POST", body: JSON.stringify(payload) });
      },
      onDelete: editing ? async () => {
        if (!await confirmAction("删除配置项目", `确定处理 ${item.code} ${item.name}？如已有引用，系统会保留历史数据并将项目归档。`, "确认删除")) return false;
        const result = await api(`/api/v1/admin/catalog/items/${encodeURIComponent(item.id)}?version=${encodeURIComponent(item.version)}`, { method: "DELETE" });
        showToast(result?.mode === "soft" ? "该项目已有历史引用，已安全归档" : "配置项目已删除");
        return true;
      } : null
    });
    const status = $("[name=translation_status]", dialog);
    if (status) status.value = item?.translation_status || "machine_draft";
    return dialog;
  }

  window.addConfigCategory = function addConfigCategoryV2() { return openCatalogCategoryEditor(); };
  window.editConfigCategory = function editConfigCategoryV2(category) { return openCatalogCategoryEditor(category); };
  window.addConfigOption = function addConfigOptionV2(categoryId) { return openCatalogItemEditor(null, categoryId); };
  window.openConfigOptionEditor = function openConfigOptionEditorV2(item) { return openCatalogItemEditor(item); };

  function selectCatalogRoot(rootId, focus = false) {
    if (!catalogRoots().some((root) => root.id === rootId)) return;
    state.catalogRootId = rootId;
    const url = new URL(window.location.href);
    url.searchParams.set("catalog", rootId);
    history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    window.renderConfigCatalog();
    if (focus) $$('[data-catalog-root]').find((button) => button.dataset.catalogRoot === rootId)?.focus();
  }

  window.selectCatalogRootFromNavigation = function selectCatalogRootFromNavigation(rootId) {
    selectCatalogRoot(rootId);
  };

  document.addEventListener("click", (event) => {
    const removeColor = event.target.closest("[data-remove-color]");
    if (removeColor) {
      event.preventDefault();
      event.stopImmediatePropagation();
      const rows = $$(".color-editor-row", $("#color-editor-list"));
      if (rows.length <= 1) { showToast("设备至少需要保留一个外观颜色", "error"); return; }
      confirmAction("删除外观颜色", "保存设备后，该颜色及其图片关联将从当前设备中移除。确定继续吗？", "删除颜色").then((confirmed) => {
        if (!confirmed) return;
        const row = removeColor.closest(".color-editor-row");
        const wasDefault = $('[data-color-field="is_default"]', row).checked;
        row.remove();
        if (wasDefault) $('[data-color-field="is_default"]', $("#color-editor-list"))?.click();
      });
      return;
    }
    const catalogCancel = event.target.closest('.catalog-v2-dialog button[value="cancel"]');
    if (catalogCancel) {
      const form = catalogCancel.form;
      const current = JSON.stringify(Object.fromEntries(new FormData(form)));
      if (form.dataset.initialSnapshot && current !== form.dataset.initialSnapshot) {
        event.preventDefault();
        event.stopImmediatePropagation();
        confirmAction("放弃未保存修改", "当前配置目录内容尚未保存，确定关闭编辑窗口吗？", "放弃修改").then((confirmed) => { if (confirmed) catalogCancel.closest("dialog").close(); });
        return;
      }
    }
    const productCancel = event.target.closest('#product-dialog button[value="cancel"]');
    if (productCancel && state.editingProduct) {
      if (window.hasUnsavedProductChanges()) {
        event.preventDefault();
        event.stopImmediatePropagation();
        confirmAction("放弃未保存的修改？", "此设备的修改尚未保存。关闭后，本次修改将无法恢复。", "放弃修改").then((confirmed) => {
          if (confirmed) $("#product-dialog").close();
        });
        return;
      }
    }
    const rootButton = event.target.closest("[data-catalog-root]");
    if (rootButton) { selectCatalogRoot(rootButton.dataset.catalogRoot); return; }
    if (event.target.closest("[data-add-catalog-category]")) { openCatalogCategoryEditor(); return; }
    const addCatalogItem = event.target.closest("[data-add-catalog-item]");
    if (addCatalogItem) { openCatalogItemEditor(null, addCatalogItem.dataset.addCatalogItem); return; }
    const editCatalogItem = event.target.closest("[data-edit-catalog-item]");
    if (editCatalogItem) {
      const item = findCatalogItem(editCatalogItem.dataset.editCatalogItem);
      if (item) openCatalogItemEditor(item);
      return;
    }
    const moveCatalog = event.target.closest("[data-move-catalog-item]");
    if (moveCatalog) {
      moveCatalogItem(moveCatalog.dataset.moveCatalogItem, moveCatalog.dataset.categoryId, moveCatalog.dataset.direction, moveCatalog);
      return;
    }
    const editCatalogCategory = event.target.closest("[data-edit-catalog-category]");
    if (editCatalogCategory) {
      const category = findCatalogCategory(editCatalogCategory.dataset.editCatalogCategory);
      if (category) openCatalogCategoryEditor(category);
      editCatalogCategory.closest("details")?.removeAttribute("open");
      return;
    }
    const deleteCatalogCategory = event.target.closest("[data-delete-catalog-category]");
    if (deleteCatalogCategory) {
      const category = findCatalogCategory(deleteCatalogCategory.dataset.deleteCatalogCategory);
      deleteCatalogCategory.closest("details")?.removeAttribute("open");
      if (category) confirmAction("删除配置分类", `确定删除“${category.name}”吗？分类中仍有项目时系统会阻止删除。`, "删除分类").then(async (confirmed) => {
        if (!confirmed) return;
        try { await api(`/api/v1/admin/catalog/categories/${encodeURIComponent(category.id)}`, { method: "DELETE" }); showToast("配置分类已删除"); await loadData(); }
        catch (failure) { showToast(failure.message, "error"); }
      });
      return;
    }
    if (event.target.closest("#add-color-button")) setTimeout(showProductLanguageFields, 0);
    if (event.target.closest("#add-specification-button") && state.editingProduct) {
      state.editingProduct.specifications.push({ id: temporaryId("spec"), label: "", label_en: "", value: "", value_en: "", sort_order: state.editingProduct.specifications.length });
      renderSpecifications();
      return;
    }
    const removeSpec = event.target.closest("[data-remove-spec]");
    if (removeSpec && state.editingProduct) {
      captureSpecifications();
      state.editingProduct.specifications.splice(Number(removeSpec.dataset.removeSpec), 1);
      renderSpecifications();
      return;
    }
    const moveSpec = event.target.closest("[data-move-spec]");
    if (moveSpec && state.editingProduct) {
      captureSpecifications();
      const from = Number(moveSpec.dataset.moveSpec);
      const to = from + Number(moveSpec.dataset.direction);
      if (to >= 0 && to < state.editingProduct.specifications.length) {
        const items = state.editingProduct.specifications;
        [items[from], items[to]] = [items[to], items[from]];
        renderSpecifications();
      }
      return;
    }
    const add = event.target.closest("[data-add-base-option]");
    if (add && state.editingProduct) {
      captureBaseOptions();
      const group = ensureGroup(add.dataset.addBaseOption);
      group.options.push({
        id: temporaryId(`base-${state.editingProduct.id}-${group.option_type}`),
        name_zh: "",
        name_en: "",
        price_cny_minor: 0,
        price_usd_minor: 0,
        price_confirmed: false,
        is_free: false,
        enabled: true,
        translation_status: "machine_draft",
        sort_order: group.options.length
      });
      renderBaseOptions();
      return;
    }
    const toggleBaseGroup = event.target.closest("[data-toggle-base-group]");
    if (toggleBaseGroup && state.editingProduct) {
      captureBaseOptions();
      const type = toggleBaseGroup.dataset.toggleBaseGroup;
      state.collapsedBaseGroups ||= new Set();
      if (state.collapsedBaseGroups.has(type)) state.collapsedBaseGroups.delete(type);
      else state.collapsedBaseGroups.add(type);
      renderBaseOptions();
      return;
    }
    const remove = event.target.closest("[data-remove-base-option]");
    if (remove && state.editingProduct) {
      captureBaseOptions();
      const optionId = remove.dataset.removeBaseOption;
      const affected = (state.editingProduct.price_variants || []).filter((item) => item.motor_option_id === optionId || item.channel_option_id === optionId).length;
      confirmAction("删除基本配置", affected ? `该选项关联 ${affected} 个基础价格方案。保存后这些价格方案会同时停用，确定继续吗？` : "确定删除这个基本配置选项吗？", "确认删除").then((confirmed) => {
        if (!confirmed) return;
        state.editingProduct.base_option_groups.forEach((group) => {
          group.options = group.options.filter((item) => item.id !== optionId);
        });
        state.editingProduct.price_variants = (state.editingProduct.price_variants || []).filter((item) => item.motor_option_id !== optionId && item.channel_option_id !== optionId);
        renderBaseOptions();
      });
    }
    const moveBase = event.target.closest("[data-move-base-option]");
    if (moveBase && state.editingProduct) {
      captureBaseOptions();
      const group = state.editingProduct.base_option_groups.find((item) => item.options.some((option) => option.id === moveBase.dataset.moveBaseOption));
      const from = group?.options.findIndex((item) => item.id === moveBase.dataset.moveBaseOption) ?? -1;
      const to = from + Number(moveBase.dataset.direction);
      if (group && from >= 0 && to >= 0 && to < group.options.length) {
        [group.options[from], group.options[to]] = [group.options[to], group.options[from]];
        renderBaseOptions();
      }
    }
  });

  document.addEventListener("change", (event) => {
    const free = event.target.closest("[data-base-free]");
    if (free) {
      const row = free.closest("[data-base-option]");
      $$('[data-base-price-cny],[data-base-price-usd]', row).forEach((input) => {
        input.disabled = free.checked;
        if (free.checked && input.type === "number") input.value = "0.00";
      });
    }
    const colorValue = event.target.closest('[data-color-field="display_color"]');
    if (colorValue) colorValue.title = colorValue.value;
    if (event.target.matches?.('#product-form [name="enabled"]')) {
      const status = $("#product-editor-status");
      status.textContent = event.target.checked ? "已启用" : "已下架";
      status.className = `badge ${event.target.checked ? "good" : "off"}`;
    }
  });

  document.addEventListener("input", (event) => {
    const colorName = event.target.closest?.('[data-color-field="name_zh"],[data-color-field="name_en"]');
    if (colorName) colorName.closest("[data-color-id]").dataset.translationStatus = colorName.dataset.colorField === "name_en" ? "reviewed" : "machine_draft";
    const baseName = event.target.closest?.("[data-base-name]");
    if (baseName) baseName.closest("[data-base-option]").dataset.translationStatus = editorLanguage() === "en" ? "reviewed" : "machine_draft";
  });

  document.addEventListener("keydown", (event) => {
    const rootButton = event.target.closest?.("[data-catalog-root]");
    if (!rootButton || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const tabs = $$("[data-catalog-root]", rootButton.closest('[role="tablist"]'));
    const current = tabs.indexOf(rootButton);
    if (current < 0) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    selectCatalogRoot(tabs[next].dataset.catalogRoot, true);
  });

  $("#product-dialog")?.addEventListener("cancel", (event) => {
    if (!state.editingProduct) return;
    if (!window.hasUnsavedProductChanges()) return;
    event.preventDefault();
    confirmAction("放弃未保存的修改？", "此设备的修改尚未保存。关闭后，本次修改将无法恢复。", "放弃修改").then((confirmed) => {
      if (confirmed) $("#product-dialog").close();
    });
  });

  window.addEventListener("beforeunload", (event) => {
    if (!window.hasUnsavedProductChanges()) return;
    event.preventDefault();
    event.returnValue = "";
  });
})();
