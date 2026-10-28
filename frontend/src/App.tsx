import React, { useState } from 'react';
import { Header } from './components/Header';
import { Navigation, NavTab } from './components/Navigation';
import { AnalyzePage } from './components/AnalyzePage';
import { ResultsPage } from './components/ResultsPage';
import { ReplayPage } from './components/ReplayPage';
import { FaultLabPage } from './components/FaultLabPage';
import { ReportsPage } from './components/ReportsPage';
import { SignalLabPage } from './components/SignalLabPage';
import { SDRMonitorPage } from './components/SDRMonitorPage';
import { AdvancedToolsPage } from './components/AdvancedToolsPage';
import { ModalEvidence } from './components/ModalEvidence';
import { AnalysisSummary, DiagnosticFinding } from './types';
import { getAnalysis } from './services/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavTab>('analyze');
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Evidence Modal state
  const [inspectingFinding, setInspectingFinding] = useState<DiagnosticFinding | null>(null);

  // Replay deep-linking state
  const [replayPid, setReplayPid] = useState<number | undefined>(undefined);
  const [replayPacketIndex, setReplayPacketIndex] = useState<number>(0);

  const handleAnalysisComplete = async (fileId: string) => {
    try {
      const data = await getAnalysis(fileId);
      setSummary(data);
      setActiveTab('results');
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleJumpToReplay = (pid?: number, packetIndex?: number) => {
    setReplayPid(pid);
    if (packetIndex !== undefined) {
      setReplayPacketIndex(packetIndex);
    }
    setActiveTab('replay');
  };

  return (
    <div className="app-container">
      <Header
        currentFile={
          summary
            ? {
                filename: summary.filename,
                file_size: summary.file_size,
                detected_format: summary.detected_format,
              }
            : null
        }
      />

      <Navigation
        activeTab={activeTab}
        onTabChange={setActiveTab}
        hasAnalysis={!!summary}
        findingCount={summary ? summary.findings.length : 0}
      />

      <main className="content-wrap">
        {activeTab === 'analyze' && (
          <AnalyzePage
            onAnalysisComplete={handleAnalysisComplete}
            isLoading={isLoading}
            setIsLoading={setIsLoading}
          />
        )}

        {activeTab === 'results' && summary && (
          <ResultsPage
            summary={summary}
            onInspectEvidence={(finding) => setInspectingFinding(finding)}
            onJumpToReplay={handleJumpToReplay}
            onNavigateToFaultLab={() => setActiveTab('fault_lab')}
          />
        )}

        {activeTab === 'replay' && summary && (
          <ReplayPage
            summary={summary}
            initialPid={replayPid}
            initialPacketIndex={replayPacketIndex}
            onReturnToFinding={() => setActiveTab('results')}
          />
        )}

        {activeTab === 'fault_lab' && summary && (
          <FaultLabPage
            summary={summary}
            onNavigateToReplay={(fileId) => {
              setActiveTab('replay');
            }}
          />
        )}

        {activeTab === 'reports' && summary && <ReportsPage summary={summary} />}

        {activeTab === 'signal_lab' && <SignalLabPage />}

        {activeTab === 'sdr_monitor' && <SDRMonitorPage />}

        {activeTab === 'advanced' && <AdvancedToolsPage summary={summary} />}
      </main>

      {/* Evidence Modal */}
      <ModalEvidence
        finding={inspectingFinding}
        onClose={() => setInspectingFinding(null)}
        onJumpToPacket={(pktIndex) => {
          handleJumpToReplay(undefined, pktIndex);
        }}
      />
    </div>
  );
};

export default App;
