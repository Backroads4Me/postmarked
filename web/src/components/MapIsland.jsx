import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useStore } from '@nanostores/react';
import { getRuntimeConfig } from '../lib/runtimeConfig.js';
import { urlState } from '../stores/urlState';

let googleMapsPromise = null;

export default function MapIsland({ stops, activeStopId, onStopClick }) {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);
  const routeRef = useRef(null);
  const initialViewportSkippedRef = useRef(false);
  const fittedStopsKeyRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);
  const [fallbackReason, setFallbackReason] = useState('');
  const state = useStore(urlState);

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
    let cancelled = false;
    const config = getRuntimeConfig();
    const googleMapsApiKey = config.googleMapsApiKey || '';
    const googleMapsMapId = config.googleMapsMapId || 'DEMO_MAP_ID';

    if (!googleMapsApiKey) {
      setFallbackReason('Google Maps key missing');
      return;
    }

    loadGoogleMaps(googleMapsApiKey)
      .then(({ Map }) => {
        if (cancelled || mapRef.current || !mapContainer.current) return;

        const map = new Map(mapContainer.current, {
          center: { lat: 39, lng: -98 },
          zoom: 4,
          mapId: googleMapsMapId,
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: false,
          backgroundColor: '#101419',
        });

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
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !stops || stops.length === 0) return;
    addGoogleStops(map, stops, activeStopId, onStopClick, markersRef, routeRef, fittedStopsKeyRef);
  }, [stops, activeStopId, mapReady, onStopClick]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !activeStopId || !stops) return;

    const stop = stops.find(s => s.id === activeStopId);
    if (!stop) return;

    const coords = readStopCoords(stop);
    if (!coords) return;

    map.panTo({ lat: coords.lat, lng: coords.lon });
    if ((map.getZoom() || 0) < 10) map.setZoom(10);
  }, [activeStopId, stops]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !state.lat || !state.lon || !state.z) return;

    if (!initialViewportSkippedRef.current) {
      initialViewportSkippedRef.current = true;
      return;
    }

    const newLat = parseFloat(state.lat);
    const newLon = parseFloat(state.lon);
    const newZ = parseFloat(state.z);
    if (!Number.isFinite(newLat) || !Number.isFinite(newLon) || !Number.isFinite(newZ)) return;

    const currentLoc = map.getCenter();
    const currentZoom = map.getZoom();
    if (!currentLoc) return;
    if (Math.abs(currentLoc.lat() - newLat) > 0.01 || Math.abs(currentLoc.lng() - newLon) > 0.01 || Math.abs(currentZoom - newZ) > 0.1) {
      map.setCenter({ lat: newLat, lng: newLon });
      map.setZoom(newZ);
    }
  }, [state.lat, state.lon, state.z]);

  const showFallbackRoute = Boolean(fallbackReason) && stopPoints.length > 0;

  return (
    <div className="relative w-full h-full overflow-hidden">
      <div ref={mapContainer} className="absolute inset-0" />
      {showFallbackRoute && (
        <FallbackRoute stopPoints={stopPoints} activeStopId={activeStopId} onStopClick={onStopClick} />
      )}
      <div className="map-overlay top-4 left-4">
        GOOGLE MAPS • {stops?.length || 0} STOPS
        <div className="mt-1" style={{ color: 'var(--dim)' }} suppressHydrationWarning>{fallbackReason || `${state.lat || '-'}, ${state.lon || '-'}`}</div>
      </div>
      <style>{`
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
  if (window.google?.maps?.Map) {
    return Promise.resolve({ google: window.google, Map: window.google.maps.Map });
  }

  if (googleMapsPromise) return googleMapsPromise;

  googleMapsPromise = new Promise((resolve, reject) => {
    let script = document.querySelector('script[src^="https://maps.googleapis.com/maps/api/js"]');

    if (!script) {
      script = document.createElement('script');
      const params = new URLSearchParams({
        key: apiKey,
        v: 'weekly',
        libraries: 'marker',
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
        reject(new Error('Google Maps did not initialize'));
      }
      cleanup();
    };

    const onError = (e) => {
      console.error('[MapIsland] Google Maps script failed to load', e);
      reject(new Error('Failed to load Google Maps'));
      cleanup();
    };

    function cleanup() {
      script.removeEventListener('load', onLoad);
      script.removeEventListener('error', onError);
    }

    script.addEventListener('load', onLoad);
    script.addEventListener('error', onError);
  });

  return googleMapsPromise;
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
