# ORBITSTREAM — Integrated Satellite Stream Troubleshooting Platform
### SIH260002 | Offline Satellite Stream Analysis, Replay & Fault Verification

ORBITSTREAM is an offline-capable satellite stream troubleshooting platform designed to analyze receiver-output files (MPEG-TS, GSE, BBFrame), detect packet-level anomalies using evidence-based diagnostic rules, provide deterministic packet replay, and simulate controlled faults on derived copies to validate diagnostics.

---

## 1. System Requirements

- **Operating System:** Windows 10 / 11 (PowerShell 5.1 or PowerShell Core 7+)
- **Python:** Python 3.11 or newer (Installed & added to `PATH`)
- **Node.js:** Node.js v18.0.0 or newer (with `npm`)

---

## 2. Windows PowerShell Setup Guide

Open Windows PowerShell (no administrator privileges needed) and run:

### Step 1: Clone or Navigate to the Workspace
```powershell
cd "c:\Users\Aryan\Desktop\innotech final"
```

### Step 2: Set Up Backend Virtual Environment & Dependencies
```powershell
# Create Python virtual environment
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r backend\requirements.txt
```

### Step 3: Set Up Frontend Dependencies
```powershell
cd frontend
npm install
cd ..
```

---

## 3. Running ORBITSTREAM

### Option A: Using the Automated PowerShell Startup Script (Recommended)
We provide a convenient, automated startup script that starts both the backend API and frontend dev server:

```powershell
# Run with default ports (Backend: 8000, Frontend: 5173)
.\scripts\start.ps1

# Or specify custom ports if desired:
.\scripts\start.ps1 -BackendPort 8080 -FrontendPort 3000
```

Once running:
- **Web Interface:** [http://127.0.0.1:5173](http://127.0.0.1:5173)
- **FastAPI Documentation & Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

To stop both services, press `Ctrl + C` in the PowerShell window.

---

### Option B: Running Manually in Separate Terminals

**Terminal 1 (Backend FastAPI):**
```powershell
cd "c:\Users\Aryan\Desktop\innotech final\backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 (Frontend React):**
```powershell
cd "c:\Users\Aryan\Desktop\innotech final\frontend"
npm run dev
```

---

## 4. Running the Automated Test Suite

ORBITSTREAM includes 34 automated test suites covering all protocol, diagnostic, simulation, signal lab, persistent database, RTL-SDR collector telemetry, and API requirements:

```powershell
cd "c:\Users\Aryan\Desktop\innotech final v2\backend"
python -m pytest tests -v
```

The 34 test suites cover:
- Valid MPEG-TS parsing (188, 192, 204 bytes)
- Sync byte alignment and loss detection
- PID demuxing and Null packet accounting
- PAT and PMT section assembly and CRC32 verification
- Per-PID Continuity Counter tracking and discontinuity semantics
- Transport Scrambling Control extraction
- Truncated and malformed packet resilience
- Unknown and unsupported format handling
- Structured evidence references and certainty levels
- Offline packet indexing and random-access replay
- Controlled fault injection without modifying source files
- Independent post-simulation reanalysis
- Expected-vs-observed automated verification (PASS/FAIL/INCONCLUSIVE)
- JSON and CSV report generation
- Full REST API endpoints via TestClient
- **Signal Lab — QPSK modulation simulation at high & low SNR**
- **Signal Lab — 8PSK DVB-S2 modulation simulation & Gray mapping**
- **Signal Lab — Simulation reproducibility with deterministic RNG seeds**
- **Signal Lab — Carrier phase offset & frequency drift impairment modeling**
- **Signal Lab — Raw Float32 LE binary I/Q sample ingestion & circular moment analysis**
- **Signal Lab — Unaligned buffer validation & format boundary enforcement**
- **Signal Lab — Signal simulation, sample loading, and upload API endpoints**
- **RTL-SDR Collector — Pure carrier relative power, PAPR, SNR, and 64-bin FFT spectrum calculation**
- **RTL-SDR Collector — Non-finite and empty sample buffer rejection**
- **RTL-SDR Collector — Dual-rail ADC clipping ratio calculation**
- **RTL-SDR Collector — Token and Bearer authentication enforcement on ingestion**
- **RTL-SDR Collector — Request schema boundary and parameter validation**
- **RTL-SDR Collector — Persistent database storage & latest status queries**
- **RTL-SDR Collector — Time-range filtering on historical telemetry**
- **RTL-SDR Collector — Configurable signal power drop anomaly detection**
- **RTL-SDR Collector — Anomaly event deduplication across consecutive intervals**
- **RTL-SDR Collector — Automated recovery tracking and resolution note generation**
- **RTL-SDR Collector — Telemetry and anomaly CSV/JSON export and PDF diagnostic reports**
- **RTL-SDR Collector — Dynamic credential revocation enforcement**
- **RTL-SDR Collector — Hardware mode vs demonstration mode strict separation**

---

## 5. Sample Fixtures

Synthetic test vectors are automatically generated in `fixtures/`:

### MPEG-TS Fixtures
- `valid_basic.ts`: Valid MPEG-TS with PAT, PMT, H.264 video (`0x0100`), and AAC audio (`0x0101`).
- `multi_program.ts`: Two-program TS with multiple elementary streams and PCR PIDs.
- `cc_error.ts`: Deliberate continuity counter gap on PID `0x0100`.
- `corrupt_sync.ts`: Corrupted sync byte at packet #5 to test resynchronization.
- `truncated.ts`: Stream ending abruptly mid-packet to test bounds safety.

### Signal Lab I/Q Fixtures (`fixtures/iq_samples/`)
- `qpsk_clean_20db.iq`: Clean QPSK vector at 20 dB SNR (Float32 LE, 1000 symbols).
- `8psk_snr_18db.iq`: 8PSK vector at 18 dB SNR (Float32 LE, 8-cluster phase distribution).
- `qpsk_int16_noisy.iq`: Impaired QPSK vector at 8 dB SNR with 15° carrier phase offset (Int16 LE).

You can load any of these sample files with a single click from the web interface under **"Try a sample file"** or **"Signal Lab → Load Test Vectors"**.

---

## 6. Project Architecture

```
innotech final v2/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI application entrypoint, CORS, lifespan DB init
│   │   ├── api/
│   │   │   ├── routes.py            # Upload, analysis, replay, simulation, signal lab routes
│   │   │   └── sdr_routes.py        # Authenticated SDR ingestion, history, anomalies, reports
│   │   ├── core/
│   │   │   └── config.py            # Port, storage, database URL, and API key config
│   │   ├── sdr/
│   │   │   ├── models.py            # SQLAlchemy PostgreSQL/SQLite models & Pydantic schemas
│   │   │   ├── database.py          # Async PostgreSQL & SQLite persistence manager
│   │   │   ├── anomaly_engine.py    # Power drop, low SNR, saturation & recovery tracking
│   │   │   └── reports.py           # Telemetry CSV/JSON & printable PDF/HTML generator
│   │   ├── diagnostics/
│   │   │   └── engine.py            # Evidence-based diagnostic rule engine
│   │   ├── models/
│   │   │   └── diagnostic_models.py # Pydantic schemas for findings & summaries
│   │   ├── parsers/
│   │   │   ├── fixture_generator.py # Deterministic synthetic test fixture generator
│   │   │   ├── mpegts/              # Full MPEG-TS parser, CRC32, models, constants
│   │   │   ├── gse/                 # GSE parser scaffold (ETSI TS 102 606)
│   │   │   ├── bbframe/             # DVB-S2 BBFrame scaffold (ETSI EN 302 307)
│   │   │   └── pcap/                # PCAP file header & record parser scaffold
│   │   ├── replay/
│   │   │   └── engine.py            # Offline packet indexing and random access
│   │   ├── reporting/
│   │   │   └── generator.py         # JSON and CSV export generation
│   │   ├── signal_lab/              # Physical layer QPSK/8PSK simulation & I/Q analysis
│   │   │   ├── models.py            # Pydantic models for I/Q symbols, simulation & analysis
│   │   │   ├── simulator.py         # QPSK/8PSK modulation simulator, AWGN, EVM, BER/SER
│   │   │   ├── analyzer.py          # Circular moments (R4/R8), AGC, EVM & offset estimator
│   │   │   └── fixtures.py          # Synthetic I/Q binary vector generator (.iq files)
│   │   ├── simulation/
│   │   │   └── engine.py            # Fault simulation lab (separate derived copy)
│   │   └── storage/
│   │       └── manager.py           # Path traversal protection & file lifecycle
│   └── tests/
│       ├── test_backend.py          # 15 automated pytest test suites for core engine
│       ├── test_signal_lab.py       # 8 automated pytest test suites for Signal Lab
│       └── test_sdr_collector.py    # 11 automated test suites for SDR collector & persistence
├── sdr_collector/                   # Local Windows RTL-SDR Physical Collector Station
│   ├── collector.py                 # Telemetry loop, sample acquisition & HTTP sender
│   ├── device.py                    # Real RTL-SDR hardware interface & explicit Demo mode
│   ├── metrics.py                   # Relative power (dBFS), PAPR, SNR & 64-bin FFT spectrum
│   ├── config.py                    # Environment and configuration loader
│   ├── run_collector.ps1            # Windows PowerShell one-click launcher
│   ├── run_collector.bat            # Windows batch launcher
│   ├── requirements.txt             # pyrtlsdr, pyrtlsdrlib, numpy, requests, python-dotenv
│   ├── .env.example                 # Collector environment template
│   └── README.md                    # Detailed Windows Zadig & hardware setup guide
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx           # Clean top bar with offline status
│   │   │   ├── Navigation.tsx       # Tab bar (Analyze, Results, Replay, Fault lab, Reports, Signal lab, SDR Monitor)
│   │   │   ├── AnalyzePage.tsx      # Upload dropzone & sample selector
│   │   │   ├── ResultsPage.tsx      # Plain-language summary & stream inventory
│   │   │   ├── ReplayPage.tsx       # Offline packet replay & hex viewer
│   │   │   ├── FaultLabPage.tsx     # 7-step fault simulation & automated verification
│   │   │   ├── SignalLabPage.tsx    # QPSK/8PSK simulator, I/Q analyzer & signal chain guide
│   │   │   ├── SDRMonitorPage.tsx   # Live RTL-SDR spectrum, gauges, time-series & anomaly feed
│   │   │   ├── ConstellationPlot.tsx# Interactive HTML5 Canvas I/Q constellation diagram
│   │   │   ├── ReportsPage.tsx      # Stream & physical SDR CSV/JSON/PDF exports
│   │   │   ├── AdvancedToolsPage.tsx# Protocol inspection & engine configuration
│   │   │   └── ModalEvidence.tsx    # Evidence inspector modal
│   │   ├── services/
│   │   │   └── api.ts               # Frontend API client with SDR endpoints
│   │   ├── styles/
│   │   │   └── index.css            # Calm, human-designed design system
│   │   ├── types/
│   │   │   └── index.ts             # TypeScript definitions including SDR schemas
│   │   ├── App.tsx                  # Main router & state manager
│   │   └── main.tsx                 # React bootstrap
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── fixtures/                        # Generated MPEG-TS and I/Q test vectors
├── scripts/
│   └── start.ps1                    # One-command Windows PowerShell launcher
└── README.md
```

---

## 7. RTL-SDR Physical Layer Collector (Local Station)

ORBITSTREAM includes an independent local physical layer telemetry collector designed to stream real I/Q measurements from a local Windows station with an RTL-SDR USB receiver to the deployed Render backend:

### Quick Windows Setup:
```powershell
# 1. Install dependencies
pip install -r sdr_collector\requirements.txt

# 2. Configure target (deployed Render backend or local)
Copy-Item sdr_collector\.env.example sdr_collector\.env

# 3. Run collector in real hardware mode
.\sdr_collector\run_collector.ps1

# Or test in synthetic demonstration mode
.\sdr_collector\run_collector.ps1 -Demo
```

For complete Zadig WinUSB installation steps and RF metric specifications, see [`sdr_collector/README.md`](sdr_collector/README.md).

---

## 8. Troubleshooting & Port Conflicts

### Port Already in Use (Errno 10048)
If port 8000 or 5173 is occupied by another application:
```powershell
# Check which process is using port 8000
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess

# Or launch ORBITSTREAM on alternate ports:
.\scripts\start.ps1 -BackendPort 8081 -FrontendPort 5174
```

### PowerShell Script Execution Policy
If PowerShell blocks running scripts:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start.ps1
```

---

## 9. Honest Engineering Limitations

- **MPEG-TS Scope:** Complete ISO/IEC 13818-1 parsing implemented for 188-byte packets, with format detection for 192-byte and 204-byte layouts.
- **Physical vs Protocol Causes:** The diagnostic engine identifies structural anomalies (e.g., CC gaps, sync losses) with verifiable packet evidence, but explicitly notes when a physical RF cause cannot be determined from packet bits alone.
- **Extensible Scaffolds:** GSE, BBFrame, and PCAP modules are implemented as clean, validated protocol scaffolds and documented accordingly.
