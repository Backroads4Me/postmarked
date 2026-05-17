import { useEffect, useRef, useState } from "react";

const DRAFT_KEY = "goodpath:draft:quick-post";
const TUS_VERSION = "1.0.0";

const ACTIVITY_TYPES = [
  { value: "hiking", label: "Hiking" },
  { value: "museum", label: "Museum" },
  { value: "restaurant", label: "Restaurant" },
  { value: "attraction", label: "Attraction" },
  { value: "service", label: "Service" },
  { value: "scenic_drive", label: "Scenic Drive" },
  { value: "shopping", label: "Shopping" },
  { value: "family", label: "Family" },
  { value: "other", label: "Other" },
];

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

export default function QuickPostIsland() {
  const [postType, setPostType] = useState("update");
  const [stops, setStops] = useState([]);
  const [currentStopId, setCurrentStopId] = useState("");
  const [stopId, setStopId] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [summary, setSummary] = useState("");
  const [visibility, setVisibility] = useState("public");
  const [activityType, setActivityType] = useState("other");
  const [activityStartedAt, setActivityStartedAt] = useState("");
  const [activityEndedAt, setActivityEndedAt] = useState("");
  const [pois, setPois] = useState([]);
  const [poiId, setPoiId] = useState("");

  const [photos, setPhotos] = useState([]);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

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

  // Load POIs when stop changes
  useEffect(() => {
    setPoiId("");
    setPois([]);
    if (!stopId) return;
    fetch(`/api/admin/stops/${stopId}/pois`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then(setPois)
      .catch(() => {});
  }, [stopId]);

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
        patchRes.headers.get("X-Goodpath-Asset-Id") || location.split("/").pop();

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

  async function publish() {
    if (!title.trim()) { setError("Title is required"); return; }
    if (postType === "activity" && !activityStartedAt) {
      setError("Activity date/time is required");
      return;
    }
    const pending = photos.filter((p) => p.status === "uploading" || p.status === "queued");
    if (pending.length > 0) { setError("Wait for photo uploads to finish"); return; }

    setPublishing(true);
    setError(null);
    try {
      const mediaIds = photos.filter((p) => p.status === "done" && p.mediaId).map((p) => p.mediaId);
      const payload = {
        title: title.trim(),
        body: body.trim() || null,
        stop_id: stopId || null,
        visibility,
        media_ids: mediaIds,
        post_type: postType,
      };
      if (postType === "activity") {
        payload.activity_type = activityType;
        payload.summary = summary.trim() || null;
        payload.activity_started_at = activityStartedAt || null;
        payload.activity_ended_at = activityEndedAt || null;
        payload.poi_id = poiId || null;
      }
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

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {error && (
        <div className="card-flat" style={{ padding: 12, fontSize: 13, color: "var(--ember)" }}>
          {error}
        </div>
      )}

      {/* Mode selector */}
      <div style={{ display: "flex", gap: 8 }}>
        {["update", "activity"].map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setPostType(t)}
            style={{
              padding: "8px 18px",
              borderRadius: 6,
              border: "1px solid var(--line)",
              background: postType === t ? "var(--ember)" : "var(--surface-2)",
              color: postType === t ? "#fff" : "var(--muted)",
              fontSize: 13,
              fontWeight: postType === t ? 600 : 400,
              cursor: "pointer",
            }}
          >
            {t === "update" ? "Quick Update" : "Activity"}
          </button>
        ))}
      </div>

      <div>
        <label className="label" htmlFor="qp-title">Title</label>
        <input
          id="qp-title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={200}
          placeholder={postType === "activity" ? "What did you do?" : "Quick note from the road"}
          autoComplete="off"
          style={{ ...inputStyle, fontSize: 16, padding: "12px 14px" }}
        />
      </div>

      {postType === "activity" && (
        <div>
          <label className="label" htmlFor="qp-summary">Summary (short card text)</label>
          <input
            id="qp-summary"
            type="text"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            maxLength={500}
            placeholder="One-line description for the activity card"
            style={inputStyle}
          />
        </div>
      )}

      <div>
        <label className="label" htmlFor="qp-body">
          {postType === "activity" ? "Details (markdown)" : "Body (markdown)"}
        </label>
        <textarea
          id="qp-body"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={6}
          maxLength={10000}
          placeholder={postType === "activity" ? "Tell the story..." : "What's happening?"}
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

      {postType === "activity" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <label className="label" htmlFor="qp-activity-type">Activity type</label>
            <select id="qp-activity-type" value={activityType} onChange={(e) => setActivityType(e.target.value)} style={inputStyle}>
              {ACTIVITY_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="qp-started-at">
              When <span style={{ color: "var(--ember)" }}>*</span>
            </label>
            <input
              id="qp-started-at"
              type="datetime-local"
              value={activityStartedAt}
              onChange={(e) => setActivityStartedAt(e.target.value)}
              style={inputStyle}
            />
          </div>
          <div>
            <label className="label" htmlFor="qp-ended-at">Ended at (optional)</label>
            <input
              id="qp-ended-at"
              type="datetime-local"
              value={activityEndedAt}
              onChange={(e) => setActivityEndedAt(e.target.value)}
              style={inputStyle}
            />
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <label className="label" htmlFor="qp-stop">Stop</label>
          <select id="qp-stop" value={stopId} onChange={(e) => setStopId(e.target.value)} style={inputStyle}>
            <option value="">No stop</option>
            {stops.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}{s.id === currentStopId ? "  (current)" : ""}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="qp-vis">Visibility</label>
          <select id="qp-vis" value={visibility} onChange={(e) => setVisibility(e.target.value)} style={inputStyle}>
            <option value="public">Public — family can see</option>
            <option value="private">Private — only admin</option>
          </select>
        </div>
      </div>

      {postType === "activity" && stopId && pois.length > 0 && (
        <div>
          <label className="label" htmlFor="qp-poi">Place (optional)</label>
          <select id="qp-poi" value={poiId} onChange={(e) => setPoiId(e.target.value)} style={inputStyle}>
            <option value="">No place linked</option>
            {pois.map((p) => (
              <option key={p.id} value={p.id}>{p.label} ({p.poi_type})</option>
            ))}
          </select>
        </div>
      )}

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
              setTitle(""); setBody(""); setSummary(""); setPhotos([]);
            }
          }}
          disabled={publishing}
        >
          Discard
        </button>
        <span className="label" style={{ marginLeft: "auto" }}>Draft autosaves</span>
      </div>
    </div>
  );
}
