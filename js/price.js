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

function pricePreviewText(key, zh, en) {
  return window.botenI18n?.t(key) || (localStorage.getItem("boten-language") === "en" ? en : zh);
}

function initPricePreview() {
  const title = document.getElementById("pricing-preview-title");
  const message = document.getElementById("pricing-enquiry-message");
  if (title) title.textContent = pricePreviewText("requestQuote", "获取报价", "Request a Quote");
  if (message) message.textContent = pricePreviewText("contactSalesQuote", "请联系销售人员获取报价", "Please contact our sales team for a quotation");
}
