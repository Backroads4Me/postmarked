import { useEffect, useRef } from "react";
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

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    if (latitude == null || longitude == null) return;

    let map;
    let googleMarkers = [];
    const config = getRuntimeConfig();
    const googleMapsApiKey = config.googleMapsApiKey || "";
    const googleMapsMapId = config.googleMapsMapId || "DEMO_MAP_ID";

    async function init() {
      if (!googleMapsApiKey) return;

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
    }

    init().catch(console.error);

    return () => {
      googleMarkers.forEach((marker) => { marker.map = null; });
      googleMarkers = [];
      if (map?.remove) map.remove();
      mapRef.current = null;
    };
  }, [latitude, longitude]);

  if (latitude == null || longitude == null) return null;

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: 280, borderRadius: 8, overflow: "hidden", border: "1px solid var(--line-soft)" }}
    />
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
    content: pin.element,
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
  if (googleMapsPromise) return googleMapsPromise;

  googleMapsPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector("script[data-postmarked-google-maps]");
    if (existing && window.google?.maps?.Map) {
      resolve({ google: window.google, Map: window.google.maps.Map });
      return;
    }

    const script = document.createElement("script");
    const params = new URLSearchParams({
      key: apiKey,
      v: "weekly",
      libraries: "marker",
    });
    script.dataset.postmarkedGoogleMaps = "true";
    script.src = `https://maps.googleapis.com/maps/api/js?${params.toString()}`;
    script.async = true;
    script.defer = true;
    script.onload = () => {
      if (!window.google?.maps?.Map) {
        reject(new Error("Google Maps did not initialize"));
        return;
      }
      resolve({ google: window.google, Map: window.google.maps.Map });
    };
    script.onerror = () => {
      reject(new Error("Failed to load Google Maps"));
    };
    document.head.appendChild(script);
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
