import React, { useState, useEffect } from 'react';

function formatDate(dateStr) {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch { return ''; }
}

export default function SearchIsland() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setIsOpen(o => !o);
      }
      if (e.key === 'Escape') setIsOpen(false);
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, []);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    
    const timeoutId = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        if (res.ok) {
          setResults(await res.json());
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [query]);

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="nav-link hidden md:inline-flex flex-row gap-1.5 text-xs"
      >
        <span className="nav-symbol">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
        </span>
        <span>Search</span>
      </button>
    );
  }

  return (
    <div className="fixed inset-x-0 bottom-0 z-50 flex items-start justify-center pt-8 bg-bg/80 backdrop-blur-sm" style={{ top: '56px' }} onClick={() => setIsOpen(false)}>
      <div className="w-full max-w-2xl bg-surface-1 border border-line rounded-lg shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex border-b border-line items-center px-4 py-3">
          <span className="text-muted mr-3">🔍</span>
          <input 
            autoFocus 
            type="text" 
            placeholder="Search trips and stops..." 
            className="flex-1 bg-transparent border-none outline-none text-lg text-fg"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button onClick={() => setIsOpen(false)} className="text-xs text-muted hover:text-fg font-mono uppercase tracking-widest bg-surface-2 px-2 py-1 rounded">Esc</button>
        </div>
        
        <div className="max-h-96 overflow-y-auto">
          {loading && <div className="p-8 text-center text-dim font-mono text-xs uppercase tracking-widest">Searching...</div>}
          
          {!loading && results.length > 0 && (
            <ul className="divide-y divide-line">
              {results.map(r => (
                <li key={`${r.entity_type}-${r.id}`}>
                  <a href={r.slug} className="block p-4 hover:bg-surface-2 transition-colors">
                    <div className="flex justify-between items-start mb-1">
                      <div className="flex flex-col gap-0.5">
                        <span className="font-bold text-fg">{r.title}</span>
                        {r.start_date && (
                          <span style={{ fontFamily: 'var(--mono)', fontSize: '9px', color: 'var(--dim)' }}>
                            {formatDate(r.start_date)}
                          </span>
                        )}
                      </div>
                      <span className="badge badge-sm">{r.entity_type}</span>
                    </div>
                    {r.summary && <div className="text-sm text-muted clamp-2">{r.summary}</div>}
                  </a>
                </li>
              ))}
            </ul>
          )}


          {!loading && query.length >= 2 && results.length === 0 && (
            <div className="p-8 text-center text-dim">No results found for "{query}"</div>
          )}
          
          {!loading && query.length < 2 && (
            <div className="p-8 text-center text-dim font-mono text-xs uppercase tracking-widest">Type to search the journal</div>
          )}
        </div>
      </div>
    </div>
  );
}
