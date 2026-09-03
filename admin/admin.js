// An empty runtime base is deliberate for the NAS Nginx same-origin proxy.
const API_BASE = typeof window.BOTEN_API_BASE === "string"
  ? window.BOTEN_API_BASE
  : (window.location.port === "8001" ? "" : `${window.location.protocol}//${window.location.hostname || "127.0.0.1"}:8001`);
const TOKEN_KEY = "boten_admin_token";
const CUSTOMER_TOKEN_KEY = "boten_user_token";

function getStoredCollapsedCategories() { try { const value = JSON.parse(localStorage.getItem("boten-admin-collapsed-categories") || "[]"); return Array.isArray(value) ? value : []; } catch (_) { return []; } }
const state = { user: null, products: [], users: [], shares: [], quotes: [], audits: [], countries: [], editingProduct: null, mappingEditor: null, userRoleFilter: "all", catalogLanguage: localStorage.getItem("boten-admin-language") || "zh", configCatalog: [], collapsedCategories: new Set(getStoredCollapsedCategories()) };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

async function api(path, requestOptions = {}) {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const { timeout: timeoutMs = 15000, ...options } = requestOptions;
  const method = String(options.method || "GET").toUpperCase();
  // 页面首次进入会并发读取多个目录。仅对不会修改数据的 GET 请求重试一次，
  // 避免 NAS 冷启动或 SQLite 短暂繁忙时把正常页面误显示成加载失败。
  const attempts = method === "GET" ? 2 : 1;
  let failure;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const controller = new AbortController();
    let timedOut = false;
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(options.headers || {})
        }, signal: controller.signal
      });
      if (response.status === 204) return null;
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || `请求失败 (${response.status})`);
      return body;
    } catch (error) {
      failure = timedOut ? new Error("请求超时，请稍后重试") : error;
      if (attempt + 1 < attempts) await new Promise(resolve => setTimeout(resolve, 500));
    } finally {
      clearTimeout(timeout);
    }
  }
  throw failure;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

function catalogAssetUrl(path) {
  const value = String(path || "").trim();
  if (!value) return "";
  if (value.startsWith("/api/")) return `${API_BASE}${value}`;
  if (/^(?:[a-z]+:|\/|\.{1,2}\/)/i.test(value)) return value;
  // The administration page is served from /admin/, while catalog asset
  // paths are stored relative to the customer-facing site root.
  return `../${value}`;
}

async function uploadCatalogImage(file, control) {
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) { showToast("图片不能超过 8 MB"); return; }
  const button = $("[data-pick-image]", control);
  const pathInput = $('[name="image_path"],[data-color-field="image_path"]', control);
  if (button) { button.disabled = true; button.textContent = "上传中…"; }
  try {
    const result = await api(`/api/v1/admin/media?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
      timeout: 30000
    });
    if (pathInput) pathInput.value = result.path;
    const preview = $("[data-color-image-preview]", control);
    if (preview) preview.innerHTML = `<img src="${escapeHtml(catalogAssetUrl(result.path))}" alt="颜色图片缩略图" width="152" height="92" />`;
    showToast("图片上传成功");
  } catch (failure) {
    showToast(failure.name === "AbortError" ? "图片上传超时" : failure.message);
  } finally {
    if (button) { button.disabled = false; button.textContent = "上传"; }
  }
}

function confirmAction(title, message, confirmLabel = "确认删除") {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.className = "product-dialog";
    dialog.dataset.dynamic = "true";
    dialog.innerHTML = `<form method="dialog" class="dialog-card confirm-card"><header><div><span class="eyebrow">CONFIRM ACTION</span><h2>${escapeHtml(title)}</h2></div><button class="icon-button" value="cancel" aria-label="关闭">×</button></header><p>${escapeHtml(message)}</p><footer><button class="button button-quiet" value="cancel">取消</button><button class="button button-danger" value="confirm">${escapeHtml(confirmLabel)}</button></footer></form>`;
    document.body.appendChild(dialog);
    let settled = false;
    dialog.addEventListener("close", () => { if (!settled) resolve(false); dialog.remove(); });
    dialog.querySelector("form").addEventListener("submit", (event) => { event.preventDefault(); settled = true; const confirmed = event.submitter?.value === "confirm"; dialog.close(); resolve(confirmed); });
    dialog.showModal();
  });
}

function renderCatalogThumbnail(option) {
  const source = catalogAssetUrl(option.image_path);
  if (!source) return '<span class="config-thumbnail-empty">—</span>';
  return `<span class="config-thumbnail"><img src="${escapeHtml(source)}" alt="${escapeHtml(option.code)}" width="112" height="72" loading="lazy" onerror="this.parentElement.classList.add('missing')" /><span aria-hidden="true">—</span></span>`;
}

function showToast(message) {
  const toast = $("#toast");
  const openDialogs = Array.from(document.querySelectorAll("dialog[open]"));
  const host = openDialogs.at(-1) || document.body;
  if (toast.parentElement !== host) host.appendChild(toast);
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    toast.hidden = true;
    if (toast.parentElement !== document.body) document.body.appendChild(toast);
  }, 2800);
}

async function runButtonAction(button, pendingLabel, action) {
  if (!button || button.disabled) return;
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = pendingLabel;
  try { return await action(); }
  finally { button.disabled = false; button.textContent = originalLabel; }
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));
}

function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(String(value).includes("T") ? value : `${value.replace(" ", "T")}Z`);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", { hour12: false });
}

function roleLabel(role) {
  return { admin: "管理员", sales: "业务员", customer: "客户", guest: "游客" }[role] || role;
}

async function checkApi() {
  const status = $("#api-status");
  try {
    await api("/api/v1/health");
    status.textContent = "服务连接正常";
    status.style.color = "var(--green)";
    return true;
  } catch (_) {
    status.textContent = "无法连接后端，请先启动 8001 端口的 API 服务";
    status.style.color = "var(--red)";
    return false;
  }
}

async function restoreSession() {
  const token = sessionStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(CUSTOMER_TOKEN_KEY);
  if (!token) return false;
  if (!sessionStorage.getItem(TOKEN_KEY)) sessionStorage.setItem(TOKEN_KEY, token);
  try {
    const user = await api("/api/v1/auth/me");
    if (!["admin", "sales"].includes(user.role)) throw new Error("该账号没有后台访问权限");
    state.user = user;
    await enterAdmin();
    return true;
  } catch (_) {
    sessionStorage.removeItem(TOKEN_KEY);
    return false;
  }
}

async function login(event) {
  event.preventDefault();
  const error = $("#login-error");
  const submit = $("#login-form button[type=submit]");
  error.hidden = true;
  submit.disabled = true;
  submit.firstElementChild.textContent = "正在登录…";
  try {
    const result = await api("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ identifier: $("#login-identifier").value.trim(), password: $("#login-password").value })
    });
    if (!["admin", "sales"].includes(result.user.role)) throw new Error("该账号没有后台访问权限");
    sessionStorage.setItem(TOKEN_KEY, result.session.token);
    state.user = result.user;
    await enterAdmin();
  } catch (failure) {
    error.textContent = failure.message;
    error.hidden = false;
  } finally {
    submit.disabled = false;
    submit.firstElementChild.textContent = "进入后台";
  }
}

async function enterAdmin() {
  $("#login-page").hidden = true;
  $("#admin-app").hidden = false;
  $("#admin-name").textContent = state.user.display_name || "Administrator";
  $("#admin-email").textContent = state.user.email || state.user.phone || "管理员";
  $("#admin-avatar").textContent = (state.user.display_name || state.user.email || "A").charAt(0).toUpperCase();
  const isAdmin = state.user.role === "admin";
  $$('[data-admin-only]').forEach((element) => { element.hidden = !isAdmin; });
  $(".sidebar-brand span").textContent = isAdmin ? "管理后台" : "业务员工作台";
  await loadData();
  const requestedView = window.location.hash.slice(1);
  const allowed = isAdmin ? ["dashboard", "products", "config-catalog", "shares", "quotes", "audit", "users"] : ["products", "config-catalog", "shares", "quotes"];
  switchView(allowed.includes(requestedView) ? requestedView : (isAdmin ? "dashboard" : "products"), false);
}

async function loadData() {
  try {
    const isAdmin = state.user.role === "admin";
    const [shares, quotes] = await Promise.all([
      api(isAdmin ? "/api/v1/admin/shares" : "/api/v1/staff/shares"),
      api("/api/v1/quotes")
    ]);
    state.shares = shares.items || [];
    state.quotes = quotes?.items || [];

    const [products, configCatalog, countries] = await Promise.all([
      api("/api/v1/admin/products"),
      api("/api/v1/admin/config-catalog"),
      api("/api/v1/auth/countries?lang=zh")
    ]);
    state.products = products.items || [];
    state.configCatalog = configCatalog.items || [];
    state.countries = countries.items || [];
    renderConfigCatalog(state.configCatalog);
    setTimeout(() => {
      addCatalogLanguageSwitches();
      applyCatalogLanguage(state.catalogLanguage);
      restoreCollapsedCategories();
    }, 0);
    if (isAdmin) {
      const [users, audits] = await Promise.all([
        api("/api/v1/admin/users"),
        api("/api/v1/admin/audit-logs")
      ]);
      state.users = users.items || [];
      state.audits = audits.items || [];
    } else {
      state.products = [];
      state.users = [];
      state.configCatalog = [];
    }
    renderAll();
  } catch (failure) {
    ["#products-table", "#users-table", "#shares-table"].forEach((selector) => {
      const target = $(selector);
      if (target) target.innerHTML = `<tr><td colspan="6" class="empty">无法加载数据：${escapeHtml(failure.message)}<br><small>请稍后刷新重试；若持续出现，请检查 NAS 中 API 容器状态与日志。</small></td></tr>`;
    });
    showToast(failure.message);
    if (/session|token|401/i.test(failure.message)) logout();
  }
}

function renderAll() {
  $("#metric-products").textContent = state.products.length;
  $("#metric-users").textContent = state.users.length;
  $("#metric-shares").textContent = state.shares.filter((item) => item.active && new Date(item.expires_at) > new Date()).length;
  $("#metric-views").textContent = state.shares.reduce((sum, item) => sum + item.view_count, 0);
    renderProducts(); renderUsers(); renderShares(); renderQuotes(); renderAudits(); renderDashboard();
}

function renderDashboard() {
  $("#dashboard-products").innerHTML = state.products.slice(0, 5).map((product) => `
    <div class="mini-row"><div><strong>${escapeHtml(product.name)}</strong><span>${escapeHtml(product.title_name)}</span></div><div class="model-mark">${escapeHtml(product.id.toUpperCase())}</div></div>
  `).join("") || '<div class="empty">暂无产品数据</div>';
  $("#dashboard-shares").innerHTML = state.shares.slice(0, 5).map((share) => `
    <div class="mini-row"><div><strong>${escapeHtml(share.code)}</strong><span>${escapeHtml(share.name)}</span></div><span class="badge ${share.active ? "good" : "off"}">${share.active ? "有效" : "已关闭"}</span></div>
  `).join("") || '<div class="empty">暂无分享记录</div>';
}

function renderProducts() {
  const english = state.catalogLanguage === "en";
  const priceLabel = $("[data-view-panel=\"products\"] thead th:nth-child(3)");
  if (priceLabel) priceLabel.textContent = english ? "价格 / USD" : "价格 / 人民币";
  $("#products-table").innerHTML = state.products.map((product) => `
    <tr><td><strong>${escapeHtml(english ? (product.name_en || product.name) : product.name)}</strong></td><td>${escapeHtml(english ? (product.title_name_en || product.title_name) : product.title_name)}</td><td>${english ? "$" + Number(product.price_usd || 0).toLocaleString("en-US") : "¥" + Number(product.base_price || 0).toLocaleString("zh-CN")}</td><td><span class="badge ${product.enabled ? "good" : "off"}">${product.enabled ? "已启用" : "已下架"}</span></td><td class="align-right"><button class="table-action" data-edit-product="${product.id}">编辑</button></td></tr>
  `).join("") || '<tr><td colspan="5" class="empty">暂无产品数据</td></tr>';
}

function renderConfigCatalog(categories) {
  const target = $("#config-catalog-list"); if (!target) return;
  target.innerHTML = categories.map((category) => `<section class="config-catalog-group"><header><div class="catalog-collapse-target" data-collapse-category="${escapeHtml(category.id)}" role="button" tabindex="0" aria-expanded="true"><h3>${escapeHtml(category.name)}</h3><p>${escapeHtml(category.description || "")}</p></div><div><span>${category.options.length} 项</span><button class="text-button" data-add-option="${escapeHtml(category.id)}">添加配置</button><details class="catalog-more"><summary>更多</summary><div><button class="text-button" data-edit-category='${escapeHtml(JSON.stringify(category))}'>编辑分类</button></div></details></div></header><div class="config-catalog-table"><table><thead><tr><th>编号</th><th>名称</th><th>图片</th><th>参考价格</th><th>状态</th><th></th></tr></thead><tbody>${category.options.map((option) => `<tr><td><strong>${escapeHtml(option.code)}</strong></td><td>${escapeHtml(option.name)}<br><small>${escapeHtml(option.description || "")}</small></td><td class="config-image-cell">${renderCatalogThumbnail(option)}</td><td>¥${Number(option.price || 0).toLocaleString("zh-CN")}</td><td><span class="badge ${option.enabled ? "good" : "off"}">${option.enabled ? "启用" : "停用"}</span></td><td class="align-right"><button class="table-action" data-edit-option='${escapeHtml(JSON.stringify(option))}'>编辑</button></td></tr>`).join("")}</tbody></table></div></section>`).join("") || '<div class="empty">暂无配置目录</div>';
}

async function addConfigCategory() { categoryCard(); }
async function editConfigCategory(category) { categoryCard(category); }

function addLanguageToggles() { ["#product-dialog", "#config-option-dialog"].forEach((selector) => { const dialog = $(selector); const header = $(".dialog-card > header", dialog); if (!header || $(".lang-toggle", header)) return; const box = document.createElement("div"); box.className = "catalog-language dialog-language"; box.innerHTML = '<button type="button" class="lang-toggle active" data-lang="zh" aria-pressed="true">中文</button><button type="button" class="lang-toggle" data-lang="en" aria-pressed="false">EN</button>'; box.addEventListener("click", (event) => { const button = event.target.closest(".lang-toggle"); if (!button) return; event.stopPropagation(); toggleDialogLanguage(button); }); header.appendChild(box); }); const examples={name:"例如：CR318C",name_en:"例如：CR318C",title_name:"例如：共轨喷油器试验台",title_name_en:"例如：Common Rail Test Bench",description:"例如：适用于多种喷油器测试",description_en:"例如：Designed for common rail injector testing",code:"例如：BTK-1019",price:"例如：1500"}; Object.entries(examples).forEach(([name,placeholder])=>$$(`[name="${name}"]`).forEach(el=>{if(!el.placeholder)el.placeholder=placeholder;})); }
function toggleDialogLanguage(button) { const dialog = button.closest("dialog"); const lang = button.dataset.lang; $$(".lang-toggle", dialog).forEach((item) => { const active = item === button; item.classList.toggle("active", active); item.setAttribute("aria-pressed", String(active)); }); $$('[name$="_en"]', dialog).forEach((field) => { const label = field.closest("label"); if (label) label.hidden = lang !== "en"; }); $$('[name="name"],[name="title_name"],[name="description"]', dialog).forEach((field) => { const label = field.closest("label"); if (label) label.hidden = lang === "en"; }); $$('[data-color-name-lang]', dialog).forEach((label) => { label.hidden = label.dataset.colorNameLang !== lang; }); if (dialog.id === "product-dialog") { state.catalogLanguage = lang; localStorage.setItem("boten-admin-language", lang); renderMappingEditor(); } }
function applyCatalogLanguage(lang) { state.catalogLanguage=lang; $$(".catalog-language button").forEach(b=>b.classList.toggle("active",b.dataset.catalogLang===lang)); $$("#products-table tr").forEach((row,i)=>{const p=state.products[i];if(!p)return;const cells=row.children;cells[0].querySelector("strong").textContent=lang==="en"?(p.name_en||p.name):p.name;cells[1].textContent=lang==="en"?(p.title_name_en||p.title_name):p.title_name;}); $$(".config-catalog-group").forEach((group,i)=>{const c=state.configCatalog[i];if(!c)return;group.querySelector("h3").textContent=lang==="en"?(c.name_en||c.name):c.name;const p=group.querySelector("header p");if(p)p.textContent=lang==="en"?(c.description_en||c.description||""):(c.description||"");$$('tbody tr',group).forEach((row,n)=>{const o=c.options[n];if(!o)return;const cell=row.children[1];cell.childNodes[0].textContent=lang==="en"?(o.name_en||o.name):o.name;const small=cell.querySelector("small");if(small)small.textContent=lang==="en"?(o.description_en||o.description||""):(o.description||"");});}); }
function addCatalogLanguageSwitches(){[["products","设备目录"],["config-catalog","配置目录"]].forEach(([view])=>{const header=$(`[data-view-panel="${view}"] .panel-header`);if(!header||$(".catalog-language",header))return;const box=document.createElement("div");box.className="catalog-language";box.innerHTML='<button type="button" class="active" data-catalog-lang="zh">中文</button><button type="button" data-catalog-lang="en">EN</button>';header.appendChild(box);box.addEventListener("click",e=>{const b=e.target.closest("[data-catalog-lang]");if(b)applyCatalogLanguage(b.dataset.catalogLang);});});}
function openConfigOptionEditor(option) {
  const form = $("#config-option-form");
  const zhButton = $(`.lang-toggle[data-lang="${state.catalogLanguage}"]`, $("#config-option-dialog")); if (zhButton) toggleDialogLanguage(zhButton);
  form.elements.option_id.value = option.id; form.elements.code.value = option.code || ""; form.elements.name.value = option.name || ""; form.elements.name_en.value = option.name_en || ""; form.elements.image_path.value = option.image_path || ""; form.elements.description.value = option.description || ""; form.elements.description_en.value = option.description_en || ""; form.elements.notes.value = option.notes || ""; form.elements.price.value = option.price || 0; if (form.elements.price_usd) form.elements.price_usd.value = option.price_usd || 0; form.elements.enabled.checked = option.enabled;
  $("#config-option-error").hidden = true; $("#config-option-dialog").showModal();
}

async function openProductEditor(productId) {
  try {
    const product = await api(`/api/v1/admin/products/${productId}`);
    state.editingProduct = product;
    const form = $("#product-form");
    form.elements.product_id.value = product.id;
    form.elements.name.value = product.name; form.elements.name_en.value = product.name_en || "";
    form.elements.title_name.value = product.title_name; form.elements.title_name_en.value = product.title_name_en || "";
    form.elements.description.value = product.description || ""; form.elements.description_en.value = product.description_en || "";
    form.elements.base_price.value = product.base_price;
    if (form.elements.price_usd) form.elements.price_usd.value = product.price_usd || 0;
    form.elements.sort_order.value = product.sort_order;
    form.elements.enabled.checked = product.enabled;
    const specificationEditor = $("#product-specifications-editor");
    const renderSpecifications = () => { specificationEditor.innerHTML = (state.editingProduct.specifications || []).map((s, i) => `<div class="specification-row" data-id="${escapeHtml(s.id || "")}"><input data-spec="label" aria-label="中文项目" value="${escapeHtml(s.label || "")}" placeholder="中文项目"><input data-spec="label_en" aria-label="英文项目" value="${escapeHtml(s.label_en || "")}" placeholder="英文项目"><input data-spec="value" aria-label="中文数据" value="${escapeHtml(s.value || "")}" placeholder="中文数据"><input data-spec="value_en" aria-label="英文数据" value="${escapeHtml(s.value_en || "")}" placeholder="英文数据"><button type="button" class="button button-quiet" data-move-spec="${i}" data-direction="-1" ${i ? "" : "disabled"}>↑</button><button type="button" class="button button-quiet" data-move-spec="${i}" data-direction="1" ${i === state.editingProduct.specifications.length - 1 ? "" : "disabled"}>↓</button><button type="button" class="button button-quiet" data-remove-spec="${i}">删除</button></div>`).join(""); };
    state.editingProduct.specifications = Array.isArray(product.specifications) ? product.specifications : [];
    renderSpecifications();
    $("#add-specification-button").onclick = () => { state.editingProduct.specifications.push({ label: "", label_en: "", value: "", value_en: "" }); renderSpecifications(); };
    const captureSpecifications = () => { state.editingProduct.specifications = Array.from(specificationEditor.querySelectorAll(".specification-row")).map((row) => ({ id: row.dataset.id || null, label: row.querySelector('[data-spec="label"]').value, label_en: row.querySelector('[data-spec="label_en"]').value, value: row.querySelector('[data-spec="value"]').value, value_en: row.querySelector('[data-spec="value_en"]').value })); };
    specificationEditor.onclick = (event) => { const remove = event.target.closest("[data-remove-spec]"); const move = event.target.closest("[data-move-spec]"); if (remove) { captureSpecifications(); state.editingProduct.specifications.splice(Number(remove.dataset.removeSpec), 1); renderSpecifications(); } if (move) { captureSpecifications(); const from = Number(move.dataset.moveSpec); const to = from + Number(move.dataset.direction); const items = state.editingProduct.specifications; [items[from], items[to]] = [items[to], items[from]]; renderSpecifications(); } };
    $("#product-dialog-title").textContent = `编辑 ${product.name}`;
    renderColorEditor(product.colors);
    state.mappingEditor = {
      categories: product.categories,
      selected: new Set(product.categories.flatMap((category) => category.options.filter((option) => option.selected).map((option) => option.id))),
      notes: new Map(product.categories.flatMap((category) => category.options.map((option) => [option.id, { zh: option.description_override || "", en: option.description_override_en || "", mapped: Boolean(option.mapped), dirty: false }]))),
      motorPrices: new Map(product.categories.flatMap((category) => category.id === "motor" ? category.options.map((option) => [option.id, { base_price_cny: option.motor_base_price_cny ?? product.base_price ?? 0, base_price_usd: option.motor_base_price_usd ?? product.price_usd ?? 0 }]) : [])),
      query: "",
      filter: "all",
      collapsed: new Set(product.categories.map((category) => category.id))
    };
    renderMappingEditor();
    switchEditorTab("basic");
    $("#product-error").hidden = true;
    const zhButton = $(`.lang-toggle[data-lang="${state.catalogLanguage}"]`, $("#product-dialog")); if (zhButton) toggleDialogLanguage(zhButton);
    $("#product-dialog").showModal();
  } catch (failure) { showToast(failure.message); }
}

function renderColorEditor(colors) {
  $("#color-editor-list").innerHTML = colors.map((color) => colorEditorRow(color)).join("");
}

function colorEditorRow(color = { code: "", label: "", label_en: "", image_path: "", is_default: false }) {
  const code = color.code || `color-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const image = color.image_path ? `<img src="${escapeHtml(catalogAssetUrl(color.image_path))}" alt="颜色图片缩略图" width="152" height="92" />` : "<span>暂无图片</span>";
  return `<div class="color-editor-row">
    <input data-color-field="code" type="hidden" value="${escapeHtml(code)}" />
    <label class="color-name-field" data-color-name-lang="zh"><span>颜色名称</span><input data-color-field="label" value="${escapeHtml(color.label)}" placeholder="例如：绿色" /></label>
    <label class="color-name-field" data-color-name-lang="en" hidden><span>颜色名称</span><input data-color-field="label_en" value="${escapeHtml(color.label_en || color.label)}" placeholder="e.g. Green" /></label>
    <label class="color-image-field"><span>颜色图片</span><div class="color-image-control"><input data-color-field="image_path" type="hidden" value="${escapeHtml(color.image_path || "")}" /><div class="color-image-preview" data-color-image-preview>${image}</div><button class="button button-secondary" type="button" data-pick-image>上传图片</button><input type="file" accept="image/png,image/jpeg,image/webp" data-image-file hidden /></div></label>
    <label class="default-color"><input data-color-field="is_default" type="radio" name="default-color" ${color.is_default ? "checked" : ""} /><span>默认</span></label>
    <button class="icon-button" data-remove-color type="button" aria-label="删除颜色">✕</button>
  </div>`;
}

async function deleteCurrentConfigOption() {
  const optionId = $("#config-option-form").elements.option_id.value;
  if (!optionId) return;
  const button = $("#delete-config-option");
  try {
    const references = await api(`/api/v1/admin/config-catalog/options/${encodeURIComponent(optionId)}/references`);
    if (references.mapping_count) {
      const names = references.products.map((product) => product.name).join("、");
      showToast(`该配置仍被 ${references.mapping_count} 台设备使用：${names}`);
      return;
    }
    if (!await confirmAction("删除配置", `确定永久删除 ${references.code} ${references.name}？`)) return;
    await runButtonAction(button, "删除中…", async () => {
      await api(`/api/v1/admin/config-catalog/options/${encodeURIComponent(optionId)}`, { method: "DELETE" });
      $("#config-option-dialog").close();
      showToast("配置已删除");
      await loadData();
    });
  } catch (failure) { showToast(failure.message); }
}

async function deleteConfigCategory(category) {
  const references = await api(`/api/v1/admin/config-catalog/categories/${encodeURIComponent(category.id)}/references`);
  if (references.protected) {
    showToast("电机和供电属于系统基础分类，不能删除");
    return false;
  }
  if (references.option_count) {
    showToast(`分类中仍有 ${references.option_count} 项配置，请先处理配置项`);
    return false;
  }
  if (!await confirmAction("删除配置分类", `确定永久删除“${references.name}”？`)) return false;
  await api(`/api/v1/admin/config-catalog/categories/${encodeURIComponent(category.id)}`, { method: "DELETE" });
  showToast("配置分类已删除");
  return true;
}

function renderMappingEditor() {
  const editor = state.mappingEditor;
  if (!editor) return;
  $$("[data-motor-price-cny]").forEach((field) => { const id = field.dataset.motorPriceCny; const usd = $(`[data-motor-price-usd="${CSS.escape(id)}"]`); editor.motorPrices.set(id, { base_price_cny: Number(field.value || 0), base_price_usd: Number(usd?.value || 0) }); });
  const lang = $(".lang-toggle.active", $("#product-dialog"))?.dataset.lang || state.catalogLanguage || "zh";
  const query = (editor.query || "").trim().toLocaleLowerCase();
  const groups = editor.categories.map((category) => {
    const options = category.options.filter((option) => {
      const note = editor.notes.get(option.id);
      const matchesFilter = editor.filter === "selected" ? editor.selected.has(option.id) : editor.filter === "noted" ? Boolean(note?.zh || note?.en) : true;
      const haystack = [option.code, option.name, option.name_en, option.description, option.description_en, note?.zh, note?.en].join(" ").toLocaleLowerCase();
      return matchesFilter && (!query || haystack.includes(query));
    });
    if (!options.length) return "";
    const collapsed = editor.collapsed?.has(category.id);
    return `
    <section class="mapping-group ${category.id === "motor" ? "motor-mapping-group" : ""} ${collapsed ? "collapsed" : ""}">
      <header><button type="button" class="mapping-group-toggle" data-mapping-category="${escapeHtml(category.id)}" aria-expanded="${String(!collapsed)}"><h3>${escapeHtml(lang === "en" ? (category.name_en || category.name) : category.name)}</h3><span>${category.options.filter((option) => editor.selected.has(option.id)).length} / ${category.options.length} ${lang === "en" ? "enabled" : "项已启用"}</span></button></header>
      <div class="mapping-options" ${collapsed ? "hidden" : ""}>${options.map((option) => {
        const optionName = lang === "en" ? (option.name_en || option.name) : option.name;
        const description = lang === "en" ? (option.description_en || option.description) : option.description;
        const specialNote = editor.notes.get(option.id)?.[lang] || "";
        const motorPrice = category.id === "motor" ? (editor.motorPrices.get(option.id) || { base_price_cny: option.motor_base_price_cny ?? state.editingProduct?.base_price ?? 0, base_price_usd: option.motor_base_price_usd ?? state.editingProduct?.price_usd ?? 0 }) : null;
        return `<div class="mapping-option"><input type="checkbox" value="${escapeHtml(option.id)}" aria-label="${lang === "en" ? "Enable" : "启用"} ${escapeHtml(optionName)}" ${editor.selected.has(option.id) ? "checked" : ""} /><div class="mapping-option-copy"><strong>${escapeHtml(optionName)}</strong>${description ? `<small>${escapeHtml(description.replace(/<[^>]*>/g, " "))}</small>` : ""}${specialNote ? `<b class="mapping-special-note">${escapeHtml(specialNote)}</b>` : ""}${motorPrice ? `<div class="motor-price-fields"><label>人民币基础价<input type="number" min="0" step="1" data-motor-price-cny="${escapeHtml(option.id)}" value="${Number(motorPrice.base_price_cny || 0)}"></label><label>美元基础价<input type="number" min="0" step="1" data-motor-price-usd="${escapeHtml(option.id)}" value="${Number(motorPrice.base_price_usd || 0)}"></label></div>` : ""}</div><button type="button" class="text-button mapping-note-button" data-edit-mapping-note="${escapeHtml(option.id)}">标注</button></div>`;
      }).join("")}</div>
    </section>
  `; }).join("");
  $("#mapping-editor").innerHTML = groups || `<div class="mapping-empty">${lang === "en" ? "No matching configurations" : "没有符合条件的配置"}</div>`;
  $$('[data-mapping-filter]').forEach((button) => button.classList.toggle("active", button.dataset.mappingFilter === editor.filter));
  const expand = $("#mapping-expand-all");
  if (expand) expand.textContent = editor.collapsed?.size ? "展开全部" : "全部折叠";
}

function openMappingNoteEditor(optionId) {
  const editor = state.mappingEditor;
  const option = editor?.categories.flatMap((category) => category.options).find((item) => item.id === optionId);
  if (!option) return;
  const note = editor.notes.get(optionId) || { zh: "", en: "", mapped: false, dirty: false };
  const dialog = document.createElement("dialog");
  dialog.className = "mapping-note-dialog";
  dialog.dataset.dynamic = "true";
  dialog.innerHTML = `<form method="dialog" class="dialog-card"><header><div><span class="eyebrow">MODEL-SPECIFIC NOTE</span><h2>编辑标注</h2></div><div class="dialog-actions"><div class="catalog-language dialog-language"><button type="button" class="lang-toggle" data-note-lang="zh">中文</button><button type="button" class="lang-toggle" data-note-lang="en">EN</button></div><button class="icon-button" value="cancel" aria-label="关闭">×</button></div></header><p class="mapping-note-option-name"></p><label data-note-field="zh"><span>专有标注</span><textarea name="note_zh" rows="4" placeholder="没有标注可留空">${escapeHtml(note.zh)}</textarea></label><label data-note-field="en"><span>专有标注</span><textarea name="note_en" rows="4" placeholder="没有标注可留空">${escapeHtml(note.en)}</textarea></label><footer><button class="button button-quiet" value="cancel">取消</button><button class="button button-primary" value="save">保存标注</button></footer></form>`;
  document.body.appendChild(dialog);
  const form = $("form", dialog);
  const setLang = (lang) => {
    $$('[data-note-field]', dialog).forEach((field) => { field.hidden = field.dataset.noteField !== lang; });
    $$('[data-note-lang]', dialog).forEach((button) => button.classList.toggle("active", button.dataset.noteLang === lang));
    $(".mapping-note-option-name", dialog).textContent = lang === "en" ? (option.name_en || option.name) : option.name;
  };
  $$('[data-note-lang]', dialog).forEach((button) => button.addEventListener("click", (event) => { event.stopPropagation(); setLang(button.dataset.noteLang); }));
  setLang(state.catalogLanguage || "zh");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (event.submitter?.value !== "save") { dialog.close(); dialog.remove(); return; }
    editor.notes.set(optionId, { ...note, zh: form.elements.note_zh.value.trim(), en: form.elements.note_en.value.trim(), dirty: true });
    dialog.close(); dialog.remove();
    renderMappingEditor();
  });
  dialog.showModal();
}

function switchEditorTab(tab) {
  $$(".editor-tab").forEach((button) => { const active = button.dataset.editorTab === tab; button.classList.toggle("active", active); button.setAttribute("aria-selected", String(active)); button.tabIndex = active ? 0 : -1; });
  $$(".editor-panel").forEach((panel) => { const active = panel.dataset.editorPanel === tab; panel.classList.toggle("active", active); panel.hidden = !active; });
}

function collectColors() {
  return $$(".color-editor-row", $("#color-editor-list")).map((row) => ({
    code: $('[data-color-field="code"]', row).value.trim(),
    label: $('[data-color-field="label"]', row).value.trim(),
    label_en: $('[data-color-field="label_en"]', row).value.trim(),
    image_path: $('[data-color-field="image_path"]', row).value.trim() || null,
    is_default: $('[data-color-field="is_default"]', row).checked
  }));
}

async function saveProduct(event) {
  event.preventDefault();
  const form = event.currentTarget;
  // Buttons with formmethod="dialog" (取消/关闭) also dispatch submit.
  // They must close the dialog without sending any API mutation.
  if (event.submitter?.value === "cancel") {
    form.closest("dialog")?.close();
    return;
  }
  const productId = form.elements.product_id.value;
  const error = $("#product-error");
  const submit = $("#save-product-button");
  error.hidden = true; submit.disabled = true; submit.textContent = "正在保存…";
  try {
    const colors = collectColors();
    if (!colors.length) throw new Error("至少需要一种外观颜色");
    if (colors.some((color) => !color.code || !color.label || !color.label_en)) throw new Error("请完整填写中英文颜色名称");
    const optionIds = Array.from(state.mappingEditor?.selected || []);
    const optionOverrides = {};
    for (const [optionId, note] of state.mappingEditor?.notes || []) {
      if (note.mapped || note.dirty || note.zh || note.en || state.mappingEditor.selected.has(optionId)) {
        optionOverrides[optionId] = { description_override: note.zh || null, description_override_en: note.en || null };
      }
    }
    const motorPrices = Object.fromEntries(Array.from(state.mappingEditor?.motorPrices || []).filter(([optionId]) => state.mappingEditor.selected.has(optionId)));
    $$("[data-motor-price-cny]").forEach((field) => { const id = field.dataset.motorPriceCny; const usd = $(`[data-motor-price-usd="${CSS.escape(id)}"]`); motorPrices[id] = { base_price_cny: Number(field.value || 0), base_price_usd: Number(usd?.value || 0) }; });
    await api(`/api/v1/admin/products/${productId}/configuration`, {
      method: "PUT",
      body: JSON.stringify({
        name: form.elements.name.value.trim(), name_en: form.elements.name_en.value.trim(), title_name: form.elements.title_name.value.trim(), title_name_en: form.elements.title_name_en.value.trim(),
        description: form.elements.description.value.trim(), description_en: form.elements.description_en.value.trim(), base_price: Number(form.elements.base_price.value || 0), price_usd: Number(form.elements.price_usd?.value || 0),
        sort_order: Number(form.elements.sort_order.value || 0), enabled: form.elements.enabled.checked,
        colors, option_ids: optionIds, option_overrides: optionOverrides, motor_prices: motorPrices,
        specifications: Array.from($("#product-specifications-editor").querySelectorAll(".specification-row")).map((row, i) => ({ id: row.dataset.id || null, label: row.querySelector('[data-spec="label"]').value, label_en: row.querySelector('[data-spec="label_en"]').value, value: row.querySelector('[data-spec="value"]').value, value_en: row.querySelector('[data-spec="value_en"]').value, sort_order: i }))
      })
    });
    $("#product-dialog").close(); showToast("产品配置已保存"); await loadData();
  } catch (failure) {
    error.textContent = failure.message === "Failed to fetch"
      ? "无法连接 API，请确认 8001 端口服务已启动并重新登录后台"
      : failure.message;
    error.hidden = false;
  }
  finally { submit.disabled = false; submit.textContent = "保存产品"; }
}

function renderUsers() {
  const users = state.userRoleFilter === "all"
    ? state.users
    : state.users.filter((user) => user.role === state.userRoleFilter);
  $("#users-table").innerHTML = users.map((user) => `
    <tr>
      <td><div class="user-cell"><div class="avatar">${escapeHtml((user.display_name || user.email || "U").charAt(0).toUpperCase())}</div><strong>${escapeHtml(user.display_name || "未命名用户")}</strong></div></td>
      <td>${escapeHtml(user.email || user.phone || "—")}</td><td><span class="badge">${roleLabel(user.role)}</span></td>
      <td><span class="badge ${user.enabled ? "good" : "off"}">${user.enabled ? "正常" : "已禁用"}</span></td>
      <td class="align-right"><button class="table-action" data-edit-user='${escapeHtml(JSON.stringify(user))}'>编辑</button> <button class="table-action ${user.enabled ? "danger" : ""}" data-user-status="${user.id}" data-enabled="${!user.enabled}">${user.enabled ? "禁用" : "启用"}</button></td>
    </tr>
  `).join("") || '<tr><td colspan="5" class="empty">该分类暂无账号</td></tr>';
}

function renderShares() {
  const isAdmin = state.user?.role === "admin";
  $("#shares-table").innerHTML = state.shares.map((share) => {
    const valid = share.active && new Date(share.expires_at) > new Date();
    const sender = share.sender_name || share.sender_email || share.sender_phone || "未填写";
    const contact = share.sender_email || share.sender_phone || "—";
    const actions = valid ? `<span class="table-actions"><button class="table-action" data-lookup-share="${escapeHtml(share.code)}">查看</button><details class="table-actions-menu"><summary aria-label="更多分享操作">更多</summary><div><button class="table-action" data-export-share="${escapeHtml(share.code)}">导出 PDF</button><button class="table-action" data-quote-share="${escapeHtml(share.code)}">报价</button>${isAdmin ? `<button class="table-action danger" data-close-share="${share.id}">关闭</button>` : ""}</div></details></span>` : "—";
    return `<tr><td><button class="share-code-button" data-lookup-share="${escapeHtml(share.code)}" ${valid ? "" : "disabled"}>${escapeHtml(share.code)}</button></td><td>${escapeHtml(share.name)}<br><small>${escapeHtml(share.product_id.toUpperCase())}</small></td><td><strong>${escapeHtml(sender)}</strong><br><small>${escapeHtml(contact)}</small></td><td>${share.view_count} 次</td><td>${formatDate(share.expires_at)}</td><td><span class="badge ${valid ? "good" : "off"}">${valid ? "有效" : "已失效"}</span></td><td class="align-right">${actions}</td></tr>`;
  }).join("") || '<tr><td colspan="7" class="empty">暂无分享记录</td></tr>';
}

function renderQuotes() {
  const target = $("#quotes-table"); if (!target) return;
  target.innerHTML = state.quotes.map((quote) => { const symbol = quote.currency === "USD" ? "$" : "¥"; return `<tr><td><strong>${escapeHtml(quote.title)}</strong><br><small>${escapeHtml(quote.id.slice(0, 8))}</small></td><td>${escapeHtml(quote.display_name || quote.email || quote.phone || "—")}</td><td>${symbol}${Number(quote.total_price || 0).toLocaleString("zh-CN")}</td><td>${formatDate(quote.updated_at)}</td><td class="align-right"><button class="table-action" data-edit-quote="${escapeHtml(quote.id)}">编辑</button> <button class="table-action" data-export-quote="${escapeHtml(quote.id)}">导出PDF</button> <button class="table-action danger" data-delete-quote="${escapeHtml(quote.id)}">删除</button></td></tr>`; }).join("") || '<tr><td colspan="5" class="empty">暂无报价单</td></tr>';
}

function renderAudits() {
  const target = $("#audit-table"); if (!target) return;
  target.innerHTML = state.audits.map((item) => {
    const actor = item.display_name || item.email || item.phone || "已删除账号";
    const path = item.details?.path || `${item.entity_type}/${item.entity_id || ""}`;
    return `<tr><td>${escapeHtml(formatDateTime(item.created_at))}</td><td><strong>${escapeHtml(actor)}</strong><br><small>${escapeHtml(roleLabel(item.role || ""))}</small></td><td><span class="badge">${escapeHtml(item.action)}</span></td><td>${escapeHtml(path)}</td><td>${escapeHtml(item.details?.status || "成功")}</td></tr>`;
  }).join("") || '<tr><td colspan="5" class="empty">暂无操作记录</td></tr>';
}

function switchView(view, updateHistory = true) {
  if (state.user?.role === "sales" && !["shares", "quotes"].includes(view)) view = "shares";
  const titles = { dashboard: "管理概览", products: "设备目录", "config-catalog": "配置目录", users: "账号管理", shares: "分享记录", quotes: "报价管理", audit: "操作审计" };
  if (!titles[view]) view = state.user?.role === "admin" ? "dashboard" : "shares";
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  $$(".view").forEach((panel) => panel.classList.toggle("active", panel.dataset.viewPanel === view));
  $("#view-title").textContent = titles[view];
  if (updateHistory && window.location.hash !== `#${view}`) window.location.hash = view;
  if ($("#primary-action")) $("#primary-action").hidden = true;
  closeSidebar();
}

async function setUserStatus(button) {
  const enabled = button.dataset.enabled === "true";
  if (!await confirmAction(enabled ? "启用账号" : "禁用账号", enabled ? "确定恢复该账号的访问权限吗？" : "确定禁用该账号并撤销其当前会话吗？", enabled ? "确认启用" : "确认禁用")) return;
  try { await runButtonAction(button, "处理中…", async () => { await api(`/api/v1/admin/users/${button.dataset.userStatus}/status`, { method: "PATCH", body: JSON.stringify({ enabled }) }); showToast("账号状态已更新"); await loadData(); }); }
  catch (failure) { showToast(failure.message); }
}
function openUserEditor(user = null) {
  const dialog = $("#user-dialog");
  const form = $("#user-form");
  const editing = Boolean(user);
  form.reset();
  form.elements.user_id.value = user?.id || "";
  form.elements.display_name.value = user?.display_name || "";
  form.elements.role.value = user?.role || "sales";
  form.elements.email.value = user?.email || "";
  form.elements.phone.value = user?.phone || "";
  form.elements.phone_country.innerHTML = state.countries.map((country) => `<option value="${escapeHtml(country.code)}">${escapeHtml(country.name)}</option>`).join("");
  form.elements.phone_country.value = user?.phone_country || "CN";
  updateAdminPhoneCallingCode();
  form.elements.password.required = !editing;
  form.elements.password.placeholder = editing ? "留空表示不修改密码" : "至少8个字符";
  $("#user-dialog-eyebrow").textContent = editing ? "EDIT ACCOUNT" : "NEW ACCOUNT";
  $("#user-dialog-title").textContent = editing ? "编辑账号" : "创建账号";
  $("#user-password-label").textContent = editing ? "新密码（可选）" : "初始密码";
  $("#create-user-submit").textContent = editing ? "保存账号" : "创建账号";
  $("#user-error").hidden = true;
  dialog.showModal();
}

function updateAdminPhoneCallingCode() {
  const country = state.countries.find((item) => item.code === $("#user-form [name='phone_country']")?.value);
  const output = $("#admin-phone-calling-code");
  if (output) output.textContent = country?.calling_code || "—";
}

function editUser(user) { openUserEditor(user); }

async function createUser(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (event.submitter?.value === "cancel") { form.closest("dialog")?.close(); return; }
  const data = Object.fromEntries(new FormData(form));
  const userId = data.user_id;
  delete data.user_id;
  data.display_name = data.display_name.trim();
  data.email = data.email.trim();
  data.phone = data.phone.trim();
  data.phone_country = data.phone_country || "";
  const error = $("#user-error"); error.hidden = true;
  if (!data.display_name) { error.textContent = "请填写显示名称"; error.hidden = false; return; }
  if ((!userId && !data.password) || (data.password && data.password.length < 8)) { error.textContent = "密码至少 8 位"; error.hidden = false; return; }
  if (!data.email && !data.phone) { error.textContent = "邮箱和手机号至少填写一项"; error.hidden = false; return; }
  if (!data.password) delete data.password;
  const submit = event.submitter;
  try { await runButtonAction(submit, "正在保存…", async () => { await api(userId ? `/api/v1/admin/users/${userId}` : "/api/v1/admin/users", { method: userId ? "PATCH" : "POST", body: JSON.stringify(data) }); $("#user-dialog").close(); form.reset(); showToast(userId ? "账号已更新" : "账号创建成功"); await loadData(); }); }
  catch (failure) { error.textContent = failure.message; error.hidden = false; }
}

async function closeShare(button) {
  if (!await confirmAction("关闭分享码", "确定关闭这个分享码吗？关闭后将无法再次查询。", "确认关闭")) return;
  try { await runButtonAction(button, "关闭中…", async () => { await api(`/api/v1/admin/shares/${button.dataset.closeShare}`, { method: "DELETE" }); showToast("分享码已关闭"); await loadData(); }); }
  catch (failure) { showToast(failure.message); }
}

async function deleteQuote(button) {
  if (!await confirmAction("删除报价单", "确定永久删除这份报价单吗？", "确认删除")) return;
  try { await runButtonAction(button, "删除中…", async () => { await api(`/api/v1/quotes/${button.dataset.deleteQuote}`, { method: "DELETE" }); showToast("报价单已删除"); await loadData(); }); } catch (failure) { showToast(failure.message); }
}
async function exportQuote(quote) {
  if (!quote?.id) { showToast("报价已保存，但未取得报价编号，请在报价管理中重试导出"); return false; }
  try {
    const response = await fetch(`${API_BASE}/api/v1/quotes/${encodeURIComponent(quote.id)}/pdf`, { headers: { Authorization: `Bearer ${sessionStorage.getItem(TOKEN_KEY)}` } });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `PDF生成失败（${response.status}）`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `quote-${quote.id.slice(0, 8)}.pdf`;
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return true;
  } catch (error) {
    showToast(error.message);
    return false;
  }
}

function openQuoteEditor({ quoteId = null, configId, title, items, currency = "CNY", exportAfterSave = false }) {
  const normalizedItems = (items || []).map((item) => ({
    ...item,
    quantity: Math.max(1, Number(item.quantity || 1)),
    price: Math.max(0, Number(item.price || 0))
  }));
  const dialog = document.createElement("dialog");
  dialog.className = "product-dialog quote-editor-dialog";
  dialog.dataset.dynamic = "true";
  dialog.innerHTML = `<form method="dialog" class="dialog-card quote-editor-card">
    <header><div><span class="eyebrow">QUOTATION</span><h2>${quoteId ? "修改报价" : "创建报价"}</h2></div><button class="icon-button" value="cancel" aria-label="关闭">×</button></header>
    <div class="quote-editor-meta">
      <label class="quote-title-field"><span>配置名称</span><input name="title" value="${escapeHtml(title || "")}" required /></label>
      <div class="quote-currency-row"><label class="quote-currency-field"><span>报价货币</span><select name="currency" aria-label="报价货币"><option value="CNY" ${currency === "CNY" ? "selected" : ""}>CNY · 人民币</option><option value="USD" ${currency === "USD" ? "selected" : ""}>USD · 美元</option></select></label><button class="button button-secondary quote-auto-price" type="button">自动填价</button></div>
    </div>
    <div class="quote-edit-list">
      <div class="quote-edit-head"><span>产品 / 配置</span><span>数量</span><span>单价</span></div>
      ${normalizedItems.map((item, index) => `<div class="quote-edit-row"><div class="quote-item-name"><strong>${escapeHtml(item.name || "未命名项目")}</strong></div><input class="quote-qty-input" data-q="qty" data-i="${index}" aria-label="数量" type="number" min="1" step="1" value="${item.quantity}"><input class="quote-price-input" data-q="price" data-i="${index}" aria-label="单价" type="number" min="0" step="0.01" value="${item.price}"></div>`).join("")}
    </div>
    <div class="quote-total-row"><span>合计</span><strong class="quote-total">0</strong></div>
    <footer><button class="button button-quiet" value="cancel">取消</button><button class="button button-primary" value="default">${exportAfterSave ? "保存并导出 PDF" : "保存报价"}</button></footer>
  </form>`;
  document.body.appendChild(dialog);
  const totalElement = $(".quote-total", dialog);
  const updateTotal = () => {
    const total = normalizedItems.reduce((sum, _, index) => sum
      + Number($(`[data-q="price"][data-i="${index}"]`, dialog).value || 0)
      * Number($(`[data-q="qty"][data-i="${index}"]`, dialog).value || 1), 0);
    const selectedCurrency = $("[name=currency]", dialog).value;
    totalElement.textContent = `${selectedCurrency} ${total.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    return total;
  };
  dialog.addEventListener("input", updateTotal);
  dialog.addEventListener("change", updateTotal);
  $(".quote-auto-price", dialog).addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "读取中…";
    try {
      const prices = await api("/api/v1/staff/reference-prices");
      const selectedCurrency = $("[name=currency]", dialog).value;
      const normalizeCode = (value) => String(value || "").replace(/[^a-z0-9]/gi, "").toUpperCase();
      const productMap = new Map((prices.products || []).flatMap((product) => [[normalizeCode(product.id), product], [normalizeCode(product.name), product]]));
      const optionMap = new Map((prices.options || []).flatMap((option) => [[normalizeCode(option.id), option], [normalizeCode(option.code), option]]));
      let matched = 0;
      normalizedItems.forEach((item, index) => {
        const snapshotPrice = selectedCurrency === "USD" ? Number(item.price_usd || 0) : Number(item.price_cny || 0);
        const isSnapshotProduct = item.kind === "product" && (Object.prototype.hasOwnProperty.call(item, "price_cny") || Object.prototype.hasOwnProperty.call(item, "price_usd"));
        if (isSnapshotProduct) {
          $(`[data-q="price"][data-i="${index}"]`, dialog).value = snapshotPrice > 0 ? snapshotPrice : 0;
          if (snapshotPrice > 0) matched += 1;
          return;
        }
        const keys = [item.source_id, item.code, item.name].map(normalizeCode).filter(Boolean);
        let record = null;
        if (item.kind === "product") record = keys.map((key) => productMap.get(key)).find(Boolean);
        else if (item.kind === "option") record = keys.map((key) => optionMap.get(key)).find(Boolean);
        else record = keys.map((key) => optionMap.get(key) || productMap.get(key)).find(Boolean);
        if (!record) return;
        const price = selectedCurrency === "USD" ? Number(record.price_usd || 0) : Number(record.base_price ?? record.price ?? 0);
        if (price <= 0) return;
        $(`[data-q="price"][data-i="${index}"]`, dialog).value = price;
        matched += 1;
      });
      updateTotal();
      showToast(`已填 ${matched} 项，${normalizedItems.length - matched} 项未设置价格`);
    } catch (error) { showToast(error.message); }
    finally { button.disabled = false; button.textContent = originalText; }
  });
  $("form", dialog).addEventListener("submit", async (event) => {
    if (event.submitter?.value === "cancel") return;
    event.preventDefault();
    const total = updateTotal();
    const finalItems = normalizedItems.map((item, index) => ({
      ...item,
      quantity: Number($(`[data-q="qty"][data-i="${index}"]`, dialog).value || 1),
      price: Number($(`[data-q="price"][data-i="${index}"]`, dialog).value || 0)
    }));
    try { await runButtonAction(event.submitter, "正在保存…", async () => {
      const savedQuote = await api("/api/v1/quotes", { method: "POST", body: JSON.stringify({ quote_id: quoteId, config_id: configId, title: $("[name=title]", dialog).value.trim(), items: finalItems, total_price: total, currency: $("[name=currency]", dialog).value }) });
      const exported = exportAfterSave ? await exportQuote(savedQuote) : false;
      dialog.close(); dialog.remove();
      showToast(exportAfterSave && exported ? "报价单已保存并开始下载 PDF" : (quoteId ? "报价单已更新" : "报价单已保存"));
      await loadData();
    }); } catch (error) { showToast(error.message); }
  });
  updateTotal();
  dialog.showModal();
}

async function editQuote(quote) {
  openQuoteEditor({ quoteId: quote.id, configId: quote.config_id, title: quote.title, items: quote.items, currency: quote.currency || "CNY" });
}

function plainDescription(value) {
  return String(value || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function renderShareDetail(share) {
  const snapshot = share.snapshot;
  const categories = (snapshot.categories || []).map((category) => {
    const options = (category.options || []).map((option) => {
      const description = plainDescription(option.description);
      return `<li><strong>${escapeHtml(option.name)}</strong>${description ? `<span>${escapeHtml(description)}</span>` : ""}</li>`;
    }).join("");
    return `<section class="share-detail-group"><header><span>${escapeHtml(category.name)}</span><small>${category.options.length} 项</small></header><ul>${options}</ul></section>`;
  }).join("");
  const sender = share.sender_name || "未填写姓名";
  const contact = share.sender_email || share.sender_phone || "未填写联系方式";
  return `<header class="share-result-header"><div><span class="eyebrow">CONFIGURATION ${escapeHtml(share.code)}</span><h3>${escapeHtml(share.name)}</h3></div><span class="badge good">有效至 ${formatDate(share.expires_at)}</span></header><div class="share-device-summary"><div><span>发送用户</span><strong>${escapeHtml(sender)}</strong><small>${escapeHtml(contact)}</small></div><div><span>设备型号</span><strong>${escapeHtml(snapshot.product.name)}</strong></div><div><span>产品名称 / 外观</span><strong>${escapeHtml(snapshot.product.title_name)} · ${escapeHtml(snapshot.color.label || snapshot.color.code)}</strong></div></div><div class="share-detail-groups">${categories || '<div class="empty">该配置未选择其他选配项目</div>'}</div>`;
}

async function lookupShare(code) {
  const result = $("#share-result");
  if (!/^\d{6}$/.test(code)) { showToast("请输入6位数字分享码"); return; }
  result.hidden = false;
  result.innerHTML = '<div class="share-result-loading">正在读取配置…</div>';
  try {
    const share = await api(`/api/v1/shares/${code}`);
    result.innerHTML = renderShareDetail(share);
    result.scrollIntoView({ behavior: "smooth", block: "nearest" });
    await loadData();
  } catch (failure) {
    result.innerHTML = `<div class="share-result-error"><strong>无法读取该配置</strong><span>${escapeHtml(failure.message)}</span></div>`;
  }
}

async function searchShare(event) {
  event.preventDefault();
  await lookupShare($("#share-code").value.trim());
}

function clearShareResult() {
  const result = $("#share-result");
  result.hidden = true;
  result.innerHTML = "";
  $("#share-code").value = "";
}

async function exportSharePdf(code) {
  try {
    const response = await fetch(`${API_BASE}/api/v1/shares/${encodeURIComponent(code)}/pdf`, { headers: { Authorization: `Bearer ${sessionStorage.getItem(TOKEN_KEY)}` } });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `PDF生成失败（${response.status}）`);
    }
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = `shared-configuration-${code}.pdf`; link.style.display = "none"; document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (failure) { showToast(failure.message); }
}

async function quoteShare(code) {
  try {
    const share = await api(`/api/v1/shares/${code}`);
    const items = [{ kind: "product", source_id: share.snapshot.product.id, name: share.snapshot.product.name, code: share.snapshot.product.id, price: Number(share.snapshot.product.base_price || 0), price_cny: Number(share.snapshot.product.base_price || 0), price_usd: Number(share.snapshot.product.price_usd || 0), quantity: 1 }];
    (share.snapshot.categories || []).forEach((category) => (category.options || []).forEach((option) => items.push({ kind: "option", source_id: option.id, name: option.name, code: option.code, price: Number(option.price || 0), quantity: 1 })));
    openQuoteEditor({ configId: share.config_id, title: `分享配置 ${code}`, items, currency: "CNY", exportAfterSave: true });
  } catch (failure) { showToast(failure.message); }
}

async function logout() {
  try { await api("/api/v1/auth/logout", { method: "POST" }); } catch (_) {}
  sessionStorage.removeItem(TOKEN_KEY); state.user = null; $("#admin-app").hidden = true; $("#login-page").hidden = false;
}

function openSidebar() { $("#sidebar").classList.add("open"); $("#sidebar-backdrop").hidden = false; }
function closeSidebar() { $("#sidebar").classList.remove("open"); $("#sidebar-backdrop").hidden = true; }
function setCategoryCollapsed(group, collapsed) {
  if (!group) return;
  const table = $(".config-catalog-table", group);
  const button = $("[data-collapse-category]", group);
  group.classList.toggle("collapsed", collapsed);
  // Remove the large table from layout completely. Relying on a class alone
  // can leave a stale grid/scroll extent after collapsing long categories.
  if (table) table.hidden = collapsed;
  if (button?.classList.contains("catalog-collapse")) {
    button.textContent = collapsed ? "展开分类" : "折叠分类";
  }
  if (button) button.setAttribute("aria-expanded", String(!collapsed));
}

function restoreCollapsedCategories() {
  $$(".config-catalog-group").forEach((group, index) => {
    const id = state.configCatalog[index]?.id;
    setCategoryCollapsed(group, Boolean(id && state.collapsedCategories.has(id)));
  });
}

function bindEvents() {
  $("#login-form").addEventListener("submit", login);
  $("#logout-button").addEventListener("click", logout);
  $$(".nav-item").forEach((item) => item.addEventListener("click", () => switchView(item.dataset.view)));
  $$('[data-go]').forEach((item) => item.addEventListener("click", () => switchView(item.dataset.go)));
  if ($("#primary-action")) $("#primary-action").addEventListener("click", () => openUserEditor());
  $("#add-user-button").addEventListener("click", () => openUserEditor());
  $("#user-role-filter")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-user-role]");
    if (!button) return;
    state.userRoleFilter = button.dataset.userRole;
    $$("[data-user-role]", $("#user-role-filter")).forEach((item) => item.classList.toggle("active", item === button));
    renderUsers();
  });
  $("#user-form").addEventListener("submit", createUser);
  $("#user-form [name='phone_country']")?.addEventListener("change", updateAdminPhoneCallingCode);
  $("#product-form").addEventListener("submit", saveProduct);
  $("#config-option-form").addEventListener("submit", saveConfigOption);
  $("#delete-config-option").addEventListener("click", deleteCurrentConfigOption);
  $("#add-config-category").addEventListener("click", addConfigCategory);
  $$(".editor-tab").forEach((button) => button.addEventListener("click", () => switchEditorTab(button.dataset.editorTab)));
  $(".editor-tabs")?.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const tabs = $$(".editor-tab", event.currentTarget); const current = tabs.indexOf(document.activeElement); if (current < 0) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    switchEditorTab(tabs[next].dataset.editorTab); tabs[next].focus();
  });
  $("#mapping-search")?.addEventListener("input", (event) => { if (!state.mappingEditor) return; state.mappingEditor.query = event.target.value; renderMappingEditor(); });
  $(".mapping-filters")?.addEventListener("click", (event) => { const button = event.target.closest("[data-mapping-filter]"); if (!button || !state.mappingEditor) return; state.mappingEditor.filter = button.dataset.mappingFilter; renderMappingEditor(); });
  $("#mapping-expand-all")?.addEventListener("click", () => { const editor = state.mappingEditor; if (!editor) return; editor.collapsed = editor.collapsed?.size ? new Set() : new Set(editor.categories.map((category) => category.id)); renderMappingEditor(); });
  $("#add-color-button").addEventListener("click", () => {
    $("#color-editor-list").insertAdjacentHTML("beforeend", colorEditorRow());
    const activeLanguage = $(".lang-toggle.active", $("#product-dialog"))?.dataset.lang || "zh";
    $$("[data-color-name-lang]", $("#color-editor-list").lastElementChild).forEach((label) => { label.hidden = label.dataset.colorNameLang !== activeLanguage; });
  });
  $("#code-search").addEventListener("submit", searchShare);
  $("#clear-share-result").addEventListener("click", clearShareResult);
  $("#refresh-audit")?.addEventListener("click", loadData);
  addLanguageToggles(); addProductButton(); addCatalogLanguageSwitches();
  $("#menu-button").addEventListener("click", openSidebar);
  $("#sidebar-backdrop").addEventListener("click", closeSidebar);
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".catalog-more")) document.querySelectorAll(".catalog-more[open]").forEach((menu) => { menu.removeAttribute("open"); });
    const imageButton = event.target.closest("[data-pick-image]"); if (imageButton) { imageButton.closest(".image-path-control, .color-image-control")?.querySelector("[data-image-file]")?.click(); return; }
    const cancelButton = event.target.closest('button[value="cancel"]'); if (cancelButton) { const dialog = cancelButton.closest("dialog"); if (dialog) { event.preventDefault(); dialog.close(); if (dialog.dataset.dynamic === "true") dialog.remove(); return; } }
    const userButton = event.target.closest("[data-user-status]"); if (userButton) setUserStatus(userButton);
    const editUserButton = event.target.closest("[data-edit-user]"); if (editUserButton) editUser(JSON.parse(editUserButton.dataset.editUser));
    const shareButton = event.target.closest("[data-close-share]"); if (shareButton) closeShare(shareButton);
    const quoteButton = event.target.closest("[data-delete-quote]"); if (quoteButton) deleteQuote(quoteButton);
    const exportQuoteButton = event.target.closest("[data-export-quote]"); if (exportQuoteButton) { const quote = state.quotes.find((item) => item.id === exportQuoteButton.dataset.exportQuote); if (quote) exportQuote(quote); }
    const editQuoteButton = event.target.closest("[data-edit-quote]"); if (editQuoteButton) { const quote = state.quotes.find((item) => item.id === editQuoteButton.dataset.editQuote); if (quote) editQuote(quote); }
    const lookupButton = event.target.closest("[data-lookup-share]");
    if (lookupButton) { $("#share-code").value = lookupButton.dataset.lookupShare; lookupShare(lookupButton.dataset.lookupShare); }
    const exportButton = event.target.closest("[data-export-share]"); if (exportButton) exportSharePdf(exportButton.dataset.exportShare);
    const quoteActionButton = event.target.closest("[data-quote-share]"); if (quoteActionButton) quoteShare(quoteActionButton.dataset.quoteShare);
    const productButton = event.target.closest("[data-edit-product]"); if (productButton) openProductEditor(productButton.dataset.editProduct);
    const mappingNoteButton = event.target.closest("[data-edit-mapping-note]"); if (mappingNoteButton) openMappingNoteEditor(mappingNoteButton.dataset.editMappingNote);
    const mappingGroupButton = event.target.closest("[data-mapping-category]");
    if (mappingGroupButton && state.mappingEditor) { const id = mappingGroupButton.dataset.mappingCategory; if (state.mappingEditor.collapsed.has(id)) state.mappingEditor.collapsed.delete(id); else state.mappingEditor.collapsed.add(id); renderMappingEditor(); }
    const optionButton = event.target.closest("[data-edit-option]"); if (optionButton) openConfigOptionEditor(JSON.parse(optionButton.dataset.editOption));
    const addOptionButton = event.target.closest("[data-add-option]"); if (addOptionButton) { addOptionButton.closest(".catalog-more")?.removeAttribute("open"); addConfigOption(addOptionButton.dataset.addOption); }
    const categoryButton = event.target.closest("[data-edit-category]"); if (categoryButton) { categoryButton.closest(".catalog-more")?.removeAttribute("open"); editConfigCategory(JSON.parse(categoryButton.dataset.editCategory)); }
    const collapseButton = event.target.closest("[data-collapse-category]");
    if (collapseButton) {
      const group = collapseButton.closest(".config-catalog-group");
      const collapsed = !group.classList.contains("collapsed");
      const id = collapseButton.dataset.collapseCategory;
      setCategoryCollapsed(group, collapsed);
      if (collapsed) state.collapsedCategories.add(id);
      else state.collapsedCategories.delete(id);
      localStorage.setItem("boten-admin-collapsed-categories", JSON.stringify(Array.from(state.collapsedCategories)));
    }
    const languageButton = event.target.closest(".lang-toggle"); if (languageButton) toggleDialogLanguage(languageButton);
    const catalogLanguageButton = event.target.closest("[data-catalog-lang]"); if (catalogLanguageButton) localStorage.setItem("boten-admin-language", catalogLanguageButton.dataset.catalogLang);
    const colorButton = event.target.closest("[data-remove-color]");
    if (colorButton) {
      const rows = $$(".color-editor-row", $("#color-editor-list"));
      if (rows.length <= 1) { showToast("每台设备至少保留一种外观颜色"); return; }
      const row = colorButton.closest(".color-editor-row");
      const wasDefault = $('[data-color-field="is_default"]', row).checked;
      row.remove();
      if (wasDefault) $('[data-color-field="is_default"]', $("#color-editor-list")).checked = true;
    }
  });
  document.addEventListener("keydown", (event) => {
    const target = event.target.closest?.("[data-collapse-category]");
    if (target && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); target.click(); }
  });
  document.addEventListener("change", (event) => {
    const mappingCheckbox = event.target.closest('#mapping-editor input[type="checkbox"]');
    if (mappingCheckbox && state.mappingEditor) {
      if (mappingCheckbox.checked) state.mappingEditor.selected.add(mappingCheckbox.value);
      else state.mappingEditor.selected.delete(mappingCheckbox.value);
      renderMappingEditor();
      return;
    }
    const fileInput = event.target.closest("[data-image-file]");
    if (fileInput) uploadCatalogImage(fileInput.files?.[0], fileInput.closest(".image-path-control, .color-image-control"));
  });
  window.addEventListener("hashchange", () => { if (!$("#admin-app")?.hidden) switchView(window.location.hash.slice(1) || "dashboard", false); });
}

// Unified catalog editor cards.
function editorFieldControl(field) {
  if (field.name === "image_path") {
    return `<div class="image-path-control"><input name="image_path" value="${escapeHtml(field.value || "")}" placeholder="${escapeHtml(field.placeholder || "上传图片或填写现有路径")}"><button class="button button-secondary" type="button" data-pick-image>上传</button><input type="file" accept="image/png,image/jpeg,image/webp" data-image-file hidden></div>`;
  }
  if (field.type === "textarea") return `<textarea name="${field.name}" rows="3" placeholder="${escapeHtml(field.placeholder || "")}">${escapeHtml(field.value || "")}</textarea>`;
  return `<input name="${field.name}" type="${field.type || "text"}" value="${escapeHtml(field.value || "")}" placeholder="${escapeHtml(field.placeholder || "")}" ${field.required ? "required" : ""}>`;
}

function catalogEditorCard({ title, fields, onSave, onDelete = null, size = "medium" }) {
  const dialog = document.createElement("dialog"); dialog.className = `catalog-editor-dialog catalog-editor-dialog--${size}`;
  const titleId = `catalog-editor-title-${Date.now()}`;
  dialog.setAttribute("aria-labelledby", titleId);
  dialog.innerHTML = `<form method="dialog" class="dialog-card catalog-editor-card"><header><div><span class="eyebrow">CATALOG EDITOR</span><h2 id="${titleId}">${escapeHtml(title)}</h2></div><div class="dialog-actions"><div class="catalog-language dialog-language" role="group" aria-label="编辑语言"><button type="button" class="lang-toggle active" data-lang="zh" aria-pressed="true">中文</button><button type="button" class="lang-toggle" data-lang="en" aria-pressed="false">EN</button></div><button class="icon-button" value="cancel" aria-label="关闭">×</button></div></header><div class="catalog-editor-body"><div class="form-grid">${fields.map(f => `<label data-card-lang="${f.lang || "all"}"><span>${escapeHtml(f.label)}</span>${editorFieldControl(f)}</label>`).join("")}</div></div><footer>${onDelete ? '<button class="button button-danger" type="button" data-delete-card>删除</button>' : ""}<button class="button button-quiet" value="cancel">取消</button><button class="button button-primary" value="default">保存</button></footer></form>`;
  document.body.appendChild(dialog); const form = dialog.querySelector("form");
  const opener = document.activeElement;
  dialog.addEventListener("close", () => opener?.focus(), { once: true });
  const setLang = lang => { dialog.querySelectorAll("[data-card-lang]").forEach(row => row.hidden = !(["all", lang].includes(row.dataset.cardLang))); dialog.querySelectorAll(".lang-toggle").forEach(b => { const active = b.dataset.lang === lang; b.classList.toggle("active", active); b.setAttribute("aria-pressed", String(active)); }); };
  dialog.querySelectorAll(".lang-toggle").forEach(b => b.addEventListener("click", () => setLang(b.dataset.lang))); setLang(state.catalogLanguage || "zh");
  dialog.querySelector("[data-delete-card]")?.addEventListener("click", async event => { try { await runButtonAction(event.currentTarget, "删除中…", async () => { if (await onDelete()) { dialog.close(); dialog.remove(); await loadData(); } }); } catch (error) { showToast(error.message); } });
  form.addEventListener("submit", async event => { event.preventDefault(); if (event.submitter?.value === "cancel") { dialog.close(); dialog.remove(); return; } const data = Object.fromEntries(new FormData(form)); const missing = fields.find(field => field.required && !String(data[field.name] || "").trim()); if (missing) { showToast(`请填写${missing.label}`); form.querySelector(`[name="${missing.name}"]`)?.focus(); return; } try { await runButtonAction(event.submitter, "正在保存…", async () => { await onSave(data); dialog.close(); dialog.remove(); await loadData(); }); } catch (error) { showToast(error.message); } }); dialog.showModal(); dialog.querySelector("input, textarea, select")?.focus();
}

function categoryCard(category = null) { catalogEditorCard({ title: category ? "编辑配置分类" : "添加配置分类", size:"small", fields: [{name:"name",label:"分类标题",lang:"zh",value:category?.name,placeholder:"例如：CRI 共轨套件",required:true},{name:"description",label:"分类描述",lang:"zh",type:"textarea",value:category?.description,placeholder:"例如：适用于共轨喷油器测试"},{name:"name_en",label:"分类标题",lang:"en",value:category?.name_en,placeholder:"例如：CRI Common Rail Kits"},{name:"description_en",label:"分类描述",lang:"en",type:"textarea",value:category?.description_en,placeholder:"例如：Kits for common rail injector testing"}], onSave: data => api(category ? `/api/v1/admin/config-catalog/categories/${category.id}` : "/api/v1/admin/config-catalog/categories", {method:category?"PATCH":"POST",body:JSON.stringify({...data,multiple:true})}), onDelete: category ? () => deleteConfigCategory(category) : null }); }

async function addConfigOption(categoryId) { catalogEditorCard({ title:"添加配置", size:"medium", fields:[{name:"code",label:"配置编号",lang:"all",placeholder:"例如：BTK-1019",required:true},{name:"name",label:"配置名称",lang:"zh",placeholder:"例如：共轨喷油器测试套件",required:true},{name:"description",label:"配置描述",lang:"zh",type:"textarea",placeholder:"例如：适用于 Bosch CRIN4.2"},{name:"name_en",label:"配置名称",lang:"en",placeholder:"例如：Injector Test Kit"},{name:"description_en",label:"配置描述",lang:"en",type:"textarea",placeholder:"例如：For Bosch CRIN4.2"},{name:"image_path",label:"配置图片",lang:"all",placeholder:"上传图片或填写现有路径"},{name:"price",label:"人民币单价",lang:"all",type:"number",placeholder:"例如：1500"},{name:"price_usd",label:"美元单价",lang:"all",type:"number",placeholder:"例如：210"}], onSave:data=>api("/api/v1/admin/config-catalog/options",{method:"POST",body:JSON.stringify({...data,category_id:categoryId,price:Number(data.price||0),price_usd:Number(data.price_usd||0),enabled:true})}) }); }

// Unified bilingual add-device editor.
function addProductButton() {
  const panel = $("#product-catalog-actions");
  if (!panel || $("#add-product-button")) return;
  const button = document.createElement("button");
  button.id = "add-product-button"; button.className = "button button-secondary"; button.textContent = "添加设备";
  button.addEventListener("click", () => catalogEditorCard({ title:"添加设备", size:"large", fields:[
    {name:"id",label:"设备编号",lang:"all",placeholder:"例如：CR999",required:true},
    {name:"name",label:"设备名称",lang:"zh",placeholder:"例如：BOTEN CR999",required:true},
    {name:"title_name",label:"产品标题",lang:"zh",placeholder:"例如：共轨喷油器试验台",required:true},
    {name:"description",label:"设备概况",lang:"zh",type:"textarea",placeholder:"例如：适用于共轨喷油器测试"},
    {name:"name_en",label:"设备名称",lang:"en",placeholder:"例如：BOTEN CR999"},
    {name:"title_name_en",label:"产品标题",lang:"en",placeholder:"例如：Common Rail Test Bench"},
    {name:"description_en",label:"设备概况",lang:"en",type:"textarea",placeholder:"例如：Designed for common rail testing"},
    {name:"base_price",label:"人民币单价",lang:"all",type:"number",placeholder:"例如：158000"},
    {name:"price_usd",label:"美元单价",lang:"all",type:"number",placeholder:"例如：22000"}
  ], onSave:data => api("/api/v1/admin/products",{method:"POST",body:JSON.stringify({...data,base_price:Number(data.base_price||0),price_usd:Number(data.price_usd||0)})}) }));
  panel.appendChild(button);
}

async function saveConfigOption(event) {
  event.preventDefault(); const form=event.currentTarget; if(event.submitter?.value==="cancel"){form.closest("dialog")?.close();return;}
  const payload={code:form.elements.code.value.trim(),name:form.elements.name.value.trim(),name_en:form.elements.name_en.value.trim(),image_path:form.elements.image_path.value.trim()||null,description:form.elements.description.value.trim(),description_en:form.elements.description_en.value.trim(),notes:form.elements.notes.value.trim(),price:Number(form.elements.price.value||0),price_usd:Number(form.elements.price_usd?.value||0),enabled:form.elements.enabled.checked};
  try{await runButtonAction(event.submitter,"正在保存…",async()=>{await api(`/api/v1/admin/config-catalog/options/${form.elements.option_id.value}`,{method:"PATCH",body:JSON.stringify(payload)});$("#config-option-dialog").close();showToast("配置条目已保存");await loadData();});}catch(failure){const error=$("#config-option-error");error.textContent=failure.message;error.hidden=false;}
}

document.addEventListener("DOMContentLoaded", async () => {
  bindEvents(); await checkApi(); await restoreSession();
});
document.addEventListener("click", (event) => {
  if (event.target.closest("[data-catalog-lang]")) setTimeout(renderProducts, 0);
});
