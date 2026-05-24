import { useEffect, useState } from "react";

/**
 * Inline comments section for a target (Stop, Post, or Media).
 *
 * Mounts directly on the target page (no slide-out drawer). The owner gets
 * post-as-admin; anonymous viewers see comments but can't post.
 *
 * Props:
 *   targetKind   "stop" | "post" | "media"
 *   targetId     uuid string
 */
export default function CommentsIsland({ targetKind, targetId }) {
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState("");
  const [posting, setPosting] = useState(false);
  const [postError, setPostError] = useState(null);
  const [viewer, setViewer] = useState(undefined);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/social/comments/${encodeURIComponent(targetKind)}/${encodeURIComponent(targetId)}`,
        { credentials: "include" }
      );
      if (res.status === 404) {
        setComments([]);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      setComments(Array.isArray(body) ? body : []);
    } catch (e) {
      setError(e.message || "Failed to load comments");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (targetId) load();
  }, [targetId, targetKind]);

  useEffect(() => {
    async function loadViewer() {
      try {
        const res = await fetch("/api/users/me", { credentials: "include" });
        if (res.status === 401 || res.status === 403) {
          setViewer(null);
          return;
        }
        if (!res.ok) {
          setViewer(null);
          return;
        }
        setViewer(await res.json());
      } catch {
        setViewer(null);
      }
    }

    loadViewer();
  }, []);

  async function submit(ev) {
    ev.preventDefault();
    if (!draft.trim()) return;
    setPosting(true);
    setPostError(null);
    try {
      const res = await fetch("/api/social/comments", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_kind: targetKind,
          target_id: targetId,
          body: draft.trim(),
        }),
      });
      if (res.status === 401 || res.status === 403) {
        throw new Error("Sign in (or get approved) to comment.");
      }
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`HTTP ${res.status}: ${detail.slice(0, 120)}`);
      }
      setDraft("");
      await load();
    } catch (e) {
      setPostError(e.message || "Failed to post");
    } finally {
      setPosting(false);
    }
  }

  function fmt(d) {
    try {
      return new Date(d).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
    } catch {
      return d || "";
    }
  }

  const viewerIsApproved =
    viewer?.role === "admin" || viewer?.approval_state === "approved";
  const authKnown = viewer !== undefined;
  const canComment = Boolean(viewerIsApproved);
  const disabledReason =
    authKnown && !viewer
      ? "Sign in with an approved account to leave a comment."
      : authKnown && viewer && !viewerIsApproved
        ? "Your account is pending approval before you can comment."
        : "";
  const nextPath =
    typeof window === "undefined"
      ? ""
      : `${window.location.pathname}${window.location.search}`;
  const loginHref = `/auth/login${nextPath ? `?next=${encodeURIComponent(nextPath)}` : ""}`;

  return (
    <section
      style={{ display: "flex", flexDirection: "column", gap: 16 }}
      aria-label="Comments"
    >
      <header style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <h2 className="display" style={{ fontSize: 22, margin: 0 }}>
          Comments
        </h2>
        <span className="label">
          {comments.length} {comments.length === 1 ? "comment" : "comments"}
        </span>
      </header>

      {loading && <div className="label">Loading…</div>}
      {error && (
        <div className="card-flat" style={{ padding: 12, fontSize: 13, color: "var(--ember)" }}>
          {error}
        </div>
      )}

      {comments.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 12 }}>
          {comments.map((c) => (
            <li
              key={c.id}
              className="card-flat"
              style={{ padding: 12, display: "flex", flexDirection: "column", gap: 6 }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                <span style={{ color: "var(--paper)", fontWeight: 500 }}>
                  {c.author_display_name || "anon"}
                </span>
                <span className="label" style={{ whiteSpace: "nowrap" }}>
                  {fmt(c.created_at)}
                </span>
              </div>
              <p style={{ margin: 0, color: "var(--paper-2)", whiteSpace: "pre-wrap", fontSize: 14 }}>
                {c.body}
              </p>
            </li>
          ))}
        </ul>
      )}

      {!authKnown && <div className="label">Checking comment permissions…</div>}

      {authKnown && !canComment && (
        <div className="card-flat" style={{ padding: 12, fontSize: 13, color: "var(--muted)", display: "flex", flexDirection: "column", gap: 10 }}>
          <div>{disabledReason}</div>
          {!viewer && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <a className="btn btn-sm" href={loginHref}>Sign in</a>
              <a className="btn btn-sm btn-ghost" href="/auth/register">Register</a>
            </div>
          )}
        </div>
      )}

      {authKnown && canComment && (
        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <label htmlFor={`comment-${targetId}`} className="label">
            Add a comment
          </label>
          <textarea
            id={`comment-${targetId}`}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
            maxLength={2000}
            placeholder="Share a note…"
            style={{
              width: "100%",
              padding: "10px 12px",
              background: "var(--surface-2)",
              border: "1px solid var(--line)",
              borderRadius: 6,
              color: "var(--paper)",
              fontSize: 14,
              fontFamily: "var(--sans)",
              resize: "vertical",
            }}
          />
          {postError && (
            <div style={{ fontSize: 12, color: "var(--ember)" }}>{postError}</div>
          )}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="label">{draft.length}/2000</span>
            <button
              type="submit"
              className="btn"
              disabled={posting || !draft.trim()}
              style={{ minHeight: 36 }}
            >
              {posting ? "Posting…" : "Post comment"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
