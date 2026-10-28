import React, { useState, useEffect } from 'react';
import { AnalysisSummary, FaultScenarioInfo, SimulationResponse } from '../types';
import { getFaultScenarios, runSimulation } from '../services/api';
import { CheckCircle2, XCircle, HelpCircle, ArrowRight, RefreshCw, Cpu, Download } from 'lucide-react';

interface FaultLabPageProps {
  summary: AnalysisSummary;
  onNavigateToReplay?: (fileId: string) => void;
}

export const FaultLabPage: React.FC<FaultLabPageProps> = ({ summary, onNavigateToReplay }) => {
  const [scenarios, setScenarios] = useState<FaultScenarioInfo[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>('cc_discontinuity');
  const [targetPid, setTargetPid] = useState<number>(0x0100);
  const [targetPacketIndex, setTargetPacketIndex] = useState<number>(5);
  const [ccSkip, setCcSkip] = useState<number>(3);
  const [corruptByte, setCorruptByte] = useState<string>('0x00');
  const [scramblingValue, setScramblingValue] = useState<number>(2);

  const [loading, setLoading] = useState(false);
  const [simResult, setSimResult] = useState<SimulationResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    getFaultScenarios()
      .then((data) => {
        setScenarios(data);
        if (data.length > 0 && !selectedScenario) {
          setSelectedScenario(data[0].id);
        }
      })
      .catch(() => {});

    // Set default target PID from summary
    if (summary.pids && summary.pids.length > 0) {
      const videoOrAudio = summary.pids.find((p) => p.pid >= 0x0100 && p.pid <= 0x1FFE);
      if (videoOrAudio) {
        setTargetPid(videoOrAudio.pid);
      }
    }
  }, [summary]);

  const handleRunSimulation = async () => {
    setErrorMsg(null);
    setLoading(true);
    setSimResult(null);

    try {
      const parsedCorruptByte = parseInt(corruptByte, 16);
      const res = await runSimulation({
        file_id: summary.file_id,
        scenario: selectedScenario,
        target_pid: targetPid,
        target_packet_indices: [targetPacketIndex],
        cc_skip: ccSkip,
        corrupt_byte: isNaN(parsedCorruptByte) ? 0x00 : parsedCorruptByte,
        scrambling_value: scramblingValue,
      });

      setSimResult(res);
    } catch (err: any) {
      setErrorMsg(err.message || 'Simulation run failed');
    } finally {
      setLoading(false);
    }
  };

  const currentScenarioObj = scenarios.find((s) => s.id === selectedScenario);

  return (
    <div>
      <div style={{ marginBottom: '20px' }}>
        <h1 className="page-title">Controlled fault simulation lab</h1>
        <p className="page-desc">
          Inject controlled anomalies on a separate derived copy to validate the diagnostic engine independently.
          The original file is never modified.
        </p>
      </div>

      {errorMsg && (
        <div
          style={{
            backgroundColor: 'var(--critical-bg)',
            color: 'var(--critical)',
            border: '1px solid var(--critical-border)',
            borderRadius: 'var(--radius-md)',
            padding: '12px 16px',
            marginBottom: '20px',
            fontSize: '13px',
          }}
        >
          {errorMsg}
        </div>
      )}

      {/* Guided 4-step wizard card */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h2 className="section-title">Configure simulation scenario</h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '20px', marginTop: '16px' }}>
          {/* Step 1: Scenario */}
          <div>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
              1. Fault Scenario
            </label>
            <select
              value={selectedScenario}
              onChange={(e) => setSelectedScenario(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                fontSize: '13px',
              }}
            >
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            {currentScenarioObj && (
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '6px' }}>
                {currentScenarioObj.description}
              </div>
            )}
          </div>

          {/* Step 2: Target Stream / PID */}
          <div>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
              2. Target PID / Stream
            </label>
            <select
              value={targetPid}
              onChange={(e) => setTargetPid(parseInt(e.target.value, 10))}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border)',
                background: 'var(--surface)',
                fontSize: '13px',
              }}
            >
              {summary.pids.map((p) => (
                <option key={p.pid} value={p.pid}>
                  {p.pid_hex} &mdash; {p.stream_type_name || p.label || `PID ${p.pid}`}
                </option>
              ))}
            </select>
          </div>

          {/* Step 3: Scenario-specific parameters */}
          <div>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
              3. Fault Parameters
            </label>

            {selectedScenario === 'cc_discontinuity' && (
              <div>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Continuity counter skip:</span>
                <input
                  type="number"
                  min={1}
                  max={14}
                  value={ccSkip}
                  onChange={(e) => setCcSkip(Number(e.target.value))}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border)',
                    marginTop: '4px',
                    fontSize: '13px',
                  }}
                />
              </div>
            )}

            {selectedScenario === 'corrupt_sync' && (
              <div>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Corrupt sync byte at packet #{targetPacketIndex} to:
                </span>
                <input
                  type="text"
                  value={corruptByte}
                  onChange={(e) => setCorruptByte(e.target.value)}
                  placeholder="0x00"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border)',
                    marginTop: '4px',
                    fontSize: '13px',
                    fontFamily: 'var(--font-mono)',
                  }}
                />
              </div>
            )}

            {selectedScenario === 'change_scrambling' && (
              <div>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Scrambling bits (0-3):</span>
                <select
                  value={scramblingValue}
                  onChange={(e) => setScramblingValue(Number(e.target.value))}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border)',
                    marginTop: '4px',
                    fontSize: '13px',
                    background: 'var(--surface)',
                  }}
                >
                  <option value={1}>01 (Reserved)</option>
                  <option value={2}>10 (Even key)</option>
                  <option value={3}>11 (Odd key)</option>
                </select>
              </div>
            )}

            {(selectedScenario === 'remove_packets' || selectedScenario === 'modify_header') && (
              <div>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Target packet index:</span>
                <input
                  type="number"
                  min={0}
                  max={summary.total_packets - 1}
                  value={targetPacketIndex}
                  onChange={(e) => setTargetPacketIndex(Number(e.target.value))}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border)',
                    marginTop: '4px',
                    fontSize: '13px',
                  }}
                />
              </div>
            )}
          </div>
        </div>

        {/* Action button */}
        <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
          <button
            className="btn btn-primary"
            onClick={handleRunSimulation}
            disabled={loading}
            style={{ width: '100%', padding: '10px' }}
          >
            {loading ? (
              <>
                <RefreshCw size={15} className="spin" />
                Generating modified copy and running independent diagnostics...
              </>
            ) : (
              <>
                <Cpu size={15} />
                Generate Fault & Run Verification
              </>
            )}
          </button>
        </div>
      </div>

      {/* Verification Result Section */}
      {simResult && (
        <div>
          {/* Verification Status Banner */}
          <div
            style={{
              padding: '16px 20px',
              borderRadius: 'var(--radius-md)',
              border: `1px solid ${
                simResult.verification.status === 'pass'
                  ? 'var(--success-border)'
                  : simResult.verification.status === 'fail'
                  ? 'var(--critical-border)'
                  : 'var(--warning-border)'
              }`,
              background:
                simResult.verification.status === 'pass'
                  ? 'var(--success-bg)'
                  : simResult.verification.status === 'fail'
                  ? 'var(--critical-bg)'
                  : 'var(--warning-bg)',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {simResult.verification.status === 'pass' ? (
                <CheckCircle2 size={24} style={{ color: 'var(--success)' }} />
              ) : simResult.verification.status === 'fail' ? (
                <XCircle size={24} style={{ color: 'var(--critical)' }} />
              ) : (
                <HelpCircle size={24} style={{ color: 'var(--warning)' }} />
              )}
              <div>
                <div style={{ fontWeight: 700, fontSize: '15px' }}>
                  Verification Status: {simResult.verification.status.toUpperCase()}
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                  {simResult.verification.reason}
                </div>
              </div>
            </div>

            <a
              href={`/api/reports/${simResult.sim_id}/comparison`}
              download
              className="btn btn-secondary btn-sm"
              style={{ background: 'var(--surface)' }}
            >
              <Download size={13} />
              Export comparison JSON
            </a>
          </div>

          {/* Side-by-side comparison */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
            {/* Original File */}
            <div className="card">
              <h2 className="section-title">Original Capture</h2>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '10px' }}>
                File: {summary.filename} &bull; SHA-256: <span className="code-mono">{simResult.fault_result.source_hash}</span>
              </div>
              <div style={{ fontSize: '13px', lineHeight: 1.6 }}>
                <div>Total Packets: <strong>{summary.total_packets.toLocaleString()}</strong></div>
                <div>Diagnostic Findings: <strong>{summary.findings.length}</strong></div>
                <div>Status: <span className="badge badge-ok">Original unmodified</span></div>
              </div>
            </div>

            {/* Modified File */}
            <div className="card">
              <h2 className="section-title">Modified Capture (Derived Copy)</h2>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '10px' }}>
                SHA-256: <span className="code-mono">{simResult.fault_result.modified_hash}</span>
              </div>
              <div style={{ fontSize: '13px', lineHeight: 1.6 }}>
                <div>Total Packets: <strong>{simResult.modified_analysis.total_packets.toLocaleString()}</strong></div>
                <div>Diagnostic Findings: <strong>{simResult.modified_analysis.findings.length}</strong></div>
                <div>
                  Packets Modified: <strong>{simResult.fault_result.packets_affected}</strong>
                </div>
              </div>
            </div>
          </div>

          {/* New Diagnostic Findings Detected */}
          <div className="card" style={{ marginTop: '20px' }}>
            <h2 className="section-title">New Findings Detected by Parser & Diagnostics</h2>
            {simResult.verification.new_findings && simResult.verification.new_findings.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {simResult.verification.new_findings.map((f, i) => (
                  <div
                    key={i}
                    style={{
                      padding: '10px 14px',
                      borderRadius: 'var(--radius-sm)',
                      background: 'var(--surface-alt)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '13px' }}>{f.title}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Rule: {f.rule_id}</div>
                    </div>
                    <span className={`badge badge-${f.severity}`}>{f.severity}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                No new findings produced on modified copy.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
