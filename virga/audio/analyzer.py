from __future__ import annotations

"""
Voice analysis: LTASS and fundamental frequency (F0) estimation.

LTASS (Long-Term Average Speech Spectrum) is computed by averaging power
spectra across short overlapping frames — the standard method in ITU-T P.56
and the Bell Labs intelligibility literature.

F0 is estimated via autocorrelation of voiced frames, with a voiced/unvoiced
discriminator based on zero-crossing rate to exclude pauses and noise.
"""

import numpy as np
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    freqs: np.ndarray        # FFT frequency bins (Hz)
    ltass_db: np.ndarray     # LTASS in dB (same length as freqs)
    f0_hz: float             # Median fundamental frequency (Hz), or 0 if undetected
    f0_label: str            # e.g. "~135 Hz (typical male)"
    sample_rate: int


def compute_ltass(audio: np.ndarray, sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute the Long-Term Average Speech Spectrum.

    Returns (freqs_hz, levels_db) arrays.
    """
    frame_size = int(0.025 * sample_rate)   # 25 ms
    hop_size = int(0.010 * sample_rate)     # 10 ms
    window = np.hanning(frame_size)

    power_accumulator = np.zeros(frame_size // 2 + 1)
    frame_count = 0

    for start in range(0, len(audio) - frame_size, hop_size):
        frame = audio[start: start + frame_size] * window
        spectrum = np.abs(np.fft.rfft(frame)) ** 2
        power_accumulator += spectrum
        frame_count += 1

    if frame_count == 0:
        freqs = np.fft.rfftfreq(frame_size, 1.0 / sample_rate)
        return freqs, np.zeros_like(freqs)

    avg_power = power_accumulator / frame_count
    freqs = np.fft.rfftfreq(frame_size, 1.0 / sample_rate)
    ltass_db = 10.0 * np.log10(avg_power + 1e-12)

    # Normalise to 0 dB at ~1000 Hz
    ref_idx = np.argmin(np.abs(freqs - 1000.0))
    ltass_db -= ltass_db[ref_idx]

    return freqs, ltass_db


def _autocorr_f0(frame: np.ndarray, sample_rate: int,
                  fmin: float = 75.0, fmax: float = 350.0) -> float:
    """Estimate F0 of a single frame via autocorrelation. Returns 0 if no pitch found."""
    n = len(frame)
    corr = np.correlate(frame, frame, mode='full')[n - 1:]
    lag_min = max(1, int(sample_rate / fmax))
    lag_max = min(n - 1, int(sample_rate / fmin))
    if lag_min >= lag_max:
        return 0.0
    peak_lag = lag_min + int(np.argmax(corr[lag_min:lag_max]))
    # Confidence: peak must exceed 30% of zero-lag energy
    if corr[peak_lag] < 0.30 * corr[0]:
        return 0.0
    return sample_rate / peak_lag


def detect_f0(audio: np.ndarray, sample_rate: int) -> float:
    """
    Estimate the speaker's fundamental frequency across the recording.
    Returns the median voiced-frame F0 in Hz, or 0 if voice not detected.
    """
    frame_size = int(0.040 * sample_rate)   # 40 ms — longer than LTASS frame for pitch
    hop_size = int(0.010 * sample_rate)

    voiced_f0s = []
    for start in range(0, len(audio) - frame_size, hop_size):
        frame = audio[start: start + frame_size].copy()

        # Skip silent frames
        rms = np.sqrt(np.mean(frame ** 2))
        if rms < 0.005:
            continue

        # Zero-crossing rate — voiced speech has low ZCR
        zcr = np.mean(np.abs(np.diff(np.sign(frame)))) / 2
        if zcr > 0.15:
            continue

        f0 = _autocorr_f0(frame, sample_rate)
        if f0 > 0:
            voiced_f0s.append(f0)

    if not voiced_f0s:
        return 0.0
    return float(np.median(voiced_f0s))


def _f0_label(f0: float) -> str:
    if f0 == 0:
        return "Not detected"
    if f0 < 145:
        range_label = "typical male"
    elif f0 < 195:
        range_label = "higher male / lower female"
    else:
        range_label = "typical female"
    return f"~{f0:.0f} Hz ({range_label})"


def analyse(audio: np.ndarray, sample_rate: int) -> AnalysisResult:
    freqs, ltass_db = compute_ltass(audio, sample_rate)
    f0 = detect_f0(audio, sample_rate)
    return AnalysisResult(
        freqs=freqs,
        ltass_db=ltass_db,
        f0_hz=f0,
        f0_label=_f0_label(f0),
        sample_rate=sample_rate,
    )
