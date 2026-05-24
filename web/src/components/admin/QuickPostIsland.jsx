import { useEffect, useRef, useState } from "react";
import { renderMarkdown } from "../../lib/markdown.js";

const DRAFT_KEY = "postmarked:draft:quick-post";
const TUS_VERSION = "1.0.0";

const inputStyle = {
  width: "100%",
  padding: "10px 12px",
  background: "var(--surface-2)",
  border: "1px solid var(--line)",
  borderRadius: 6,
  color: "var(--paper)",
  fontSize: 14,
  marginTop: 6,
  minHeight: 44,
};

function toDatetimeLocal(date = new Date()) {
  const offsetMs = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

export default function QuickPostIsland() {
  const [stops, setStops] = useState([]);
  const [trips, setTrips] = useState([]);
  const [currentStopId, setCurrentStopId] = useState("");
  const [stopId, setStopId] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [postedAt, setPostedAt] = useState(() => toDatetimeLocal());
  const [status, setStatus] = useState("draft");
  const [visibility, setVisibility] = useState("public");

  const [photos, setPhotos] = useState([]);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);
  const photoUrlsRef = useRef(new Set());

  useEffect(() => {
    (async () => {
      try {
        const [stopsRes, currentRes, tripsRes] = await Promise.all([
          fetch("/api/admin/stops", { credentials: "include" }),
          fetch("/api/admin/current-stop", { credentials: "include" }),
          fetch("/api/admin/trips", { credentials: "include" }),
        ]);
        const stopsBody = stopsRes.ok ? await stopsRes.json() : [];
        const currentBody = currentRes.ok ? await currentRes.json() : { current_stop: null };
        const tripsBody = tripsRes.ok ? await tripsRes.json() : [];
        stopsBody.sort((a, b) => new Date(b.start_date) - new Date(a.start_date));
        setStops(stopsBody);
        setTrips(tripsBody);
        const cur = currentBody.current_stop?.id ?? "";
        setCurrentStopId(cur);
        setStopId(cur);
        setVisibility(visibilityForStop(cur, stopsBody, tripsBody));
      } catch {
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

  function visibilityForStop(nextStopId, stopList = stops, tripList = trips) {
    if (!nextStopId) return "public";
    const stop = stopList.find((s) => s.id === nextStopId);
    if (!stop) return "public";
    const trip = tripList.find((t) => t.id === stop.trip_id);
    return trip?.visibility || "public";
  }

  function selectStop(nextStopId) {
    setStopId(nextStopId);
    setVisibility(visibilityForStop(nextStopId));
  }

  function formatStopOptionDate(value) {
    if (!value) return 'No date';
    try {
      return new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return 'No date';
    }
  }

  function stopOptionLabel(stop) {
    const date = formatStopOptionDate(stop.start_date);
    const current = stop.id === currentStopId ? ' (current)' : '';
    return date + ' - ' + stop.title + current;
  }


  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({ title, body }));
    } catch {}
  }, [title, body]);

  function clearDraft() {
    try { localStorage.removeItem(DRAFT_KEY); } catch {}
  }

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
        patchRes.headers.get("X-Postmarked-Asset-Id") || location.split("/").pop();

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
    const queued = files.map((f) => {
      const previewUrl = URL.createObjectURL(f);
      photoUrlsRef.current.add(previewUrl);
      return {
        localId: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: f.name,
        type: f.type,
        previewUrl,
        status: "queued",
        progress: 0,
        file: f,
      };
    });
    setPhotos((prev) => [...prev, ...queued]);
    queued.forEach((q) => uploadOne(q.localId, q.file));
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function removePhoto(localId) {
    setPhotos((prev) => {
      const removed = prev.find((p) => p.localId === localId);
      if (removed?.previewUrl) {
        URL.revokeObjectURL(removed.previewUrl);
        photoUrlsRef.current.delete(removed.previewUrl);
      }
      return prev.filter((p) => p.localId !== localId);
    });
  }

  function clearPhotos() {
    for (const url of photoUrlsRef.current) {
      URL.revokeObjectURL(url);
    }
    photoUrlsRef.current.clear();
    setPhotos([]);
  }

  useEffect(() => {
    return () => {
      for (const url of photoUrlsRef.current) {
        URL.revokeObjectURL(url);
      }
      photoUrlsRef.current.clear();
    };
  }, []);

  async function publish() {
    if (!title.trim()) { setError("Title is required"); return; }
    if (!postedAt) {
      setError("Post date is required");
      return;
    }
    const pending = photos.filter((p) => p.status === "uploading" || p.status === "queued");
    if (pending.length > 0) { setError("Wait for media uploads to finish"); return; }

    setPublishing(true);
    setError(null);
    try {
      const mediaIds = photos.filter((p) => p.status === "done" && p.mediaId).map((p) => p.mediaId);
      const payload = {
        title: title.trim(),
        body: body.trim() || null,
        stop_id: stopId || null,
        status,
        visibility,
        posted_at: new Date(postedAt).toISOString(),
        media_ids: mediaIds,
        post_type: "update",
      };
      const res = await fetch("/api/admin/posts", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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
  const selectedStop = stops.find((s) => s.id === stopId);
  const previewPhotos = photos.filter((p) => p.previewUrl).slice(0, 3);
  const previewBody = renderMarkdown(body.trim());
  const previewPlace = selectedStop?.place_name || selectedStop?.title || "";
  const previewDate = postedAt
    ? new Date(postedAt).toLocaleDateString("en-US", { month: "short", day: "numeric" })
    : "Today";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {error && (
        <div className="card-flat" style={{ padding: 12, fontSize: 13, color: "var(--ember)" }}>
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_18rem] gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-bold" htmlFor="qp-title">Title</label>
          <input
            id="qp-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            placeholder="Postcard from the road"
            autoComplete="off"
            className="bg-surface-2 border border-line p-3 focus:border-ember"
          />
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-sm font-bold" htmlFor="qp-posted-at">Post date</label>
          <input
            id="qp-posted-at"
            type="datetime-local"
            value={postedAt}
            onChange={(e) => setPostedAt(e.target.value)}
            className="bg-surface-2 border border-line p-3 focus:border-ember"
          />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-sm font-bold" htmlFor="qp-body">Body (markdown)</label>
        <textarea
          id="qp-body"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={8}
          maxLength={10000}
          placeholder="What do you want to share?"
          className="bg-surface-2 border border-line p-3 font-sans focus:border-ember"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_14rem_18rem] gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-bold" htmlFor="qp-stop">Stop</label>
          <select id="qp-stop" value={stopId} onChange={(e) => selectStop(e.target.value)} className="bg-surface-2 border border-line p-3">
            <option value="">No stop</option>
            {stops.map((s) => (
              <option key={s.id} value={s.id}>
                {stopOptionLabel(s)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-bold" htmlFor="qp-status">Status</label>
          <select id="qp-status" value={status} onChange={(e) => setStatus(e.target.value)} className="bg-surface-2 border border-line p-3">
            <option value="draft">Draft</option>
            <option value="published">Published</option>
            <option value="unpublished">Unpublished</option>
            <option value="archived">Archived</option>
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-bold" htmlFor="qp-vis">Visibility</label>
          <select id="qp-vis" value={visibility} onChange={(e) => setVisibility(e.target.value)} className="bg-surface-2 border border-line p-3">
            <option value="private">Private — logged-in users</option>
            <option value="public">Public — anyone</option>
          </select>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-sm font-bold">Media</label>
        <div className="flex flex-col gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,video/*"
            multiple
            onChange={onFilesSelected}
            className="bg-surface-2 border border-dashed border-line p-3 text-sm text-muted"
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
                      color: p.status === "done" ? "var(--ok, #4ade80)" : p.status === "error" ? "var(--ember)" : "var(--muted)",
                    }}
                  >
                    {p.status}{p.error ? `: ${p.error}` : ""}
                  </span>
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => removePhoto(p.localId)}>✕</button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <section style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12 }}>
          <h2 className="display" style={{ fontSize: 20, margin: 0 }}>Timeline preview</h2>
          <span className="label">{status} · {visibility}</span>
        </div>
        <article className="card-flat">
          <div className="flex items-center gap-2 mb-3">
            <span className="inline-symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M5 19h14"/><path d="m14 5 5 5"/><path d="M4 16.5 15.5 5 19 8.5 7.5 20H4v-3.5Z"/></svg>
            </span>
            <span className="eyebrow">Update</span>
            <span className="label" style={{ marginLeft: "auto" }}>{previewDate}</span>
          </div>

          <h3 className="text-lg font-medium text-paper mb-1">
            {title.trim() || "Untitled post"}
          </h3>

          {previewBody ? (
            <div
              className="post-preview-markdown text-muted text-sm leading-relaxed line-clamp-3"
              dangerouslySetInnerHTML={{ __html: previewBody }}
            />
          ) : (
            <p className="text-muted text-sm leading-relaxed line-clamp-3">
              Markdown preview appears here as you write.
            </p>
          )}

          {previewPhotos.length > 0 && (
            <div className="mt-3 flex flex-col gap-2 max-w-sm">
              {previewPhotos.map((p) => {
                const isVideo = p.type?.startsWith("video/");
                return isVideo ? (
                  <div key={p.localId} className="block bg-line-soft overflow-hidden rounded-md">
                    <video
                      src={p.previewUrl}
                      controls
                      muted
                      preload="metadata"
                      className="block max-w-full h-auto object-contain mx-auto"
                      style={{ maxHeight: previewPhotos.length === 1 ? "28rem" : "18rem" }}
                    />
                  </div>
                ) : (
                  <a
                    key={p.localId}
                    href={p.previewUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block bg-line-soft overflow-hidden rounded-md"
                  >
                    <img
                      src={p.previewUrl}
                      alt={p.name}
                      className="block max-w-full h-auto object-contain mx-auto"
                      style={{ maxHeight: previewPhotos.length === 1 ? "28rem" : "18rem" }}
                    />
                  </a>
                );
              })}
            </div>
          )}

          <div className="flex items-center gap-3 mt-3 text-xs">
            {previewPlace && <span className="coord">{previewPlace}</span>}
          </div>
        </article>
      </section>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button
          type="button"
          className="btn btn-primary"
          onClick={publish}
          disabled={publishing || hasPendingUploads || !title.trim()}
          style={{ minHeight: 44, paddingInline: 24 }}
        >
          {publishing ? "Saving…" : status === "published" ? "Publish Post" : "Save Post"}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => {
            if (confirm("Discard this draft?")) {
              clearDraft();
              setTitle(""); setBody(""); setPostedAt(toDatetimeLocal()); setStatus("draft"); setVisibility(visibilityForStop(stopId)); clearPhotos();
            }
          }}
          disabled={publishing}
        >
          Discard
        </button>
        <span className="label" style={{ marginLeft: "auto" }}>Draft autosaves</span>
      </div>
      <style>{`
        .post-preview-markdown p {
          margin: 0 0 0.45rem;
        }
        .post-preview-markdown p:last-child,
        .post-preview-markdown ul:last-child,
        .post-preview-markdown h3:last-child,
        .post-preview-markdown h4:last-child,
        .post-preview-markdown h5:last-child {
          margin-bottom: 0;
        }
        .post-preview-markdown h3,
        .post-preview-markdown h4,
        .post-preview-markdown h5 {
          color: var(--paper);
          font-size: 1rem;
          font-weight: 600;
          margin: 0.7rem 0 0.3rem;
        }
        .post-preview-markdown ul {
          list-style: disc;
          margin: 0.35rem 0 0.45rem 1.1rem;
          padding: 0;
        }
        .post-preview-markdown a {
          color: var(--ember);
          text-decoration: none;
        }
        .post-preview-markdown code {
          background: var(--surface-2);
          border: 1px solid var(--line-soft);
          border-radius: 4px;
          color: var(--paper);
          font-size: 0.85em;
          padding: 0.05rem 0.25rem;
        }
      `}</style>
    </div>
  );
}
