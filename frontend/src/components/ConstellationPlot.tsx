import React, { useRef, useEffect, useState, useMemo } from 'react';
import { ConstellationPoint } from '../types';

interface ConstellationPlotProps {
  idealPoints?: ConstellationPoint[];
  txPoints?: ConstellationPoint[];
  rxPoints?: ConstellationPoint[];
  title?: string;
  subtitle?: string;
  maxDisplayPoints?: number;
}

export const ConstellationPlot: React.FC<ConstellationPlotProps> = ({
  idealPoints = [],
  txPoints = [],
  rxPoints = [],
  title = 'I/Q Constellation Diagram',
  subtitle,
  maxDisplayPoints = 800,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [showIdeal, setShowIdeal] = useState(true);
  const [showTx, setShowTx] = useState(true);
  const [showRx, setShowRx] = useState(true);
  const [hoverCoords, setHoverCoords] = useState<{ i: number; q: number; r: number; deg: number } | null>(null);

  // Subsample RX points if there are too many to keep rendering fast and smooth
  const displayRxPoints = useMemo(() => {
    if (rxPoints.length <= maxDisplayPoints) return rxPoints;
    const step = Math.ceil(rxPoints.length / maxDisplayPoints);
    return rxPoints.filter((_, idx) => idx % step === 0);
  }, [rxPoints, maxDisplayPoints]);

  const displayTxPoints = useMemo(() => {
    if (txPoints.length <= 400) return txPoints;
    const step = Math.ceil(txPoints.length / 400);
    return txPoints.filter((_, idx) => idx % step === 0);
  }, [txPoints]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    // Set display buffer size with DPR
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    // Coordinate mapping: center is (width/2, height/2)
    // Scale: map [-1.6, 1.6] to [padding, width - padding]
    const size = Math.min(width, height);
    const centerX = width / 2;
    const centerY = height / 2;
    const radiusPixels = (size / 2) * 0.72; // radius for 1.0 amplitude

    const toScreenX = (iVal: number) => centerX + iVal * radiusPixels;
    const toScreenY = (qVal: number) => centerY - qVal * radiusPixels; // inverted Y

    // 1. Background
    ctx.fillStyle = '#0b1120';
    ctx.fillRect(0, 0, width, height);

    // 2. Grid lines
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;

    const gridValues = [-1.5, -1.0, -0.5, 0.5, 1.0, 1.5];
    gridValues.forEach((val) => {
      // Vertical grid
      const x = toScreenX(val);
      ctx.beginPath();
      ctx.moveTo(x, 10);
      ctx.lineTo(x, height - 10);
      ctx.stroke();

      // Horizontal grid
      const y = toScreenY(val);
      ctx.beginPath();
      ctx.moveTo(10, y);
      ctx.lineTo(width - 10, y);
      ctx.stroke();
    });

    // 3. Unit circle (r = 1.0) and r = 0.5 circle
    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = '#334155';
    ctx.beginPath();
    ctx.arc(centerX, centerY, radiusPixels, 0, 2 * Math.PI);
    ctx.stroke();

    ctx.strokeStyle = '#1e293b';
    ctx.beginPath();
    ctx.arc(centerX, centerY, radiusPixels * 0.5, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.restore();

    // 4. Main I and Q Axes
    ctx.strokeStyle = '#475569';
    ctx.lineWidth = 1.5;

    // I-axis (Horizontal)
    ctx.beginPath();
    ctx.moveTo(15, centerY);
    ctx.lineTo(width - 15, centerY);
    ctx.stroke();

    // Q-axis (Vertical)
    ctx.beginPath();
    ctx.moveTo(centerX, 15);
    ctx.lineTo(centerX, height - 15);
    ctx.stroke();

    // Axis labels & tick numbers
    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText('+I (In-Phase)', width - 20, centerY - 8);

    ctx.textAlign = 'left';
    ctx.fillText('+Q (Quadrature)', centerX + 8, 26);

    ctx.fillStyle = '#64748b';
    ctx.font = '10px ui-monospace, monospace';
    // Tick marks and values
    gridValues.forEach((val) => {
      // I tick
      const x = toScreenX(val);
      ctx.beginPath();
      ctx.moveTo(x, centerY - 4);
      ctx.lineTo(x, centerY + 4);
      ctx.stroke();
      ctx.textAlign = 'center';
      ctx.fillText(val.toFixed(1), x, centerY + 14);

      // Q tick
      const y = toScreenY(val);
      ctx.beginPath();
      ctx.moveTo(centerX - 4, y);
      ctx.lineTo(centerX + 4, y);
      ctx.stroke();
      ctx.textAlign = 'right';
      ctx.fillText(val.toFixed(1), centerX - 6, y + 3);
    });

    // 5. Received (Rx) Symbols / Cloud
    if (showRx && displayRxPoints.length > 0) {
      ctx.fillStyle = 'rgba(56, 189, 248, 0.45)'; // Sky blue
      for (let i = 0; i < displayRxPoints.length; i++) {
        const pt = displayRxPoints[i];
        const sx = toScreenX(pt.i);
        const sy = toScreenY(pt.q);

        ctx.beginPath();
        ctx.arc(sx, sy, 2.5, 0, 2 * Math.PI);
        ctx.fill();
      }
    }

    // 6. Transmitted (Tx) Symbols
    if (showTx && displayTxPoints.length > 0) {
      ctx.strokeStyle = '#22c55e'; // Green ring
      ctx.lineWidth = 1.2;
      for (let i = 0; i < displayTxPoints.length; i++) {
        const pt = displayTxPoints[i];
        const sx = toScreenX(pt.i);
        const sy = toScreenY(pt.q);

        ctx.beginPath();
        ctx.arc(sx, sy, 4, 0, 2 * Math.PI);
        ctx.stroke();
      }
    }

    // 7. Ideal Constellation Points + Bit Pattern Labels
    if (showIdeal && idealPoints.length > 0) {
      for (let i = 0; i < idealPoints.length; i++) {
        const pt = idealPoints[i];
        const sx = toScreenX(pt.i);
        const sy = toScreenY(pt.q);

        // Outer glow cross
        ctx.strokeStyle = '#f59e0b'; // Amber cross
        ctx.lineWidth = 2.5;
        const arm = 7;
        ctx.beginPath();
        ctx.moveTo(sx - arm, sy);
        ctx.lineTo(sx + arm, sy);
        ctx.moveTo(sx, sy - arm);
        ctx.lineTo(sx, sy + arm);
        ctx.stroke();

        // Label with bit pattern if present
        if (pt.bit_pattern) {
          ctx.fillStyle = '#fde68a';
          ctx.font = 'bold 11px ui-monospace, monospace';
          // Offset label away from center
          const angle = Math.atan2(- (sy - centerY), sx - centerX);
          const offsetX = Math.cos(angle) * 18;
          const offsetY = -Math.sin(angle) * 18;

          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(pt.bit_pattern, sx + offsetX, sy + offsetY);
        }
      }
    }
  }, [displayRxPoints, displayTxPoints, idealPoints, showIdeal, showTx, showRx]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const size = Math.min(rect.width, rect.height);
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    const radiusPixels = (size / 2) * 0.72;

    const iVal = (x - centerX) / radiusPixels;
    const qVal = (centerY - y) / radiusPixels;
    const rVal = Math.sqrt(iVal * iVal + qVal * qVal);
    let degVal = (Math.atan2(qVal, iVal) * 180) / Math.PI;
    if (degVal < 0) degVal += 360;

    setHoverCoords({
      i: iVal,
      q: qVal,
      r: rVal,
      deg: degVal,
    });
  };

  const handleMouseLeave = () => {
    setHoverCoords(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-main)' }}>{title}</h3>
          {subtitle && <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{subtitle}</p>}
        </div>

        {/* Live Coordinate Inspector */}
        <div
          style={{
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            padding: '4px 10px',
            background: 'var(--surface-alt)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border)',
            minWidth: '220px',
            textAlign: 'right',
            color: 'var(--text-muted)',
          }}
        >
          {hoverCoords ? (
            <span>
              I: <strong style={{ color: 'var(--text-main)' }}>{hoverCoords.i.toFixed(3)}</strong> | Q:{' '}
              <strong style={{ color: 'var(--text-main)' }}>{hoverCoords.q.toFixed(3)}</strong> | r:{' '}
              {hoverCoords.r.toFixed(2)} | {hoverCoords.deg.toFixed(1)}°
            </span>
          ) : (
            <span>Hover canvas to inspect (I, Q)</span>
          )}
        </div>
      </div>

      {/* Canvas */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          aspectRatio: '1 / 1',
          maxHeight: '440px',
          borderRadius: 'var(--radius-md)',
          overflow: 'hidden',
          boxShadow: 'inset 0 0 0 1px rgba(255, 255, 255, 0.1)',
        }}
      >
        <canvas
          ref={canvasRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          style={{
            width: '100%',
            height: '100%',
            display: 'block',
            cursor: 'crosshair',
          }}
        />
      </div>

      {/* Visibility Toggles & Legend */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '14px',
          fontSize: '12px',
          padding: '6px 2px',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', gap: '16px' }}>
          {idealPoints.length > 0 && (
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={showIdeal}
                onChange={(e) => setShowIdeal(e.target.checked)}
              />
              <span
                style={{
                  display: 'inline-block',
                  width: '10px',
                  height: '10px',
                  background: '#f59e0b',
                  borderRadius: '2px',
                }}
              />
              <span>Ideal Reference Points ({idealPoints.length})</span>
            </label>
          )}

          {txPoints.length > 0 && (
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={showTx}
                onChange={(e) => setShowTx(e.target.checked)}
              />
              <span
                style={{
                  display: 'inline-block',
                  width: '10px',
                  height: '10px',
                  border: '2px solid #22c55e',
                  borderRadius: '50%',
                }}
              />
              <span>Tx Symbols ({txPoints.length})</span>
            </label>
          )}

          {rxPoints.length > 0 && (
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={showRx}
                onChange={(e) => setShowRx(e.target.checked)}
              />
              <span
                style={{
                  display: 'inline-block',
                  width: '10px',
                  height: '10px',
                  background: '#38bdf8',
                  borderRadius: '50%',
                }}
              />
              <span>
                Rx / Scatter ({displayRxPoints.length}
                {rxPoints.length > maxDisplayPoints ? ` of ${rxPoints.length}` : ''})
              </span>
            </label>
          )}
        </div>

        <span style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>
          Dashed circle: r = 1.0 (Unit normalized power)
        </span>
      </div>
    </div>
  );
};
