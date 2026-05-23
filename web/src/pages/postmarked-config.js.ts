export function GET() {
  const config = {
    googleMapsApiKey: (typeof process !== "undefined" && process.env.PUBLIC_GOOGLE_MAPS_API_KEY) || import.meta.env.PUBLIC_GOOGLE_MAPS_API_KEY || "",
    googleMapsMapId: (typeof process !== "undefined" && process.env.PUBLIC_GOOGLE_MAPS_MAP_ID) || import.meta.env.PUBLIC_GOOGLE_MAPS_MAP_ID || "",
  };

  return new Response(`window.__POSTMARKED_CONFIG__ = ${JSON.stringify(config)};\n`, {
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
