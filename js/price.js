function getColorLabel(color, model = null) {
  if (model?.colorNames?.[color]) return model.colorNames[color];
  return color;
}

function getSpecLabel(categoryId, name) {
  // Option names are already localized by the catalog API.
  return name;
}

function buildSummaryGroups(model, snapshot) {
  const groups = [];

  // 颜色
  groups.push({
    type: "single",
    category: localStorage.getItem("boten-language") === "en" ? "Appearance" : "外观颜色",
    value: getColorLabel(snapshot.currentColor, model)
  });

  model.categories.forEach((cat) => {
    const selected = snapshot.selections[cat.id];
    if (!selected || (Array.isArray(selected) && selected.length === 0)) return;

    if (cat.multiple) {
      const items = selected
        .map((optId) => cat.options.find((o) => o.id === optId))
        .filter(Boolean)
        .map((opt) => {
          if (cat.id !== "cri" || !opt.description) return opt.name;
          const description = opt.description
            .replace(/<[^>]*>/g, " ")
            .replace(/\s+/g, " ")
            .trim();
          return `${opt.name} | ${description}`;
        });

      if (items.length > 0) {
        groups.push({
          type: "multi",
          category: cat.name,
          value: items,
          count: items.length
        });
      }
    } else {
      const option = cat.options.find((o) => o.id === selected);
      if (option) {
        groups.push({
          type: "single",
          category: cat.name,
          value: getSpecLabel(cat.id, option.name)
        });
      }
    }
  });

  return groups;
}

function initSalesContact() {
  const openButton = document.getElementById("sales-contact-open");
  const dialog = document.getElementById("sales-contact-dialog");
  const closeButton = document.getElementById("sales-contact-close");
  const doneButton = document.getElementById("sales-contact-done");
  if (!openButton || !dialog || !closeButton || !doneButton) return;

  const contact = window.BOTEN_SALES_CONTACT || {};
  const email = document.getElementById("sales-contact-email");
  const whatsapp = document.getElementById("sales-contact-whatsapp");
  if (email) {
    email.textContent = contact.email || "--";
    email.href = `mailto:${contact.email || ""}`;
  }
  if (whatsapp) {
    whatsapp.href = contact.whatsappHref || "#";
  }

  const closeDialog = () => {
    if (dialog.open) dialog.close();
  };
  openButton.addEventListener("click", () => {
    if (typeof window.openCurrentInquiryDialog === "function") {
      window.openCurrentInquiryDialog();
      return;
    }
    dialog.showModal();
  });
  closeButton.addEventListener("click", closeDialog);
  doneButton.addEventListener("click", closeDialog);
  dialog.addEventListener("close", () => openButton.focus());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) closeDialog();
  });
}
