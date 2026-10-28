import React, { useState, useEffect, useRef } from 'react';
import {
  SDRStatus,
  SDRMeasurement,
  SDRAnomaly,
} from '../types';
import {
  getSDRLatestStatus,
  getSDRHistory,
  getSDRAnomalies,
  getSDRReportDownloadUrl,
} from '../services/api';
import {
  Radio,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Download,
  RotateCw,
  Sliders,
  ShieldCheck,
  ShieldAlert,
  Clock,
  Wifi,
  WifiOff,
  FileText,
  Table,
} from 'lucide-react';

export const SDRMonitorPage: React.FC = () => {
  const [status, setStatus] = useState<SDRStatus | null>(null);
  const [history, setHistory] = useState<SDRMeasurement[]>([]);
  const [anomalies, setAnomalies] = useState<SDRAnomaly[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAutoRefresh, setIsAutoRefresh] = useState(true);
  const [anomalyFilter, setAnomalyFilter] = useState<'all' | 'active' | 'resolved'>('all');
  const [selectedBinIndex, setSelectedBinIndex] = useState<number | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const historyCanvasRef = useRef<HTMLCanvasElement | null>(null);

  // Poll status every 10 seconds (matching the default SDR collector interval)
  useEffect(() => {
    fetchData();

    if (!isAutoRefresh) return;
    const interval = setInterval(() => {
      fetchData(false);
    }, 10000);

    return () => clearInterval(interval);
  }, [isAutoRefresh]);

  const fetchData = async (showLoading: boolean = true) => {
    if (showLoading) setIsLoading(true);
    setError(null);
    try {
      const [latestStatus, historyData, anomaliesData] = await Promise.all([
        getSDRLatestStatus(),
        getSDRHistory({ limit: 40 }),
        getSDRAnomalies({ limit: 50 }),
      ]);
      setStatus(latestStatus);
      setHistory(historyData.measurements || []);
      setAnomalies(anomaliesData.anomalies || []);
    } catch (err: any) {
      console.error('Error fetching SDR telemetry:', err);
      setError(err.message || 'Failed to connect to SDR telemetry service');
    } finally {
      if (showLoading) setIsLoading(false);
    }
  };

  // Draw 64-bin FFT RF Spectrum Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const bins = status?.latest_measurement?.spectrum_bins || [];
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // Dark sleek background
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, width, height);

    // Grid lines (-20, -40, -60, -80, -100 dBFS)
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);

    const levels = [-20, -40, -60, -80, -100];
    ctx.fillStyle = '#64748b';
    ctx.font = '10px monospace';

    levels.forEach((lvl) => {
      // Map 0 to -110 dBFS to canvas height
      const y = ((lvl - 0) / -110) * height;
      ctx.beginPath();
      ctx.moveTo(35, y);
      ctx.lineTo(width, y);
      ctx.stroke();
      ctx.fillText(`${lvl} dB`, 2, y + 3);
    });

    ctx.setLineDash([]);

    if (bins.length === 0) {
      ctx.fillStyle = '#94a3b8';
      ctx.font = '13px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Awaiting FFT spectrum telemetry...', width / 2, height / 2);
      return;
    }

    const marginX = 40;
    const plotWidth = width - marginX;
    const binWidth = plotWidth / bins.length;

    // Draw Spectrum Bars
    bins.forEach((dbfs, idx) => {
      const clamped = Math.max(-110, Math.min(0, dbfs));
      const barHeight = ((clamped - (-110)) / 110) * (height - 20);
      const x = marginX + idx * binWidth;
      const y = height - barHeight;

      // Color gradient by power level
      let color = '#38bdf8'; // Blue for normal
      if (dbfs > -15) color = '#f87171'; // Red for near saturation
      else if (dbfs > -30) color = '#fbbf24'; // Yellow for strong carrier

      if (idx === selectedBinIndex) {
        ctx.fillStyle = '#ffffff';
      } else {
        ctx.fillStyle = color;
      }

      ctx.fillRect(x + 1, y, Math.max(1, binWidth - 2), barHeight);
    });

    // Draw frequency bounds text
    const centerFreq = status?.latest_measurement?.center_frequency_hz || 100000000;
    const sampleRate = status?.latest_measurement?.sample_rate_hz || 1024000;
    const startMhz = (centerFreq - sampleRate / 2) / 1e6;
    const endMhz = (centerFreq + sampleRate / 2) / 1e6;
    const centerMhz = centerFreq / 1e6;

    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`${startMhz.toFixed(3)} MHz`, marginX + 4, height - 4);
    ctx.textAlign = 'center';
    ctx.fillText(`Center: ${centerMhz.toFixed(3)} MHz`, marginX + plotWidth / 2, height - 4);
    ctx.textAlign = 'right';
    ctx.fillText(`${endMhz.toFixed(3)} MHz`, width - 4, height - 4);
  }, [status, selectedBinIndex]);

  // Draw History Power & SNR Time-Series Canvas
  useEffect(() => {
    const canvas = historyCanvasRef.current;
    if (!canvas || history.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, width, height);

    // Grid lines
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);

    const powerTicks = [0, -20, -40, -60, -80, -100];
    ctx.fillStyle = '#64748b';
    ctx.font = '10px monospace';

    powerTicks.forEach((lvl) => {
      const y = ((lvl - 0) / -110) * (height - 25) + 10;
      ctx.beginPath();
      ctx.moveTo(35, y);
      ctx.lineTo(width, y);
      ctx.stroke();
      ctx.fillText(`${lvl}`, 5, y + 3);
    });

    ctx.setLineDash([]);

    const marginX = 40;
    const plotWidth = width - marginX - 10;
    const count = history.length;
    const stepX = count > 1 ? plotWidth / (count - 1) : plotWidth;

    // Line 1: Relative Power (Cyan)
    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 2;
    ctx.beginPath();
    history.forEach((rec, i) => {
      const x = marginX + i * stepX;
      const y = ((rec.relative_power_dbfs - 0) / -110) * (height - 25) + 10;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Line 2: Estimated SNR (Amber)
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 2;
    ctx.beginPath();
    history.forEach((rec, i) => {
      const x = marginX + i * stepX;
      // Map 0 to 50 dB SNR
      const y = height - 20 - ((rec.snr_estimate_db - 0) / 50) * (height - 35);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Legend
    ctx.fillStyle = '#06b6d4';
    ctx.fillRect(width - 170, 8, 10, 10);
    ctx.fillStyle = '#cbd5e1';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('Power (dBFS)', width - 155, 17);

    ctx.fillStyle = '#f59e0b';
    ctx.fillRect(width - 80, 8, 10, 10);
    ctx.fillStyle = '#cbd5e1';
    ctx.fillText('SNR (dB)', width - 65, 17);
  }, [history]);

  const filteredAnomalies = anomalies.filter((a) => {
    if (anomalyFilter === 'active') return !a.resolved;
    if (anomalyFilter === 'resolved') return a.resolved;
    return true;
  });

  const getStatusColor = (st?: string) => {
    switch (st) {
      case 'active':
        return 'var(--success)';
      case 'degraded':
        return 'var(--warning)';
      case 'demo':
        return 'var(--info)';
      case 'offline':
      default:
        return 'var(--text-muted)';
    }
  };

  const getSeverityBadgeClass = (sev: string) => {
    switch (sev.toUpperCase()) {
      case 'CRITICAL':
        return 'badge-critical';
      case 'ERROR':
        return 'badge-error';
      case 'WARNING':
        return 'badge-warning';
      default:
        return 'badge-info';
    }
  };

  return (
    <div className="sdr-monitor-container">
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Radio size={24} style={{ color: 'var(--accent)' }} />
            RTL-SDR Physical Layer Telemetry
          </h1>
          <p className="page-desc">
            Continuous I/Q power measurements, 64-bin FFT spectrum analyzer, and anomaly detection from local station collector.
          </p>
        </div>

        {/* Live Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={isAutoRefresh}
              onChange={(e) => setIsAutoRefresh(e.target.checked)}
            />
            Auto-refresh (10s)
          </label>

          <button
            className="btn btn-secondary"
            onClick={() => fetchData(true)}
            disabled={isLoading}
            title="Refresh telemetry"
          >
            <RotateCw size={14} className={isLoading ? 'spin-icon' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ backgroundColor: '#fef2f2', borderColor: '#fca5a5', marginBottom: '16px', color: '#991b1b' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={18} />
            <span><strong>Connection Note:</strong> {error}</span>
          </div>
        </div>
      )}

      {/* Station Status Bar */}
      <div className="card" style={{ marginBottom: '20px', padding: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                backgroundColor: getStatusColor(status?.status),
                display: 'inline-block',
                boxShadow: `0 0 8px ${getStatusColor(status?.status)}`,
              }}
            />
            <div>
              <span style={{ fontSize: '15px', fontWeight: 600 }}>
                Station ID: {status?.device_id || 'rtlsdr-station-win01'}
              </span>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Hardware: {status?.device_type || 'RTL-SDR Receiver'} ({status?.latest_measurement?.serial ? `Serial: ${status.latest_measurement.serial}` : 'Local USB'})
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <span
              className="badge"
              style={{
                backgroundColor: status?.mode === 'demo' ? 'rgba(56, 189, 248, 0.2)' : 'rgba(34, 197, 94, 0.2)',
                color: status?.mode === 'demo' ? '#0284c7' : '#15803d',
                fontWeight: 600,
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '11px',
              }}
            >
              {status?.mode === 'demo' ? 'MODE: SYNTHETIC DEMO' : 'MODE: PHYSICAL HARDWARE'}
            </span>

            <span
              className="badge"
              style={{
                backgroundColor: getStatusColor(status?.status) + '20',
                color: getStatusColor(status?.status),
                fontWeight: 700,
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                textTransform: 'uppercase',
              }}
            >
              {status?.status || 'OFFLINE'}
            </span>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '14px',
          marginBottom: '20px',
        }}
      >
        <div className="card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            Center Frequency
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
            {status?.frequency_mhz !== null && status?.frequency_mhz !== undefined ? `${status.frequency_mhz.toFixed(3)} MHz` : '--'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Sample Rate: {status?.sample_rate_msps ? `${status.sample_rate_msps.toFixed(3)} MS/s` : '--'}
          </div>
        </div>

        <div className="card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            Relative Power
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#38bdf8', marginTop: '4px' }}>
            {status?.relative_power_dbfs !== null && status?.relative_power_dbfs !== undefined ? `${status.relative_power_dbfs.toFixed(2)} dBFS` : '--'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Peak: {status?.latest_measurement?.peak_power_dbfs ? `${status.latest_measurement.peak_power_dbfs.toFixed(1)} dBFS` : '--'}
          </div>
        </div>

        <div className="card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            Estimated SNR
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#fbbf24', marginTop: '4px' }}>
            {status?.snr_estimate_db !== null && status?.snr_estimate_db !== undefined ? `${status.snr_estimate_db.toFixed(1)} dB` : '--'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Noise Floor: {status?.latest_measurement?.noise_floor_dbfs ? `${status.latest_measurement.noise_floor_dbfs.toFixed(1)} dBFS` : '--'}
          </div>
        </div>

        <div className="card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            PAPR & Clipping
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
            {status?.latest_measurement?.papr_db ? `${status.latest_measurement.papr_db.toFixed(1)} dB` : '--'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Clipping: {status?.latest_measurement?.clipping_ratio ? `${(status.latest_measurement.clipping_ratio * 100).toFixed(2)}%` : '0.0%'}
          </div>
        </div>

        <div className="card" style={{ padding: '14px' }}>
          <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
            Active Anomalies
          </div>
          <div
            style={{
              fontSize: '20px',
              fontWeight: 700,
              color: (status?.active_anomaly_count || 0) > 0 ? '#ef4444' : '#22c55e',
              marginTop: '4px',
            }}
          >
            {status?.active_anomaly_count || 0}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Validity: {status?.latest_measurement?.is_valid ? 'Valid I/Q' : 'Invalid / Lost'}
          </div>
        </div>
      </div>

      {/* Visualizers Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
        {/* Spectrum Canvas */}
        <div className="card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <h3 style={{ fontSize: '14px', margin: 0, fontWeight: 600 }}>
              Real-Time RF Power Spectrum (64 FFT Bins)
            </h3>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              dBFS relative to ADC ceiling
            </span>
          </div>
          <canvas
            ref={canvasRef}
            width={540}
            height={200}
            style={{ width: '100%', height: '200px', borderRadius: '4px', display: 'block' }}
          />
        </div>

        {/* History Canvas */}
        <div className="card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <h3 style={{ fontSize: '14px', margin: 0, fontWeight: 600 }}>
              Telemetry Trend: Relative Power & SNR
            </h3>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Last {history.length} collections (10s intervals)
            </span>
          </div>
          <canvas
            ref={historyCanvasRef}
            width={540}
            height={200}
            style={{ width: '100%', height: '200px', borderRadius: '4px', display: 'block' }}
          />
        </div>
      </div>

      {/* Anomaly & Recovery Event Feed */}
      <div className="card" style={{ marginBottom: '24px', padding: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '15px', margin: 0, fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldAlert size={18} style={{ color: 'var(--warning)' }} />
              Signal Anomaly & Recovery Event Feed
            </h3>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Configurable automated diagnostic rules with deduplication and recovery tracking.
            </span>
          </div>

          <div style={{ display: 'flex', gap: '6px' }}>
            <button
              className={`btn ${anomalyFilter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '4px 10px', fontSize: '12px' }}
              onClick={() => setAnomalyFilter('all')}
            >
              All ({anomalies.length})
            </button>
            <button
              className={`btn ${anomalyFilter === 'active' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '4px 10px', fontSize: '12px' }}
              onClick={() => setAnomalyFilter('active')}
            >
              Active ({anomalies.filter((a) => !a.resolved).length})
            </button>
            <button
              className={`btn ${anomalyFilter === 'resolved' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '4px 10px', fontSize: '12px' }}
              onClick={() => setAnomalyFilter('resolved')}
            >
              Resolved ({anomalies.filter((a) => a.resolved).length})
            </button>
          </div>
        </div>

        {filteredAnomalies.length === 0 ? (
          <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
            <CheckCircle2 size={24} style={{ color: 'var(--success)', marginBottom: '8px' }} />
            <div>No signal anomalies in this view. RF parameters operating within nominal margins.</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {filteredAnomalies.map((anom) => (
              <div
                key={anom.id}
                style={{
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  padding: '12px 14px',
                  backgroundColor: anom.resolved ? '#f8fafc' : '#fff',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span
                      style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontSize: '10px',
                        fontWeight: 700,
                        backgroundColor: anom.resolved
                          ? '#e2e8f0'
                          : anom.severity === 'CRITICAL'
                          ? '#fee2e2'
                          : anom.severity === 'ERROR'
                          ? '#fef3c7'
                          : '#ffedd5',
                        color: anom.resolved
                          ? '#475569'
                          : anom.severity === 'CRITICAL'
                          ? '#991b1b'
                          : anom.severity === 'ERROR'
                          ? '#92400e'
                          : '#9a3412',
                      }}
                    >
                      {anom.severity}
                    </span>
                    <strong style={{ fontSize: '13px' }}>{anom.title}</strong>
                    {anom.occurrence_count > 1 && (
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        (Triggered {anom.occurrence_count} times)
                      </span>
                    )}
                  </div>

                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    {anom.explanation}
                  </div>

                  {anom.resolved && anom.recovery_note && (
                    <div style={{ fontSize: '12px', color: '#15803d', fontWeight: 500 }}>
                      ✓ {anom.recovery_note} (at {new Date(anom.resolved_at || '').toLocaleTimeString()})
                    </div>
                  )}
                </div>

                <div style={{ textAlign: 'right', fontSize: '11px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                  <div>Observed: <strong>{anom.observed_value}</strong> (Threshold: {anom.threshold_value})</div>
                  <div>Last seen: {new Date(anom.last_seen).toLocaleTimeString()}</div>
                  <div style={{ marginTop: '4px', fontWeight: 600, color: anom.resolved ? '#16a34a' : '#dc2626' }}>
                    {anom.resolved ? 'RESOLVED' : 'ACTIVE EVENT'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Reports & Exports Quick Bar */}
      <div className="card" style={{ padding: '16px' }}>
        <h3 style={{ fontSize: '14px', margin: '0 0 12px 0', fontWeight: 600 }}>
          Export SDR Telemetry & Diagnostic Reports
        </h3>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <a
            className="btn btn-secondary"
            href={getSDRReportDownloadUrl('measurements_csv', status?.device_id || undefined)}
            download
            style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Table size={14} />
            Telemetry CSV
          </a>

          <a
            className="btn btn-secondary"
            href={getSDRReportDownloadUrl('measurements_json', status?.device_id || undefined)}
            download
            style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <FileText size={14} />
            Telemetry JSON
          </a>

          <a
            className="btn btn-secondary"
            href={getSDRReportDownloadUrl('anomalies_csv')}
            download
            style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Table size={14} />
            Anomalies CSV
          </a>

          <a
            className="btn btn-primary"
            href={getSDRReportDownloadUrl('pdf', status?.device_id || undefined)}
            target="_blank"
            rel="noopener noreferrer"
            style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Download size={14} />
            Printable Diagnostic PDF/HTML Report
          </a>
        </div>
      </div>
    </div>
  );
};

