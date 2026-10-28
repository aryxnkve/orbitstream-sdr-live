export type Severity = 'critical' | 'warning' | 'info' | 'ok';

export type Certainty = 'confirmed' | 'observed' | 'heuristic' | 'possible' | 'unknown';

export interface DiagnosticFinding {
  id: string;
  rule_id: string;
  severity: Severity;
  title: string;
  explanation: string;
  technical_detail: string;
  evidence: Record<string, any>;
  affected_pid?: number | null;
  affected_pid_hex?: string;
  affected_stream?: string;
  packet_indices: number[];
  byte_offsets: number[];
  expected_value?: string | null;
  observed_value?: string | null;
  certainty: Certainty;
  possible_causes: string[];
  recommended_steps: string[];
  limitations: string[];
}

export interface PIDInfo {
  pid: number;
  pid_hex: string;
  packet_count: number;
  byte_count: number;
  label: string;
  stream_type?: number | null;
  stream_type_name?: string;
  program_number?: number | null;
  has_errors: boolean;
  error_count: number;
  scrambled_count: number;
  is_scrambled: boolean;
  continuity_errors: number;
  first_packet_index: number;
  last_packet_index: number;
}

export interface PMTStream {
  stream_type: number;
  stream_type_name: string;
  elementary_pid: number;
  elementary_pid_hex: string;
  es_info_length: number;
}

export interface ProgramInfo {
  program_number: number;
  pcr_pid: string;
  streams: PMTStream[];
}

export interface AnalysisSummary {
  file_id: string;
  filename: string;
  file_size: number;
  detected_format: string;
  packet_size: number;
  total_packets: number;
  valid_packets: number;
  error_packets: number;
  null_packets: number;
  scrambled_packets: number;
  pid_count: number;
  program_count: number;
  findings: DiagnosticFinding[];
  findings_by_severity: Record<string, number>;
  pids: PIDInfo[];
  programs: ProgramInfo[];
  warnings: string[];
  errors: string[];
  parser_version: string;
  analysis_timestamp: string;
  is_synthetic?: boolean;
  sync_losses: number;
}

export interface SampleFixture {
  name: string;
  filename: string;
  file_size: number;
  description: string;
  is_synthetic: boolean;
}

export interface PacketDisplay {
  index: number;
  offset: number;
  offset_hex: string;
  sync_byte: string;
  pid: number;
  pid_hex: string;
  tei: boolean;
  pusi: boolean;
  priority: boolean;
  scrambling: number;
  scrambling_name: string;
  afc: number;
  afc_name: string;
  cc: number;
  has_payload: boolean;
  is_valid: boolean;
  parse_error?: string | null;
  raw_hex?: string | null;
  payload_hex?: string | null;
  adaptation_field?: {
    length: number;
    discontinuity_indicator: boolean;
    random_access_indicator: boolean;
    elementary_stream_priority: boolean;
    pcr_flag: boolean;
    opcr_flag: boolean;
    pcr?: number | null;
  } | null;
  context?: PacketDisplay[];
}

export interface ReplayResponse {
  packets: PacketDisplay[];
  total: number;
  start: number;
  count: number;
  available_pids: number[];
}

export interface FaultScenarioInfo {
  id: string;
  name: string;
  description: string;
  parameters: string[];
}

export interface FaultResult {
  scenario: string;
  description: string;
  source_file: string;
  modified_file: string;
  source_hash: string;
  modified_hash: string;
  packets_affected: number;
  modifications: Array<{
    packet_index?: number;
    byte_offset?: number;
    original_value?: string;
    new_value?: string;
    reason?: string;
  }>;
  expected_diagnostic: string;
  success: boolean;
  error?: string;
}

export interface SimulationResponse {
  sim_id: string;
  fault_result: FaultResult;
  modified_analysis: AnalysisSummary;
  verification: {
    status: 'pass' | 'fail' | 'inconclusive';
    reason: string;
    expected: string;
    new_finding_count: number;
    new_findings: Array<{
      rule_id: string;
      title: string;
      severity: string;
    }>;
  };
}

// ── Signal Lab (QPSK / 8PSK) Types ──────────────────────────────────

export type ModulationType = 'qpsk' | '8psk';

export type SampleFormat = 'float32_le' | 'int16_le' | 'uint8';

export interface ConstellationPoint {
  i: number;
  q: number;
  symbol_index?: number;
  bit_pattern?: string;
}

export interface SignalSimulationRequest {
  modulation: ModulationType;
  snr_db: number;
  phase_offset_deg: number;
  freq_offset_norm: number;
  symbol_count: number;
  seed?: number;
}

export interface SimulationResult {
  modulation: ModulationType;
  snr_db: number;
  symbol_count: number;
  bit_count: number;
  bit_errors: number;
  symbol_errors: number;
  ber: number;
  ser: number;
  theoretical_ber: number;
  theoretical_ser: number;
  evm_rms_percent: number;
  phase_offset_deg: number;
  freq_offset_norm: number;
  ideal_constellation: ConstellationPoint[];
  tx_symbols: ConstellationPoint[];
  rx_symbols: ConstellationPoint[];
  is_simulated: boolean;
  disclaimer: string;
}

export interface IQAnalysisResult {
  filename: string;
  total_samples: number;
  sample_format: SampleFormat;
  estimated_modulation: string;
  modulation_confidence: number;
  estimated_snr_db: number;
  estimated_evm_percent: number;
  estimated_freq_offset_norm: number;
  estimated_phase_offset_deg: number;
  constellation_samples: ConstellationPoint[];
  uncertainty_note: string;
  is_estimate: boolean;
}

export interface SignalSampleItem {
  name: string;
  filename: string;
  file_size: number;
  format: SampleFormat;
  description: string;
}

// ── SDR Telemetry & Monitoring Types ──────────────────────────────

export interface SDRMeasurement {
  id: number;
  device_id: string;
  timestamp: string;
  center_frequency_hz: number;
  sample_rate_hz: number;
  gain: string;
  relative_power_dbfs: number;
  peak_power_dbfs: number;
  papr_db: number;
  snr_estimate_db: number;
  noise_floor_dbfs: number;
  dc_i: number;
  dc_q: number;
  clipping_ratio: number;
  spectrum_bins: number[];
  sample_count: number;
  is_valid: boolean;
  validation_notes: string;
  mode: 'hardware' | 'demo';
  device_type: string;
  serial: string;
  is_synthetic: boolean;
  created_at: string;
}

export interface SDRAnomaly {
  id: number;
  device_id: string;
  rule_id: string;
  severity: 'CRITICAL' | 'ERROR' | 'WARNING' | 'INFO';
  title: string;
  explanation: string;
  metric_name: string;
  threshold_value: number;
  observed_value: number;
  timestamp: string;
  last_seen: string;
  occurrence_count: number;
  resolved: boolean;
  resolved_at?: string | null;
  recovery_note?: string | null;
}

export interface SDRStatus {
  status: 'active' | 'degraded' | 'offline' | 'demo';
  device_id?: string | null;
  device_type?: string | null;
  is_synthetic: boolean;
  mode: 'hardware' | 'demo';
  last_seen?: string | null;
  frequency_mhz?: number | null;
  sample_rate_msps?: number | null;
  relative_power_dbfs?: number | null;
  snr_estimate_db?: number | null;
  active_anomaly_count: number;
  active_anomalies: SDRAnomaly[];
  latest_measurement?: SDRMeasurement | null;
}

