# Virga — SSB Voice Equaliser

**Virga** calibrates your microphone and voice for optimal SSB radio communication. It measures your Long-Term Average Speech Spectrum (LTASS), compares it against scientifically derived targets, and produces a set of EQ gain values you enter directly into your radio or external equaliser.

> *Virga — precipitation that evaporates before reaching the ground. Like the signal path from your mic to the far end: what starts as sound should arrive as intelligibility.*

---

## Two Profiles

| Profile | Passband | Character | Use |
|---------|----------|-----------|-----|
| **Ragchew** | 200–2800 Hz | Warm, natural, full low-end | Casual QSOs, nets, rag-chew |
| **Contest** | 400–2500 Hz | Tight, punchy, cuts pileups | Contest operating, DX pile-ups |

The target curves are grounded in the **Bell Labs Articulation Index** (French & Steinberg 1947) and the **ITU-T P.56 LTASS** reference (Byrne et al. 1994). The 1000–3000 Hz range carries the majority of speech intelligibility; both profiles boost this region while shaping the passband edges to suit the operating style.

---

## Supported EQ Devices

| Device | Bands | Range | Compressor |
|--------|-------|-------|------------|
| **SmartSDR TX EQ** | 63, 125, 250, 500, 1k, 2k, 4k, 8k Hz | ±10 dB | No |
| **UR6QW External EQ** | 80, 160, 250, 900, 1500, 2500, 3200 Hz | ±12 dB | Yes |

Switch between devices in the Export tab — gains are re-computed instantly for the selected hardware.

---

## Requirements

- **Windows 10/11** (64-bit)
- **Python 3.12** — required; 3.13+ breaks audio library compatibility

Python 3.12 installer:
```
winget install Python.Python.3.12
```

---

## Installation

```bat
git clone https://github.com/va3mw/Virga.git
cd Virga
setup.bat
```

`setup.bat` creates a virtual environment, installs all dependencies, and validates the Python version. Run it once; it is safe to re-run if something goes wrong.

### Dependencies (installed automatically)

| Package | Purpose |
|---------|---------|
| PySide6 ≥ 6.6 | GUI framework and audio I/O (QtMultimedia) |
| numpy ≥ 1.26 | FFT, spectrum analysis |
| scipy ≥ 1.11 | Savitzky-Golay smoothing, biquad filter chain |
| pyqtgraph ≥ 0.13 | Real-time spectrum plot |

---

## Running

```bat
run.bat
```

The console window stays open and shows status messages. Close it to exit.

---

## Workflow

### 1 — Create an operator profile
Click **+ New Operator** in the sidebar. Enter your callsign and name. Each callsign gets its own profile; profiles persist across sessions.

### 2 — Calibrate
Go to the **Calibrate** tab.

- Select your microphone from the input device list.
- Choose **Ragchew** or **Contest** mode (the same Rainbow Passage is used for both — mode only affects the EQ target applied to your measurement).
- Click **Start Recording** and read the passage aloud at your normal operating distance and level.
- Recording stops automatically after 35 seconds, or click **Stop** early (minimum 5 seconds of audio).

The passage is the **Rainbow Passage** (Fairbanks 1960) — the telecommunications gold standard for voice analysis. It contains every English phoneme in natural proportion and has been used in Bell Labs speech intelligibility studies.

### 3 — Review Results
The **Results** tab shows:

| Curve | Description |
|-------|-------------|
| White — *Your voice (measured)* | Your smoothed LTASS, normalised to 0 dB at 1 kHz |
| Grey dashed — *Bell Labs LTASS* | ITU-T P.56 long-term average speech reference |
| Green dotted — *Ragchew target* | Desired output shape for ragchew |
| Orange dotted — *Contest target* | Desired output shape for contest |
| Blue — *Your corrected voice* | Predicted output after applying Ragchew EQ |
| Red lines — *F₀ harmonics* | Detected fundamental frequency and harmonics H1–H4 |

Toggle any curve using the checkboxes at the top. The F₀ strip at the bottom reports your detected fundamental frequency and which harmonics fall inside the SSB passband.

### 4 — Export
Go to the **Export (SmartSDR)** tab.

1. Select your **EQ device** from the dropdown.
2. Choose the **Ragchew** or **Contest** sub-tab.
3. Read the gain table — each value is the dB adjustment for that band.
4. Click **Copy to Clipboard** or **Save to File** to export the settings.
5. Use **Play Raw** / **Play Ragchew EQ** / **Play Contest EQ** to audition the effect before applying it to the radio.

#### Entering values in SmartSDR
`Transmit` → `TX EQ` → set each band slider to the value shown.

For Contest: TX ALC ~80 %, Compander ON.  
For Ragchew: TX ALC ~60 %, Compander optional.

---

## Science Background

### LTASS
The Long-Term Average Speech Spectrum averages the power spectral density of speech across many short frames (25 ms, 10 ms hop, Hann window). This smooths out individual phoneme variation to reveal the characteristic spectral shape of the speaker's voice. Normalising to 0 dB at 1 kHz gives a shape measurement independent of recording level.

### Articulation Index (Bell Labs)
French & Steinberg (1947) showed that intelligibility is not uniformly distributed across frequency. The 1000–3000 Hz band carries disproportionate weight; boosting this region — even at the cost of naturalness — maximises word recognition under noise and QRM. The Contest profile exploits this directly.

### F₀ Detection
Fundamental frequency is estimated per frame via autocorrelation. Frames are classified as voiced using zero-crossing rate (ZCR < 0.15) and minimum RMS. The reported F₀ is the median across voiced frames. Knowing F₀ helps interpret the spectrum: resonances at integer multiples are harmonic structure, not EQ artefacts.

---

## File Locations

| Path | Contents |
|------|----------|
| `%APPDATA%\Virga\profiles\` | Operator profiles (JSON, one per callsign) |

Profiles store the callsign, name, creation date, measured LTASS spectrum, F₀, and the EQ gains last computed. Switching EQ devices re-solves gains from the stored spectrum without re-recording.

---

## Version

Version is auto-incremented on every `git commit` via a pre-commit hook (`BUILD` field only). Current version: **0.1.10**

---

## Roadmap

- **Phase 2** — Direct SmartSDR API integration: push EQ values to the radio over the network without manual entry
- Custom user-defined EQ devices (JSON device files in `%APPDATA%\Virga\devices\`)
- Installer / standalone `.exe` (no Python required)
