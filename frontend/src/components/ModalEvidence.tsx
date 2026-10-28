import React from 'react';
import { DiagnosticFinding } from '../types';
import { X, Play, AlertCircle, AlertTriangle, Info, CheckCircle2 } from 'lucide-react';

interface ModalEvidenceProps {
  finding: DiagnosticFinding | null;
  onClose: () => void;
  onJumpToPacket: (packetIndex: number) => void;
}

export const ModalEvidence: React.FC<ModalEvidenceProps> = ({
  finding,
  onClose,
  onJumpToPacket,
}) => {
  if (!finding) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontWeight: 600, fontSize: '15px' }}>Diagnostic Evidence Inspector</span>
            <span className={`badge badge-${finding.severity}`}>{finding.severity}</span>
          </div>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={onClose}
            style={{ padding: '4px' }}
          >
            <X size={16} />
          </button>
        </div>

        <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <div style={{ fontSize: '16px', fontWeight: 600, marginBottom: '6px' }}>{finding.title}</div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              {finding.explanation}
            </div>
          </div>

          {finding.technical_detail && (
            <div
              style={{
                background: 'var(--surface-alt)',
                padding: '12px 14px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border)',
                fontSize: '12px',
                lineHeight: 1.6,
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: '4px', color: 'var(--text-main)' }}>
                Technical Specification Detail
              </div>
              <div>{finding.technical_detail}</div>
            </div>
          )}

          {/* Structured Evidence Table */}
          <div>
            <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '8px' }}>
              Observed Evidence & Values
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <tbody>
                  <tr>
                    <td style={{ width: '160px', color: 'var(--text-muted)' }}>Diagnostic Rule</td>
                    <td className="code-mono">{finding.rule_id}</td>
                  </tr>
                  <tr>
                    <td style={{ color: 'var(--text-muted)' }}>Certainty Level</td>
                    <td style={{ textTransform: 'capitalize' }}>{finding.certainty}</td>
                  </tr>
                  {finding.affected_pid_hex && (
                    <tr>
                      <td style={{ color: 'var(--text-muted)' }}>Affected PID</td>
                      <td className="code-mono">
                        {finding.affected_pid_hex} ({finding.affected_pid})
                      </td>
                    </tr>
                  )}
                  {finding.expected_value && (
                    <tr>
                      <td style={{ color: 'var(--text-muted)' }}>Expected Value</td>
                      <td className="code-mono">{finding.expected_value}</td>
                    </tr>
                  )}
                  {finding.observed_value && (
                    <tr>
                      <td style={{ color: 'var(--text-muted)' }}>Observed Value</td>
                      <td className="code-mono" style={{ color: 'var(--critical)' }}>
                        {finding.observed_value}
                      </td>
                    </tr>
                  )}
                  {finding.packet_indices && finding.packet_indices.length > 0 && (
                    <tr>
                      <td style={{ color: 'var(--text-muted)' }}>Packet Indices</td>
                      <td className="code-mono">
                        #{finding.packet_indices.slice(0, 10).join(', #')}
                        {finding.packet_indices.length > 10 ? ` (+${finding.packet_indices.length - 10} more)` : ''}
                      </td>
                    </tr>
                  )}
                  {finding.byte_offsets && finding.byte_offsets.length > 0 && (
                    <tr>
                      <td style={{ color: 'var(--text-muted)' }}>Source Byte Offsets</td>
                      <td className="code-mono">
                        0x{finding.byte_offsets[0].toString(16).toUpperCase()} ({finding.byte_offsets[0].toLocaleString()} B)
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Possible Causes */}
          {finding.possible_causes && finding.possible_causes.length > 0 && (
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Plausible Explanations</div>
              <ul style={{ paddingLeft: '20px', fontSize: '12px', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {finding.possible_causes.map((cause, i) => (
                  <li key={i}>{cause}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommended Steps */}
          {finding.recommended_steps && finding.recommended_steps.length > 0 && (
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Recommended Investigation Steps</div>
              <ul style={{ paddingLeft: '20px', fontSize: '12px', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {finding.recommended_steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            Close
          </button>
          {finding.packet_indices && finding.packet_indices.length > 0 && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => {
                onJumpToPacket(finding.packet_indices[0]);
                onClose();
              }}
            >
              <Play size={13} />
              Replay at Packet #{finding.packet_indices[0]}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
