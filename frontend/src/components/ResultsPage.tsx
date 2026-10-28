import React, { useState } from 'react';
import { AnalysisSummary, DiagnosticFinding, PIDInfo } from '../types';
import { ChevronDown, ChevronUp, AlertTriangle, AlertCircle, Info, CheckCircle2, Search, Play } from 'lucide-react';

interface ResultsPageProps {
  summary: AnalysisSummary;
  onInspectEvidence: (finding: DiagnosticFinding) => void;
  onJumpToReplay: (pid?: number, packetIndex?: number) => void;
  onNavigateToFaultLab: () => void;
}

export const ResultsPage: React.FC<ResultsPageProps> = ({
  summary,
  onInspectEvidence,
  onJumpToReplay,
  onNavigateToFaultLab,
}) => {
  const [showTechnical, setShowTechnical] = useState(false);

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case 'critical':
        return <span className="badge badge-critical">Critical</span>;
      case 'warning':
        return <span className="badge badge-warning">Warning</span>;
      case 'info':
        return <span className="badge badge-info">Info</span>;
      case 'ok':
        return <span className="badge badge-ok">Good</span>;
      default:
        return <span className="badge">{sev}</span>;
    }
  };

  const getSeverityIcon = (sev: string) => {
    switch (sev) {
      case 'critical':
        return <AlertCircle size={16} className="text-critical" />;
      case 'warning':
        return <AlertTriangle size={16} className="text-warning" />;
      case 'info':
        return <Info size={16} className="text-info" />;
      case 'ok':
        return <CheckCircle2 size={16} className="text-success" />;
      default:
        return null;
    }
  };

  const issuesRequiringReview =
    (summary.findings_by_severity?.['critical'] || 0) +
    (summary.findings_by_severity?.['warning'] || 0);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h1 className="page-title">Analysis complete</h1>
          <p className="page-desc" style={{ marginBottom: 0 }}>
            File: <strong>{summary.filename}</strong> &bull; Inspected{' '}
            {summary.total_packets.toLocaleString()} packets
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-secondary" onClick={() => onJumpToReplay()}>
            <Play size={14} />
            Replay packets
          </button>
          <button className="btn btn-primary" onClick={onNavigateToFaultLab}>
            Open in Fault Lab
          </button>
        </div>
      </div>

      {/* Summary Stat Grid */}
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Packets inspected</div>
          <div className="stat-value">{summary.total_packets.toLocaleString()}</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Streams identified</div>
          <div className="stat-value">{summary.pid_count}</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Issues requiring review</div>
          <div
            className="stat-value"
            style={{ color: issuesRequiringReview > 0 ? 'var(--warning)' : 'var(--success)' }}
          >
            {issuesRequiringReview}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Detected input format</div>
          <div className="stat-value" style={{ fontSize: '15px', textTransform: 'uppercase' }}>
            {summary.detected_format === 'mpegts_188'
              ? 'MPEG-TS (188B)'
              : summary.detected_format === 'mpegts_192'
              ? 'MPEG-TS (192B)'
              : summary.detected_format === 'mpegts_204'
              ? 'MPEG-TS (204B)'
              : summary.detected_format}
          </div>
        </div>
      </div>

      {/* What we found */}
      <div style={{ marginBottom: '32px' }}>
        <h2 className="section-title">What we found</h2>
        {summary.findings && summary.findings.length > 0 ? (
          summary.findings.map((finding) => (
            <div key={finding.id} className={`finding-item ${finding.severity}`}>
              <div className="finding-content">
                <div className="finding-header">
                  {getSeverityIcon(finding.severity)}
                  <span className="finding-title">{finding.title}</span>
                  {getSeverityBadge(finding.severity)}
                  {finding.affected_pid_hex && (
                    <span className="code-mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      PID: {finding.affected_pid_hex}
                    </span>
                  )}
                </div>
                <div className="finding-explanation">{finding.explanation}</div>
                <div className="finding-meta">
                  <span>Rule: {finding.rule_id}</span>
                  <span>Certainty: {finding.certainty}</span>
                  {finding.packet_indices?.length > 0 && (
                    <span>
                      Packet: #{finding.packet_indices[0]}
                      {finding.packet_indices.length > 1 ? ` (+${finding.packet_indices.length - 1})` : ''}
                    </span>
                  )}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  className="btn btn-sm btn-secondary"
                  onClick={() => onInspectEvidence(finding)}
                >
                  <Search size={13} />
                  Inspect evidence
                </button>
                {finding.packet_indices && finding.packet_indices.length > 0 && (
                  <button
                    type="button"
                    className="btn btn-sm btn-secondary"
                    onClick={() => onJumpToReplay(finding.affected_pid || undefined, finding.packet_indices[0])}
                    title="Jump to packet in replay viewer"
                  >
                    <Play size={13} />
                    Replay
                  </button>
                )}
              </div>
            </div>
          ))
        ) : (
          <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
            No diagnostic issues found. Stream parsed cleanly.
          </div>
        )}
      </div>

      {/* Stream Inventory */}
      <div style={{ marginBottom: '32px' }}>
        <h2 className="section-title">Stream inventory</h2>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Stream / Type</th>
                <th>PID (Hex / Dec)</th>
                <th>Packet count</th>
                <th>Byte count</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {summary.pids && summary.pids.length > 0 ? (
                summary.pids.map((pidInfo: PIDInfo) => (
                  <tr key={pidInfo.pid}>
                    <td style={{ fontWeight: 500 }}>
                      {pidInfo.stream_type_name || pidInfo.label || `PID ${pidInfo.pid}`}
                    </td>
                    <td className="code-mono">
                      {pidInfo.pid_hex} <span style={{ color: 'var(--text-subtle)' }}>({pidInfo.pid})</span>
                    </td>
                    <td>{pidInfo.packet_count.toLocaleString()}</td>
                    <td>{(pidInfo.byte_count / 1024).toFixed(1)} KB</td>
                    <td>
                      {pidInfo.has_errors ? (
                        <span className="badge badge-warning">
                          {pidInfo.continuity_errors > 0 ? `${pidInfo.continuity_errors} CC errors` : 'Has errors'}
                        </span>
                      ) : pidInfo.is_scrambled ? (
                        <span className="badge badge-info">Scrambled</span>
                      ) : (
                        <span className="badge badge-ok">Normal</span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        type="button"
                        className="btn btn-sm btn-secondary"
                        onClick={() => onJumpToReplay(pidInfo.pid, pidInfo.first_packet_index)}
                      >
                        Filter replay
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                    No streams identified
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Technical Details Expandable */}
      <div className="card">
        <button
          type="button"
          onClick={() => setShowTechnical(!showTechnical)}
          style={{
            background: 'none',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <div style={{ fontWeight: 600, fontSize: '15px' }}>Technical details & PSI tables</div>
          {showTechnical ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>

        {showTechnical && (
          <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '8px' }}>
                Parser Metadata
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: '8px',
                  fontSize: '12px',
                }}
              >
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Parser engine:</span> MPEGTSParser v
                  {summary.parser_version}
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Packet size:</span> {summary.packet_size} bytes
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Valid packets:</span>{' '}
                  {summary.valid_packets.toLocaleString()}
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Null packets:</span>{' '}
                  {summary.null_packets.toLocaleString()}
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Scrambled packets:</span>{' '}
                  {summary.scrambled_packets.toLocaleString()}
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>Sync losses:</span> {summary.sync_losses}
                </div>
              </div>
            </div>

            {summary.programs && summary.programs.length > 0 && (
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '8px' }}>
                  Program Map Tables (PMT)
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {summary.programs.map((prog) => (
                    <div
                      key={prog.program_number}
                      style={{
                        background: 'var(--surface-alt)',
                        padding: '10px 14px',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '12px',
                      }}
                    >
                      <div style={{ fontWeight: 600, marginBottom: '4px' }}>
                        Program #{prog.program_number} &bull; PCR PID: {prog.pcr_pid}
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {prog.streams.map((st) => (
                          <div key={st.elementary_pid_hex} style={{ paddingLeft: '8px' }}>
                            &bull; PID {st.elementary_pid_hex}: {st.stream_type_name} (type 0x
                            {st.stream_type.toString(16).toUpperCase()})
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {summary.warnings && summary.warnings.length > 0 && (
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '8px', color: 'var(--warning)' }}>
                  Parser Warnings ({summary.warnings.length})
                </div>
                <div className="hex-box" style={{ maxHeight: '120px' }}>
                  {summary.warnings.map((w, idx) => (
                    <div key={idx}>{w}</div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
