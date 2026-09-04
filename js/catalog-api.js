// runtime-config.js always loads first. An empty string intentionally means
// that Nginx proxies the API on this same origin.
const CATALOG_API_BASE = typeof window.BOTEN_API_BASE === "string"
  ? window.BOTEN_API_BASE
  : (window.location.port === "8001" ? "" : `${window.location.protocol}//${window.location.hostname || "127.0.0.1"}:8001`);

async function catalogRequest(path) {
  return catalogJsonRequest(path);
}

async function catalogJsonRequest(path, options = {}) {
  const response = await fetch(`${CATALOG_API_BASE}${path}`, {
    ...options,
    headers: { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) },
    // Product translations are maintained in the admin catalog. Never let the
    // browser reuse an older response after an administrator saves changes.
    cache: "no-store"
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : "";
    const error = new Error(detail || `Catalog API request failed (${response.status})`);
    error.status = response.status;
    error.code = body.error?.code || "";
    throw error;
  }
  return response.json();
}

function mapApiCategory(category) {
  return {
    id: category.id,
    name: category.name,
    description: category.description || "",
    multiple: Boolean(category.multiple),
    options: category.options.map((option) => ({
      id: option.id,
      code: option.code || "",
      name: option.name,
      description: option.description || "",
      note: option.note || "",
      specialNote: option.special_note || "",
      image: window.botenAssetUrl(option.image?.path) || null,
      imageWidth: Number(option.image?.width) || 640,
      imageHeight: Number(option.image?.height) || 320,
      mappingId: option.mapping_id || null
    }))
  };
}

function mapApiProduct(product, localAssets) {
  const colorImages = {};
  const colorNames = {};
  const colorStyles = {};
  const colorDimensions = {};
  product.colors.forEach((color) => {
    if (color.image?.path) colorImages[color.code] = window.botenAssetUrl(color.image.path);
    colorNames[color.code] = color.name || color.code;
    colorStyles[color.code] = color.display_color || "#374151";
    colorDimensions[color.code] = {
      width: Number(color.image?.width) || 1600,
      height: Number(color.image?.height) || 900
    };
  });

  const baseCategories = product.base_option_groups.map((group) => {
    const categoryId = group.type === "power" ? "voltage" : group.type;
    return {
      id: categoryId,
      sourceType: group.type,
      name: group.name,
      description: "",
      multiple: false,
      required: Boolean(group.required),
      options: group.options.map((option) => ({
        id: option.id,
        name: option.name,
        description: "",
        baseOptionType: group.type
      }))
    };
  });
  const optionalCategories = product.optional_categories.map(mapApiCategory);

  return {
    id: product.id,
    schemaVersion: Number(product.schema_version || 2),
    name: product.model,
    type: product.model,
    titleName: product.name,
    description: product.overview || "",
    colors: product.colors.map((color) => color.code),
    defaultColor: product.colors.find((color) => color.is_default)?.code || product.colors[0]?.code || null,
    colorImages,
    colorNames,
    colorStyles,
    colorDimensions,
    // data.js is retained only as a source for local gallery assets. All
    // customer-facing product text must come from the catalog API.
    detailImages: localAssets?.detailImages || [],
    categories: [...baseCategories, ...optionalCategories],
    specifications: product.specifications || []
  };
}

async function loadCatalogFromApi() {
  if (window.location.protocol === "file:") {
    window.catalogSource = "error";
    throw new Error("Catalog API cannot be loaded from a file URL");
  }

  const localAssets = new Map(configData.models.map((model) => [model.id, model]));
  try {
    const lang = localStorage.getItem("boten-language") || "zh";
    const language = lang === "en" ? "en" : "zh";
    const list = await catalogRequest(`/api/v1/products?lang=${language}`);
    const products = await Promise.all(
      list.items.map((item) => catalogRequest(`/api/v1/products/${encodeURIComponent(item.id)}/snapshot?lang=${language}`))
    );
    const models = products
      .map((product) => mapApiProduct(product, localAssets.get(product.id)))
      .filter((model) => model.colors.length > 0 && model.categories.length > 0);

    if (!models.length) throw new Error("Catalog API returned no usable products");
    configData.models.splice(0, configData.models.length, ...models);
    window.catalogSource = "api";
    return true;
  } catch (error) {
    // Do not silently display the static data.js copy: it can differ from what
    // was entered in the administration catalog and show the wrong language.
    console.error("Catalog API unavailable.", error);
    window.catalogSource = "error";
    throw error;
  }
}
