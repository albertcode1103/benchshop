const CATALOG_API_BASE = window.BOTEN_API_BASE || (
  window.location.port === "8001"
    ? ""
    : `${window.location.protocol}//${window.location.hostname || "127.0.0.1"}:8001`
);

async function catalogRequest(path) {
  const response = await fetch(`${CATALOG_API_BASE}${path}`, {
    headers: { Accept: "application/json" },
    // Product translations are maintained in the admin catalog. Never let the
    // browser reuse an older response after an administrator saves changes.
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Catalog API request failed (${response.status})`);
  }
  return response.json();
}

function mapApiCategory(category) {
  const isBuiltInSingleChoice = category.id === "motor" || category.id === "voltage";
  return {
    id: category.id,
    name: category.name,
    description: category.description || "",
    // Motor and power supply are always single-choice sections. Older catalog
    // records may still have multiple=1, which previously prevented defaults.
    multiple: isBuiltInSingleChoice ? false : Boolean(category.multiple),
    options: category.options.map((option) => ({
      id: option.id,
      name: option.name,
      description: option.description_override || option.description || "",
      price: Number(option.price || 0),
      image: window.botenAssetUrl(option.image_path) || null,
      mappingId: option.mapping_id || null
    }))
  };
}

function mapApiProduct(product, localAssets) {
  const colorImages = {};
  product.colors.forEach((color) => {
    if (color.image_path) colorImages[color.code] = window.botenAssetUrl(color.image_path);
  });

  return {
    id: product.id,
    name: product.name,
    type: product.name,
    titleName: product.title_name,
    description: product.description || "",
    basePrice: Number(product.base_price || 0),
    colors: product.colors.map((color) => color.code),
    colorImages,
    // data.js is retained only as a source for local gallery assets. All
    // customer-facing product text must come from the catalog API.
    detailImages: localAssets?.detailImages || [],
    categories: product.categories.map(mapApiCategory)
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
      list.items.map((item) => catalogRequest(`/api/v1/products/${encodeURIComponent(item.id)}?lang=${language}`))
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
