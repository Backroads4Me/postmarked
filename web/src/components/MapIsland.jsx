import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useStore } from '@nanostores/react';
import { urlState } from '../stores/urlState';

const MAP_PROVIDER = (import.meta.env.PUBLIC_MAP_PROVIDER || 'google').toLowerCase();
const GOOGLE_MAPS_API_KEY = import.meta.env.PUBLIC_GOOGLE_MAPS_API_KEY || '';
const GOOGLE_MAPS_MAP_ID = import.meta.env.PUBLIC_GOOGLE_MAPS_MAP_ID || 'DEMO_MAP_ID';

let protocolRegistered = false;
let googleMapsPromise = null;
let mapLibrePromise = null;

// CartoDB Dark Matter: no-key fallback when MapLibre is selected and PMTiles are absent.
const REMOTE_FALLBACK_STYLE = {
  version: 8,
  sources: {
    carto: {
      type: 'raster',
      tiles: ['https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© CARTO © OpenStreetMap contributors',
      maxzoom: 20,
    },
  },
  layers: [{ id: 'carto-dark', type: 'raster', source: 'carto' }],
};

// Dark basemap using PMTiles mounted under Astro public assets at /tiles/*.pmtiles.
const PMTILES_STYLE = {
  version: 8,
  sources: {
    protomaps: {
      type: 'vector',
      url: 'pmtiles:///tiles/basemap.pmtiles',
      attribution: '&copy; OpenStreetMap &copy; Protomaps',
    },
  },
  layers: [
    { id: 'bg', type: 'background', paint: { 'background-color': '#101419' } },
    { id: 'water', type: 'fill', source: 'protomaps', 'source-layer': 'water', paint: { 'fill-color': '#0a1016' } },
    { id: 'earth', type: 'fill', source: 'protomaps', 'source-layer': 'earth', paint: { 'fill-color': '#131a23' } },
    { id: 'landcover', type: 'fill', source: 'protomaps', 'source-layer': 'landcover', paint: { 'fill-color': '#141c26' } },
    { id: 'roads-minor', type: 'line', source: 'protomaps', 'source-layer': 'roads', filter: ['<=', ['get', 'kind_detail'], 3], paint: { 'line-color': '#1d2535', 'line-width': 1 } },
    { id: 'roads-major', type: 'line', source: 'protomaps', 'source-layer': 'roads', filter: ['>', ['get', 'kind_detail'], 3], paint: { 'line-color': '#242e40', 'line-width': 2 } },
    { id: 'buildings', type: 'fill', source: 'protomaps', 'source-layer': 'buildings', paint: { 'fill-color': '#181f2b', 'fill-opacity': 0.6 } },
    { id: 'boundaries', type: 'line', source: 'protomaps', 'source-layer': 'boundaries', paint: { 'line-color': '#253044', 'line-width': 1, 'line-dasharray': [4, 2] } },
  ],
};

export default function MapIsland({ stops, activeStopId, onStopClick }) {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);
  const mapLibreRef = useRef(null);
  const providerRef = useRef(null);
  const markersRef = useRef([]);
  const routeRef = useRef(null);
  const initialViewportSkippedRef = useRef(false);
  const fittedStopsKeyRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);
  const [fallbackReason, setFallbackReason] = useState('');
  const state = useStore(urlState);

  const useGoogle = MAP_PROVIDER === 'google';
  const useMapLibre = MAP_PROVIDER === 'maplibre';

  const stopPoints = useMemo(() => {
    const coords = (stops || [])
      .map((stop, index) => {
        const point = readStopCoords(stop);
        return point ? { ...point, stop, index } : null;
      })
      .filter(Boolean);

    if (coords.length === 0) return [];

    const minLat = Math.min(...coords.map(p => p.lat));
    const maxLat = Math.max(...coords.map(p => p.lat));
    const minLon = Math.min(...coords.map(p => p.lon));
    const maxLon = Math.max(...coords.map(p => p.lon));
    const latSpan = Math.max(maxLat - minLat, 0.1);
    const lonSpan = Math.max(maxLon - minLon, 0.1);

    return coords.map(point => ({
      ...point,
      x: 8 + ((point.lon - minLon) / lonSpan) * 84,
      y: 12 + ((maxLat - point.lat) / latSpan) * 76,
    }));
  }, [stops]);

  useEffect(() => {
    if (useGoogle) {
      let cancelled = false;

      if (!GOOGLE_MAPS_API_KEY) {
        setFallbackReason('Google Maps key missing');
        return;
      }

      loadGoogleMaps(GOOGLE_MAPS_API_KEY)
        .then(({ Map }) => {
          if (cancelled || mapRef.current || !mapContainer.current) return;

          const map = new Map(mapContainer.current, {
            center: { lat: 39, lng: -98 },
            zoom: 4,
            mapId: GOOGLE_MAPS_MAP_ID,
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: false,
            backgroundColor: '#101419',
          });

          providerRef.current = 'google';
          mapRef.current = map;
          setMapReady(true);

          map.addListener('idle', () => {
            const center = map.getCenter();
            if (!center) return;
            urlState.set({
              ...urlState.get(),
              lat: center.lat().toFixed(4),
              lon: center.lng().toFixed(4),
              z: map.getZoom().toFixed(2),
            });
          });
        })
        .catch((err) => {
          console.error('[MapIsland] Google Maps load failed:', err);
          if (!cancelled) setFallbackReason('Google Maps unavailable');
        });

      return () => {
        cancelled = true;
      };
    }

    if (!useMapLibre) {
      setFallbackReason(`Unknown map provider: ${MAP_PROVIDER}`);
      return;
    }

    if (!mapRef.current) {
      let cancelled = false;
      const createMap = async () => {
        const maplibregl = await loadMapLibre();
        mapLibreRef.current = maplibregl;

        if (!protocolRegistered) {
          const { Protocol } = await import('pmtiles');
          const protocol = new Protocol();
          maplibregl.addProtocol('pmtiles', protocol.tile.bind(protocol));
          protocolRegistered = true;
        }

        let style = REMOTE_FALLBACK_STYLE;
        let fallbackOnly = false;
        try {
          const res = await fetch('/tiles/basemap.pmtiles', { method: 'HEAD' });
          if (res.ok) style = PMTILES_STYLE;
        } catch {
          // local tiles unavailable, use remote
        }
        if (cancelled || mapRef.current || !mapContainer.current) return;

        const map = new maplibregl.Map({
          container: mapContainer.current,
          style,
          center: [-98, 39],
          zoom: 4,
          attributionControl: false,
        });

        map.addControl(new maplibregl.NavigationControl(), 'top-right');
        providerRef.current = 'maplibre';
        mapRef.current = map;

        map.once('load', () => {
          setMapReady(true);
        });

        map.once('error', () => {
          if (fallbackOnly || !mapRef.current) return;
          fallbackOnly = true;
          setFallbackReason('Map tiles unavailable');
        });

        map.on('moveend', () => {
          const center = map.getCenter();
          const zoom = map.getZoom();
          urlState.set({
            ...urlState.get(),
            lat: center.lat.toFixed(4),
            lon: center.lng.toFixed(4),
            z: zoom.toFixed(2),
          });
        });
      };
      createMap();
      return () => {
        cancelled = true;
      };
    }
  }, [useGoogle, useMapLibre]);

  useEffect(() => {
    const map = mapRef.current;
    const provider = providerRef.current;
    if (!map || !stops || stops.length === 0) return;

    if (provider === 'google') {
      addGoogleStops(map, stops, activeStopId, onStopClick, markersRef, routeRef, fittedStopsKeyRef);
      return;
    }

    if (provider !== 'maplibre') return;
    const maplibregl = mapLibreRef.current;
    if (!maplibregl) return;

    const addMarkers = () => {
      markersRef.current.forEach(m => m.remove());
      markersRef.current = [];

      const bounds = new maplibregl.LngLatBounds();
      let hasValidCoords = false;

      stops.forEach((stop) => {
        const coords = readStopCoords(stop);
        const lat = coords?.lat;
        const lon = coords?.lon;

        if (lat == null || lon == null || isNaN(lat) || isNaN(lon)) return;

        hasValidCoords = true;
        bounds.extend([lon, lat]);

        const isActive = activeStopId && stop.id === activeStopId;
        const isCurrent = stop.is_current;

        const el = createDotMarkerElement({ isActive, isCurrent });

        if (isCurrent) {
          const pulse = document.createElement('div');
          pulse.style.cssText = `
            position: absolute;
            inset: -5px;
            border-radius: 50%;
            border: 2px solid #4a9f6e;
            animation: pulse-ring 2s ease-out infinite;
          `;
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
          <div style="font-family: var(--sans); padding: 8px;">
            <div style="font-size: 13px; font-weight: 600; color: #f0ebe0;">${escapeHtml(stop.title)}</div>
            ${stop.place_name ? `<div style="font-size: 11px; color: #9a9a9f; margin-top: 2px;">${escapeHtml(stop.place_name)}</div>` : ''}
            ${stop.stop_type ? `<div style="font-size: 10px; color: #e8893f; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.1em;">${escapeHtml(stop.stop_type)}</div>` : ''}
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

      if (hasValidCoords && stops.length > 1) {
        const lineCoords = stops
          .map(s => {
            const coords = readStopCoords(s);
            return coords ? [coords.lon, coords.lat] : null;
          })
          .filter(Boolean);

        if (lineCoords.length > 1) {
          if (map.getSource('route')) {
            map.getSource('route').setData({
              type: 'Feature',
              geometry: { type: 'LineString', coordinates: lineCoords },
            });
          } else {
            map.addSource('route', {
              type: 'geojson',
              data: {
                type: 'Feature',
                geometry: { type: 'LineString', coordinates: lineCoords },
              },
            });
            map.addLayer({
              id: 'route-line',
              type: 'line',
              source: 'route',
              paint: {
                'line-color': '#e8893f',
                'line-width': 2,
                'line-opacity': 0.4,
                'line-dasharray': [4, 4],
              },
            });
          }
        }
      }

      if (hasValidCoords) {
        map.fitBounds(bounds, { padding: 36, maxZoom: 12, duration: 500 });
      }
    };

    if (map.loaded()) {
      addMarkers();
    } else {
      map.on('load', addMarkers);
    }
  }, [stops, activeStopId, mapReady, onStopClick]);

  useEffect(() => {
    const map = mapRef.current;
    const provider = providerRef.current;
    if (!map || !activeStopId || !stops) return;

    const stop = stops.find(s => s.id === activeStopId);
    if (!stop) return;

    const coords = readStopCoords(stop);
    if (!coords) return;

    if (provider === 'google') {
      map.panTo({ lat: coords.lat, lng: coords.lon });
      if ((map.getZoom() || 0) < 10) map.setZoom(10);
      return;
    }

    if (provider === 'maplibre') {
      map.flyTo({ center: [coords.lon, coords.lat], zoom: 10, duration: 800 });
    }
  }, [activeStopId, stops]);

  useEffect(() => {
    const map = mapRef.current;
    const provider = providerRef.current;
    if (!map || !state.lat || !state.lon || !state.z) return;

    if (!initialViewportSkippedRef.current) {
      initialViewportSkippedRef.current = true;
      return;
    }

    const newLat = parseFloat(state.lat);
    const newLon = parseFloat(state.lon);
    const newZ = parseFloat(state.z);
    if (!Number.isFinite(newLat) || !Number.isFinite(newLon) || !Number.isFinite(newZ)) return;

    if (provider === 'google') {
      const currentLoc = map.getCenter();
      const currentZoom = map.getZoom();
      if (!currentLoc) return;
      if (Math.abs(currentLoc.lat() - newLat) > 0.01 || Math.abs(currentLoc.lng() - newLon) > 0.01 || Math.abs(currentZoom - newZ) > 0.1) {
        map.setCenter({ lat: newLat, lng: newLon });
        map.setZoom(newZ);
      }
      return;
    }

    if (provider === 'maplibre') {
      const currentLoc = map.getCenter();
      const currentZoom = map.getZoom();
      if (Math.abs(currentLoc.lat - newLat) > 0.01 || Math.abs(currentLoc.lng - newLon) > 0.01 || Math.abs(currentZoom - newZ) > 0.1) {
        map.jumpTo({ center: [newLon, newLat], zoom: newZ });
      }
    }
  }, [state.lat, state.lon, state.z]);

  const showFallbackRoute = Boolean(fallbackReason) && stopPoints.length > 0;
  const providerLabel = useGoogle ? 'GOOGLE MAPS' : useMapLibre ? 'MAPLIBRE' : MAP_PROVIDER.toUpperCase();

  return (
    <div className="relative w-full h-full overflow-hidden">
      <div ref={mapContainer} className="absolute inset-0" />
      {showFallbackRoute && (
        <FallbackRoute stopPoints={stopPoints} activeStopId={activeStopId} onStopClick={onStopClick} />
      )}
      <div className="map-overlay top-4 left-4">
        {providerLabel} • {stops?.length || 0} STOPS
        <div className="mt-1" style={{ color: 'var(--dim)' }} suppressHydrationWarning>{fallbackReason || `${state.lat || '-'}, ${state.lon || '-'}`}</div>
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
        .fallback-route {
          position: absolute;
          inset: 16px;
          pointer-events: none;
          z-index: 2;
        }
        .fallback-route svg {
          position: absolute;
          inset: 0;
          width: 100%;
          height: 100%;
          overflow: visible;
          filter: drop-shadow(0 2px 8px rgba(0,0,0,.5));
        }
        .fallback-marker {
          position: absolute;
          width: 28px;
          height: 28px;
          transform: translate(-50%, -50%);
          border: 2px solid rgba(255,255,255,.78);
          border-radius: 999px;
          background: #6fa3c4;
          color: #0b1016;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          font-family: var(--mono);
          font-size: 11px;
          font-weight: 700;
          line-height: 1;
          box-shadow: 0 8px 20px rgba(0,0,0,.45);
          cursor: pointer;
          pointer-events: auto;
        }
        .fallback-marker.is-active {
          background: #e8893f;
          color: #17110b;
        }
        .fallback-marker.is-current {
          width: 34px;
          height: 34px;
          background: #4a9f6e;
          color: #06100a;
          border-color: #fff;
        }
        .fallback-marker.is-current::after {
          content: "";
          position: absolute;
          inset: -8px;
          border: 2px solid rgba(74,159,110,.72);
          border-radius: inherit;
          animation: pulse-ring 2s ease-out infinite;
        }
      `}</style>
    </div>
  );
}

function FallbackRoute({ stopPoints, activeStopId, onStopClick }) {
  return (
    <div className="fallback-route" aria-hidden="true">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none">
        {stopPoints.length > 1 && (
          <polyline
            points={stopPoints.map(point => `${point.x},${point.y}`).join(' ')}
            fill="none"
            stroke="#e8893f"
            strokeWidth="1.4"
            strokeDasharray="3 2"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.9"
          />
        )}
      </svg>
      {stopPoints.map(point => (
        <button
          key={point.stop.id || point.index}
          type="button"
          className={`fallback-marker ${point.stop.is_current ? 'is-current' : ''} ${activeStopId === point.stop.id ? 'is-active' : ''}`}
          style={{ left: `${point.x}%`, top: `${point.y}%` }}
          aria-label={point.stop.title}
          onClick={() => onStopClick?.(point.stop.id)}
        >
          <span>{point.index + 1}</span>
        </button>
      ))}
    </div>
  );
}

function addGoogleStops(map, stops, activeStopId, onStopClick, markersRef, routeRef, fittedStopsKeyRef) {
  markersRef.current.forEach(removeGoogleMarker);
  markersRef.current = [];
  if (routeRef.current) {
    routeRef.current.setMap(null);
    routeRef.current = null;
  }

  const google = window.google;
  const bounds = new google.maps.LatLngBounds();
  const route = [];

  stops.forEach((stop) => {
    const coords = readStopCoords(stop);
    if (!coords) return;

    const position = { lat: coords.lat, lng: coords.lon };
    const isActive = activeStopId && stop.id === activeStopId;
    const isCurrent = stop.is_current;
    bounds.extend(position);
    route.push(position);

    const markerElement = createDotMarkerElement({ isActive, isCurrent });

    const marker = new google.maps.marker.AdvancedMarkerElement({
      map,
      position,
      title: stop.title,
      content: markerElement,
    });

    const infoWindow = new google.maps.InfoWindow({
      content: `
        <div style="font-family: system-ui, sans-serif; color: #101419;">
          <div style="font-size: 13px; font-weight: 700;">${escapeHtml(stop.title)}</div>
          ${stop.place_name ? `<div style="font-size: 12px; margin-top: 2px;">${escapeHtml(stop.place_name)}</div>` : ''}
        </div>
      `,
    });

    marker.addListener('gmp-click', () => {
      infoWindow.open({ map, anchor: marker });
      onStopClick?.(stop.id);
    });

    markersRef.current.push(marker);
  });

  if (route.length > 1) {
    routeRef.current = new google.maps.Polyline({
      map,
      path: route,
      geodesic: true,
      strokeColor: '#e8893f',
      strokeOpacity: 0.75,
      strokeWeight: 3,
    });
  }

  const stopsKey = stops
    .map((stop) => {
      const coords = readStopCoords(stop);
      return coords ? `${stop.id || stop.slug}:${coords.lat.toFixed(4)},${coords.lon.toFixed(4)}` : null;
    })
    .filter(Boolean)
    .join('|');
  const shouldFitRoute = fittedStopsKeyRef.current !== stopsKey;

  if (route.length === 1 && shouldFitRoute) {
    map.setCenter(route[0]);
    map.setZoom(9);
    fittedStopsKeyRef.current = stopsKey;
  } else if (route.length > 1 && shouldFitRoute) {
    map.fitBounds(bounds, 36);
    fittedStopsKeyRef.current = stopsKey;
  }
}

function createDotMarkerElement({ isActive, isCurrent }) {
  const el = document.createElement('button');
  const size = isCurrent ? 16 : isActive ? 14 : 10;
  const color = isCurrent ? '#4a9f6e' : isActive ? '#e8893f' : '#1d7f9d';
  el.type = 'button';
  el.className = 'gp-dot-marker';
  el.style.cssText = `
    width: ${size}px;
    height: ${size}px;
    border-radius: 999px;
    background: ${color};
    border: 2px solid rgba(255,255,255,.9);
    cursor: pointer;
    padding: 0;
    display: block;
    position: relative;
    transition: transform 0.16s ease, box-shadow 0.16s ease;
    box-shadow: 0 0 0 2px rgba(10,13,17,.32), 0 2px 8px rgba(0,0,0,.35);
  `;
  return el;
}

function loadGoogleMaps(apiKey) {
  if (googleMapsPromise) return googleMapsPromise;

  googleMapsPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    const params = new URLSearchParams({
      key: apiKey,
      v: 'weekly',
      libraries: 'marker',
    });
    script.src = `https://maps.googleapis.com/maps/api/js?${params.toString()}`;
    script.async = true;
    script.defer = true;
    script.onload = () => {
      if (!window.google?.maps?.Map) {
        reject(new Error('Google Maps did not initialize'));
        return;
      }
      resolve({ google: window.google, Map: window.google.maps.Map });
    };
    script.onerror = (e) => {
      console.error('[MapIsland] Google Maps script failed to load', e);
      reject(new Error('Failed to load Google Maps'));
    };
    document.head.appendChild(script);
  });

  return googleMapsPromise;
}

function loadMapLibre() {
  if (mapLibrePromise) return mapLibrePromise;

  mapLibrePromise = Promise.all([
    import('maplibre-gl'),
    import('maplibre-gl/dist/maplibre-gl.css'),
  ]).then(([module]) => module.default);

  return mapLibrePromise;
}

function removeGoogleMarker(marker) {
  if (typeof marker.setMap === 'function') {
    marker.setMap(null);
    return;
  }

  marker.map = null;
}

function readStopCoords(stop) {
  if (!stop) return null;
  let lat = stop.latitude;
  let lon = stop.longitude;

  if ((lat == null || lon == null) && stop.location) {
    const match = String(stop.location).match(/POINT\(([-\d.]+)\s+([-\d.]+)\)/);
    if (match) {
      lon = parseFloat(match[1]);
      lat = parseFloat(match[2]);
    }
  }

  lat = Number(lat);
  lon = Number(lon);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return { lat, lon };
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
