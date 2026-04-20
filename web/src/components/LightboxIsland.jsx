import React, { useEffect, useState } from 'react';
import { useStore } from '@nanostores/react';
import { urlState } from '../stores/urlState';

export default function LightboxIsland({ stops }) {
  const state = useStore(urlState);
  
  if (!state.media_id) return null;

  // Flatten media to find the active one and it's neighbors for arrow keys
  const allMedia = stops?.flatMap(s => s.media || []) || [];
  const currentIndex = allMedia.findIndex(m => m.id === state.media_id);
  const activeMedia = allMedia[currentIndex];

  const handleClose = () => {
    urlState.set({ ...urlState.get(), media_id: null });
  };

  const handlePrev = (e) => {
    e.stopPropagation();
    if (currentIndex > 0) {
      urlState.set({ ...urlState.get(), media_id: allMedia[currentIndex - 1].id });
    }
  };

  const handleNext = (e) => {
    e.stopPropagation();
    if (currentIndex < allMedia.length - 1) {
      urlState.set({ ...urlState.get(), media_id: allMedia[currentIndex + 1].id });
    }
  };

  // Bind Esc and Arrow keys
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') handleClose();
      if (e.key === 'ArrowLeft') handlePrev(e);
      if (e.key === 'ArrowRight') handleNext(e);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  if (!activeMedia) return null;

  return (
    <div className="fixed inset-0 z-50 bg-bg/95 backdrop-blur-sm flex items-center justify-center" onClick={handleClose}>
      
      {/* Top Bar */}
      <div className="absolute top-0 left-0 right-0 p-4 flex justify-between items-center bg-gradient-to-b from-black/50 to-transparent">
        <div className="font-mono text-xs tracking-widest uppercase text-dim">
          {currentIndex + 1} / {allMedia.length}
        </div>
        <button onClick={handleClose} className="text-fg hover:text-ember cursor-pointer font-mono tracking-widest text-xs uppercase p-2">Close ✕</button>
      </div>

      {/* Media Rendering */}
      <div className="relative max-w-7xl w-full max-h-[85vh] flex items-center justify-center p-8 pointer-events-none">
        
       {/* If we had original hi-res url mapping, we'd use it here. We'll use the highest res derivative we have. */}
       {activeMedia.derivative_paths?.webp ? (
          <img 
            src={activeMedia.derivative_paths.webp} 
            className="max-w-full max-h-full object-contain pointer-events-auto shadow-2xl rounded"
            onClick={(e) => e.stopPropagation()} 
          />
       ) : activeMedia.derivative_paths?.poster ? (
         // If video, render html5 video element. Assuming original_path mapping exists in a real scenario
         <video 
           controls 
           poster={activeMedia.derivative_paths.poster} 
           className="max-w-full max-h-full object-contain pointer-events-auto rounded shadow-2xl"
           onClick={e => e.stopPropagation()}
          >
            <source src={`/media/originals/${activeMedia.id}.bin`} />
         </video>
       ) : (
          <div className="text-muted">Loading asset...</div>
       )}

      </div>

      {/* Navigation Arrows */}
      {currentIndex > 0 && (
        <button className="absolute left-8 top-1/2 -translate-y-1/2 p-4 text-dim hover:text-fg focus:outline-none" onClick={handlePrev}>←</button>
      )}
      {currentIndex < allMedia.length - 1 && (
        <button className="absolute right-8 top-1/2 -translate-y-1/2 p-4 text-dim hover:text-fg focus:outline-none" onClick={handleNext}>→</button>
      )}
    </div>
  );
}
