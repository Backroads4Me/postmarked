import React, { useRef, useEffect } from 'react';
import { useStore } from '@nanostores/react';
import { urlState } from '../stores/urlState';

export default function TimelineIsland({ stops }) {
  const state = useStore(urlState);
  const scrollRef = useRef(null);

  // Group media globally into flat array mapping back to stop
  // Assuming stops eventually contain a .media array from backend
  const flatItems = [];
  stops?.forEach(stop => {
    // Add Stop header
    flatItems.push({ type: 'stop', stop });
    // Add media if present
    if (stop.media) {
      stop.media.forEach(m => flatItems.push({ type: 'media', item: m, stop }));
    }
  });

  const handleMediaClick = (media_id) => {
    urlState.set({ ...urlState.get(), media_id });
  };

  const handleStopClick = (stop_id) => {
    // We could pan the map explicitly here, but URL state will trigger it anyway if we persist stop's coords
    urlState.set({ ...urlState.get(), stop_id, media_id: null });
  };

  return (
    <div className="w-full h-full flex flex-col bg-surface-1 border-t border-line overflow-hidden">
      <div className="px-4 py-3 text-xs font-mono tracking-widest text-dim border-b border-line flex justify-between">
        <span>TIMELINE</span>
        <span>{flatItems.filter(i => i.type === 'media').length} ASSETS</span>
      </div>
      
      <div 
        ref={scrollRef}
        className="flex-1 overflow-x-auto overflow-y-hidden flex items-center px-4 gap-4"
        style={{ scrollBehavior: 'smooth' }}
      >
        {flatItems.length === 0 && (
          <div className="text-muted text-sm italic">No stops recorded</div>
        )}
        
        {flatItems.map((entry, idx) => {
          if (entry.type === 'stop') {
            const isActive = state.stop_id === entry.stop.id;
            return (
              <div 
                key={`stop-${entry.stop.id}`} 
                onClick={() => handleStopClick(entry.stop.id)}
                className={`flex-shrink-0 h-32 w-12 flex items-center justify-center border-l-2 cursor-pointer transition-colors ${isActive ? 'border-ember text-ember' : 'border-line text-dim hover:text-fg hover:border-fg'}`}
              >
                <div className="rotate-180" style={{ writingMode: 'vertical-rl' }}>
                  <span className="font-mono text-xs uppercase tracking-widest">{new Date(entry.stop.start_date).toLocaleDateString(undefined, {month:'short', day:'numeric'})}</span>
                </div>
              </div>
            )
          } else {
            const m = entry.item;
            const isActive = state.media_id === m.id;
            return (
              <div 
                key={`media-${m.id}`}
                onClick={() => handleMediaClick(m.id)}
                className={`flex-shrink-0 h-40 aspect-[4/3] bg-surface-2 rounded overflow-hidden cursor-pointer border-2 transition-colors ${isActive ? 'border-ember' : 'border-transparent hover:border-line'}`}
              >
                {m.derivative_paths?.webp || m.derivative_paths?.poster ? (
                 <img src={m.derivative_paths.webp || m.derivative_paths.poster} className="w-full h-full object-cover" />
                ) : (
                  <div className="flex items-center justify-center w-full h-full text-xs text-dim uppercase">
                    {m.processing_state}
                  </div>
                )}
              </div>
            )
          }
        })}
      </div>
    </div>
  );
}
