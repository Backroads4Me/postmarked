import { useEffect, useRef } from "react";

const POI_COLORS = {
  campground: "#4a9f6e",
  trailhead: "#6fa3c4",
  fuel: "#e8893f",
  restaurant: "#c46f9f",
  attraction: "#9f6fc4",
  other: "#888",
};

export default function StopMapIsland({ latitude, longitude, pois = [], mediaGps = [] }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    if (latitude == null || longitude == null) return;

    let map;

    async function init() {
      const maplibregl = (await import("maplibre-gl")).default;
      await import("maplibre-gl/dist/maplibre-gl.css");

      const style = {
        version: 8,
        sources: {
          carto: {
            type: "raster",
            tiles: ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© CartoDB",
          },
        },
        layers: [{ id: "carto-base", type: "raster", source: "carto" }],
      };

      map = new maplibregl.Map({
        container: containerRef.current,
        style,
        center: [longitude, latitude],
        zoom: 12,
        attributionControl: false,
      });
      mapRef.current = map;

      map.on("load", () => {
        // Stop center marker
        const el = document.createElement("div");
        el.style.cssText = `width:18px;height:18px;border-radius:50%;background:#4a9f6e;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.5);`;
        new maplibregl.Marker({ element: el })
          .setLngLat([longitude, latitude])
          .setPopup(new maplibregl.Popup({ offset: 12 }).setHTML("<strong>Stop</strong>"))
          .addTo(map);

        // POI markers
        for (const poi of pois) {
          const color = POI_COLORS[poi.poi_type] ?? POI_COLORS.other;
          const poiEl = document.createElement("div");
          poiEl.style.cssText = `width:12px;height:12px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.4);cursor:pointer;`;
          const popup = new maplibregl.Popup({ offset: 10 }).setHTML(
            `<strong>${poi.label}</strong><br><span style="font-size:11px;opacity:.7">${poi.poi_type}</span>` +
            (poi.google_maps_url ? `<br><a href="${poi.google_maps_url}" target="_blank" rel="noopener" style="font-size:11px;">Open in Maps ↗</a>` : "")
          );
          new maplibregl.Marker({ element: poiEl })
            .setLngLat([poi.longitude, poi.latitude])
            .setPopup(popup)
            .addTo(map);
        }

        // Photo GPS dots
        for (const pt of mediaGps) {
          const dotEl = document.createElement("div");
          dotEl.style.cssText = `width:8px;height:8px;border-radius:50%;background:#e8c44a;border:1px solid rgba(255,255,255,.6);box-shadow:0 1px 2px rgba(0,0,0,.3);`;
          new maplibregl.Marker({ element: dotEl })
            .setLngLat([pt.longitude, pt.latitude])
            .addTo(map);
        }

        // Fit bounds if there are POIs or photo dots
        const allPoints = [
          { lng: longitude, lat: latitude },
          ...pois.map((p) => ({ lng: p.longitude, lat: p.latitude })),
          ...mediaGps.map((p) => ({ lng: p.longitude, lat: p.latitude })),
        ];
        if (allPoints.length > 1) {
          const lngs = allPoints.map((p) => p.lng);
          const lats = allPoints.map((p) => p.lat);
          map.fitBounds(
            [[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]],
            { padding: 40, maxZoom: 14 }
          );
        }
      });
    }

    init().catch(console.error);

    return () => { if (map) map.remove(); mapRef.current = null; };
  }, [latitude, longitude]);

  if (latitude == null || longitude == null) return null;

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: 280, borderRadius: 8, overflow: "hidden", border: "1px solid var(--line-soft)" }}
    />
  );
}
