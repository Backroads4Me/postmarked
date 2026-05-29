import { useState, useEffect } from "react";

/**
 * Inline like button for a target (Stop, Post, or Media).
 *
 * Props:
 *   targetKind   "stop" | "post" | "media"
 *   targetId     uuid string
 */
export default function LikesIsland({ targetKind, targetId }) {
  const [count, setCount] = useState(null);
  const [liked, setLiked] = useState(null);
  const [viewer, setViewer] = useState(undefined);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadViewer() {
      try {
        const res = await fetch("/api/users/me", { credentials: "include" });
        if (res.ok) setViewer(await res.json());
        else setViewer(null);
      } catch {
        setViewer(null);
      }
    }
    loadViewer();
  }, []);

  useEffect(() => {
    async function loadStatus() {
      try {
        const res = await fetch(
          `/api/social/likes/${encodeURIComponent(targetKind)}/${encodeURIComponent(targetId)}/status`,
          { credentials: "include" }
        );
        if (res.ok) {
          const data = await res.json();
          setCount(data.count);
          setLiked(data.liked);
        }
      } catch {}
    }
    if (targetId) loadStatus();
  }, [targetId, targetKind]);

  async function toggle() {
    if (loading) return;
    setLoading(true);
    try {
      const res = await fetch("/api/social/likes", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_kind: targetKind, target_id: targetId }),
      });
      if (res.ok) {
        const data = await res.json();
        setLiked(data.liked);
        setCount((c) => (data.liked ? c + 1 : c - 1));
      }
    } catch {}
    finally {
      setLoading(false);
    }
  }

  const viewerIsApproved =
    viewer?.role === "admin" || viewer?.approval_state === "approved";
  const canLike = Boolean(viewerIsApproved);

  return (
    <button
      onClick={canLike ? toggle : undefined}
      disabled={loading}
      title={
        !viewer
          ? "Sign in to like"
          : !viewerIsApproved
            ? "Account pending approval"
            : liked
              ? "Unlike"
              : "Like"
      }
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        background: "none",
        border: "2px solid",
        borderRadius: 20,
        padding: "4px 12px",
        cursor: canLike ? "pointer" : "default",
        color: (count > 0) ? "var(--ember)" : "var(--paper)",
        fontSize: 13,
        fontWeight: 500,
        transition: "color 0.15s, border-color 0.15s",
        borderColor: (count > 0) ? "var(--ember)" : "var(--line)",
      }}
    >
      <span style={{ fontSize: 16, lineHeight: 1 }}>{liked ? "♥" : "♡"}</span>
      {count !== null && <span>{count}</span>}
    </button>
  );
}
