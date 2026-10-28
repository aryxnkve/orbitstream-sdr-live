import React, { useState, useEffect } from 'react';
import { AnalysisSummary, PacketDisplay, DiagnosticFinding } from '../types';
import { getReplayPackets, getSinglePacket } from '../services/api';
import { Play, Pause, ChevronLeft, ChevronRight, SkipBack, SkipForward, Filter, Search } from 'lucide-react';

interface ReplayPageProps {
  summary: AnalysisSummary;
  initialPid?: number;
  initialPacketIndex?: number;
  onReturnToFinding?: () => void;
}

export const ReplayPage: React.FC<ReplayPageProps> = ({
  summary,
  initialPid,
  initialPacketIndex = 0,
  onReturnToFinding,
}) => {
  const [currentIndex, setCurrentIndex] = useState(initialPacketIndex);
  const [currentPacket, setCurrentPacket] = useState<PacketDisplay | null>(null);
  const [surroundingPackets, setSurroundingPackets] = useState<PacketDisplay[]>([]);
  const [selectedPid, setSelectedPid] = useState<number | undefined>(initialPid);
  const [isPlaying, setIsPlaying] = useState(false);
  const [jumpInput, setJumpInput] = useState(initialPacketIndex.toString());
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(300); // ms per step
  const [loading, setLoading] = useState(false);

  // Fetch current packet and surrounding context
  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    getSinglePacket(summary.file_id, currentIndex)
      .then((pkt) => {
        if (!isMounted) return;
        setCurrentPacket(pkt);
        if (pkt.context) {
          setSurroundingPackets(pkt.context);
        }
        setJumpInput(currentIndex.toString());
      })
      .catch((err) => {
        console.error(err);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [summary.file_id, currentIndex]);

  // Offline replay playback loop
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    if (isPlaying) {
      timer = setInterval(() => {
        setCurrentIndex((prev) => {
          if (prev >= summary.total_packets - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, playbackSpeed);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isPlaying, playbackSpeed, summary.total_packets]);

  const handleStepPrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  };

  const handleStepNext = () => {
    if (currentIndex < summary.total_packets - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handleJumpSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const target = parseInt(jumpInput, 10);
    if (!isNaN(target) && target >= 0 && target < summary.total_packets) {
      setCurrentIndex(target);
    }
  };

  const formatHexDump = (hexString?: string | null) => {
    if (!hexString) return 'No raw payload bytes available';
    const lines = [];
    const bytesPerLine = 16;
    for (let i = 0; i < hexString.length; i += bytesPerLine * 2) {
      const chunk = hexString.substring(i, i + bytesPerLine * 2);
      const hexParts = [];
      let ascii = '';
      for (let j = 0; j < chunk.length; j += 2) {
        const byteHex = chunk.substring(j, j + 2);
        hexParts.push(byteHex);
        const charCode = parseInt(byteHex, 16);
        ascii += charCode >= 32 && charCode <= 126 ? String.fromCharCode(charCode) : '.';
      }
      const lineOffset = (i / 2).toString(16).padStart(4, '0');
      const hexFormatted = hexParts.join(' ').padEnd(bytesPerLine * 3, ' ');
      lines.push(`${lineOffset}  ${hexFormatted}  |${ascii}|`);
    }
    return lines.join('\n');
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h1 className="page-title">Offline packet replay</h1>
          <p className="page-desc" style={{ marginBottom: 0 }}>
            Inspect byte-exact TS packets in sequence from captured file <strong>{summary.filename}</strong>.
          </p>
        </div>
        {onReturnToFinding && (
          <button className="btn btn-secondary" onClick={onReturnToFinding}>
            &larr; Back to finding
          </button>
        )}
      </div>

      {/* Playback & Navigation Toolbar */}
      <div className="card" style={{ padding: '14px 20px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px' }}>
          {/* Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setCurrentIndex(0)}
              title="Jump to first packet"
              disabled={currentIndex === 0}
            >
              <SkipBack size={14} />
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleStepPrev}
              title="Step backward 1 packet"
              disabled={currentIndex === 0}
            >
              <ChevronLeft size={16} />
            </button>
            <button
              className={`btn btn-sm ${isPlaying ? 'btn-secondary' : 'btn-primary'}`}
              onClick={() => setIsPlaying(!isPlaying)}
              style={{ minWidth: '75px' }}
            >
              {isPlaying ? <><Pause size={14} /> Pause</> : <><Play size={14} /> Play</>}
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleStepNext}
              title="Step forward 1 packet"
              disabled={currentIndex >= summary.total_packets - 1}
            >
              <ChevronRight size={16} />
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setCurrentIndex(summary.total_packets - 1)}
              title="Jump to last packet"
              disabled={currentIndex >= summary.total_packets - 1}
            >
              <SkipForward size={14} />
            </button>
          </div>

          {/* Jump To Form */}
          <form onSubmit={handleJumpSubmit} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Packet:</span>
            <input
              type="number"
              min={0}
              max={summary.total_packets - 1}
              value={jumpInput}
              onChange={(e) => setJumpInput(e.target.value)}
              style={{
                width: '80px',
                padding: '4px 8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border)',
                fontSize: '13px',
                fontFamily: 'var(--font-mono)',
              }}
            />
            <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              of {(summary.total_packets - 1).toLocaleString()}
            </span>
            <button type="submit" className="btn btn-secondary btn-sm">
              Jump
            </button>
          </form>

          {/* Filter by PID */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Filter size={14} style={{ color: 'var(--text-muted)' }} />
            <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>PID:</span>
            <select
              value={selectedPid !== undefined ? selectedPid : ''}
              onChange={(e) => {
                const val = e.target.value;
                setSelectedPid(val === '' ? undefined : parseInt(val, 10));
              }}
              style={{
                padding: '4px 8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border)',
                fontSize: '13px',
                background: 'var(--surface)',
              }}
            >
              <option value="">All PIDs</option>
              {summary.pids.map((p) => (
                <option key={p.pid} value={p.pid}>
                  {p.pid_hex} ({p.stream_type_name || p.label || p.pid})
                </option>
              ))}
            </select>
          </div>

          {/* Speed */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Speed:</span>
            <select
              value={playbackSpeed}
              onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
              style={{
                padding: '3px 6px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border)',
                fontSize: '12px',
                background: 'var(--surface)',
              }}
            >
              <option value={1000}>1 pkt / s</option>
              <option value={300}>3 pkt / s</option>
              <option value={100}>10 pkt / s</option>
              <option value={30}>30 pkt / s</option>
            </select>
          </div>
        </div>

        {/* Timeline Slider */}
        <div style={{ marginTop: '14px' }}>
          <input
            type="range"
            min={0}
            max={summary.total_packets - 1}
            value={currentIndex}
            onChange={(e) => setCurrentIndex(parseInt(e.target.value, 10))}
            style={{ width: '100%', cursor: 'pointer' }}
          />
        </div>
      </div>

      {/* Surrounding Context strip */}
      {surroundingPackets.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px' }}>
            Packet Sequence Timeline
          </div>
          <div style={{ display: 'flex', gap: '4px', overflowX: 'auto', paddingBottom: '4px' }}>
            {surroundingPackets.map((pkt) => {
              const isSelected = pkt.index === currentIndex;
              return (
                <div
                  key={pkt.index}
                  onClick={() => setCurrentIndex(pkt.index)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 'var(--radius-sm)',
                    border: isSelected ? '2px solid var(--accent)' : '1px solid var(--border)',
                    background: isSelected ? 'var(--accent-light)' : 'var(--surface)',
                    cursor: 'pointer',
                    fontSize: '11px',
                    minWidth: '85px',
                    textAlign: 'center',
                    flexShrink: 0,
                  }}
                >
                  <div style={{ fontWeight: 600 }}>#{pkt.index}</div>
                  <div className="code-mono" style={{ color: 'var(--text-muted)' }}>{pkt.pid_hex}</div>
                  <div>CC: {pkt.cc}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Current Packet Breakdown */}
      {currentPacket ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
          {/* Header decoded fields */}
          <div className="card">
            <h2 className="section-title" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Decoded Header Fields</span>
              <span className="code-mono" style={{ fontSize: '12px', fontWeight: 'normal', color: 'var(--text-muted)' }}>
                Offset: {currentPacket.offset_hex} ({currentPacket.offset.toLocaleString()} B)
              </span>
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: '4px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Sync Byte:</span>
                <span className="code-mono">{currentPacket.sync_byte} {currentPacket.sync_byte === '0x47' ? '(Valid)' : '(Corrupted!)'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: '4px' }}>
                <span style={{ color: 'var(--text-muted)' }}>PID:</span>
                <span className="code-mono">{currentPacket.pid_hex} ({currentPacket.pid})</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: '4px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Continuity Counter (CC):</span>
                <span className="code-mono">{currentPacket.cc} (0x{currentPacket.cc.toString(16)})</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: '4px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Transport Error (TEI):</span>
                <span>{currentPacket.tei ? <span className="badge badge-critical">Set (Error)</span> : '0 (No error)'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: '4px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Payload Unit Start (PUSI):</span>
                <span>{currentPacket.pusi ? '1 (PES/Section start)' : '0'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: '4px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Transport Priority:</span>
                <span>{currentPacket.priority ? '1' : '0'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: '4px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Scrambling Control:</span>
                <span>{currentPacket.scrambling_name} ({currentPacket.scrambling})</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: '4px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Adaptation Field Control:</span>
                <span>{currentPacket.afc_name}</span>
              </div>

              {currentPacket.adaptation_field && (
                <div style={{ marginTop: '8px', padding: '10px', background: 'var(--surface-alt)', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontWeight: 600, fontSize: '12px', marginBottom: '4px' }}>Adaptation Field</div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Length: {currentPacket.adaptation_field.length} bytes &bull;{' '}
                    Discontinuity: {currentPacket.adaptation_field.discontinuity_indicator ? 'Yes' : 'No'} &bull;{' '}
                    Random Access: {currentPacket.adaptation_field.random_access_indicator ? 'Yes' : 'No'}
                    {currentPacket.adaptation_field.pcr !== null && (
                      <div>PCR: {currentPacket.adaptation_field.pcr}</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Hex Dump */}
          <div className="card">
            <h2 className="section-title">Packet Byte Dump (188 Bytes)</h2>
            <div className="hex-box" style={{ height: '240px' }}>
              {formatHexDump(currentPacket.raw_hex)}
            </div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ textAlign: 'center', padding: '30px' }}>
          Loading packet #{currentIndex}...
        </div>
      )}
    </div>
  );
};
