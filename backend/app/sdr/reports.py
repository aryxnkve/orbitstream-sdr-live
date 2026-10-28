"""
Report generators for RTL-SDR measurements, anomaly events, and diagnostic summaries.
Supports JSON, CSV, and printable HTML/PDF export formats.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List
from .models import SDRAnomalyModel, SDRMeasurementModel, SDRStatusResponse


class SDRReportGenerator:
    """Generates downloadable reports for SDR physical layer telemetry."""

    REPORT_VERSION = "0.1.0"

    def measurements_json(self, records: List[SDRMeasurementModel]) -> str:
        """Export measurement time series as JSON."""
        data = {
            "report_type": "sdr_measurements_export",
            "report_version": self.REPORT_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "measurements": [r.to_dict() for r in records],
        }
        return json.dumps(data, indent=2, default=str)

    def measurements_csv(self, records: List[SDRMeasurementModel]) -> str:
        """Export measurement time series as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Device ID", "Timestamp (UTC)", "Center Frequency (Hz)",
            "Sample Rate (Hz)", "Gain", "Relative Power (dBFS)", "Peak Power (dBFS)",
            "PAPR (dB)", "SNR Estimate (dB)", "Noise Floor (dBFS)", "DC I", "DC Q",
            "Clipping Ratio", "Valid", "Mode", "Device Type", "Serial",
        ])
        for r in records:
            writer.writerow([
                r.id,
                r.device_id,
                r.timestamp,
                r.center_frequency_hz,
                r.sample_rate_hz,
                r.gain,
                r.relative_power_dbfs,
                r.peak_power_dbfs,
                r.papr_db,
                r.snr_estimate_db,
                r.noise_floor_dbfs,
                r.dc_i,
                r.dc_q,
                r.clipping_ratio,
                r.is_valid,
                r.mode,
                r.device_type,
                r.serial,
            ])
        return output.getvalue()

    def anomalies_json(self, anomalies: List[SDRAnomalyModel]) -> str:
        """Export anomaly log as JSON."""
        data = {
            "report_type": "sdr_anomalies_export",
            "report_version": self.REPORT_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "anomaly_count": len(anomalies),
            "anomalies": [a.to_dict() for a in anomalies],
        }
        return json.dumps(data, indent=2, default=str)

    def anomalies_csv(self, anomalies: List[SDRAnomalyModel]) -> str:
        """Export anomaly log as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Device ID", "Rule ID", "Severity", "Title",
            "Explanation", "Metric", "Threshold", "Observed",
            "First Detected (UTC)", "Last Seen (UTC)", "Occurrences",
            "Resolved", "Resolved At (UTC)", "Recovery Note",
        ])
        for a in anomalies:
            writer.writerow([
                a.id,
                a.device_id,
                a.rule_id,
                a.severity,
                a.title,
                a.explanation,
                a.metric_name,
                a.threshold_value,
                a.observed_value,
                a.timestamp,
                a.last_seen,
                a.occurrence_count,
                a.resolved,
                a.resolved_at or "",
                a.recovery_note or "",
            ])
        return output.getvalue()

    def printable_html_report(
        self,
        status: SDRStatusResponse,
        records: List[SDRMeasurementModel],
        anomalies: List[SDRAnomalyModel],
    ) -> str:
        """Generate a styled printable HTML diagnostic report."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        anomaly_rows = ""
        for a in anomalies:
            sev_class = a.severity.lower()
            status_text = "Resolved" if a.resolved else "ACTIVE"
            anomaly_rows += f"""
            <tr>
              <td><span class="badge {sev_class}">{a.severity}</span></td>
              <td><strong>{a.title}</strong><br><small>{a.explanation}</small></td>
              <td>{a.metric_name}</td>
              <td>{a.threshold_value}</td>
              <td>{a.observed_value}</td>
              <td>{a.timestamp}</td>
              <td>{status_text}</td>
            </tr>
            """

        if not anomaly_rows:
            anomaly_rows = "<tr><td colspan='7' style='text-align:center;'>No signal anomalies detected.</td></tr>"

        measurement_rows = ""
        for r in records[-15:]:
            measurement_rows += f"""
            <tr>
              <td>{r.timestamp}</td>
              <td>{r.center_frequency_hz / 1e6:.3f} MHz</td>
              <td>{r.relative_power_dbfs:.2f} dBFS</td>
              <td>{r.snr_estimate_db:.2f} dB</td>
              <td>{r.noise_floor_dbfs:.2f} dBFS</td>
              <td>{r.papr_db:.2f} dB</td>
              <td>{'VALID' if r.is_valid else 'INVALID'}</td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ORBITSTREAM RTL-SDR Physical Layer Diagnostic Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 40px; color: #1e293b; background: #fff; }}
  h1 {{ margin: 0 0 4px 0; font-size: 22px; color: #0f172a; }}
  .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
  .card {{ border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin-bottom: 24px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
  .kpi-box {{ border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; background: #f8fafc; }}
  .kpi-label {{ font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; margin-bottom: 4px; }}
  .kpi-value {{ font-size: 20px; font-weight: 700; color: #0f172a; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
  th {{ background: #f1f5f9; padding: 8px 10px; text-align: left; border-bottom: 1px solid #cbd5e1; font-size: 11px; text-transform: uppercase; color: #475569; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #e2e8f0; }}
  .badge {{ display: inline-block; padding: 2px 6px; font-size: 10px; font-weight: 700; border-radius: 4px; text-transform: uppercase; }}
  .badge.critical {{ background: #fee2e2; color: #991b1b; }}
  .badge.error {{ background: #fef3c7; color: #92400e; }}
  .badge.warning {{ background: #ffedd5; color: #9a3412; }}
  .badge.info {{ background: #e0f2fe; color: #075985; }}
  .footer {{ margin-top: 40px; border-top: 1px solid #e2e8f0; padding-top: 12px; font-size: 11px; color: #94a3b8; display: flex; justify-content: space-between; }}
  @media print {{ body {{ margin: 10mm; }} }}
</style>
</head>
<body>
  <h1>ORBITSTREAM RTL-SDR Physical Layer Diagnostic Report</h1>
  <div class="subtitle">Generated on {now_str} | Station: {status.device_id or 'Unknown'} ({status.mode.upper()})</div>

  <div class="kpi-grid">
    <div class="kpi-box">
      <div class="kpi-label">Collector Status</div>
      <div class="kpi-value">{status.status.upper()}</div>
    </div>
    <div class="kpi-box">
      <div class="kpi-label">Relative Power</div>
      <div class="kpi-value">{f"{status.relative_power_dbfs:.1f} dBFS" if status.relative_power_dbfs is not None else "--"}</div>
    </div>
    <div class="kpi-box">
      <div class="kpi-label">SNR Estimate</div>
      <div class="kpi-value">{f"{status.snr_estimate_db:.1f} dB" if status.snr_estimate_db is not None else "--"}</div>
    </div>
    <div class="kpi-box">
      <div class="kpi-label">Active Anomalies</div>
      <div class="kpi-value">{status.active_anomaly_count}</div>
    </div>
  </div>

  <div class="card">
    <h3 style="margin-top:0;">Station & RF Tuner Parameters</h3>
    <table style="width: auto; min-width: 50%;">
      <tr><td><strong>Station ID:</strong></td><td>{status.device_id or 'N/A'}</td></tr>
      <tr><td><strong>Receiver Type:</strong></td><td>{status.device_type or 'RTL-SDR'}</td></tr>
      <tr><td><strong>Operating Mode:</strong></td><td>{status.mode.upper()} ({'Synthetic Data' if status.is_synthetic else 'Real Hardware'})</td></tr>
      <tr><td><strong>Center Frequency:</strong></td><td>{f"{status.frequency_mhz:.3f} MHz" if status.frequency_mhz else "N/A"}</td></tr>
      <tr><td><strong>Sample Rate:</strong></td><td>{f"{status.sample_rate_msps:.3f} MS/s" if status.sample_rate_msps else "N/A"}</td></tr>
      <tr><td><strong>Last Telemetry:</strong></td><td>{status.last_seen or "None"}</td></tr>
    </table>
  </div>

  <div class="card">
    <h3 style="margin-top:0;">Detected Signal Anomalies & Recovery Events</h3>
    <table>
      <thead>
        <tr>
          <th>Severity</th>
          <th>Anomaly / Finding</th>
          <th>Metric</th>
          <th>Threshold</th>
          <th>Observed</th>
          <th>Timestamp</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {anomaly_rows}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h3 style="margin-top:0;">Recent RF Telemetry Measurements</h3>
    <table>
      <thead>
        <tr>
          <th>Timestamp (UTC)</th>
          <th>Center Freq</th>
          <th>Relative Power</th>
          <th>SNR Estimate</th>
          <th>Noise Floor</th>
          <th>PAPR</th>
          <th>Validity</th>
        </tr>
      </thead>
      <tbody>
        {measurement_rows}
      </tbody>
    </table>
  </div>

  <div class="footer">
    <div>ORBITSTREAM Satellite Stream Analysis & Physical SDR Monitoring Platform</div>
    <div>Page 1 of 1</div>
  </div>
</body>
</html>"""
        return html

