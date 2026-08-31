function initPDF() {
  const exportPrint = document.getElementById("export-print");
  if (exportPrint) {
    exportPrint.addEventListener("click", () => {
      window.print();
    });
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
