/* Deployment override: set this to the public API origin, or "" when the
   website and API share one origin behind a reverse proxy. */
window.BOTEN_API_BASE = window.BOTEN_API_BASE || "http://127.0.0.1:8001";
window.botenAssetUrl = function (path) {
  const value = String(path || "").trim();
  if (value.startsWith("/api/")) return `${window.BOTEN_API_BASE || ""}${value}`;
  return value;
};
