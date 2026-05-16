import React, { useRef, useState } from 'react';

export default function TimelineIsland({ stops, activeStopId, onStopClick }) {
  const scrollRef = useRef(null);

  const handleStopClick = (stopId) => {
    if (onStopClick) onStopClick(stopId);
  };

  function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch { return ''; }
  }

  function getStopTypeLabel(type) {
    const labels = {
      campground: 'Camp',
      boondocking: 'Wild',
      harvest_host: 'Host',
      service: 'Svc',
      attraction: 'See',
      family: 'Fam',
      overnight: 'Night',
      fuel: 'Fuel',
      restaurant: 'Food',
    };
    return labels[type] || 'Stop';
  }

  return (
    <div className="w-full h-full flex flex-col overflow-hidden" style={{ background: 'var(--surface)', borderTop: '1px solid var(--line)' }}>
      <div className="px-4 py-2 flex justify-between items-center" style={{ borderBottom: '1px solid var(--line-soft)' }}>
        <span className="eyebrow">Route Timeline</span>
        <span className="label">{stops?.length || 0} stops</span>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-x-auto overflow-y-hidden flex items-center px-3 gap-1"
        style={{ scrollBehavior: 'smooth' }}
      >
        {(!stops || stops.length === 0) && (
          <div className="text-sm italic" style={{ color: 'var(--muted)' }}>No stops recorded</div>
        )}

        {stops?.map((stop, idx) => {
          const isActive = activeStopId === stop.id;
          const isCurrent = stop.is_current;

          return (
            <div key={stop.id} className="flex items-center gap-1 flex-shrink-0">
              {/* Connector line */}
              {idx > 0 && (
                <div className="w-6 h-px flex-shrink-0" style={{ background: 'var(--line)' }} />
              )}

              {/* Stop node */}
              <button
                onClick={() => handleStopClick(stop.id)}
                className="flex-shrink-0 flex flex-col items-center gap-1 px-2 py-2 rounded-lg transition-all duration-200"
                style={{
                  background: isActive ? 'var(--ember-glow)' : 'transparent',
                  border: isActive ? '1px solid rgba(232,137,63,.3)' : '1px solid transparent',
                  minWidth: '72px',
                  cursor: 'pointer',
                }}
                title={stop.title}
              >
                {/* Dot */}
                <div
                  className="rounded-full transition-all duration-200"
                  style={{
                    width: isActive || isCurrent ? '14px' : '10px',
                    height: isActive || isCurrent ? '14px' : '10px',
                    background: isCurrent ? 'var(--forest)' : isActive ? 'var(--ember)' : 'var(--sky)',
                    border: isCurrent ? '2px solid white' : isActive ? '2px solid white' : '2px solid rgba(255,255,255,.3)',
                    boxShadow: isCurrent || isActive ? '0 2px 8px rgba(0,0,0,.3)' : 'none',
                  }}
                />

                {/* Type */}
                <span className="label" style={{ fontSize: '8px', color: isActive ? 'var(--ember)' : 'var(--dim)' }}>
                  {getStopTypeLabel(stop.stop_type)}
                </span>

                {/* Label */}
                <span
                  className="text-center leading-tight"
                  style={{
                    fontFamily: 'var(--mono)',
                    fontSize: '9px',
                    letterSpacing: '0.04em',
                    color: isActive ? 'var(--ember)' : 'var(--muted)',
                    maxWidth: '64px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {stop.title?.length > 12 ? stop.title.slice(0, 12) + '…' : stop.title}
                </span>

                {/* Date */}
                <span
                  style={{
                    fontFamily: 'var(--mono)',
                    fontSize: '8px',
                    color: 'var(--dim)',
                  }}
                >
                  {formatDate(stop.start_date)}
                </span>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
