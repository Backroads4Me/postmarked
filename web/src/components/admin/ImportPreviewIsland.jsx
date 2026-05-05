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
      added: '#4a9f6e',
      unchanged: '#9a9a9f',
      changed: '#e8893f',
      removed: '#d46b5c',
      needs_review: '#f4a663',
    };
    return map[status] || '#9a9a9f';
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
    <div style={{ fontFamily: 'var(--sans)' }}>

      {/* File Upload */}
      <div className="card-flat" style={{ marginBottom: '24px' }}>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-lg">📄</span>
          <span className="eyebrow">Upload Excel File</span>
        </div>

        <div className="flex flex-col md:flex-row items-start md:items-center gap-3">
          <label
            className="btn cursor-pointer"
            style={{ position: 'relative', overflow: 'hidden' }}
          >
            <input
              type="file"
              accept=".xlsx"
              onChange={handleFileChange}
              style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer' }}
            />
            Choose .xlsx File
          </label>

          {file && (
            <span style={{ color: 'var(--paper-2)', fontSize: '14px' }}>
              {file.name} ({(file.size / 1024).toFixed(1)} KB)
            </span>
          )}

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
        <div className="card-flat" style={{ borderColor: 'var(--sunset)', marginBottom: '24px' }}>
          <span style={{ color: 'var(--sunset)' }}>⚠ {error}</span>
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
              <span className="badge" style={{ background: 'rgba(74,159,110,.15)', color: '#4a9f6e', borderColor: 'rgba(74,159,110,.3)' }}>
                {preview.summary?.added || 0} New
              </span>
              <span className="badge">
                {preview.summary?.unchanged || 0} Unchanged
              </span>
              <span className="badge" style={{ background: 'var(--ember-glow)', color: 'var(--ember)', borderColor: 'rgba(232,137,63,.3)' }}>
                {preview.summary?.changed || 0} Changed
              </span>
              <span className="badge" style={{ background: 'rgba(212,107,92,.15)', color: '#d46b5c', borderColor: 'rgba(212,107,92,.3)' }}>
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
          <div className="card-flat" style={{ padding: 0, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--line)' }}>
                  <th style={thStyle}>#</th>
                  <th style={thStyle}>Status</th>
                  <th style={{ ...thStyle, textAlign: 'left' }}>Stop Name</th>
                  <th style={thStyle}>Arrival</th>
                  <th style={thStyle}>Departure</th>
                  <th style={thStyle}>Nights</th>
                  <th style={thStyle}>Miles</th>
                  <th style={{ ...thStyle, textAlign: 'left' }}>Changes</th>
                </tr>
              </thead>
              <tbody>
                {preview.diff?.map((item, idx) => (
                  <tr
                    key={idx}
                    style={{
                      borderBottom: '1px solid var(--line-soft)',
                      background: item.is_dangerous ? 'rgba(212,107,92,.08)' : 'transparent',
                    }}
                  >
                    <td style={tdStyle}>{item.sequence}</td>
                    <td style={tdStyle}>
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
                    <td style={{ ...tdStyle, textAlign: 'left', color: 'var(--paper)' }}>
                      {item.name}
                      {item.is_dangerous && (
                        <span style={{ color: 'var(--sunset)', fontSize: '10px', marginLeft: '4px' }}>
                          ⚠ linked
                        </span>
                      )}
                    </td>
                    <td style={tdStyle}>{item.arrival_date || '—'}</td>
                    <td style={tdStyle}>{item.departure_date || '—'}</td>
                    <td style={tdStyle}>{item.nights ?? '—'}</td>
                    <td style={tdStyle}>{item.miles?.toFixed(1) || '—'}</td>
                    <td style={{ ...tdStyle, textAlign: 'left', fontSize: '11px' }}>
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
                {loading ? 'Applying...' : `Apply Import (${preview.parsed_stop_count} stops)`}
              </button>
            </div>
          )}

          {/* Applied confirmation */}
          {applied && preview.appliedResult && (
            <div className="card" style={{ marginTop: '16px', borderColor: 'rgba(74,159,110,.3)' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xl">✅</span>
                <span style={{ color: 'var(--forest)', fontWeight: 600 }}>Import Applied Successfully</span>
              </div>
              <p style={{ color: 'var(--muted)', fontSize: '14px' }}>
                Trip: <a href={`/trips/${preview.appliedResult.trip_slug}`} style={{ color: 'var(--ember)' }}>
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

const thStyle = {
  padding: '10px 12px',
  textAlign: 'center',
  fontFamily: 'var(--mono)',
  fontSize: '10px',
  letterSpacing: '0.1em',
  textTransform: 'uppercase',
  color: 'var(--dim)',
  fontWeight: 500,
};

const tdStyle = {
  padding: '8px 12px',
  textAlign: 'center',
  color: 'var(--muted)',
};
