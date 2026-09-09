/*
 * The production Nginx container serves the website and proxies /api/ on the
 * same origin.  Local `py -m http.server 8080` development still reaches the
 * separately started API on port 8001 without requiring a file edit.
 */
const botenIsLocalStaticServer = ["8080", "8081"].includes(window.location.port);
if (typeof window.BOTEN_API_BASE !== "string") {
  window.BOTEN_API_BASE = botenIsLocalStaticServer
    ? `${window.location.protocol}//${window.location.hostname}:8001`
    : "";
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
