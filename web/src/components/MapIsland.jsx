import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { Protocol } from 'pmtiles';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useStore } from '@nanostores/react';
import { urlState } from '../stores/urlState';

let protocolRegistered = false;

// Dark basemap using PMTiles (served by Caddy at /tiles/*.pmtiles).
// If no pmtiles file is present, MapLibre logs tile errors but renders
// the dark background and all markers/routes correctly.
const PMTILES_STYLE = {
  version: 8,
  sources: {
    protomaps: {
      type: "vector",
      url: "pmtiles:///tiles/basemap.pmtiles",
      attribution: "&copy; OpenStreetMap &copy; Protomaps",
    },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#101419" } },
    { id: "water", type: "fill", source: "protomaps", "source-layer": "water", paint: { "fill-color": "#0a1016" } },
    { id: "earth", type: "fill", source: "protomaps", "source-layer": "earth", paint: { "fill-color": "#131a23" } },
    { id: "landcover", type: "fill", source: "protomaps", "source-layer": "landcover", paint: { "fill-color": "#141c26" } },
    { id: "roads-minor", type: "line", source: "protomaps", "source-layer": "roads", filter: ["<=", ["get", "kind_detail"], 3], paint: { "line-color": "#1d2535", "line-width": 1 } },
    { id: "roads-major", type: "line", source: "protomaps", "source-layer": "roads", filter: [">", ["get", "kind_detail"], 3], paint: { "line-color": "#242e40", "line-width": 2 } },
    { id: "buildings", type: "fill", source: "protomaps", "source-layer": "buildings", paint: { "fill-color": "#181f2b", "fill-opacity": 0.6 } },
    { id: "boundaries", type: "line", source: "protomaps", "source-layer": "boundaries", paint: { "line-color": "#253044", "line-width": 1, "line-dasharray": [4, 2] } },
  ],
};

export default function MapIsland({ stops, activeStopId, onStopClick }) {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);
  const state = useStore(urlState);

  useEffect(() => {
    if (!protocolRegistered) {
      const protocol = new Protocol();
      maplibregl.addProtocol("pmtiles", protocol.tile.bind(protocol));
      protocolRegistered = true;
    }

    if (!mapRef.current) {
      const map = new maplibregl.Map({
        container: mapContainer.current,
        style: PMTILES_STYLE,
        center: [-98, 39],
        zoom: 4,
        attributionControl: false,
      });

      map.addControl(new maplibregl.NavigationControl(), 'top-right');
      mapRef.current = map;

      map.on('moveend', () => {
        const center = map.getCenter();
        const zoom = map.getZoom();
        urlState.set({
          ...urlState.get(),
          lat: center.lat.toFixed(4),
          lon: center.lng.toFixed(4),
          z: zoom.toFixed(2)
        });
      });
    }
  }, []);

  // Add/update markers when stops change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !stops || stops.length === 0) return;

    // Wait for map load
    const addMarkers = () => {
      // Clear old markers
      markersRef.current.forEach(m => m.remove());
      markersRef.current = [];

      const bounds = new maplibregl.LngLatBounds();
      let hasValidCoords = false;

      stops.forEach((stop, idx) => {
        // Extract lat/lon from various formats
        let lat = stop.latitude;
        let lon = stop.longitude;

        // Try to parse from location string if needed
        if (!lat && stop.location) {
          const match = String(stop.location).match(/POINT\(([-\d.]+)\s+([-\d.]+)\)/);
          if (match) {
            lon = parseFloat(match[1]);
            lat = parseFloat(match[2]);
          }
        }

        if (lat == null || lon == null || isNaN(lat) || isNaN(lon)) return;

        hasValidCoords = true;
        bounds.extend([lon, lat]);

        const isActive = activeStopId && stop.id === activeStopId;
        const isCurrent = stop.is_current;

        // Create marker element
        const el = document.createElement('div');
        el.className = 'gp-marker';
        el.style.cssText = `
          width: ${isActive || isCurrent ? '18px' : '12px'};
          height: ${isActive || isCurrent ? '18px' : '12px'};
          border-radius: 50%;
          background: ${isCurrent ? '#4a9f6e' : isActive ? '#e8893f' : '#6fa3c4'};
          border: 2px solid ${isCurrent ? '#fff' : isActive ? '#fff' : 'rgba(255,255,255,.4)'};
          cursor: pointer;
          transition: all 0.2s;
          box-shadow: 0 2px 8px rgba(0,0,0,.4);
        `;

        if (isCurrent) {
          const pulse = document.createElement('div');
          pulse.style.cssText = `
            position: absolute;
            inset: -6px;
            border-radius: 50%;
            border: 2px solid #4a9f6e;
            animation: pulse-ring 2s ease-out infinite;
          `;
          el.style.position = 'relative';
          el.appendChild(pulse);
        }

        el.addEventListener('mouseenter', () => {
          el.style.transform = 'scale(1.3)';
        });
        el.addEventListener('mouseleave', () => {
          el.style.transform = 'scale(1)';
        });

        const popup = new maplibregl.Popup({
          offset: 16,
          closeButton: false,
          className: 'gp-popup',
        }).setHTML(`
          <div style="font-family: 'IBM Plex Sans', sans-serif; padding: 8px;">
            <div style="font-size: 13px; font-weight: 600; color: #f0ebe0;">${stop.title}</div>
            ${stop.place_name ? `<div style="font-size: 11px; color: #9a9a9f; margin-top: 2px;">${stop.place_name}</div>` : ''}
            ${stop.stop_type ? `<div style="font-size: 10px; color: #e8893f; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.1em;">${stop.stop_type}</div>` : ''}
          </div>
        `);

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([lon, lat])
          .setPopup(popup)
          .addTo(map);

        el.addEventListener('click', () => {
          if (onStopClick) onStopClick(stop.id);
        });

        markersRef.current.push(marker);
      });

      // Draw route line between stops
      if (hasValidCoords && stops.length > 1) {
        const lineCoords = stops
          .map(s => {
            let lat = s.latitude, lon = s.longitude;
            if (!lat && s.location) {
              const m = String(s.location).match(/POINT\(([-\d.]+)\s+([-\d.]+)\)/);
              if (m) { lon = parseFloat(m[1]); lat = parseFloat(m[2]); }
            }
            return lat != null && lon != null ? [lon, lat] : null;
          })
          .filter(Boolean);

        if (lineCoords.length > 1) {
          if (map.getSource('route')) {
            map.getSource('route').setData({
              type: 'Feature',
              geometry: { type: 'LineString', coordinates: lineCoords }
            });
          } else {
            map.addSource('route', {
              type: 'geojson',
              data: {
                type: 'Feature',
                geometry: { type: 'LineString', coordinates: lineCoords }
              }
            });
            map.addLayer({
              id: 'route-line',
              type: 'line',
              source: 'route',
              paint: {
                'line-color': '#e8893f',
                'line-width': 2,
                'line-opacity': 0.4,
                'line-dasharray': [4, 4]
              }
            });
          }
        }
      }

      // Fit bounds
      if (hasValidCoords) {
        map.fitBounds(bounds, { padding: 60, maxZoom: 12, duration: 500 });
      }
    };

    if (map.loaded()) {
      addMarkers();
    } else {
      map.on('load', addMarkers);
    }
  }, [stops, activeStopId]);

  // Fly to active stop
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !activeStopId || !stops) return;

    const stop = stops.find(s => s.id === activeStopId);
    if (!stop) return;

    let lat = stop.latitude, lon = stop.longitude;
    if (!lat && stop.location) {
      const m = String(stop.location).match(/POINT\(([-\d.]+)\s+([-\d.]+)\)/);
      if (m) { lon = parseFloat(m[1]); lat = parseFloat(m[2]); }
    }
    if (lat == null || lon == null) return;

    map.flyTo({ center: [lon, lat], zoom: 10, duration: 800 });
  }, [activeStopId]);

  // React to URL state
  useEffect(() => {
    const map = mapRef.current;
    if (map && state.lat && state.lon && state.z) {
      const currentLoc = map.getCenter();
      const currentZoom = map.getZoom();
      const newLat = parseFloat(state.lat);
      const newLon = parseFloat(state.lon);
      const newZ = parseFloat(state.z);
      if (Math.abs(currentLoc.lat - newLat) > 0.01 || Math.abs(currentLoc.lng - newLon) > 0.01 || Math.abs(currentZoom - newZ) > 0.1) {
        map.jumpTo({ center: [newLon, newLat], zoom: newZ });
      }
    }
  }, [state.lat, state.lon, state.z]);

  return (
    <div className="relative w-full h-full overflow-hidden">
      <div ref={mapContainer} className="absolute inset-0" />
      <div className="map-overlay top-4 left-4">
        MAP • {stops?.length || 0} STOPS
        <div className="mt-1" style={{ color: 'var(--dim)' }}>{state.lat || '—'}, {state.lon || '—'}</div>
      </div>
      <style>{`
        .gp-popup .maplibregl-popup-content {
          background: rgba(16,20,25,.92);
          backdrop-filter: blur(8px);
          border: 1px solid rgba(46,56,72,.6);
          border-radius: 8px;
          box-shadow: 0 8px 24px rgba(0,0,0,.4);
          padding: 0;
        }
        .gp-popup .maplibregl-popup-tip {
          border-top-color: rgba(16,20,25,.92);
        }
        @keyframes pulse-ring {
          0% { transform: scale(1); opacity: 0.6; }
          100% { transform: scale(2.2); opacity: 0; }
        }
      `}</style>
    </div>
  );
}
