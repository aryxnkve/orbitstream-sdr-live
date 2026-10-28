import React from 'react';
import { UploadCloud, BarChart2, PlayCircle, Cpu, Download, Settings, Radio, Activity } from 'lucide-react';

export type NavTab = 'analyze' | 'results' | 'replay' | 'fault_lab' | 'reports' | 'signal_lab' | 'sdr_monitor' | 'advanced';

interface NavigationProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  hasAnalysis: boolean;
  findingCount: number;
}

export const Navigation: React.FC<NavigationProps> = ({
  activeTab,
  onTabChange,
  hasAnalysis,
  findingCount,
}) => {
  return (
    <nav className="app-nav">
      <button
        className={`nav-item ${activeTab === 'analyze' ? 'active' : ''}`}
        onClick={() => onTabChange('analyze')}
      >
        <UploadCloud size={16} />
        <span>Analyze</span>
      </button>

      <button
        className={`nav-item ${activeTab === 'results' ? 'active' : ''}`}
        onClick={() => onTabChange('results')}
        disabled={!hasAnalysis}
        title={!hasAnalysis ? 'Analyze a file first to view results' : ''}
      >
        <BarChart2 size={16} />
        <span>Results</span>
        {hasAnalysis && findingCount > 0 && (
          <span className="nav-badge">{findingCount}</span>
        )}
      </button>

      <button
        className={`nav-item ${activeTab === 'replay' ? 'active' : ''}`}
        onClick={() => onTabChange('replay')}
        disabled={!hasAnalysis}
        title={!hasAnalysis ? 'Analyze a file first to enable replay' : ''}
      >
        <PlayCircle size={16} />
        <span>Replay</span>
      </button>

      <button
        className={`nav-item ${activeTab === 'fault_lab' ? 'active' : ''}`}
        onClick={() => onTabChange('fault_lab')}
        disabled={!hasAnalysis}
        title={!hasAnalysis ? 'Analyze a file first to use Fault Lab' : ''}
      >
        <Cpu size={16} />
        <span>Fault lab</span>
      </button>

      <button
        className={`nav-item ${activeTab === 'reports' ? 'active' : ''}`}
        onClick={() => onTabChange('reports')}
        disabled={!hasAnalysis}
        title={!hasAnalysis ? 'Analyze a file first to export reports' : ''}
      >
        <Download size={16} />
        <span>Reports</span>
      </button>

      <button
        className={`nav-item ${activeTab === 'signal_lab' ? 'active' : ''}`}
        onClick={() => onTabChange('signal_lab')}
      >
        <Radio size={16} />
        <span>Signal lab</span>
      </button>

      <button
        className={`nav-item ${activeTab === 'sdr_monitor' ? 'active' : ''}`}
        onClick={() => onTabChange('sdr_monitor')}
      >
        <Activity size={16} />
        <span>SDR Monitor</span>
      </button>

      <button
        className={`nav-item ${activeTab === 'advanced' ? 'active' : ''}`}
        onClick={() => onTabChange('advanced')}
      >
        <Settings size={16} />
        <span>Advanced tools</span>
      </button>
    </nav>
  );
};
