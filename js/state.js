function createState() {
  let saved = null;
  try {
    saved = JSON.parse(sessionStorage.getItem("boten-language-config") || "null");
  } catch (_) {}
  sessionStorage.removeItem("boten-language-config");

  const firstModel = configData.models.find((model) => model.id === saved?.currentModelId) || configData.models[0];
  const currentModelId = firstModel.id;
  const currentCategoryId = firstModel.categories.some((category) => category.id === saved?.currentCategoryId)
    ? saved.currentCategoryId
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
      this.subscribers.forEach((fn) => fn(snapshot));
    }
  };
}

function getFirstConfigCategoryId(model) {
  return model.categories.find((category) => category.id !== "motor" && category.id !== "voltage")?.id || null;
}

let state = null;

function initializeState() {
  state = createState();
  return state;
}
