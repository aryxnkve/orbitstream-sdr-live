import React, { useState } from 'react';
import { AnalysisSummary } from '../types';
import { Sliders, Layers, FileCode, CheckCircle, Info } from 'lucide-react';

interface AdvancedToolsPageProps {
  summary?: AnalysisSummary | null;
}

export const AdvancedToolsPage: React.FC<AdvancedToolsPageProps> = ({ summary }) => {
  const [activeSubTab, setActiveSubTab] = useState<'protocols' | 'settings'>('protocols');

  return (
    <div>
      <div style={{ marginBottom: '20px' }}>
        <h1 className="page-title">Advanced protocol tools</h1>
        <p className="page-desc">
          Low-level protocol parsers, extensible format status, and system configuration.
        </p>
      </div>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
        <button
          className={`btn btn-sm ${activeSubTab === 'protocols' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveSubTab('protocols')}
        >
          <Layers size={14} />
          Protocol Support Status
        </button>
        <button
          className={`btn btn-sm ${activeSubTab === 'settings' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveSubTab('settings')}
        >
          <Sliders size={14} />
          Engine Configuration
        </button>
      </div>

      {activeSubTab === 'protocols' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* MPEG-TS Card */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ fontWeight: 600, fontSize: '15px' }}>MPEG-2 Transport Stream (ISO/IEC 13818-1)</span>
                  <span className="badge badge-ok">Fully Supported</span>
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                  Standard 188-byte packet synchronization, 192-byte timestamped BDAV streams, 204-byte DVB FEC streams.
                  Per-PID demuxing, Continuity Counter verification, Transport Error Indicator (TEI) tracking, Adaptation Field flags,
                  PCR timestamp extraction, PAT/PMT table section assembly, and CRC32 verification.
                </div>
              </div>
            </div>
          </div>

          {/* GSE Card */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ fontWeight: 600, fontSize: '15px' }}>Generic Stream Encapsulation (ETSI TS 102 606)</span>
                  <span className="badge badge-info">Modular Scaffold</span>
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                  Architectural interface created for DVB-S2 GSE packet dissection (GS Header, Start/End Indicator, Protocol Type).
                  Full payload reconstruction requires raw baseband receiver streams with validated test vectors.
                </div>
              </div>
            </div>
          </div>

          {/* DVB-S2 BBFrame Card */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ fontWeight: 600, fontSize: '15px' }}>DVB-S2 BaseBand Frame (ETSI EN 302 307)</span>
                  <span className="badge badge-info">Modular Scaffold</span>
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                  Scaffold for DVB-S2 Baseband Header (MATYPE, UPL, DFL, SYNC, SYNCD). Distinguishes baseband frames
                  from higher-layer transport stream packets without fabricating invalid frame boundaries.
                </div>
              </div>
            </div>
          </div>

          {/* PCAP Card */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ fontWeight: 600, fontSize: '15px' }}>Packet Capture (PCAP / PCAPNG)</span>
                  <span className="badge badge-info">Scaffold</span>
                </div>
                <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                  Scaffold for identifying capture headers and extracting UDP/RTP transported MPEG-TS or GSE payloads.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeSubTab === 'settings' && (
        <div className="card">
          <h2 className="section-title">Local Engine Settings</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: '8px' }}>
              <div>
                <div style={{ fontWeight: 600 }}>Maximum File Upload Size</div>
                <div style={{ color: 'var(--text-muted)' }}>Configured safe limit for single stream uploads</div>
              </div>
              <div className="code-mono">100 MB</div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: '8px' }}>
              <div>
                <div style={{ fontWeight: 600 }}>Sync Scan Window</div>
                <div style={{ color: 'var(--text-muted)' }}>Bytes examined to detect sync byte alignment</div>
              </div>
              <div className="code-mono">4,080 Bytes</div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: '8px' }}>
              <div>
                <div style={{ fontWeight: 600 }}>Offline Mode</div>
                <div style={{ color: 'var(--text-muted)' }}>No external telemetry or third-party cloud API dependencies</div>
              </div>
              <span className="badge badge-ok">Active</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: '8px' }}>
              <div>
                <div style={{ fontWeight: 600 }}>Safe Temporary Storage</div>
                <div style={{ color: 'var(--text-muted)' }}>UUID-scoped file isolation with path traversal protection</div>
              </div>
              <span className="badge badge-ok">Protected</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
