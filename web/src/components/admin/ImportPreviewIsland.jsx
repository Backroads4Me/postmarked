import React, { useState, useCallback } from 'react';

/**
 * ImportPreviewIsland — Interactive import preview and diff table.
 * Handles file upload, preview display, and apply confirmation.
 */
export default function ImportPreviewIsland() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [applied, setApplied] = useState(false);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setPreview(null);
    setError(null);
    setApplied(false);
  };

  const handlePreview = useCallback(async () => {
    if (!file) return;
    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`/api/admin/imports/rv-trip-wizard/preview`, {
        method: 'POST',
        body: formData,
        credentials: 'include',
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Upload failed (${res.status})`);
      }

      const data = await res.json();
      setPreview(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [file]);

  const handleApply = useCallback(async () => {
    if (!preview) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/admin/imports/${preview.import_run_id}/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ create_trip: true }),
        credentials: 'include',
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Apply failed (${res.status})`);
      }

      const data = await res.json();
      setApplied(true);
      setPreview(prev => ({ ...prev, appliedResult: data }));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [preview]);

  function statusColor(status) {
    const map = {
      added: 'var(--forest)',
      unchanged: 'var(--muted)',
      changed: 'var(--ember)',
      removed: 'var(--sunset)',
      needs_review: 'var(--postcard-yellow)',
    };
    return map[status] || 'var(--muted)';
  }

  function statusIcon(status) {
    const map = {
      added: '＋',
      unchanged: '＝',
      changed: '△',
      removed: '✕',
      needs_review: '⚠',
    };
    return map[status] || '?';
  }

  return (
    <div>

      {/* File Upload */}
      <div className="card-flat" style={{ marginBottom: '24px' }}>
        <div className="flex flex-col md:flex-row md:items-center gap-3">
          <label
            className="btn cursor-pointer"
            style={{ position: 'relative', overflow: 'hidden', flexShrink: 0 }}
          >
            <input
              type="file"
              accept=".xlsx"
              onChange={handleFileChange}
              style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer' }}
            />
            Choose .xlsx File
          </label>

          <div className="flex min-w-0 flex-1 items-center gap-2">
            <span className="text-lg" aria-hidden="true">📄</span>
            <span className="eyebrow whitespace-nowrap">RV Trip Wizard export file</span>
            {file && (
              <span className="truncate" style={{ color: 'var(--paper-2)', fontSize: '14px' }}>
                {file.name} ({(file.size / 1024).toFixed(1)} KB)
              </span>
            )}
          </div>

          {file && !preview && (
            <button
              className="btn btn-primary"
              onClick={handlePreview}
              disabled={loading}
            >
              {loading ? 'Parsing...' : 'Preview Import'}
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-danger mb-6">
          <span>! {error}</span>
        </div>
      )}

      {/* Preview Results */}
      {preview && (
        <div>
          {/* Summary header */}
          <div className="card" style={{ marginBottom: '16px' }}>
            <div className="flex items-center gap-3 mb-3">
              <span className="text-xl">🗺️</span>
              <div>
                <h3 className="text-lg font-semibold" style={{ color: 'var(--paper)' }}>
                  {preview.trip_title}
                </h3>
                {preview.start_date && (
                  <p className="coord">{preview.start_date}</p>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <span className="badge badge-active">
                {preview.summary?.added || 0} New
              </span>
              <span className="badge">
                {preview.summary?.unchanged || 0} Unchanged
              </span>
              <span className="badge badge-ember">
                {preview.summary?.changed || 0} Changed
              </span>
              <span className="badge badge-private">
                {preview.summary?.removed || 0} Removed
              </span>
            </div>

            {preview.warnings?.length > 0 && (
              <div className="mt-3">
                {preview.warnings.map((w, i) => (
                  <p key={i} style={{ color: 'var(--sunset)', fontSize: '13px' }}>⚠ {w}</p>
                ))}
              </div>
            )}
          </div>

          {/* Diff table */}
          <div className="card-flat" style={{ padding: 0, overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: '760px', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr>
                  <th className="table-header text-center">#</th>
                  <th className="table-header text-center">Status</th>
                  <th className="table-header">Stop Name</th>
                  <th className="table-header text-center">Arrival</th>
                  <th className="table-header text-center">Departure</th>
                  <th className="table-header text-center">Nights</th>
                  <th className="table-header text-center">Miles</th>
                  <th className="table-header">Changes</th>
                </tr>
              </thead>
              <tbody>
                {preview.diff?.map((item, idx) => (
                  <tr
                    key={idx}
                    style={{
                      borderBottom: '1px solid var(--line-soft)',
                      background: item.is_dangerous ? 'color-mix(in srgb, var(--sunset) 8%, transparent)' : 'transparent',
                    }}
                  >
                    <td className="table-cell text-center">{item.sequence}</td>
                    <td className="table-cell text-center">
                      <span
                        style={{
                          color: statusColor(item.status),
                          fontFamily: 'var(--mono)',
                          fontSize: '11px',
                          fontWeight: 600,
                        }}
                      >
                        {statusIcon(item.status)} {item.status}
                      </span>
                    </td>
                    <td className="table-cell" style={{ color: 'var(--paper)' }}>
                      {item.name}
                      {item.is_dangerous && (
                        <span className="badge badge-sm badge-private" style={{ marginLeft: '4px' }}>
                          ⚠ linked
                        </span>
                      )}
                    </td>
                    <td className="table-cell text-center">{item.arrival_date || '—'}</td>
                    <td className="table-cell text-center">{item.departure_date || '—'}</td>
                    <td className="table-cell text-center">{item.nights ?? '—'}</td>
                    <td className="table-cell text-center">{item.miles?.toFixed(1) || '—'}</td>
                    <td className="table-cell text-xs">
                      {item.changes?.length > 0
                        ? item.changes.join(', ')
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Apply button */}
          {!applied && (
            <div className="flex justify-end mt-4 gap-3">
              <button
                className="btn"
                onClick={() => { setPreview(null); setFile(null); }}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleApply}
                disabled={loading}
              >
                {loading ? 'Applying...' : `Create Draft Trip (${preview.parsed_stop_count} stops)`}
              </button>
            </div>
          )}

          {/* Applied confirmation */}
          {applied && preview.appliedResult && (
            <div className="card" style={{ marginTop: '16px', borderColor: 'color-mix(in srgb, var(--forest) 32%, transparent)' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xl">✅</span>
                <span style={{ color: 'var(--forest)', fontWeight: 600 }}>Import Applied Successfully</span>
              </div>
              <p style={{ color: 'var(--muted)', fontSize: '14px' }}>
                Draft trip: <a href={`/admin/trips/${preview.appliedResult.trip_id}`} style={{ color: 'var(--ember)' }}>
                  {preview.trip_title}
                </a>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
