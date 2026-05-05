from __future__ import annotations

"""
EQ solver: maps a measured LTASS + target profile → band gains for a given device.

The solver also builds a chain of peaking biquad filters at the band frequencies
so the GUI can play back a processed preview.
"""

import numpy as np
from scipy.signal import sosfilt
from .profiles import Profile
from .eq_devices import EQDevice, SMARTSDR_TX_EQ

# Keep SMARTSDR_BANDS as a module-level name — spectrum_view imports it for markers.
SMARTSDR_BANDS = SMARTSDR_TX_EQ.bands


def solve(
    meas_freqs: np.ndarray,
    meas_levels_db: np.ndarray,
    profile: Profile,
    f0_hz: float | None = None,
    device: EQDevice = SMARTSDR_TX_EQ,
) -> dict[int, float]:
    """
    Compute EQ band gains (dB) to move meas_levels toward profile for device.

    Returns {band_hz: gain_db} rounded to the device's step size.
    """
    target_at_meas = profile.at(meas_freqs)

    # Normalise target to 0 dB at 1 kHz — same reference as measured LTASS.
    ref_idx = np.argmin(np.abs(meas_freqs - 1000.0))
    target_at_meas -= target_at_meas[ref_idx]

    correction = target_at_meas - meas_levels_db

    band_gains = np.interp(device.bands, meas_freqs, correction)
    band_gains = np.clip(band_gains, device.min_db, device.max_db)

    # Round to device step size
    steps = 1.0 / device.step_db
    band_gains = np.round(band_gains * steps) / steps

    return {int(f): float(g) for f, g in zip(device.bands, band_gains)}


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
    """Build a scipy SOS filter chain from a band gain dict."""
    rows = []
    for band_hz, gain_db in band_gains.items():
        if abs(gain_db) < 0.25:
            continue
        rows.append(_peaking_biquad(float(band_hz), gain_db, Q, sample_rate))
    if not rows:
        return np.array([[1, 0, 0, 1, 0, 0]], dtype=float)
    return np.vstack(rows)


def apply_eq(audio: np.ndarray, sos: np.ndarray) -> np.ndarray:
    """Apply an SOS filter chain to a mono audio array."""
    return sosfilt(sos, audio).astype(np.float32)
