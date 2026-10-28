# ORBITSTREAM RTL-SDR Collector (Windows Setup & Guide)

The **ORBITSTREAM RTL-SDR Collector** is an independent, lightweight physical layer telemetry service designed to run on a local Windows station with an RTL-SDR USB receiver connected. It samples real I/Q signals every 10 seconds, calculates relative power (dBFS), peak power, PAPR, DC offset, and downsampled FFT spectrum bins, and transmits authenticated measurements to the deployed ORBITSTREAM backend over HTTPS (`https://orbitstream.onrender.com`).

---

## 1. Prerequisites & Hardware Setup

### Hardware
- Any standard **RTL2832U-based USB dongle** (e.g. RTL-SDR Blog V3/V4, NooElec, generic DVB-T stick).
- An antenna matched to your frequency of interest.

### Windows WinUSB Driver Installation (Zadig)
Windows installs a default DVB-T TV tuner driver when you plug in an RTL-SDR stick. For raw I/Q access via `librtlsdr`, the **WinUSB** driver must be assigned to **Interface 0**:

1. Download **Zadig** from [https://zadig.akeo.ie/](https://zadig.akeo.ie/).
2. Plug your RTL-SDR dongle into a USB port.
3. Open Zadig (Run as Administrator).
4. In the menu, click **Options** → Check **List All Devices**.
5. In the dropdown, select **Bulk-In, Interface (Interface 0)** (VID: `0BDA`, PID: `2838` or `2832`).
6. Select **WinUSB** as the target driver (on the right of the green arrow).
7. Click **Replace Driver** (or **Install Driver**).
8. Once finished, disconnect and reconnect the dongle once.

> **Important Note Regarding Conflicting Applications:**
> RTL-SDR devices only permit a single exclusive connection at a time. If software such as **SDR# (SDRSharp)**, **SDR++**, or **CubicSDR** is running and using the device, `librtlsdr` will return `LIBUSB_ERROR_ACCESS (-3)` or `LIBUSB_ERROR_IO (-1)`. Close any conflicting SDR applications before running the collector.

---

## 2. Python Environment Installation

Open Windows PowerShell in the project directory:

```powershell
# Navigate to the repository root
cd "C:\Users\Aryan\Desktop\innotech final v2"

# Activate the existing virtual environment (or create a new one)
.\.venv\Scripts\Activate.ps1

# Install collector dependencies
pip install -r sdr_collector\requirements.txt
```

---

## 3. Configuration & Environment Variables

Create or edit `sdr_collector\.env` (or copy from `sdr_collector\.env.example`):

| Variable | Default Value | Description |
|---|---|---|
| `ORBITSTREAM_BACKEND_URL` | `https://orbitstream.onrender.com` | Target deployed backend endpoint. Use `http://127.0.0.1:8000` for local dev. |
| `ORBITSTREAM_COLLECTOR_API_KEY` | `orbitstream-collector-key-2026` | Revocable secret API key matching the backend configuration. |
| `SDR_MODE` | `hardware` | `hardware` (read real samples from physical dongle) or `demo` (synthetic test samples). |
| `SDR_FREQUENCY_HZ` | `100000000` | Center frequency in Hz (e.g. `100000000` for 100.0 MHz, `137500000` for NOAA APT). |
| `SDR_SAMPLE_RATE_HZ` | `1024000` | Sample rate in Hz (1.024 MS/s). |
| `SDR_GAIN` | `auto` | Tuner gain in dB or `auto`. |
| `SDR_INTERVAL_SECONDS` | `10` | Sampling & transmission period (default 10s). |
| `SDR_SAMPLE_COUNT` | `262144` | Number of complex I/Q samples to acquire per interval ($2^{18}$). |
| `SDR_DEVICE_INDEX` | `0` | USB device index (0 for first SDR dongle). |
| `SDR_DEVICE_ID` | `rtlsdr-station-win01` | Unique device identifier label for dashboard and database tracking. |
| `SDR_SPECTRUM_BINS` | `64` | Number of downsampled FFT bins transmitted in telemetry summary. |

---

## 4. Running the Collector

### Option A: Using the PowerShell Launcher Script
```powershell
# Run in hardware mode against the deployed Render backend
.\sdr_collector\run_collector.ps1

# Run with custom frequency (e.g. 137.5 MHz)
.\sdr_collector\run_collector.ps1 -Frequency 137500000

# Run in demonstration mode (synthetic data for testing without hardware)
.\sdr_collector\run_collector.ps1 -Demo

# Run a single measurement diagnostic test
.\sdr_collector\run_collector.ps1 -Once
```

### Option B: Running via Python Module Directly
```powershell
# Hardware mode (default)
.\.venv\Scripts\python.exe -m sdr_collector.collector

# Demonstration mode
.\.venv\Scripts\python.exe -m sdr_collector.collector --mode demo

# Local backend target
.\.venv\Scripts\python.exe -m sdr_collector.collector --backend-url http://127.0.0.1:8000
```

---

## 5. Telemetry & Metric Computation

The collector evaluates the following metrics from actual complex $I + jQ$ samples:
- **Relative Power ($\text{dBFS}$):** $10 \log_{10}(\text{mean}(|s|^2))$ relative to ADC full-scale.
- **Peak Power ($\text{dBFS}$):** Maximum instantaneous power level in buffer.
- **PAPR ($\text{dB}$):** Peak-to-Average Power Ratio indicating dynamic range.
- **DC Offsets ($I_{mean}, Q_{mean}$):** Hardware DC leak and LO leakage.
- **ADC Clipping Ratio:** Proportion of samples saturating at ADC limits ($\pm 1.0$).
- **FFT Power Spectrum:** 64-bin windowed (Hanning) Power Spectral Density across bandwidth.
- **SNR Estimate ($\text{dB}$):** Difference between spectral peak and estimated 25th percentile noise floor.

---

## 6. Hardware Mode vs Demonstration Mode Integrity

- **Hardware Mode (`SDR_MODE=hardware`):** Strictly queries physical device through `pyrtlsdr`. If the dongle is disconnected, locked by another process, or uninitialized, the collector logs the error and marks `is_valid: false`. **No synthetic data is ever generated in hardware mode.**
- **Demo Mode (`SDR_MODE=demo`):** Generates reproducible synthetic RF carriers and AWGN noise, clearly tagged with `mode: "demo"` and `is_synthetic: true`.

