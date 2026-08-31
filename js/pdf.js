function initPDF() {
  const exportPrint = document.getElementById("export-print");
  if (exportPrint) {
    exportPrint.addEventListener("click", exportCurrentConfigurationPdf);
  }
}

async function exportCurrentConfigurationPdf() {
  const button = document.getElementById("export-print");
  const original = button?.textContent;
  const english = localStorage.getItem("boten-language") === "en";
  if (button) { button.disabled = true; button.textContent = english ? "Generating…" : "生成中…"; }
  try {
    const snapshot = state.getSnapshot();
    const model = configData.models.find((item) => item.id === snapshot.currentModelId);
    let token = sessionStorage.getItem(USER_TOKEN_KEY);
    // Visitors may browse before opening the account dialog. Create their
    // short-lived guest session only when a server-side PDF is requested.
    if (!token) {
      const guest = await authRequest("/auth/guest", { method: "POST" });
      token = guest.session.token;
      sessionStorage.setItem(USER_TOKEN_KEY, token);
      currentUser = guest.user;
      notifyAuth();
    }
    if (!token) throw new Error(english ? "Please wait for session initialization" : "请等待会话初始化");
    const response = await fetch(`${CATALOG_API_BASE}/api/v1/configs/pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name: english ? "Configuration List" : "设备配置清单", product_id: snapshot.currentModelId, color: snapshot.currentColor, selections: snapshot.selections, lang: english ? "en" : "zh" })
    });
    if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || `PDF (${response.status})`); }
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = `${model?.name || "BOTEN"}-configuration.pdf`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    alert(`${english ? "PDF export failed" : "PDF 导出失败"}: ${error.message}`);
  } finally {
    if (button) { button.disabled = false; button.textContent = original; }
  }
}

function initReset() {
  const resetBtn = document.getElementById("reset-config");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      state.reset();
    });
  }
}
