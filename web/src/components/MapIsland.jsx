import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import { Protocol } from 'pmtiles';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useStore } from '@nanostores/react';
import { urlState } from '../stores/urlState';

// Register PMTiles Protocol
let protocolRegistered = false;

export default function MapIsland({ stops }) {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);
  const state = useStore(urlState);

  useEffect(() => {
    if (!protocolRegistered) {
      maplibregl.addProtocol('pmtiles', (request) => {
        return new Promise((resolve, reject) => {
          const p = new Protocol();
          p.tile(request).then(resolve).catch(reject);
        });
      });
      protocolRegistered = true;
    }

    if (!mapRef.current) {
      const map = new maplibregl.Map({
        container: mapContainer.current,
        // Graceful degradation: standard basemap if PMTiles isn't explicitly configured. 
        // We configure a placeholder vector source targeting our proxy /tiles route if desired.
        // For standard local dev without pmtiles configured, we default to CartoDB Voyager.
        style: {
          version: 8,
          sources: {
            'carto': {
              type: 'raster',
              tiles: ['https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png'],
              tileSize: 256,
              attribution: '&copy; OpenStreetMap contributors &carto;'
            }
          },
          layers: [
            {
              id: 'simple-tiles',
              type: 'raster',
              source: 'carto',
              minzoom: 0,
              maxzoom: 22
            }
          ]
        },
        center: [-100, 40],
        zoom: 3,
        attributionControl: false
      });

      map.addControl(new maplibregl.NavigationControl(), 'top-right');
      mapRef.current = map;

      map.on('load', () => {
        if (!stops || stops.length === 0) return;
        
        // Add markers for each stop
        stops.forEach(stop => {
          // If we have actual lat/lon, use it. Stops currently don't natively have lat/lon in our baseline schema without Media hints!
          // But if they did, we'd plot them:
          // new maplibregl.Marker().setLngLat([stop.lon, stop.lat]).addTo(map);
        });
      });
      
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
  }, []); // Only init once

  // React to URL state externally updated
  useEffect(() => {
    const map = mapRef.current;
    if (map && state.lat && state.lon && state.z) {
      const currentLoc = map.getCenter();
      const currentZoom = map.getZoom();
      
      const newLat = parseFloat(state.lat);
      const newLon = parseFloat(state.lon);
      const newZ = parseFloat(state.z);
      
      // Prevent recursive sync jitter
      if (Math.abs(currentLoc.lat - newLat) > 0.01 || Math.abs(currentLoc.lng - newLon) > 0.01 || Math.abs(currentZoom - newZ) > 0.1) {
        map.jumpTo({ center: [newLon, newLat], zoom: newZ });
      }
    }
  }, [state.lat, state.lon, state.z]);

  return (
    <div className="relative w-full h-full bg-surface-2 overflow-hidden border border-line">
      <div ref={mapContainer} className="absolute inset-0" />
      {/* Decorative overlay capturing the specific UI spec */}
      <div className="absolute top-4 left-4 z-10 bg-surface-1/90 backdrop-blur border border-line rounded px-3 py-2 text-xs font-mono tracking-widest pointer-events-none">
        MAP VIEW • {stops?.length || 0} SECTORS
        <div className="text-dim mt-1">{state.lat || '0'}, {state.lon || '0'} </div>
      </div>
    </div>
  );
}
