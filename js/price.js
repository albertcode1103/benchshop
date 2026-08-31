function formatPrice(value) {
  return "¥" + value.toLocaleString("zh-CN");
}

function getColorLabel(color, model = null) {
  if (model?.colorNames?.[color]) return model.colorNames[color];
  return color;
}

function getSpecLabel(categoryId, name) {
  // Option names are already localized by the catalog API.
  return name;
}

function calculateTotal(modelId, selections) {
  const model = configData.models.find((m) => m.id === modelId);
  if (!model) return 0;

  let total = model.basePrice;

  model.categories.forEach((cat) => {
    const selected = selections[cat.id];
    if (!selected) return;

    if (cat.multiple) {
      selected.forEach((optId) => {
        const option = cat.options.find((o) => o.id === optId);
        if (option) total += option.price;
      });
    } else {
      const option = cat.options.find((o) => o.id === selected);
      if (option) total += option.price;
    }
  });

  return total;
}

function getSelectedOptions(model, selections) {
  const items = [];

  model.categories.forEach((cat) => {
    const selected = selections[cat.id];
    if (!selected || (Array.isArray(selected) && selected.length === 0)) return;

    if (cat.multiple) {
      selected.forEach((optId) => {
        const option = cat.options.find((o) => o.id === optId);
        if (option) {
          items.push({
            category: cat.name,
            name: option.name,
            price: option.price
          });
        }
      });
    } else {
      const option = cat.options.find((o) => o.id === selected);
      if (option) {
        items.push({
          category: cat.name,
          name: option.name,
          price: option.price
        });
      }
    }
  });

  return items;
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
