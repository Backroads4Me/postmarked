export function getRuntimeConfig() {
  if (typeof window !== "undefined" && window.__POSTMARKED_CONFIG__) {
    return window.__POSTMARKED_CONFIG__;
  }

  return {
    googleMapsApiKey: "",
    googleMapsMapId: "",
  };
}
