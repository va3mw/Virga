"""
EQ solver: maps a measured LTASS + target profile → SmartSDR band gains.

SmartSDR TX graphic EQ has 10 fixed bands (ISO octave centres):
  32, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000 Hz
Each band is adjustable ±10 dB.

The solver also builds a chain of peaking biquad filters at those same
frequencies so the GUI can play back a processed preview.
"""

import numpy as np
from scipy.signal import sosfilt
from .profiles import Profile

# SmartSDR TX EQ band centre frequencies (Hz)
SMARTSDR_BANDS = np.array([32, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000], dtype=float)
SMARTSDR_MAX_DB = 10.0
SMARTSDR_MIN_DB = -10.0


def solve(
    meas_freqs: np.ndarray,
    meas_levels_db: np.ndarray,
    profile: Profile,
    f0_hz: float | None = None,
) -> dict[int, float]:
    """
    Compute SmartSDR band gains (dB) to move meas_levels toward profile.

    Returns a dict {band_hz: gain_db} rounded to 0.5 dB steps.
    """
    # Evaluate target at the measured frequency bins
    target_at_meas = profile.at(meas_freqs)

    # Correction = target − measured (what EQ must add)
    correction = target_at_meas - meas_levels_db

    # Remove DC offset (we equalise shape, not loudness)
    mask = (meas_freqs >= 200) & (meas_freqs <= 4000)
    if mask.sum() > 0:
        correction -= np.mean(correction[mask])

    # Interpolate correction at SmartSDR band centres
    band_gains = np.interp(SMARTSDR_BANDS, meas_freqs, correction)

    # Clip to hardware limits and round to 0.5 dB steps
    band_gains = np.clip(band_gains, SMARTSDR_MIN_DB, SMARTSDR_MAX_DB)
    band_gains = np.round(band_gains * 2) / 2

    return {int(f): float(g) for f, g in zip(SMARTSDR_BANDS, band_gains)}


def _peaking_biquad(freq: float, gain_db: float, Q: float, sr: float) -> np.ndarray:
    """Return a single peaking EQ biquad as a (1,6) SOS row."""
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * freq / sr
    alpha = np.sin(w0) / (2 * Q)

    b0 = 1 + alpha * A
    b1 = -2 * np.cos(w0)
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * np.cos(w0)
    a2 = 1 - alpha / A

    return np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]])


def build_sos(band_gains: dict[int, float], sample_rate: float, Q: float = 1.41) -> np.ndarray:
    """
    Build a scipy SOS filter chain from SmartSDR band gain dict.
    Q=1.41 (~0.7 octave) matches a graphic EQ overlap convention.
    """
    rows = []
    for band_hz, gain_db in band_gains.items():
        if abs(gain_db) < 0.25:
            continue  # skip near-unity bands
        rows.append(_peaking_biquad(float(band_hz), gain_db, Q, sample_rate))
    if not rows:
        # Identity filter
        return np.array([[1, 0, 0, 1, 0, 0]], dtype=float)
    return np.vstack(rows)


def apply_eq(audio: np.ndarray, sos: np.ndarray) -> np.ndarray:
    """Apply an SOS filter chain to a mono audio array."""
    return sosfilt(sos, audio).astype(np.float32)
