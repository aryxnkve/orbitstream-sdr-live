import React, { useState, useEffect } from 'react';
import {
  ModulationType,
  SampleFormat,
  SignalSimulationRequest,
  SimulationResult,
  IQAnalysisResult,
  SignalSampleItem,
} from '../types';
import {
  simulateSignal,
  getSignalSamples,
  analyzeSignalSample,
  uploadAndAnalyzeIQ,
} from '../services/api';
import { ConstellationPlot } from './ConstellationPlot';
import {
  Radio,
  Sliders,
  UploadCloud,
  FileCode,
  Activity,
  AlertTriangle,
  Info,
  CheckCircle,
  HelpCircle,
  RotateCw,
  Zap,
} from 'lucide-react';

export const SignalLabPage: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'simulator' | 'analyzer' | 'chain'>('simulator');

  // ── Simulator State ───────────────────────────────────────────────
  const [simModulation, setSimModulation] = useState<ModulationType>('qpsk');
  const [simSnr, setSimSnr] = useState<number>(15.0);
  const [simPhaseOffset, setSimPhaseOffset] = useState<number>(0.0);
  const [simFreqOffset, setSimFreqOffset] = useState<number>(0.0);
  const [simSymbolCount, setSimSymbolCount] = useState<number>(1000);
  const [simSeed, setSimSeed] = useState<number>(42);

  const [simResult, setSimResult] = useState<SimulationResult | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  // ── Analyzer State ────────────────────────────────────────────────
  const [sampleFormat, setSampleFormat] = useState<SampleFormat>('float32_le');
  const [availableSamples, setAvailableSamples] = useState<SignalSampleItem[]>([]);
  const [loadingSampleName, setLoadingSampleName] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<IQAnalysisResult | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Run initial simulation on mount so user immediately sees a live constellation
  useEffect(() => {
    handleRunSimulation();
    loadSamplesList();
  }, []);

  const loadSamplesList = async () => {
    try {
      const samples = await getSignalSamples();
      setAvailableSamples(samples);
    } catch (e) {
      console.warn('Could not load sample list:', e);
    }
  };

  const handleRunSimulation = async (customParams?: Partial<SignalSimulationRequest>) => {
    setIsSimulating(true);
    setSimError(null);

    const req: SignalSimulationRequest = {
      modulation: customParams?.modulation ?? simModulation,
      snr_db: customParams?.snr_db ?? simSnr,
      phase_offset_deg: customParams?.phase_offset_deg ?? simPhaseOffset,
      freq_offset_norm: customParams?.freq_offset_norm ?? simFreqOffset,
      symbol_count: customParams?.symbol_count ?? simSymbolCount,
      seed: customParams?.seed ?? simSeed,
    };

    try {
      const res = await simulateSignal(req);
      setSimResult(res);
    } catch (err: any) {
      setSimError(err.message || 'Simulation failed');
    } finally {
      setIsSimulating(false);
    }
  };

  const handleApplyPreset = (preset: {
    mod: ModulationType;
    snr: number;
    phase: number;
    freq: number;
  }) => {
    setSimModulation(preset.mod);
    setSimSnr(preset.snr);
    setSimPhaseOffset(preset.phase);
    setSimFreqOffset(preset.freq);
    handleRunSimulation({
      modulation: preset.mod,
      snr_db: preset.snr,
      phase_offset_deg: preset.phase,
      freq_offset_norm: preset.freq,
    });
  };

  const handleAnalyzeBuiltInSample = async (sampleName: string) => {
    setLoadingSampleName(sampleName);
    setAnalysisError(null);
    try {
      const res = await analyzeSignalSample(sampleName);
      setAnalysisResult(res);
    } catch (err: any) {
      setAnalysisError(err.message || 'Failed to analyze sample');
    } finally {
      setLoadingSampleName(null);
    }
  };

  const handleUploadAndAnalyze = async () => {
    if (!selectedFile) return;
    setIsAnalyzing(true);
    setAnalysisError(null);

    try {
      const res = await uploadAndAnalyzeIQ(selectedFile, sampleFormat);
      setAnalysisResult(res);
    } catch (err: any) {
      setAnalysisError(err.message || 'Failed to analyze uploaded file');
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div>
      {/* Top Banner */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
          <h1 className="page-title" style={{ margin: 0 }}>
            Signal Lab — QPSK & 8PSK
          </h1>
          <span className="badge badge-info" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Radio size={12} />
            Physical Layer Modeling
          </span>
        </div>
        <p className="page-desc">
          Interactive modulation simulator, AWGN channel impairments, constellation analysis, and raw
          I/Q sample inspection. All calculations are deterministic, reproducible, and strictly separated from
          post-demodulation MPEG-TS packet analysis.
        </p>
      </div>

      {/* Navigation Sub-Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
        <button
          className={`btn btn-sm ${activeSubTab === 'simulator' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveSubTab('simulator')}
        >
          <Sliders size={14} />
          Modulation Simulator
        </button>
        <button
          className={`btn btn-sm ${activeSubTab === 'analyzer' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveSubTab('analyzer')}
        >
          <Activity size={14} />
          I/Q Capture Analyzer
        </button>
        <button
          className={`btn btn-sm ${activeSubTab === 'chain' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveSubTab('chain')}
        >
          <HelpCircle size={14} />
          Satellite Processing Chain & FAQ
        </button>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          SUBTAB 1: MODULATION SIMULATOR
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'simulator' && (
        <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: '20px' }}>
          {/* Controls Panel */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div className="card">
              <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Sliders size={16} />
                Simulation Parameters
              </h2>

              {/* Modulation Selection */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                  Modulation Scheme
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <button
                    type="button"
                    className={`btn btn-sm ${simModulation === 'qpsk' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => setSimModulation('qpsk')}
                    style={{ justifyContent: 'center' }}
                  >
                    QPSK (4-PSK)
                  </button>
                  <button
                    type="button"
                    className={`btn btn-sm ${simModulation === '8psk' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => setSimModulation('8psk')}
                    style={{ justifyContent: 'center' }}
                  >
                    8PSK (DVB-S2)
                  </button>
                </div>
                <span style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '4px', display: 'block' }}>
                  {simModulation === 'qpsk'
                    ? '2 bits/symbol, Gray coded (45°, 135°, 225°, 315°)'
                    : '3 bits/symbol, Gray coded per DVB-S2 standard'}
                </span>
              </div>

              {/* SNR Slider */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <label style={{ fontSize: '13px', fontWeight: 600 }}>SNR / Noise Level (Es/N0)</label>
                  <span className="code-mono" style={{ fontSize: '12px', fontWeight: 600 }}>
                    {simSnr.toFixed(1)} dB
                  </span>
                </div>
                <input
                  type="range"
                  min="-2"
                  max="30"
                  step="0.5"
                  value={simSnr}
                  onChange={(e) => setSimSnr(parseFloat(e.target.value))}
                  style={{ width: '100%' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-subtle)' }}>
                  <span>-2 dB (Noisy)</span>
                  <span>15 dB (Nominal)</span>
                  <span>30 dB (Pristine)</span>
                </div>
              </div>

              {/* Carrier Phase Offset */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <label style={{ fontSize: '13px', fontWeight: 600 }}>Carrier Phase Offset</label>
                  <span className="code-mono" style={{ fontSize: '12px', fontWeight: 600 }}>
                    {simPhaseOffset.toFixed(1)}°
                  </span>
                </div>
                <input
                  type="range"
                  min="-180"
                  max="180"
                  step="5"
                  value={simPhaseOffset}
                  onChange={(e) => setSimPhaseOffset(parseFloat(e.target.value))}
                  style={{ width: '100%' }}
                />
              </div>

              {/* Normalized Frequency Offset */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <label style={{ fontSize: '13px', fontWeight: 600 }}>Freq Drift (Δf / Rs)</label>
                  <span className="code-mono" style={{ fontSize: '12px', fontWeight: 600 }}>
                    {simFreqOffset.toFixed(4)}
                  </span>
                </div>
                <input
                  type="range"
                  min="-0.03"
                  max="0.03"
                  step="0.002"
                  value={simFreqOffset}
                  onChange={(e) => setSimFreqOffset(parseFloat(e.target.value))}
                  style={{ width: '100%' }}
                />
                <span style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>
                  Carrier frequency offset normalized to symbol rate
                </span>
              </div>

              {/* Symbol Count & Seed */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, marginBottom: '4px' }}>
                    Symbols
                  </label>
                  <select
                    className="select-input"
                    value={simSymbolCount}
                    onChange={(e) => setSimSymbolCount(parseInt(e.target.value))}
                    style={{ width: '100%', padding: '6px', fontSize: '12px' }}
                  >
                    <option value={500}>500 symbols</option>
                    <option value={1000}>1,000 symbols</option>
                    <option value={2000}>2,000 symbols</option>
                    <option value={5000}>5,000 symbols</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, marginBottom: '4px' }}>
                    RNG Seed
                  </label>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <input
                      type="number"
                      className="text-input"
                      value={simSeed}
                      onChange={(e) => setSimSeed(parseInt(e.target.value) || 0)}
                      style={{ width: '100%', padding: '6px', fontSize: '12px' }}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      title="Randomize seed"
                      onClick={() => setSimSeed(Math.floor(Math.random() * 9000) + 1000)}
                    >
                      <RotateCw size={12} />
                    </button>
                  </div>
                </div>
              </div>

              {/* Simulate Button */}
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => handleRunSimulation()}
                disabled={isSimulating}
                style={{ width: '100%', justifyContent: 'center' }}
              >
                {isSimulating ? 'Computing Simulation...' : 'Simulate & Calculate'}
              </button>

              {simError && (
                <div style={{ marginTop: '12px', color: 'var(--critical)', fontSize: '12px' }}>
                  {simError}
                </div>
              )}
            </div>

            {/* Quick Presets Card */}
            <div className="card">
              <h3 style={{ fontSize: '13px', fontWeight: 600, marginBottom: '10px' }}>
                Quick Presets
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleApplyPreset({ mod: 'qpsk', snr: 22, phase: 0, freq: 0 })}
                  style={{ justifyContent: 'flex-start', fontSize: '12px' }}
                >
                  <Zap size={13} style={{ color: 'var(--success)' }} />
                  Clean QPSK (22 dB SNR, Zero Offset)
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleApplyPreset({ mod: '8psk', snr: 18, phase: 0, freq: 0 })}
                  style={{ justifyContent: 'flex-start', fontSize: '12px' }}
                >
                  <Zap size={13} style={{ color: 'var(--accent)' }} />
                  8PSK Nominal (18 dB SNR)
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleApplyPreset({ mod: 'qpsk', snr: 7.5, phase: 15, freq: 0 })}
                  style={{ justifyContent: 'flex-start', fontSize: '12px' }}
                >
                  <Zap size={13} style={{ color: 'var(--warning)' }} />
                  Marginal QPSK (7.5 dB, 15° Phase Error)
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleApplyPreset({ mod: 'qpsk', snr: 2.0, phase: 30, freq: 0.005 })}
                  style={{ justifyContent: 'flex-start', fontSize: '12px' }}
                >
                  <Zap size={13} style={{ color: 'var(--critical)' }} />
                  Severely Impaired (2 dB, Frequency Drift)
                </button>
              </div>
            </div>
          </div>

          {/* Visualization & Results Panel */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Simulation Disclaimer Alert */}
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '10px',
                padding: '12px 14px',
                backgroundColor: 'var(--surface-alt)',
                border: '1px solid var(--border)',
                borderLeft: '4px solid var(--info)',
                borderRadius: 'var(--radius-md)',
                fontSize: '12px',
                lineHeight: 1.5,
              }}
            >
              <Info size={16} style={{ color: 'var(--info)', flexShrink: 0, marginTop: '2px' }} />
              <div>
                <strong>SIMULATED MATHEMATICAL MODEL (AWGN + Channel Impairments)</strong>
                <p style={{ color: 'var(--text-muted)', margin: '2px 0 0' }}>
                  These values are calculated mathematically from an Additive White Gaussian Noise channel model
                  and known transmitted pseudo-random bit streams. They represent theoretical communication models and are
                  <strong> NOT</strong> live RF measurements from physical satellite receiver hardware.
                </p>
              </div>
            </div>

            {/* Constellation Canvas Card */}
            <div className="card" style={{ padding: '16px' }}>
              <ConstellationPlot
                title={`${simResult?.modulation.toUpperCase() || 'QPSK'} Constellation Diagram (Simulation)`}
                subtitle={`SNR: ${simSnr} dB | Phase: ${simPhaseOffset}° | Total Symbols: ${simResult?.symbol_count || simSymbolCount}`}
                idealPoints={simResult?.ideal_constellation || []}
                txPoints={simResult?.tx_symbols || []}
                rxPoints={simResult?.rx_symbols || []}
              />
            </div>

            {/* Metrics Dashboard Grid */}
            {simResult && (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: '12px',
                }}
              >
                {/* Measured BER */}
                <div className="card" style={{ padding: '14px' }}>
                  <div className="stat-label">Measured BER</div>
                  <div
                    className="stat-value"
                    style={{
                      color:
                        simResult.ber === 0
                          ? 'var(--success)'
                          : simResult.ber < 0.01
                          ? 'var(--warning)'
                          : 'var(--critical)',
                    }}
                  >
                    {simResult.ber === 0 ? '0.0000' : simResult.ber.toExponential(3)}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '4px' }}>
                    {simResult.bit_errors} errors / {simResult.bit_count} bits
                  </div>
                </div>

                {/* Theoretical BER */}
                <div className="card" style={{ padding: '14px' }}>
                  <div className="stat-label">Theoretical BER</div>
                  <div className="stat-value" style={{ color: 'var(--text-main)' }}>
                    {simResult.theoretical_ber === 0 ? '0.0000' : simResult.theoretical_ber.toExponential(3)}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '4px' }}>
                    Q(√(2·Eb/N0)) AWGN
                  </div>
                </div>

                {/* EVM RMS */}
                <div className="card" style={{ padding: '14px' }}>
                  <div className="stat-label">RMS EVM</div>
                  <div
                    className="stat-value"
                    style={{
                      color:
                        simResult.evm_rms_percent < 12
                          ? 'var(--success)'
                          : simResult.evm_rms_percent < 22
                          ? 'var(--warning)'
                          : 'var(--critical)',
                    }}
                  >
                    {simResult.evm_rms_percent.toFixed(1)}%
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '4px' }}>
                    Error Vector Magnitude
                  </div>
                </div>

                {/* Symbol Error Rate */}
                <div className="card" style={{ padding: '14px' }}>
                  <div className="stat-label">Measured SER</div>
                  <div className="stat-value" style={{ color: 'var(--text-main)' }}>
                    {(simResult.ser * 100).toFixed(2)}%
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '4px' }}>
                    {simResult.symbol_errors} / {simResult.symbol_count} symbols
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUBTAB 2: I/Q CAPTURE ANALYZER
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'analyzer' && (
        <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '20px' }}>
          {/* Left Column: Formats & Upload */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Supported Formats Card */}
            <div className="card">
              <h2 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileCode size={16} />
                Supported I/Q Binary Formats
              </h2>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                ORBITSTREAM accepts explicitly aligned raw complex baseband captures with interleaved In-Phase (I)
                and Quadrature (Q) samples:
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
                <div style={{ padding: '8px', background: 'var(--surface-alt)', borderRadius: 'var(--radius-sm)' }}>
                  <strong>Float32 Little-Endian (float32_le)</strong>
                  <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                    4 bytes I + 4 bytes Q (8 bytes/sample). Standard SDR capture format.
                  </div>
                </div>
                <div style={{ padding: '8px', background: 'var(--surface-alt)', borderRadius: 'var(--radius-sm)' }}>
                  <strong>Int16 Little-Endian (int16_le)</strong>
                  <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                    2 bytes I + 2 bytes Q (4 bytes/sample), signed [-32768, 32767]. Common in HackRF/BladeRF.
                  </div>
                </div>
                <div style={{ padding: '8px', background: 'var(--surface-alt)', borderRadius: 'var(--radius-sm)' }}>
                  <strong>UInt8 Unsigned (uint8)</strong>
                  <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                    1 byte I + 1 byte Q (2 bytes/sample), 127.5 DC bias. Standard RTL-SDR format.
                  </div>
                </div>
              </div>
            </div>

            {/* Built-in Synthetic Samples */}
            <div className="card">
              <h3 style={{ fontSize: '13px', fontWeight: 600, marginBottom: '8px' }}>
                Load Reproducible Test Vectors
              </h3>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                Evaluate the analyzer using pre-generated synthetic vectors:
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleAnalyzeBuiltInSample('qpsk_clean_20db')}
                  disabled={loadingSampleName !== null}
                  style={{ justifyContent: 'flex-start', textAlign: 'left' }}
                >
                  <CheckCircle size={14} style={{ color: 'var(--success)' }} />
                  <div>
                    <div style={{ fontWeight: 600 }}>Clean QPSK Reference (20 dB SNR)</div>
                    <div style={{ fontSize: '10px', color: 'var(--text-subtle)' }}>Float32 LE • 1,000 symbols</div>
                  </div>
                </button>

                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleAnalyzeBuiltInSample('8psk_snr_18db')}
                  disabled={loadingSampleName !== null}
                  style={{ justifyContent: 'flex-start', textAlign: 'left' }}
                >
                  <CheckCircle size={14} style={{ color: 'var(--accent)' }} />
                  <div>
                    <div style={{ fontWeight: 600 }}>8PSK Constellation Vector (18 dB SNR)</div>
                    <div style={{ fontSize: '10px', color: 'var(--text-subtle)' }}>Float32 LE • 8-cluster distribution</div>
                  </div>
                </button>

                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleAnalyzeBuiltInSample('qpsk_int16_noisy')}
                  disabled={loadingSampleName !== null}
                  style={{ justifyContent: 'flex-start', textAlign: 'left' }}
                >
                  <AlertTriangle size={14} style={{ color: 'var(--warning)' }} />
                  <div>
                    <div style={{ fontWeight: 600 }}>Impaired QPSK (8 dB SNR, 15° Offset)</div>
                    <div style={{ fontSize: '10px', color: 'var(--text-subtle)' }}>Int16 LE • Carrier phase shift</div>
                  </div>
                </button>
              </div>
            </div>

            {/* Custom File Upload */}
            <div className="card">
              <h3 style={{ fontSize: '13px', fontWeight: 600, marginBottom: '10px' }}>
                Analyze Local I/Q Recording
              </h3>

              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, marginBottom: '4px' }}>
                  Capture Sample Format
                </label>
                <select
                  className="select-input"
                  value={sampleFormat}
                  onChange={(e) => setSampleFormat(e.target.value as SampleFormat)}
                  style={{ width: '100%', padding: '6px', fontSize: '12px' }}
                >
                  <option value="float32_le">Float32 LE (8 bytes / sample)</option>
                  <option value="int16_le">Int16 LE (4 bytes / sample)</option>
                  <option value="uint8">UInt8 (2 bytes / sample, RTL-SDR)</option>
                </select>
              </div>

              <div style={{ marginBottom: '14px' }}>
                <input
                  type="file"
                  accept=".iq,.raw,.bin"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  style={{ fontSize: '12px', width: '100%' }}
                />
              </div>

              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleUploadAndAnalyze}
                disabled={!selectedFile || isAnalyzing}
                style={{ width: '100%', justifyContent: 'center' }}
              >
                {isAnalyzing ? 'Analyzing I/Q Samples...' : 'Analyze Uploaded File'}
              </button>

              {analysisError && (
                <div style={{ marginTop: '10px', color: 'var(--critical)', fontSize: '12px' }}>
                  {analysisError}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Analysis Results */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Scientific Uncertainty Notice */}
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '10px',
                padding: '12px 14px',
                backgroundColor: 'var(--surface-alt)',
                border: '1px solid var(--border)',
                borderLeft: '4px solid var(--warning)',
                borderRadius: 'var(--radius-md)',
                fontSize: '12px',
                lineHeight: 1.5,
              }}
            >
              <AlertTriangle size={16} style={{ color: 'var(--warning)', flexShrink: 0, marginTop: '2px' }} />
              <div>
                <strong>STATISTICAL ESTIMATION & UNCERTAINTY NOTICE</strong>
                <p style={{ color: 'var(--text-muted)', margin: '2px 0 0' }}>
                  Modulation classification uses 4th and 8th order circular phase moments (R4 and R8). Exact
                  verification requires root-raised-cosine (RRC) matched filtering, symbol timing recovery
                  (Gardner/Mueller-Müller), Costas carrier tracking loop, and LDPC/BCH FEC frame synchronization.
                  I/Q measurements indicate statistical signal properties, not definitive satellite transmission validity.
                </p>
              </div>
            </div>

            {analysisResult ? (
              <>
                {/* Constellation Plot */}
                <div className="card" style={{ padding: '16px' }}>
                  <ConstellationPlot
                    title={`Analyzed I/Q Constellation — ${analysisResult.filename}`}
                    subtitle={`Sample format: ${analysisResult.sample_format} | Total samples in buffer: ${analysisResult.total_samples.toLocaleString()}`}
                    rxPoints={analysisResult.constellation_samples}
                  />
                </div>

                {/* Metrics Cards */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(4, 1fr)',
                    gap: '12px',
                  }}
                >
                  <div className="card" style={{ padding: '14px' }}>
                    <div className="stat-label">Estimated Modulation</div>
                    <div className="stat-value" style={{ color: 'var(--accent)', fontSize: '18px' }}>
                      {analysisResult.estimated_modulation}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '4px' }}>
                      Confidence: {analysisResult.modulation_confidence}%
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div className="stat-label">Estimated SNR</div>
                    <div
                      className="stat-value"
                      style={{
                        color: analysisResult.estimated_snr_db > 12 ? 'var(--success)' : 'var(--warning)',
                      }}
                    >
                      {analysisResult.estimated_snr_db.toFixed(1)} dB
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '4px' }}>
                      Derived from EVM
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div className="stat-label">Estimated EVM</div>
                    <div className="stat-value">{analysisResult.estimated_evm_percent.toFixed(1)}%</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '4px' }}>
                      RMS Error Vector
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px' }}>
                    <div className="stat-label">Carrier Phase Offset</div>
                    <div className="stat-value">{analysisResult.estimated_phase_offset_deg.toFixed(1)}°</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '4px' }}>
                      Freq drift: {analysisResult.estimated_freq_offset_norm.toFixed(4)}
                    </div>
                  </div>
                </div>

                {/* Explanation text */}
                <div className="card" style={{ fontSize: '13px', lineHeight: 1.6, color: 'var(--text-muted)' }}>
                  <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: '4px' }}>
                    Analysis Findings & Context:
                  </div>
                  <p>{analysisResult.uncertainty_note}</p>
                </div>
              </>
            ) : (
              <div
                className="card"
                style={{
                  padding: '48px 24px',
                  textAlign: 'center',
                  color: 'var(--text-muted)',
                }}
              >
                <Activity size={36} style={{ margin: '0 auto 12px', color: 'var(--text-subtle)' }} />
                <h3 style={{ fontSize: '15px', color: 'var(--text-main)', marginBottom: '6px' }}>
                  No I/Q File Analyzed Yet
                </h3>
                <p style={{ fontSize: '13px', maxWidth: '420px', margin: '0 auto 16px' }}>
                  Click one of the pre-generated test vectors on the left (e.g. Clean QPSK or 8PSK), or upload a raw
                  interleaved binary I/Q recording to estimate modulation, SNR, EVM, and carrier offsets.
                </p>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleAnalyzeBuiltInSample('qpsk_clean_20db')}
                >
                  Load Clean QPSK Reference Vector
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          SUBTAB 3: SATELLITE SIGNAL CHAIN & FAQ
          ───────────────────────────────────────────────────────────── */}
      {activeSubTab === 'chain' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Signal Chain Diagram Card */}
          <div className="card">
            <h2 className="section-title">Satellite Communications Processing Chain</h2>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '18px' }}>
              Understanding where the Signal Lab fits in the physical vs. transport layer architecture:
            </p>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(5, 1fr)',
                gap: '12px',
                marginBottom: '16px',
              }}
            >
              {/* Step 1 */}
              <div
                style={{
                  padding: '12px',
                  background: 'var(--surface-alt)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border)',
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--accent)', marginBottom: '4px' }}>
                  STAGE 1
                </div>
                <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '4px' }}>RF Downconversion</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Antenna / LNB receives Ku/Ka/C band down to L-band (950–2150 MHz).
                </div>
              </div>

              {/* Step 2 */}
              <div
                style={{
                  padding: '12px',
                  background: 'var(--accent-light)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--accent-border)',
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--accent)', marginBottom: '4px' }}>
                  STAGE 2 • SIGNAL LAB
                </div>
                <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '4px' }}>I/Q Demodulation</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Quadrature ADC sampling, RRC filtering, Costas loop, QPSK/8PSK constellation slicing.
                </div>
              </div>

              {/* Step 3 */}
              <div
                style={{
                  padding: '12px',
                  background: 'var(--surface-alt)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border)',
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--accent)', marginBottom: '4px' }}>
                  STAGE 3
                </div>
                <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '4px' }}>FEC Decoding</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  LDPC (Low-Density Parity Check) inner code + BCH outer code corrects bit flips.
                </div>
              </div>

              {/* Step 4 */}
              <div
                style={{
                  padding: '12px',
                  background: 'var(--surface-alt)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border)',
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--accent)', marginBottom: '4px' }}>
                  STAGE 4
                </div>
                <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '4px' }}>Baseband Framing</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  DVB-S2 BBFRAME reconstruction and mode adaptation (MATYPE header).
                </div>
              </div>

              {/* Step 5 */}
              <div
                style={{
                  padding: '12px',
                  background: 'var(--success-bg)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--success-border)',
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--success)', marginBottom: '4px' }}>
                  STAGE 5 • ORBITSTREAM CORE
                </div>
                <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '4px' }}>MPEG-TS Transport</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  188-byte packet stream with PIDs, PAT/PMT tables, continuity counters, and video/audio ES.
                </div>
              </div>
            </div>
          </div>

          {/* Educational Q&A Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div className="card">
              <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '8px', color: 'var(--text-main)' }}>
                Why can't RF signal quality (SNR, EVM) be derived from an MPEG-TS file?
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                MPEG Transport Stream files (.ts) represent <strong>post-demodulated, error-corrected digital bitstreams</strong>.
                By the time receiver hardware writes transport stream packets to disk, all analog RF characteristics (carrier frequency offset,
                phase noise, In-Phase/Quadrature voltage levels, and noise variance) have already been stripped away.
              </p>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6, marginTop: '8px' }}>
                If receiver SNR drops below the quasi-error-free (QEF) threshold, the hardware FEC decoder fails, and either drops packets
                (causing Continuity Counter gaps) or sets the Transport Error Indicator (TEI) bit in the TS packet header.
                Therefore, ORBITSTREAM inspects TEI bits and CC counters to detect transport losses, while the <strong>Signal Lab</strong> inspects
                the preceding analog/baseband I/Q domain.
              </p>
            </div>

            <div className="card">
              <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '8px', color: 'var(--text-main)' }}>
                What is EVM (Error Vector Magnitude) and why is it important?
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                Error Vector Magnitude (EVM) measures the Euclidean distance between a received complex I/Q symbol and its
                ideal reference point on the constellation diagram, expressed as an RMS percentage of the reference symbol's magnitude.
              </p>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6, marginTop: '8px' }}>
                High EVM indicates degradation before bit errors occur. Common causes include:
              </p>
              <ul style={{ fontSize: '12px', color: 'var(--text-muted)', paddingLeft: '18px', marginTop: '6px' }}>
                <li>Low SNR from rain fade or dish misalignment</li>
                <li>Local oscillator phase noise or carrier frequency drift</li>
                <li>I/Q amplitude imbalance or quadrature phase skew</li>
                <li>Non-linear amplifier distortion (compression/AM-PM conversion)</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
