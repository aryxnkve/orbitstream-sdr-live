import React, { useState, useEffect, useRef } from 'react';
import { UploadCloud, File, AlertCircle, CheckCircle, ChevronDown, ChevronUp, RefreshCw, Sparkles } from 'lucide-react';
import { SampleFixture } from '../types';
import { uploadStreamFile, analyzeStreamFile, getSampleFixtures, loadSampleFixture } from '../services/api';

interface AnalyzePageProps {
  onAnalysisComplete: (fileId: string) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
}

export const AnalyzePage: React.FC<AnalyzePageProps> = ({
  onAnalysisComplete,
  isLoading,
  setIsLoading,
}) => {
  const [selectedFile, setSelectedFile] = useState<{
    fileId: string;
    filename: string;
    fileSize: number;
    detectedFormat: string;
    isSample?: boolean;
  } | null>(null);

  const [dragActive, setDragActive] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showFormats, setShowFormats] = useState(false);
  const [samples, setSamples] = useState<SampleFixture[]>([]);
  const [showSampleModal, setShowSampleModal] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getSampleFixtures()
      .then((data) => setSamples(data))
      .catch(() => {});
  }, []);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await processSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      await processSelectedFile(e.target.files[0]);
    }
  };

  const processSelectedFile = async (file: File) => {
    setErrorMsg(null);
    setIsLoading(true);
    try {
      const res = await uploadStreamFile(file);
      setSelectedFile({
        fileId: res.file_id,
        filename: res.filename,
        fileSize: res.file_size,
        detectedFormat: res.detected_format,
      });
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to upload stream file');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectSample = async (sampleName: string) => {
    setErrorMsg(null);
    setIsLoading(true);
    setShowSampleModal(false);
    try {
      const res = await loadSampleFixture(sampleName);
      setSelectedFile({
        fileId: res.file_id,
        filename: res.filename,
        fileSize: res.file_size,
        detectedFormat: res.detected_format,
        isSample: true,
      });
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load sample');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRunAnalysis = async () => {
    if (!selectedFile) return;
    setErrorMsg(null);
    setIsLoading(true);
    try {
      await analyzeStreamFile(selectedFile.fileId);
      onAnalysisComplete(selectedFile.fileId);
    } catch (err: any) {
      setErrorMsg(err.message || 'Analysis failed');
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setErrorMsg(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <h1 className="page-title">Analyze a satellite stream</h1>
      <p className="page-desc">
        Inspect receiver-output files, investigate packet issues, and export useful diagnostic reports.
      </p>

      {errorMsg && (
        <div
          style={{
            backgroundColor: 'var(--critical-bg)',
            color: 'var(--critical)',
            border: '1px solid var(--critical-border)',
            borderRadius: 'var(--radius-md)',
            padding: '12px 16px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <AlertCircle size={18} />
          <span style={{ fontSize: '13px' }}>{errorMsg}</span>
        </div>
      )}

      {!selectedFile ? (
        <div
          className={`dropzone ${dragActive ? 'active' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            style={{ display: 'none' }}
            onChange={handleFileInput}
            accept=".ts,.m2ts,.bin,.raw,.pcap"
          />
          <UploadCloud className="dropzone-icon" size={44} style={{ margin: '0 auto 12px' }} />
          <div className="dropzone-title">Choose a stream file</div>
          <div className="dropzone-text">Drag a file here or browse your computer.</div>
          <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
            >
              Browse files
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={(e) => {
                e.stopPropagation();
                setShowSampleModal(true);
              }}
            >
              <Sparkles size={14} />
              Try a sample file
            </button>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="card-header" style={{ marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <File className="text-accent" size={24} />
              <div>
                <div style={{ fontWeight: 600, fontSize: '15px' }}>{selectedFile.filename}</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  {(selectedFile.fileSize / 1024).toFixed(1)} KB &bull;{' '}
                  <span className="code-mono">
                    {selectedFile.detectedFormat === 'mpegts_188'
                      ? 'MPEG-TS (188 bytes)'
                      : selectedFile.detectedFormat === 'mpegts_192'
                      ? 'MPEG-TS (192 bytes prefix)'
                      : selectedFile.detectedFormat === 'mpegts_204'
                      ? 'MPEG-TS (204 bytes FEC)'
                      : 'Unknown stream format'}
                  </span>
                  {selectedFile.isSample && (
                    <span
                      style={{
                        marginLeft: '8px',
                        background: 'var(--accent-light)',
                        color: 'var(--accent)',
                        padding: '1px 6px',
                        borderRadius: '3px',
                        fontSize: '11px',
                        fontWeight: 600,
                      }}
                    >
                      SYNTHETIC FIXTURE
                    </span>
                  )}
                </div>
              </div>
            </div>
            <button type="button" className="btn btn-sm btn-secondary" onClick={handleReset}>
              Replace file
            </button>
          </div>

          <div
            style={{
              display: 'flex',
              gap: '12px',
              paddingTop: '16px',
              borderTop: '1px solid var(--border)',
            }}
          >
            <button
              type="button"
              className="btn btn-primary"
              style={{ flex: 1, padding: '10px' }}
              onClick={handleRunAnalysis}
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <RefreshCw size={15} className="spin" />
                  Analyzing stream...
                </>
              ) : (
                'Analyze file'
              )}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setShowSampleModal(true)}
              disabled={isLoading}
            >
              Try another sample
            </button>
          </div>
        </div>
      )}

      {/* Expandable supported formats */}
      <div style={{ marginTop: '28px' }}>
        <button
          type="button"
          onClick={() => setShowFormats(!showFormats)}
          style={{
            background: 'none',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '13px',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            fontWeight: 500,
            padding: '4px 0',
          }}
        >
          {showFormats ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          <span>Supported file formats</span>
        </button>

        {showFormats && (
          <div
            style={{
              marginTop: '10px',
              padding: '14px 18px',
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              fontSize: '13px',
              lineHeight: 1.6,
              color: 'var(--text-muted)',
            }}
          >
            <ul style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <li>
                <strong>MPEG-2 Transport Stream (188 bytes):</strong> Standard satellite/broadcast stream
                with sync byte <span className="code-mono">0x47</span>, PID demuxing, PAT/PMT parsing,
                and continuity checks.
              </li>
              <li>
                <strong>MPEG-TS with Timestamp (192 bytes):</strong> BDAV / M2TS captures with 4-byte
                arrival time prefix.
              </li>
              <li>
                <strong>MPEG-TS with FEC (204 bytes):</strong> DVB receiver output format with 16-byte
                Reed-Solomon FEC suffix.
              </li>
              <li>
                <strong>Generic Stream Encapsulation (GSE):</strong> Modular scaffold ready for DVB-S2
                baseband packets.
              </li>
            </ul>
          </div>
        )}
      </div>

      {/* Sample Fixtures Modal */}
      {showSampleModal && (
        <div className="modal-overlay" onClick={() => setShowSampleModal(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ fontWeight: 600, fontSize: '15px' }}>Choose a sample fixture</div>
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => setShowSampleModal(false)}
              >
                Close
              </button>
            </div>
            <div className="modal-body">
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '14px' }}>
                Synthetic test fixtures generated deterministically for testing and evaluation.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {samples.map((s) => (
                  <div
                    key={s.name}
                    style={{
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-md)',
                      padding: '12px 16px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      cursor: 'pointer',
                      transition: 'background 0.15s ease',
                    }}
                    className="sample-item"
                    onClick={() => handleSelectSample(s.name)}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '14px' }}>{s.filename}</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        {s.description}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-subtle)', marginTop: '2px' }}>
                        Size: {(s.file_size / 1024).toFixed(1)} KB &bull; Synthetic fixture
                      </div>
                    </div>
                    <button type="button" className="btn btn-sm btn-primary">
                      Select
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
