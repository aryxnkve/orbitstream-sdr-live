import {
  AnalysisSummary,
  SampleFixture,
  ReplayResponse,
  PacketDisplay,
  FaultScenarioInfo,
  SimulationResponse,
  SignalSimulationRequest,
  SimulationResult,
  IQAnalysisResult,
  SampleFormat,
  SignalSampleItem,
  SDRMeasurement,
  SDRAnomaly,
  SDRStatus,
} from '../types';

const BASE_URL = '/api';

export async function uploadStreamFile(file: File): Promise<{
  file_id: string;
  filename: string;
  file_size: number;
  detected_format: string;
}> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${BASE_URL}/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(errorData.detail || 'Upload failed');
  }

  return res.json();
}

export async function analyzeStreamFile(fileId: string): Promise<AnalysisSummary> {
  const res = await fetch(`${BASE_URL}/analyze/${fileId}`, {
    method: 'POST',
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Analysis failed' }));
    throw new Error(errorData.detail || 'Analysis failed');
  }

  return res.json();
}

export async function getAnalysis(fileId: string): Promise<AnalysisSummary> {
  const res = await fetch(`${BASE_URL}/analysis/${fileId}`);
  if (!res.ok) {
    throw new Error('Analysis not found');
  }
  return res.json();
}

export async function getSampleFixtures(): Promise<SampleFixture[]> {
  const res = await fetch(`${BASE_URL}/samples`);
  if (!res.ok) {
    throw new Error('Failed to load sample fixtures');
  }
  const data = await res.json();
  return data.samples || [];
}

export async function loadSampleFixture(sampleName: string): Promise<{
  file_id: string;
  filename: string;
  file_size: number;
  detected_format: string;
  is_synthetic: boolean;
}> {
  const res = await fetch(`${BASE_URL}/samples/${sampleName}/load`, {
    method: 'POST',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to load sample' }));
    throw new Error(err.detail || 'Failed to load sample');
  }

  return res.json();
}

export async function getReplayPackets(
  fileId: string,
  start: number = 0,
  count: number = 20,
  pid?: number
): Promise<ReplayResponse> {
  let url = `${BASE_URL}/replay/${fileId}/packets?start=${start}&count=${count}`;
  if (pid !== undefined && pid !== null) {
    url += `&pid=${pid}`;
  }

  const res = await fetch(url);
  if (!res.ok) {
    throw new Error('Failed to fetch replay packets');
  }
  return res.json();
}

export async function getSinglePacket(
  fileId: string,
  packetIndex: number
): Promise<PacketDisplay> {
  const res = await fetch(`${BASE_URL}/replay/${fileId}/packet/${packetIndex}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch packet ${packetIndex}`);
  }
  return res.json();
}

export async function getFaultScenarios(): Promise<FaultScenarioInfo[]> {
  const res = await fetch(`${BASE_URL}/simulate/scenarios`);
  if (!res.ok) {
    throw new Error('Failed to fetch simulation scenarios');
  }
  const data = await res.json();
  return data.scenarios || [];
}

export async function runSimulation(params: {
  file_id: string;
  scenario: string;
  target_pid?: number;
  target_packet_indices?: number[];
  cc_skip?: number;
  corrupt_byte?: number;
  scrambling_value?: number;
  description?: string;
}): Promise<SimulationResponse> {
  const res = await fetch(`${BASE_URL}/simulate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(params),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Simulation failed' }));
    throw new Error(err.detail || 'Simulation failed');
  }

  return res.json();
}

export function getReportDownloadUrl(
  fileId: string,
  type: 'summary' | 'findings_json' | 'findings_csv' | 'pids_csv' | 'comparison'
): string {
  switch (type) {
    case 'summary':
      return `${BASE_URL}/reports/${fileId}/summary`;
    case 'findings_json':
      return `${BASE_URL}/reports/${fileId}/findings/json`;
    case 'findings_csv':
      return `${BASE_URL}/reports/${fileId}/findings/csv`;
    case 'pids_csv':
      return `${BASE_URL}/reports/${fileId}/pids/csv`;
    case 'comparison':
      return `${BASE_URL}/reports/${fileId}/comparison`;
  }
}

// ── Signal Lab API ──────────────────────────────────────────────────

export async function simulateSignal(req: SignalSimulationRequest): Promise<SimulationResult> {
  const res = await fetch(`${BASE_URL}/signal/simulate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Signal simulation failed' }));
    throw new Error(err.detail || 'Signal simulation failed');
  }

  return res.json();
}

export async function getSignalSamples(): Promise<SignalSampleItem[]> {
  const res = await fetch(`${BASE_URL}/signal/samples`);
  if (!res.ok) {
    throw new Error('Failed to fetch signal samples');
  }
  const data = await res.json();
  return data.samples || [];
}

export async function analyzeSignalSample(sampleName: string): Promise<IQAnalysisResult> {
  const res = await fetch(`${BASE_URL}/signal/samples/${sampleName}/analyze`, {
    method: 'POST',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to analyze signal sample' }));
    throw new Error(err.detail || 'Failed to analyze signal sample');
  }

  return res.json();
}

export async function uploadAndAnalyzeIQ(
  file: File,
  sampleFormat: SampleFormat = 'float32_le'
): Promise<IQAnalysisResult> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${BASE_URL}/signal/upload?sample_format=${sampleFormat}`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'I/Q file upload/analysis failed' }));
    throw new Error(err.detail || 'I/Q file upload/analysis failed');
  }

  return res.json();
}

// ── RTL-SDR Physical Layer Telemetry API ─────────────────────────────

export async function getSDRLatestStatus(deviceId?: string): Promise<SDRStatus> {
  let url = `${BASE_URL}/sdr/latest`;
  if (deviceId) {
    url += `?device_id=${encodeURIComponent(deviceId)}`;
  }
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error('Failed to fetch SDR status');
  }
  return res.json();
}

export async function getSDRHistory(params?: {
  start_time?: string;
  end_time?: string;
  limit?: number;
  device_id?: string;
}): Promise<{ count: number; measurements: SDRMeasurement[] }> {
  const query = new URLSearchParams();
  if (params?.start_time) query.append('start_time', params.start_time);
  if (params?.end_time) query.append('end_time', params.end_time);
  if (params?.limit) query.append('limit', params.limit.toString());
  if (params?.device_id) query.append('device_id', params.device_id);

  const res = await fetch(`${BASE_URL}/sdr/history?${query.toString()}`);
  if (!res.ok) {
    throw new Error('Failed to fetch SDR telemetry history');
  }
  return res.json();
}

export async function getSDRAnomalies(params?: {
  resolved?: boolean;
  severity?: string;
  limit?: number;
  device_id?: string;
}): Promise<{ count: number; anomalies: SDRAnomaly[] }> {
  const query = new URLSearchParams();
  if (params?.resolved !== undefined) query.append('resolved', params.resolved.toString());
  if (params?.severity) query.append('severity', params.severity);
  if (params?.limit) query.append('limit', params.limit.toString());
  if (params?.device_id) query.append('device_id', params.device_id);

  const res = await fetch(`${BASE_URL}/sdr/anomalies?${query.toString()}`);
  if (!res.ok) {
    throw new Error('Failed to fetch SDR anomaly feed');
  }
  return res.json();
}

export function getSDRReportDownloadUrl(
  type: 'measurements_json' | 'measurements_csv' | 'anomalies_json' | 'anomalies_csv' | 'pdf',
  deviceId?: string
): string {
  const devParam = deviceId ? `&device_id=${encodeURIComponent(deviceId)}` : '';
  switch (type) {
    case 'measurements_json':
      return `${BASE_URL}/sdr/reports/export?format=json${devParam}`;
    case 'measurements_csv':
      return `${BASE_URL}/sdr/reports/export?format=csv${devParam}`;
    case 'anomalies_json':
      return `${BASE_URL}/sdr/reports/anomalies?format=json`;
    case 'anomalies_csv':
      return `${BASE_URL}/sdr/reports/anomalies?format=csv`;
    case 'pdf':
      return `${BASE_URL}/sdr/reports/pdf?${deviceId ? `device_id=${encodeURIComponent(deviceId)}` : ''}`;
  }
}
