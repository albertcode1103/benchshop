/*
 * Both the local development proxy and production Nginx serve /api/ on the
 * website origin. Never infer an externally reachable API port from the URL.
 */
if (typeof window.BOTEN_API_BASE !== "string") {
  window.BOTEN_API_BASE = "";
}
window.botenAssetUrl = function (path) {
  const value = String(path || "").trim();
  if (value.startsWith("/api/")) return `${window.BOTEN_API_BASE || ""}${value}`;
  return value;
};

window.BOTEN_SALES_CONTACT = Object.freeze({
  email: "info@boten-diesel.com",
  whatsappHref: "https://wa.me/8617625542926"
});
