import React, { useState, useCallback } from 'react';
import MapIsland from './MapIsland.jsx';
import TimelineIsland from './TimelineIsland.jsx';

/**
 * TripProgressIsland — Combined map + timeline + stop detail view.
 * Manages active stop state and synchronizes map/timeline.
 */
export default function TripProgressIsland({ trip }) {
  const [activeStopId, setActiveStopId] = useState(null);

  const stops = trip?.stops || [];
  const activeStop = stops.find(s => s.id === activeStopId);

  const handleStopClick = useCallback((stopId) => {
    setActiveStopId(prev => prev === stopId ? null : stopId);
  }, []);

  function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        weekday: 'short', month: 'short', day: 'numeric'
      });
    } catch { return ''; }
  }

  function getStopTypeIcon(type) {
    const icons = {
      campground: '⛺',
      boondocking: '🏕️',
      harvest_host: '🍇',
      service: '🔧',
      attraction: '🎡',
      family: '👨‍👩‍👧‍👦',
      overnight: '🌙',
      fuel: '⛽',
      restaurant: '🍽️',
    };
    return icons[type] || '📍';
  }

  return (
    <div className="flex flex-col w-full h-full" style={{ background: 'var(--bg)' }}>

      {/* Map section */}
      <div className="flex-1 relative min-h-0">
        <MapIsland
          stops={stops}
          activeStopId={activeStopId}
          onStopClick={handleStopClick}
        />

        {/* Active stop detail overlay */}
        {activeStop && (
          <div
            className="absolute bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-80 z-20 rounded-xl p-4"
            style={{
              background: 'rgba(16,20,25,.92)',
              backdropFilter: 'blur(16px)',
              border: '1px solid var(--line)',
              boxShadow: 'var(--shadow-float)',
            }}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">{getStopTypeIcon(activeStop.stop_type)}</span>
              {activeStop.is_current && (
                <span className="badge badge-active text-[9px] py-0.5">
                  <span className="pulse-dot mr-1" style={{ width: '6px', height: '6px' }}></span>
                  Now
                </span>
              )}
              {activeStop.status === 'planned' && (
                <span className="badge badge-planned text-[9px] py-0.5">Planned</span>
              )}
              <button
                onClick={() => setActiveStopId(null)}
                className="ml-auto text-dim hover:text-paper transition-colors"
                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '16px' }}
              >
                ✕
              </button>
            </div>

            <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--paper)' }}>
              {activeStop.title}
            </h3>

            {activeStop.place_name && (
              <p className="coord mb-2">{activeStop.place_name}</p>
            )}

            {activeStop.summary && (
              <p className="text-sm mb-3" style={{ color: 'var(--muted)', lineHeight: '1.4' }}>
                {activeStop.summary}
              </p>
            )}

            <div className="flex flex-wrap gap-3 text-xs">
              {activeStop.start_date && (
                <div>
                  <span className="label block mb-0.5">Arrived</span>
                  <span style={{ color: 'var(--paper-2)' }}>{formatDate(activeStop.start_date)}</span>
                </div>
              )}
              {activeStop.nights > 0 && (
                <div>
                  <span className="label block mb-0.5">Nights</span>
                  <span style={{ color: 'var(--paper-2)' }}>{activeStop.nights}</span>
                </div>
              )}
              {activeStop.would_stay_again !== null && activeStop.would_stay_again !== undefined && (
                <div>
                  <span className="label block mb-0.5">Again?</span>
                  <span style={{ color: activeStop.would_stay_again ? 'var(--forest)' : 'var(--sunset)' }}>
                    {activeStop.would_stay_again ? '👍 Yes' : '👎 No'}
                  </span>
                </div>
              )}
            </div>

            {/* RV Features */}
            {activeStop.rv_features && activeStop.rv_features.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-3">
                {activeStop.rv_features.map((f, i) => (
                  <span key={i} className="rv-chip">{f}</span>
                ))}
              </div>
            )}

            {activeStop.public_note && (
              <p className="mt-3 text-sm italic" style={{ color: 'var(--paper-2)', borderLeft: '2px solid var(--ember)', paddingLeft: '8px' }}>
                "{activeStop.public_note}"
              </p>
            )}
          </div>
        )}
      </div>

      {/* Timeline strip */}
      <div className="h-[120px] md:h-[140px] w-full flex-shrink-0">
        <TimelineIsland
          stops={stops}
          activeStopId={activeStopId}
          onStopClick={handleStopClick}
        />
      </div>
    </div>
  );
}
