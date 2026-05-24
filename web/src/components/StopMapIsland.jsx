import { useEffect, useRef, useState } from "react";
import { getRuntimeConfig } from "../lib/runtimeConfig.js";

let googleMapsPromise = null;

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
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    if (latitude == null || longitude == null) return;

    let map;
    let googleMarkers = [];
    const config = getRuntimeConfig();
    const googleMapsApiKey = config.googleMapsApiKey || "";
    const googleMapsMapId = config.googleMapsMapId || "DEMO_MAP_ID";

    async function init() {
      if (!googleMapsApiKey) {
        setFailed(true);
        return;
      }

      try {
        const { google, Map } = await loadGoogleMaps(googleMapsApiKey);
        map = new Map(containerRef.current, {
          center: { lat: Number(latitude), lng: Number(longitude) },
          zoom: 12,
          mapId: googleMapsMapId,
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: false,
          backgroundColor: "#101419",
        });
        mapRef.current = map;

        const bounds = new google.maps.LatLngBounds();
        const allPoints = [
          { lat: Number(latitude), lng: Number(longitude) },
          ...pois.map((p) => ({ lat: Number(p.latitude), lng: Number(p.longitude) })),
          ...mediaGps.map((p) => ({ lat: Number(p.latitude), lng: Number(p.longitude) })),
        ].filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lng));

        addGoogleMarker({
          google,
          map,
          position: { lat: Number(latitude), lng: Number(longitude) },
          title: "Stop",
          color: POI_COLORS.campground,
          scale: 1.1,
          markers: googleMarkers,
        });

        for (const poi of pois) {
          const lat = Number(poi.latitude);
          const lng = Number(poi.longitude);
          if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;

          const title = escapeHtml(poi.label);
          const type = escapeHtml(poi.poi_type);
          const mapsLink = poi.google_maps_url
            ? `<br><a href="${escapeHtml(poi.google_maps_url)}" target="_blank" rel="noopener" style="font-size:11px;">Open in Maps</a>`
            : "";

          addGoogleMarker({
            google,
            map,
            position: { lat, lng },
            title: poi.label,
            color: POI_COLORS[poi.poi_type] ?? POI_COLORS.other,
            scale: 0.8,
            content: `<strong>${title}</strong><br><span style="font-size:11px;opacity:.7">${type}</span>${mapsLink}`,
            markers: googleMarkers,
          });
        }

        for (const pt of mediaGps) {
          const lat = Number(pt.latitude);
          const lng = Number(pt.longitude);
          if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;

          addGoogleMarker({
            google,
            map,
            position: { lat, lng },
            title: "Photo",
            color: "#e8c44a",
            scale: 0.6,
            markers: googleMarkers,
          });
        }

        for (const point of allPoints) bounds.extend(point);
        if (allPoints.length > 1) {
          map.fitBounds(bounds, 40);
        }
      } catch (err) {
        console.error("[StopMapIsland] Google Maps load failed:", err);
        setFailed(true);
      }
    }

    init();

    return () => {
      googleMarkers.forEach((marker) => { marker.map = null; });
      googleMarkers = [];
      if (map?.remove) map.remove();
      mapRef.current = null;
    };
  }, [latitude, longitude]);

  if (latitude == null || longitude == null) return null;

  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height: 280,
        borderRadius: 8,
        overflow: "hidden",
        border: "1px solid var(--line-soft)",
        position: "relative",
      }}
    >
      {failed && (
        <div style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "#101419",
          color: "var(--dim)",
          fontFamily: "var(--sans)",
          fontSize: "13px",
          textAlign: "center",
          padding: "16px",
          gap: "12px",
        }}>
          <span>Google Maps could not be loaded.</span>
          <a
            href={mapsUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: "var(--ember)",
              textDecoration: "none",
              fontWeight: 500,
              fontSize: "12px",
              padding: "6px 12px",
              border: "1px solid var(--ember)",
              borderRadius: "4px",
              transition: "all 0.2s",
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.background = "var(--ember-glow)";
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            Open in Google Maps ↗
          </a>
        </div>
      )}
    </div>
  );
}

function addGoogleMarker({ google, map, position, title, color, scale, content, markers }) {
  const pin = new google.maps.marker.PinElement({
    scale,
    background: color,
    borderColor: "#ffffff",
    glyphColor: "#101419",
  });

  const marker = new google.maps.marker.AdvancedMarkerElement({
    map,
    position,
    title,
    content: pin,
  });

  if (content || title) {
    const infoWindow = new google.maps.InfoWindow({
      content: `<div style="font-family: system-ui, sans-serif; color: #101419;">${content || `<strong>${escapeHtml(title)}</strong>`}</div>`,
    });
    marker.addListener("gmp-click", () => {
      infoWindow.open({ map, anchor: marker });
    });
  }

  markers.push(marker);
}

function loadGoogleMaps(apiKey) {
  if (window.google?.maps?.Map) {
    return Promise.resolve({ google: window.google, Map: window.google.maps.Map });
  }

  if (googleMapsPromise) return googleMapsPromise;

  googleMapsPromise = new Promise((resolve, reject) => {
    let script = document.querySelector('script[src^="https://maps.googleapis.com/maps/api/js"]');

    if (!script) {
      script = document.createElement("script");
      const params = new URLSearchParams({
        key: apiKey,
        v: "weekly",
        libraries: "marker",
      });
      script.src = `https://maps.googleapis.com/maps/api/js?${params.toString()}`;
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }

    if (window.google?.maps?.Map) {
      resolve({ google: window.google, Map: window.google.maps.Map });
      return;
    }

    const onLoad = () => {
      if (window.google?.maps?.Map) {
        resolve({ google: window.google, Map: window.google.maps.Map });
      } else {
        reject(new Error("Google Maps did not initialize"));
      }
      cleanup();
    };

    const onError = () => {
      reject(new Error("Failed to load Google Maps"));
      cleanup();
    };

    function cleanup() {
      script.removeEventListener("load", onLoad);
      script.removeEventListener("error", onError);
    }

    script.addEventListener("load", onLoad);
    script.addEventListener("error", onError);
  });

  return googleMapsPromise;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
