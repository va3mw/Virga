"""
Long-Term Average Speech Spectrum (LTASS) reference data.

Derived from Bell Labs / ITU-T P.56 research (French & Steinberg 1947,
Byrne et al. 1994). Values represent the average spectral shape of
conversational speech, normalised to 0 dB at 1000 Hz.

These data are used to:
  1. Compare a user's measured LTASS against the population norm.
  2. Anchor the target curves for ragchew and contest profiles.
"""

import numpy as np

# 1/3-octave centre frequencies (Hz)
LTASS_FREQS = np.array([
    100, 125, 160, 200, 250, 315, 400, 500, 630, 800,
    1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000
], dtype=float)

# Relative levels (dB), normalised to 0 dB at 1000 Hz.
# Natural speech rolls off ~6 dB/octave above ~500 Hz.
LTASS_LEVELS = np.array([
    2.0, 3.6, 4.9, 5.9, 6.6, 7.0, 6.5, 5.8, 4.5, 2.8,
    0.0, -2.2, -4.5, -6.9, -9.5, -12.3, -15.3, -18.5, -21.8, -25.3
], dtype=float)


def get_ltass_at(freqs: np.ndarray) -> np.ndarray:
    """Interpolate the LTASS reference at arbitrary frequencies."""
    return np.interp(freqs, LTASS_FREQS, LTASS_LEVELS,
                     left=LTASS_LEVELS[0], right=LTASS_LEVELS[-1])
