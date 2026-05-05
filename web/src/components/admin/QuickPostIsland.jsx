import { useEffect, useRef, useState } from "react";

const DRAFT_KEY = "goodpath:draft:quick-post";
const TUS_VERSION = "1.0.0";

/**
 * Quick Post composer — designed for one-handed use from a phone on the road.
 *
 * Flow:
 *   1. Pick stop (defaults to currently-marked stop)
 *   2. Type title (required) + body (markdown ok)
 *   3. Optionally attach photos — each is uploaded via TUS to
 *      /api/admin/media/tus, returning a MediaAsset id
 *   4. Publish → POST /api/admin/posts with {title, body, stop_id, media_ids}
 *
 * Body autosaves to localStorage so an interrupted session doesn't lose work.
 */
export default function QuickPostIsland() {
  const [stops, setStops] = useState([]);
  const [currentStopId, setCurrentStopId] = useState("");
  const [stopId, setStopId] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState("public");

  const [photos, setPhotos] = useState([]); // { localId, name, status: 'queued'|'uploading'|'done'|'error', progress, mediaId, error }
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  // Load stops + current, hydrate draft.
  useEffect(() => {
    (async () => {
      try {
        const [stopsRes, currentRes] = await Promise.all([
          fetch("/api/admin/stops", { credentials: "include" }),
          fetch("/api/admin/current-stop", { credentials: "include" }),
        ]);
        const stopsBody = stopsRes.ok ? await stopsRes.json() : [];
        const currentBody = currentRes.ok ? await currentRes.json() : { current_stop: null };
        stopsBody.sort((a, b) => new Date(b.start_date) - new Date(a.start_date));
        setStops(stopsBody);
        const cur = currentBody.current_stop?.id ?? "";
        setCurrentStopId(cur);
        setStopId(cur);
      } catch (e) {
        setError("Failed to load stops");
      }
    })();

    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (raw) {
        const draft = JSON.parse(raw);
        if (draft.title) setTitle(draft.title);
        if (draft.body) setBody(draft.body);
      }
    } catch {}
  }, []);

  // Persist draft on body/title changes.
  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({ title, body }));
    } catch {}
  }, [title, body]);

  function clearDraft() {
    try {
      localStorage.removeItem(DRAFT_KEY);
    } catch {}
  }

  // ── TUS upload (single-shot, no resume — fine for <10MB phone photos) ──

  async function uploadOne(localId, file) {
    setPhotos((prev) => prev.map((p) => (p.localId === localId ? { ...p, status: "uploading" } : p)));
    try {
      const meta = `filename ${btoa(file.name)},filetype ${btoa(file.type || "application/octet-stream")}`;
      const createRes = await fetch("/api/admin/media/tus", {
        method: "POST",
        credentials: "include",
        headers: {
          "Tus-Resumable": TUS_VERSION,
          "Upload-Length": String(file.size),
          "Upload-Metadata": meta,
        },
      });
      if (!createRes.ok) throw new Error(`create: ${createRes.status}`);
      const location = createRes.headers.get("Location");
      if (!location) throw new Error("no Location header");

      const patchRes = await fetch(location, {
        method: "PATCH",
        credentials: "include",
        headers: {
          "Tus-Resumable": TUS_VERSION,
          "Upload-Offset": "0",
          "Content-Type": "application/offset+octet-stream",
        },
        body: file,
      });
      if (!patchRes.ok) throw new Error(`patch: ${patchRes.status}`);

      const assetId =
        patchRes.headers.get("X-Goodpath-Asset-Id") ||
        // location is /api/admin/media/tus/{file_id} — file_id == asset_id on success
        location.split("/").pop();

      setPhotos((prev) =>
        prev.map((p) => (p.localId === localId ? { ...p, status: "done", mediaId: assetId, progress: 100 } : p))
      );
    } catch (e) {
      setPhotos((prev) =>
        prev.map((p) => (p.localId === localId ? { ...p, status: "error", error: e.message || "upload failed" } : p))
      );
    }
  }

  function onFilesSelected(ev) {
    const files = Array.from(ev.target.files || []);
    const queued = files.map((f) => ({
      localId: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      name: f.name,
      status: "queued",
      progress: 0,
      file: f,
    }));
    setPhotos((prev) => [...prev, ...queued]);
    queued.forEach((q) => uploadOne(q.localId, q.file));
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function removePhoto(localId) {
    setPhotos((prev) => prev.filter((p) => p.localId !== localId));
  }

  // ── Publish ─────────────────────────────────────────────────────────

  async function publish() {
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    const pending = photos.filter((p) => p.status === "uploading" || p.status === "queued");
    if (pending.length > 0) {
      setError("Wait for photo uploads to finish");
      return;
    }
    setPublishing(true);
    setError(null);
    try {
      const mediaIds = photos.filter((p) => p.status === "done" && p.mediaId).map((p) => p.mediaId);
      const res = await fetch("/api/admin/posts", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          body: body.trim() || null,
          stop_id: stopId || null,
          visibility,
          media_ids: mediaIds,
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`HTTP ${res.status}: ${detail.slice(0, 160)}`);
      }
      clearDraft();
      window.location.href = "/admin/posts";
    } catch (e) {
      setError(e.message || "Publish failed");
    } finally {
      setPublishing(false);
    }
  }

  const hasPendingUploads = photos.some((p) => p.status === "uploading" || p.status === "queued");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {error && (
        <div className="card-flat" style={{ padding: 12, fontSize: 13, color: "var(--ember)" }}>
          {error}
        </div>
      )}

      <div>
        <label className="label" htmlFor="qp-title">
          Title
        </label>
        <input
          id="qp-title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={200}
          placeholder="Quick note from the road"
          autoComplete="off"
          style={{
            width: "100%",
            padding: "12px 14px",
            background: "var(--surface-2)",
            border: "1px solid var(--line)",
            borderRadius: 6,
            color: "var(--paper)",
            fontSize: 16,
            marginTop: 6,
          }}
        />
      </div>

      <div>
        <label className="label" htmlFor="qp-body">
          Body (markdown)
        </label>
        <textarea
          id="qp-body"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={6}
          maxLength={10000}
          placeholder="What's happening?"
          style={{
            width: "100%",
            padding: "12px 14px",
            background: "var(--surface-2)",
            border: "1px solid var(--line)",
            borderRadius: 6,
            color: "var(--paper)",
            fontSize: 15,
            fontFamily: "var(--sans)",
            marginTop: 6,
            resize: "vertical",
          }}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <label className="label" htmlFor="qp-stop">
            Stop
          </label>
          <select
            id="qp-stop"
            value={stopId}
            onChange={(e) => setStopId(e.target.value)}
            style={{
              width: "100%",
              padding: "10px 12px",
              background: "var(--surface-2)",
              border: "1px solid var(--line)",
              borderRadius: 6,
              color: "var(--paper)",
              fontSize: 14,
              marginTop: 6,
              minHeight: 44,
            }}
          >
            <option value="">No stop</option>
            {stops.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
                {s.id === currentStopId ? "  (current)" : ""}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="qp-vis">
            Visibility
          </label>
          <select
            id="qp-vis"
            value={visibility}
            onChange={(e) => setVisibility(e.target.value)}
            style={{
              width: "100%",
              padding: "10px 12px",
              background: "var(--surface-2)",
              border: "1px solid var(--line)",
              borderRadius: 6,
              color: "var(--paper)",
              fontSize: 14,
              marginTop: 6,
              minHeight: 44,
            }}
          >
            <option value="public">Public — family can see</option>
            <option value="private">Private — only admin</option>
          </select>
        </div>
      </div>

      <div>
        <label className="label">Photos</label>
        <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 8 }}>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,video/*"
            multiple
            onChange={onFilesSelected}
            style={{
              padding: 10,
              background: "var(--surface-2)",
              border: "1px dashed var(--line)",
              borderRadius: 6,
              color: "var(--muted)",
              fontSize: 13,
            }}
          />
          {photos.length > 0 && (
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 4 }}>
              {photos.map((p) => (
                <li
                  key={p.localId}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "8px 12px",
                    border: "1px solid var(--line-soft)",
                    borderRadius: 4,
                    fontSize: 13,
                  }}
                >
                  <span style={{ flex: 1, color: "var(--paper)", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {p.name}
                  </span>
                  <span
                    className="label"
                    style={{
                      color:
                        p.status === "done"
                          ? "var(--ok, #4ade80)"
                          : p.status === "error"
                          ? "var(--ember)"
                          : "var(--muted)",
                    }}
                  >
                    {p.status}
                    {p.error ? `: ${p.error}` : ""}
                  </span>
                  <button
                    type="button"
                    className="btn btn-sm btn-ghost"
                    onClick={() => removePhoto(p.localId)}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button
          type="button"
          className="btn btn-primary"
          onClick={publish}
          disabled={publishing || hasPendingUploads || !title.trim()}
          style={{ minHeight: 44, paddingInline: 24 }}
        >
          {publishing ? "Publishing…" : "Publish"}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => {
            if (confirm("Discard this draft?")) {
              clearDraft();
              setTitle("");
              setBody("");
              setPhotos([]);
            }
          }}
          disabled={publishing}
        >
          Discard
        </button>
        <span className="label" style={{ marginLeft: "auto" }}>
          Draft autosaves
        </span>
      </div>
    </div>
  );
}
