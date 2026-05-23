export function GET() {
  const config = {
    googleMapsApiKey: import.meta.env.PUBLIC_GOOGLE_MAPS_API_KEY || "",
    googleMapsMapId: import.meta.env.PUBLIC_GOOGLE_MAPS_MAP_ID || "",
  };

  return new Response(`window.__POSTMARKED_CONFIG__ = ${JSON.stringify(config)};\n`, {
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
