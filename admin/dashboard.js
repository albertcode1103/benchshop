/* Independent dashboard snapshot. List filters never mutate these records. */
const dashboardState = { data: null, days: 30, work: "drafts", recent: "inquiries", loading: false, error: "", request: 0, owner: null };

function dashboardDate(value, dateOnly = false) {
  if (!value) return "—";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const text = String(value).replace(" ", "T");
  const date = new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(text) ? text : text + "Z");
  if (!Number.isFinite(date.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit", ...(!dateOnly ? { hour: "2-digit", minute: "2-digit" } : {}) }).format(date);
}

function resetDashboard() {
  dashboardState.request += 1;
  Object.assign(dashboardState, { data: null, loading: false, error: "", owner: null });
  renderDashboard();
}

async function loadDashboard() {
  if (!state.user || !["admin", "sales"].includes(state.user.role)) return;
  const owner = `${state.user.id}:${state.user.role}`;
  if (dashboardState.owner !== owner) { resetDashboard(); dashboardState.owner = owner; }
  const request = ++dashboardState.request;
  dashboardState.loading = true;
  dashboardState.error = "";
  renderDashboard();
  try {
    const data = await api(`/api/v1/staff/dashboard?days=${dashboardState.days}`);
    if (request !== dashboardState.request) return;
    if (!data.counts || !data.tasks || !data.trend?.dates || !data.recent || !data.catalog || !data.scopes || !data.shares) throw new Error("当前 API 尚不支持新版仪表盘，请先发布兼容的 API。");
    dashboardState.data = data;
  } catch (failure) {
    if (request !== dashboardState.request) return;
    if (failure.status === 401) { logout(); return; }
    dashboardState.error = failure.status === 404 ? "当前 API 尚不支持新版仪表盘，请先发布兼容的 API。其他工作台功能仍可使用。" : failure.message;
  } finally {
    if (request === dashboardState.request) { dashboardState.loading = false; renderDashboard(); }
  }
}

function dashboardRows(items, kind) {
  return items.map(item => {
    let title, detail, status, badge, action;
    if (kind === "inquiries") {
      title = item.inquiry_number;
      status = ({ new: "新询价", assigned: "已分配", contacted: "已联系", pending: "待报价", sent: "已报价", archived: "报价已归档", closed: "已完成", cancelled: "客户已取消" })[item.business_status || item.status] || "—";
      detail = `${item.customer_name || "未填写客户"} · 负责人：${item.assignee_name || "未分配"}`;
      detail += ` · 更新 ${dashboardDate(item.updated_at)}`;
      badge = ["closed", "cancelled", "archived"].includes(item.business_status) ? "off" : item.business_status === "sent" ? "good" : "warn";
      action = `data-dashboard-inquiry="${escapeHtml(item.id)}"`;
    } else if (kind === "quotes") {
      title = item.quote_number || item.title || "未编号报价";
      status = quoteLifecycleLabel(item.lifecycle_status);
      detail = `${item.customer_name || "未填写客户"} · 有效期：${item.valid_until ? dashboardDate(item.valid_until) : "未设置"} · 更新 ${dashboardDate(item.updated_at)}`;
      badge = item.lifecycle_status === "sent" ? "good" : item.lifecycle_status === "archived" ? "off" : "warn";
      action = `data-dashboard-quote="${escapeHtml(item.id)}"`;
    } else {
      title = item.code;
      status = ({ active: "有效", closed: "已关闭", expired: "已过期" })[item.status] || "—";
      detail = `${item.name || "未命名分享"} · 创建 ${dashboardDate(item.created_at)}`;
      badge = item.status === "active" ? "good" : "off";
      action = `data-dashboard-share="${escapeHtml(item.code)}"`;
    }
    return `<div class="mini-row dashboard-row"><div><button class="dashboard-record" type="button" ${action}>${escapeHtml(title)}</button><span>${escapeHtml(detail)}</span></div><span class="badge ${badge}">${escapeHtml(status)}</span></div>`;
  }).join("") || '<div class="empty">暂无记录</div>';
}

function renderDashboardChart(data) {
  const { trend, scopes } = data;
  const labels = { inquiries: scopes.inquiries, quotes: scopes.quotes, shares: scopes.shares };
  const series = Object.keys(labels);
  $("#dashboard-trend-totals").innerHTML = series.map(key => `<div class="dashboard-trend-total ${key}"><span>${escapeHtml(labels[key])}</span><strong>${trend[key].reduce((sum, value) => sum + value, 0)}</strong><small>近${data.days}天新增</small></div>`).join("");
  const max = Math.max(1, ...series.flatMap(key => trend[key]));
  const width = Math.max(240, Math.min(1000, $("#dashboard-chart").clientWidth || 800));
  const right = width - 12;
  const x = index => 44 + index * (right - 44) / Math.max(1, trend.dates.length - 1);
  const y = value => 176 - value / max * 148;
  const lines = series.map(key => `<polyline class="dashboard-line ${key}" points="${trend[key].map((value, index) => `${x(index)},${y(value)}`).join(" ")}" />`).join("");
  const hits = trend.dates.map((date, index) => `<rect data-dashboard-day="${index}" x="${x(index) - 8}" y="20" width="16" height="164" fill="transparent"><title>${date}：${series.map(key => `${labels[key]} ${trend[key][index]}`).join("，")}</title></rect>`).join("");
  $("#dashboard-chart").innerHTML = `<svg viewBox="0 0 ${width} 218" role="img" aria-label="最近${data.days}天业务新增趋势，使用下方日期选择器查看每日数值"><path class="dashboard-chart-grid" d="M44 28H${right} M44 102H${right} M44 176H${right}"/><text x="8" y="32">${max}</text><text x="24" y="180">0</text>${lines}${hits}<text x="44" y="208">${trend.dates[0]}</text><text x="${right}" y="208" text-anchor="end">${trend.dates.at(-1)}</text></svg>`;
  const select = $("#dashboard-trend-date");
  const selected = select.value;
  select.innerHTML = trend.dates.map(date => `<option value="${date}">${date}</option>`).join("");
  select.value = trend.dates.includes(selected) ? selected : trend.dates.at(-1);
  renderDashboardDay();
}

function renderDashboardDay() {
  const data = dashboardState.data;
  if (!data) return;
  const index = data.trend.dates.indexOf($("#dashboard-trend-date").value);
  if (index < 0) return;
  $("#dashboard-trend-detail").textContent = ["inquiries", "quotes", "shares"].map(key => `${data.scopes[key]} ${data.trend[key][index]} 份`).join(" · ");
}

function renderDashboard() {
  const body = $("#dashboard-body");
  if (!body) return;
  const { data, loading, error } = dashboardState;
  body.hidden = !data;
  body.setAttribute("aria-busy", String(loading));
  $("#dashboard-refresh").disabled = loading;
  $("#dashboard-refresh").textContent = loading ? "正在刷新…" : "刷新";
  const message = $("#dashboard-message");
  message.hidden = !!data && !loading && !error;
  message.classList.toggle("error", !!error);
  message.textContent = error ? `${data ? "更新失败，以下保留上次数据。" : "加载失败。"}${error}` : loading ? (data ? "正在更新，以下为上次数据…" : "正在加载仪表盘…") : "仪表盘尚未加载";
  if (!data) { $("#dashboard-admin").hidden = true; $("#dashboard-updated").textContent = ""; return; }
  $("#dashboard-scope").textContent = state.user.role === "admin" ? "管理员 · 全局业务与管理概况" : "业务员 · 公共询价与分享，我的待办与报价";
  $("#dashboard-updated").textContent = `更新于 ${dashboardDate(data.generated_at)} · 北京时间`;
  $$('[data-dashboard-count]').forEach(el => { el.textContent = data.counts[el.dataset.dashboardCount]; el.closest("button").classList.toggle("has-reminder", ["stale", "due"].includes(el.dataset.dashboardCount) && data.counts[el.dataset.dashboardCount] > 0); });
  $$('[data-dashboard-task-scope]').forEach(el => { el.textContent = data.scopes.tasks; });
  $$('[data-dashboard-quote-scope]').forEach(el => { el.textContent = data.scopes.quotes; });
  $("#dashboard-inquiries").innerHTML = dashboardRows(data.tasks.inquiries, "inquiries");
  $("#dashboard-work-quotes").innerHTML = dashboardRows(data.tasks[dashboardState.work], "quotes");
  $("#dashboard-recent").innerHTML = dashboardRows(data.recent[dashboardState.recent], dashboardState.recent);
  ["work", "recent", "days"].forEach(group => $$(`[data-dashboard-${group}]`).forEach(button => { button.setAttribute("aria-pressed", String(button.dataset[`dashboard${group[0].toUpperCase() + group.slice(1)}`] === String(group === "days" ? data.days : dashboardState[group]))); if (group === "days") button.disabled = loading; }));
  renderDashboardChart(data);
  $("#dashboard-catalog").innerHTML = data.catalog.map(item => `<button class="dashboard-catalog-item" type="button" data-go="${escapeHtml(item.view)}"><span>${escapeHtml(item.label)}目录</span><strong>${item.enabled}<small> / ${item.total}</small></strong><span>启用 / 全部 →</span></button>`).join("");
  $("#dashboard-active-shares").textContent = data.shares.active;
  $("#dashboard-share-views").textContent = data.shares.views;
  const management = state.user.role === "admin" ? data.admin : null;
  $("#dashboard-admin").hidden = !management;
  if (management) {
    $("#dashboard-accounts").innerHTML = `<button class="text-button" type="button" data-dashboard-users="customer">客户 <strong>${management.customers}</strong></button><span>员工 <strong>${management.staff}</strong></span><button class="text-button" type="button" data-go="users">管理账号</button><span>不含游客与已归档账号</span>`;
    $("#dashboard-audits").innerHTML = management.audits.map(item => `<div class="mini-row dashboard-row"><div><strong>${escapeHtml(item.actor)} · ${escapeHtml(item.action)}</strong><span>${escapeHtml(item.entity_type)} · ${escapeHtml(item.entity_id || "—")}</span></div><time>${escapeHtml(dashboardDate(item.created_at))}</time></div>`).join("") || '<div class="empty">暂无操作记录</div>';
  }
}

async function dashboardNavigate(view, queue = "all") {
  if (view === "inquiries") {
    Object.assign(state, { inquiryQuery: "", inquiryStatus: "all", inquiryQueue: queue, inquiryPage: 1 });
    $("#inquiry-filter-form").reset(); $("#inquiry-queue-filter").value = queue;
  } else if (view === "quotes") {
    Object.assign(state, { quoteQuery: "", quoteStatus: queue === "drafts" ? "draft" : queue === "due" ? "sent" : "all", quoteDue: queue === "due" });
    $("#quote-filter-form").reset(); $("#quote-status-filter").value = state.quoteStatus; $("#quote-due-filter").value = state.quoteDue ? "due" : "all";
  } else if (view === "shares") {
    Object.assign(state, { shareQuery: "", shareStatus: queue, shareProduct: "", shareCreatedFrom: "", shareCreatedTo: "", sharePage: 1 });
    $("#share-filter-form").reset(); $("#share-status-filter").value = queue;
  }
  syncBusinessFilterUrl();
  switchView(view);
  // Clear previous rows while loading so stale results are never mistaken for a queue.
  const target = $(`#${view}-table`);
  if (target) target.innerHTML = '<tr><td colspan="8" class="empty">正在加载…</td></tr>';
  try { await ({ inquiries: loadInquiries, quotes: loadQuotes, shares: loadShares })[view](); }
  catch (failure) { if (target) target.innerHTML = `<tr><td colspan="8" class="empty">加载失败：${escapeHtml(failure.message)}。请点击筛选重试。</td></tr>`; showToast(failure.message, "error"); }
}

function bindDashboardEvents() {
  $("#dashboard-refresh").addEventListener("click", () => void loadDashboard());
  $("#dashboard-trend-date").addEventListener("change", renderDashboardDay);
  $("#dashboard-quotes-all").addEventListener("click", () => void dashboardNavigate("quotes", dashboardState.work));
  $("#dashboard-recent-all").addEventListener("click", () => void dashboardNavigate(dashboardState.recent));
  $("#inquiry-queue-filter").addEventListener("change", () => { state.inquiryQueue = $("#inquiry-queue-filter").value; state.inquiryStatus = "all"; $("#inquiry-status-filter").value = "all"; state.inquiryPage = 1; void loadInquiries().catch(e => showToast(e.message, "error")); });
  $("#quote-due-filter").addEventListener("change", () => { state.quoteDue = $("#quote-due-filter").value === "due"; state.quoteStatus = state.quoteDue ? "sent" : "all"; $("#quote-status-filter").value = state.quoteStatus; void loadQuotes().catch(e => showToast(e.message, "error")); });
  let resizeFrame;
  window.addEventListener("resize", () => { cancelAnimationFrame(resizeFrame); resizeFrame = requestAnimationFrame(() => { if (dashboardState.data && $(".view.active")?.dataset.viewPanel === "dashboard") renderDashboardChart(dashboardState.data); }); });
  let refreshTimer;
  document.addEventListener("business-data-changed", () => {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => { if ($(".view.active")?.dataset.viewPanel === "dashboard" && state.user) void loadDashboard(); }, 150);
  });
  $("[data-view-panel=dashboard]").addEventListener("click", async event => {
    const button = event.target.closest("button, [data-dashboard-day]");
    if (!button) return;
    const action = button.dataset;
    try {
      if (action.dashboardQueue) return void dashboardNavigate(["followup", "stale"].includes(action.dashboardQueue) ? "inquiries" : "quotes", action.dashboardQueue);
      if (action.dashboardShares) return void dashboardNavigate("shares", action.dashboardShares);
      if (action.dashboardWork) { dashboardState.work = action.dashboardWork; renderDashboard(); }
      if (action.dashboardRecent) { dashboardState.recent = action.dashboardRecent; renderDashboard(); }
      if (action.dashboardDays) { dashboardState.days = Number(action.dashboardDays); return void loadDashboard(); }
      if (action.dashboardDay !== undefined) { $("#dashboard-trend-date").value = dashboardState.data.trend.dates[Number(action.dashboardDay)]; renderDashboardDay(); }
      if (action.dashboardInquiry) await viewInquiry(action.dashboardInquiry);
      if (action.dashboardShare) {
        const share = dashboardState.data.recent.shares.find(item => item.code === action.dashboardShare);
        if (share && share.status !== "active") {
          const label = share.status === "closed" ? "已关闭" : "已过期";
          setShareDrawerContent("", `<div class="share-result-error"><strong>${escapeHtml(share.code)} · ${label}</strong><span>${escapeHtml(share.name || "未命名分享")}</span><span>创建时间：${escapeHtml(dashboardDate(share.created_at))}</span><span>到期时间：${escapeHtml(dashboardDate(share.expires_at))}</span><span>此分享当前不可预览配置、导出或报价。</span></div>`);
          openShareDrawer();
        } else await lookupShare(action.dashboardShare);
      }
      if (action.dashboardQuote) {
        const quote = await api(`/api/v1/quotes/${encodeURIComponent(action.dashboardQuote)}`);
        if (quote.lifecycle_status === "archived") await viewQuoteHistory(quote.id);
        else await editQuote(quote);
      }
      if (action.dashboardUsers) {
        Object.assign(state, { userQuery: "", userRoleFilter: action.dashboardUsers === "customer" ? "customer" : "all", userStatusFilter: "all", userArchivedFilter: false, userPage: 1 });
        syncUserFilterUrl(); restoreUserFilterState(); switchView("users"); await loadUsers();
      }
    } catch (failure) { showToast(failure.message, "error"); }
  });
}
