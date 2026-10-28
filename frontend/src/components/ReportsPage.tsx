import React from 'react';
import { AnalysisSummary } from '../types';
import { Download, FileText, Table, CheckSquare, Radio } from 'lucide-react';
import { getReportDownloadUrl, getSDRReportDownloadUrl } from '../services/api';

interface ReportsPageProps {
  summary: AnalysisSummary;
}

export const ReportsPage: React.FC<ReportsPageProps> = ({ summary }) => {
  const reports = [
    {
      id: 'summary',
      title: 'Complete Analysis Summary',
      type: 'JSON',
      description: 'Comprehensive report containing file metadata, packet statistics, PID inventory, and full diagnostic findings.',
      icon: <FileText size={20} className="text-accent" />,
      url: getReportDownloadUrl(summary.file_id, 'summary'),
      filename: `orbitstream_summary_${summary.file_id}.json`,
    },
    {
      id: 'findings_csv',
      title: 'Diagnostic Findings',
      type: 'CSV',
      description: 'Structured spreadsheet of all detected issues, severity levels, affected PIDs, and diagnostic rule IDs.',
      icon: <Table size={20} style={{ color: 'var(--warning)' }} />,
      url: getReportDownloadUrl(summary.file_id, 'findings_csv'),
      filename: `orbitstream_findings_${summary.file_id}.csv`,
    },
    {
      id: 'findings_json',
      title: 'Diagnostic Findings',
      type: 'JSON',
      description: 'Raw array of finding objects including structured evidence, packet indices, and offset references.',
      icon: <FileText size={20} style={{ color: 'var(--warning)' }} />,
      url: getReportDownloadUrl(summary.file_id, 'findings_json'),
      filename: `orbitstream_findings_${summary.file_id}.json`,
    },
    {
      id: 'pids_csv',
      title: 'PID & Stream Inventory',
      type: 'CSV',
      description: 'Complete breakdown of all observed PIDs, byte volume, packet volume, stream types, and error tallies.',
      icon: <Table size={20} style={{ color: 'var(--info)' }} />,
      url: getReportDownloadUrl(summary.file_id, 'pids_csv'),
      filename: `orbitstream_pids_${summary.file_id}.csv`,
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h1 className="page-title">Diagnostic reports & exports</h1>
        <p className="page-desc">
          Download verifiable, structured reports for stream <strong>{summary.filename}</strong>.
        </p>
      </div>

      {/* Metadata Overview Card */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h2 className="section-title">Report Metadata</h2>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '12px',
            fontSize: '13px',
          }}
        >
          <div>
            <span style={{ color: 'var(--text-muted)' }}>Input filename:</span> {summary.filename}
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)' }}>Detected format:</span>{' '}
            <span className="code-mono">{summary.detected_format}</span>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)' }}>Packet count:</span>{' '}
            {summary.total_packets.toLocaleString()}
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)' }}>Analysis timestamp:</span>{' '}
            {new Date(summary.analysis_timestamp).toLocaleString()}
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)' }}>Parser engine:</span> MPEGTSParser v
            {summary.parser_version}
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)' }}>Diagnostic rules:</span> Engine v0.1.0
          </div>
        </div>
      </div>

      {/* Available Downloads List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {reports.map((report) => (
          <div
            key={report.id}
            className="card"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '16px 20px',
              marginBottom: 0,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div
                style={{
                  background: 'var(--surface-alt)',
                  padding: '10px',
                  borderRadius: 'var(--radius-md)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {report.icon}
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: 600, fontSize: '14px' }}>{report.title}</span>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      padding: '1px 6px',
                      borderRadius: 'var(--radius-sm)',
                      background: 'var(--surface-alt)',
                      color: 'var(--text-muted)',
                    }}
                  >
                    {report.type}
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {report.description}
                </div>
              </div>
            </div>

            <a
              href={report.url}
              download={report.filename}
              className="btn btn-secondary btn-sm"
              style={{ flexShrink: 0 }}
            >
              <Download size={14} />
              Download {report.type}
            </a>
          </div>
        ))}
      </div>

      {/* RTL-SDR Physical Telemetry Reports Section */}
      <div style={{ marginTop: '36px', marginBottom: '20px' }}>
        <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Radio size={18} style={{ color: 'var(--accent)' }} />
          RTL-SDR Physical Telemetry & Signal Diagnostic Reports
        </h2>
        <p className="page-desc">
          Download continuous physical-layer RF measurements, power logs, and anomaly recovery audit trails.
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div
          className="card"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            padding: '16px 20px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--surface-alt)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Table size={20} style={{ color: 'var(--accent)' }} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: 600, fontSize: '14px' }}>SDR Physical Telemetry History</span>
                <span style={{ fontSize: '11px', fontWeight: 600, padding: '1px 6px', borderRadius: 'var(--radius-sm)', background: 'var(--surface-alt)', color: 'var(--text-muted)' }}>CSV</span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Time-series table of relative power (dBFS), peak power, PAPR, noise floor, SNR, and DC rail metrics.
              </div>
            </div>
          </div>
          <a
            href={getSDRReportDownloadUrl('measurements_csv')}
            download="orbitstream_sdr_telemetry.csv"
            className="btn btn-secondary btn-sm"
            style={{ flexShrink: 0 }}
          >
            <Download size={14} />
            Download CSV
          </a>
        </div>

        <div
          className="card"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            padding: '16px 20px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--surface-alt)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <FileText size={20} style={{ color: 'var(--accent)' }} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: 600, fontSize: '14px' }}>SDR Physical Telemetry & Spectrum JSON</span>
                <span style={{ fontSize: '11px', fontWeight: 600, padding: '1px 6px', borderRadius: 'var(--radius-sm)', background: 'var(--surface-alt)', color: 'var(--text-muted)' }}>JSON</span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Full telemetry records including 64-bin FFT spectrum power arrays and tuner metadata.
              </div>
            </div>
          </div>
          <a
            href={getSDRReportDownloadUrl('measurements_json')}
            download="orbitstream_sdr_telemetry.json"
            className="btn btn-secondary btn-sm"
            style={{ flexShrink: 0 }}
          >
            <Download size={14} />
            Download JSON
          </a>
        </div>

        <div
          className="card"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            padding: '16px 20px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--surface-alt)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Table size={20} style={{ color: 'var(--warning)' }} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: 600, fontSize: '14px' }}>SDR Anomaly & Recovery Event Log</span>
                <span style={{ fontSize: '11px', fontWeight: 600, padding: '1px 6px', borderRadius: 'var(--radius-sm)', background: 'var(--surface-alt)', color: 'var(--text-muted)' }}>CSV</span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Full audit log of power drop, low SNR, saturation, and hardware invalid events with deduplication counts.
              </div>
            </div>
          </div>
          <a
            href={getSDRReportDownloadUrl('anomalies_csv')}
            download="orbitstream_sdr_anomalies.csv"
            className="btn btn-secondary btn-sm"
            style={{ flexShrink: 0 }}
          >
            <Download size={14} />
            Download CSV
          </a>
        </div>

        <div
          className="card"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            padding: '16px 20px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--surface-alt)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <FileText size={20} style={{ color: 'var(--success)' }} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontWeight: 600, fontSize: '14px' }}>Printable SDR Physical Diagnostic Report</span>
                <span style={{ fontSize: '11px', fontWeight: 600, padding: '1px 6px', borderRadius: 'var(--radius-sm)', background: 'var(--surface-alt)', color: 'var(--text-muted)' }}>PDF / HTML</span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Comprehensive formatted printable document with station parameters, RF gauges, and anomaly tables.
              </div>
            </div>
          </div>
          <a
            href={getSDRReportDownloadUrl('pdf')}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary btn-sm"
            style={{ flexShrink: 0 }}
          >
            <Download size={14} />
            View / Print Report
          </a>
        </div>
      </div>
    </div>
  );
};
