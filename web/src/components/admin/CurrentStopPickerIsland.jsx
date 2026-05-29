import { useEffect, useState } from "react";

/**
 * Admin hero widget: shows where the rig is right now, lets the owner change
 * it in two taps. Mobile-first — full-width controls, big touch targets.
 *
 * Backed by:
 *   GET  /api/admin/stops               (list candidates)
 *   GET  /api/admin/current-stop        (read current)
 *   POST /api/admin/current-stop        (update)
 *
 * Origin/CSRF middleware enforces same-origin POSTs; cookies are sent
 * automatically same-origin.
 */
export default function CurrentStopPickerIsland() {
  const [stops, setStops] = useState([]);
  const [current, setCurrent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [picking, setPicking] = useState(false);
  const [saving, setSaving] = useState(null);
  const [error, setError] = useState(null);

  async function refresh() {
    setError(null);
    try {
      const [stopsRes, currentRes] = await Promise.all([
        fetch("/api/admin/stops", { credentials: "include" }),
        fetch("/api/admin/current-stop", { credentials: "include" }),
      ]);
      if (!stopsRes.ok) throw new Error(`stops: ${stopsRes.status}`);
      if (!currentRes.ok) throw new Error(`current: ${currentRes.status}`);
      const stopsBody = await stopsRes.json();
      const currentBody = await currentRes.json();
      // Newest first.
      stopsBody.sort((a, b) => new Date(b.start_date) - new Date(a.start_date));
      setStops(stopsBody);
      setCurrent(currentBody.current_stop ?? null);
    } catch (e) {
      setError(e.message || "Failed to load stops");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function setCurrentStop(stopId) {
    setSaving(stopId);
    setError(null);
    try {
      const res = await fetch("/api/admin/current-stop", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stop_id: stopId }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`HTTP ${res.status}: ${detail.slice(0, 120)}`);
      }
      const body = await res.json();
      setCurrent(body.current_stop ?? null);
      setPicking(false);
    } catch (e) {
      setError(e.message || "Failed to set current stop");
    } finally {
      setSaving(null);
    }
  }

  if (loading) {
    return (
      <div className="card" style={{ minHeight: 120 }}>
        <span className="label">Loading current location…</span>
      </div>
    );
  }

  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span className="pulse-dot" />
        <span className="eyebrow">Current Stop</span>
      </div>

      {current ? (
        <>
          <h2 className="display" style={{ fontSize: 28, margin: 0 }}>
            {current.title}
          </h2>
        </>
      ) : (
        <p className="text-muted" style={{ margin: 0 }}>
          No stop is marked as current yet.
        </p>
      )}

      {error && (
        <div className="card-flat" style={{ padding: 10, fontSize: 13, color: "var(--ember)" }}>
          {error}
        </div>
      )}

      {!picking ? (
        <button
          type="button"
          className="btn"
          style={{ alignSelf: "flex-start" }}
          onClick={() => setPicking(true)}
          disabled={stops.length === 0}
        >
          {current ? "Change" : "Set current stop"}
        </button>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span className="label">Pick a stop</span>
            <button
              type="button"
              className="btn btn-sm btn-ghost"
              onClick={() => setPicking(false)}
            >
              Cancel
            </button>
          </div>
          <div
            style={{
              maxHeight: 320,
              overflowY: "auto",
              border: "1px solid var(--line)",
              borderRadius: 6,
            }}
          >
            {stops.map((s) => {
              const isCurrent = current && s.id === current.id;
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => !isCurrent && setCurrentStop(s.id)}
                  disabled={isCurrent || saving !== null}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    padding: "12px 14px",
                    background: isCurrent ? "var(--ember-glow)" : "transparent",
                    borderBottom: "1px solid var(--line-soft)",
                    color: "var(--paper)",
                    cursor: isCurrent ? "default" : "pointer",
                    minHeight: 44,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                    <span style={{ fontWeight: 500 }}>
                      {s.title}
                      {isCurrent && (
                        <span className="badge badge-active" style={{ marginLeft: 8, fontSize: 10 }}>
                          current
                        </span>
                      )}
                    </span>
                    <span className="label" style={{ whiteSpace: "nowrap" }}>
                      {s.start_date
                        ? new Date(s.start_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })
                        : ""}
                    </span>
                  </div>
                  {s.place_name && (
                    <div className="coord" style={{ marginTop: 2 }}>
                      {s.place_name}
                    </div>
                  )}
                  {saving === s.id && (
                    <div className="label" style={{ marginTop: 4 }}>
                      Saving…
                    </div>
                  )}
                </button>
              );
            })}
            {stops.length === 0 && (
              <div style={{ padding: 14, color: "var(--dim)", fontSize: 13 }}>
                No stops to choose from yet.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
