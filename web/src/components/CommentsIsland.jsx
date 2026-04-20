import React, { useState, useEffect } from 'react';
import { useStore } from '@nanostores/react';
import { urlState } from '../stores/urlState';

// A dynamic sliding drawer for comments based on the selected stop_id
export default function CommentsIsland() {
  const state = useStore(urlState);
  const [isOpen, setIsOpen] = useState(false);
  const [comments, setComments] = useState([]);
  const [newComment, setNewComment] = useState('');
  const [loading, setLoading] = useState(false);

  const stopId = state.stop_id;

  // Auto-close if no stop is selected
  useEffect(() => {
    if (!stopId) setIsOpen(false);
  }, [stopId]);

  useEffect(() => {
    if (isOpen && stopId) {
      fetchComments();
    }
  }, [isOpen, stopId]);

  const fetchComments = async () => {
    try {
      const res = await fetch(`/api/social/comments/stop/${stopId}`);
      if (res.ok) {
        setComments(await res.json());
      }
    } catch (e) {
      console.error("Failed to load comments", e);
    }
  };

  const handlePost = async () => {
    if (!newComment.trim()) return;
    setLoading(true);
    try {
      const res = await fetch('/api/social/comments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entity_type: 'stop',
          entity_id: stopId,
          body_markdown: newComment
        })
      });
      if (res.ok) {
        setNewComment('');
        await fetchComments();
      } else {
        alert("Must be an approved user to comment.");
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (!stopId) return null;

  return (
    <>
      {/* Floating Toggle Button */}
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="fixed right-6 bottom-48 z-40 bg-surface-1 border border-line shadow-2xl rounded-full p-4 hover:border-ember hover:text-ember transition-colors"
      >
        <span className="font-mono text-xs uppercase tracking-widest flex items-center gap-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
          Discuss
        </span>
      </button>

      {/* Drawer */}
      <div className={`fixed top-0 right-0 bottom-0 w-full md:w-96 bg-surface-1 border-l border-line shadow-2xl z-50 transform transition-transform duration-300 flex flex-col ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}>
        
        <div className="flex justify-between items-center p-4 border-b border-line">
          <h3 className="font-bold text-lg">Sector Discussion</h3>
          <button onClick={() => setIsOpen(false)} className="text-dim hover:text-fg px-2 py-1 rounded">✕</button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6">
          {comments.length === 0 ? (
            <div className="text-center text-muted italic mt-10">No comments yet. Start the conversation!</div>
          ) : (
            comments.map(c => (
              <div key={c.id} className="text-sm">
                <div className="flex items-center gap-2 mb-1">
                  <div className="w-6 h-6 bg-surface-2 rounded-full border border-line"></div>
                  <span className="font-bold text-fg text-xs">{c.user_id.split('-')[0]}</span>
                  <span className="text-[10px] font-mono tracking-widest text-dim">{new Date(c.created_at).toLocaleDateString()}</span>
                </div>
                <div className="pl-8 text-muted">{c.body_markdown}</div>
              </div>
            ))
          )}
        </div>

        <div className="p-4 border-t border-line bg-surface-2">
          <textarea 
            className="w-full bg-surface-1 border border-line p-3 text-sm rounded outline-none focus:border-ember min-h-24 resize-none mb-3"
            placeholder="Share an insight or observation..."
            value={newComment}
            onChange={e => setNewComment(e.target.value)}
          ></textarea>
          <div className="flex justify-end">
            <button 
              className="btn btn-sm" 
              onClick={handlePost} 
              disabled={loading || !newComment.trim()}
            >
              {loading ? 'Posting...' : 'Post Reply'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
