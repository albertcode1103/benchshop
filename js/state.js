function createState() {
  let saved = null;
  let pageState = null;
  try {
    saved = JSON.parse(sessionStorage.getItem("boten-language-config") || "null");
  } catch (_) {}
  try {
    pageState = JSON.parse(sessionStorage.getItem("boten-page-device-state") || "null");
  } catch (_) {}
  sessionStorage.removeItem("boten-language-config");

  const preferredModelId = saved?.currentModelId || pageState?.currentModelId;
  const firstModel = configData.models.find((model) => model.id === preferredModelId)
    || configData.models.find((model) => model.id === "cr1016")
    || configData.models[0];
  const currentModelId = firstModel.id;
  const preferredCategoryId = saved?.currentCategoryId || pageState?.currentCategoryId;
  const currentCategoryId = firstModel.categories.some((category) => category.id === preferredCategoryId)
    ? preferredCategoryId
    : getFirstConfigCategoryId(firstModel);
  const currentColor = firstModel.colors.includes(saved?.currentColor)
    ? saved.currentColor
    : getDefaultColor(firstModel);
  const selections = getDefaultSelections(firstModel);

  firstModel.categories.forEach((category) => {
    const savedSelection = saved?.selections?.[category.id];
    const validIds = new Set(category.options.map((option) => option.id));
    if (category.multiple && Array.isArray(savedSelection)) {
      selections[category.id] = savedSelection.filter((optionId) => validIds.has(optionId));
    } else if (!category.multiple && validIds.has(savedSelection)) {
      selections[category.id] = savedSelection;
    }
  });

  return {
    currentModelId,
    currentCategoryId,
    currentColor,
    selections,
    subscribers: [],

    setModel(modelId) {
      const model = configData.models.find((m) => m.id === modelId);
      if (!model) return;

      this.currentModelId = modelId;
      this.currentColor = getDefaultColor(model);
      this.currentCategoryId = getFirstConfigCategoryId(model);
      this.selections = getDefaultSelections(model);
      this.notify();
    },

    loadSnapshot(snapshot, allowUnavailable = false) {
      const productId = snapshot?.product?.id;
      const model = configData.models.find((item) => item.id === productId);
      if (!model) return { loaded: false, missingCount: 1 };
      const colorCode = snapshot?.color?.code;
      const nextSelections = getDefaultSelections(model);
      let missingCount = model.colors.includes(colorCode) ? 0 : 1;
      (snapshot.categories || []).forEach((category) => {
        const modelCategory = model.categories.find((item) => item.id === category.id);
        if (!modelCategory) { missingCount += (category.options || []).length || 1; return; }
        const validIds = new Set(modelCategory.options.map((option) => option.id));
        const requestedIds = (category.options || []).map((option) => option.id).filter(Boolean);
        const ids = requestedIds.filter((id) => validIds.has(id));
        missingCount += requestedIds.length - ids.length;
        if (modelCategory.multiple) nextSelections[category.id] = ids;
        else if (ids[0]) nextSelections[category.id] = ids[0];
      });
      if (missingCount && !allowUnavailable) return { loaded: false, missingCount };
      this.currentModelId = productId;
      this.currentColor = model.colors.includes(colorCode) ? colorCode : getDefaultColor(model);
      this.currentCategoryId = getFirstConfigCategoryId(model);
      this.selections = nextSelections;
      this.notify();
      return { loaded: true, missingCount };
    },

    setColor(color) {
      const model = configData.models.find((m) => m.id === this.currentModelId);
      if (!model || !model.colors.includes(color)) return;
      this.currentColor = color;
      this.notify();
    },

    setCategory(categoryId) {
      this.currentCategoryId = categoryId;
      this.notify();
    },

    selectOption(categoryId, optionId, multiple) {
      if (multiple) {
        const current = this.selections[categoryId] || [];
        const set = new Set(current);
        if (set.has(optionId)) {
          set.delete(optionId);
        } else {
          set.add(optionId);
        }
        this.selections[categoryId] = Array.from(set);
      } else {
        this.selections[categoryId] = optionId;
      }
      this.notify();
    },

    setAllOptions(categoryId, optionIds) {
      const model = configData.models.find((item) => item.id === this.currentModelId);
      const category = model?.categories.find((item) => item.id === categoryId);
      if (!category?.multiple) return;

      const validIds = new Set(category.options.map((option) => option.id));
      this.selections[categoryId] = optionIds.filter((optionId) => validIds.has(optionId));
      this.notify();
    },

    reset() {
      this.setModel(this.currentModelId);
    },

    getSnapshot() {
      return {
        currentModelId: this.currentModelId,
        currentCategoryId: this.currentCategoryId,
        currentColor: this.currentColor,
        selections: { ...this.selections }
      };
    },

    subscribe(fn) {
      this.subscribers.push(fn);
    },

    notify() {
      const snapshot = this.getSnapshot();
      try {
        sessionStorage.setItem("boten-page-device-state", JSON.stringify({
          currentModelId: snapshot.currentModelId,
          currentCategoryId: snapshot.currentCategoryId
        }));
      } catch (_) {}
      this.subscribers.forEach((fn) => fn(snapshot));
    }
  };
}

function getFirstConfigCategoryId(model) {
  return model.categories.find((category) => !["motor", "voltage", "channel"].includes(category.id))?.id || null;
}

let state = null;

function initializeState() {
  state = createState();
  return state;
}
