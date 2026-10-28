import React from 'react';
import { Radio, HardDrive } from 'lucide-react';

interface HeaderProps {
  currentFile?: {
    filename: string;
    file_size: number;
    detected_format: string;
  } | null;
}

export const Header: React.FC<HeaderProps> = ({ currentFile }) => {
  return (
    <header className="app-header">
      <div className="header-brand">
        <Radio className="text-accent" size={20} />
        <span className="brand-title">ORBITSTREAM</span>
        <span className="brand-subtitle">Satellite stream analysis</span>
      </div>

      <div className="header-status">
        {currentFile && (
          <span className="status-badge">
            <HardDrive size={13} />
            <span>{currentFile.filename}</span>
            <span className="code-mono" style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>
              ({(currentFile.file_size / 1024).toFixed(1)} KB)
            </span>
          </span>
        )}
        <span className="status-badge">
          <span className="status-indicator"></span>
          <span>Local engine offline</span>
        </span>
      </div>
    </header>
  );
};
