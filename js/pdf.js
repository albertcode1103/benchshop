function initReset() {
  const resetBtn = document.getElementById("reset-config");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      state.reset();
    });
  }
}
