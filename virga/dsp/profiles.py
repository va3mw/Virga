from __future__ import annotations

"""
Target EQ profiles for the two SSB modes.

Both curves represent the *desired* LTASS shape at the transmitter output
(mic + EQ + radio). The EQ solver computes the correction needed to move
the user's measured LTASS toward the selected target.

Science basis:
  - French & Steinberg (1947) Articulation Index: 1000–3000 Hz carries the
    majority of speech intelligibility. Higher frequencies contribute
    disproportionately to consonant discrimination.
  - LTASS rolls off naturally ~6 dB/octave above 500 Hz; boosting the high
    end compensates and flattens intelligibility across the SSB passband.
  - For ragchew, the 2nd and 3rd voice harmonics (300–750 Hz for typical
    male, 400–900 Hz female) are preserved for warmth and naturalness.
  - SSB passband is nominally 300–2700 Hz; contest mode trims aggressively
    to fit and maximise punch within that window.
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple

# Shared frequency axis for profile definitions (Hz)
PROFILE_FREQS = np.array([
    100, 200, 300, 400, 500, 630, 800, 1000, 1250, 1600,
    2000, 2500, 3000, 4000, 6300, 8000
], dtype=float)


@dataclass
class Profile:
    name: str
    freqs: np.ndarray   # Hz
    levels: np.ndarray  # dB, relative (not absolute gain)
    description: str
    passband_low: float   # Hz
    passband_high: float  # Hz

    def at(self, query_freqs: np.ndarray) -> np.ndarray:
        return np.interp(query_freqs, self.freqs, self.levels,
                         left=self.levels[0], right=self.levels[-1])


# Ragchew-specific frequency axis — extended below 100 Hz and above 3 kHz
RAGCHEW_FREQS = np.array([
    50, 100, 200, 300, 400, 500, 630, 800, 1000, 1250,
    1600, 2000, 2500, 3000, 3200, 4000, 6300, 8000
], dtype=float)

# --- Ragchew -----------------------------------------------------------
# Broad passband (50–3200 Hz). Full low-end warmth including fundamental
# voice harmonics below 100 Hz. Gentle presence lift 1.5–2 kHz.
RAGCHEW = Profile(
    name="Ragchew",
    freqs=RAGCHEW_FREQS,
    levels=np.array([
        -12.0,   # 50 Hz   — sub-bass, allow body without boom
         -5.0,   # 100 Hz
          0.0,   # 200 Hz  — low harmonic warmth
          3.5,   # 300 Hz
          5.5,   # 400 Hz
          6.5,   # 500 Hz
          6.5,   # 630 Hz
          6.0,   # 800 Hz
          5.5,   # 1000 Hz — anchor
          6.0,   # 1250 Hz
          6.5,   # 1600 Hz — gentle presence lift
          6.0,   # 2000 Hz
          4.5,   # 2500 Hz
          2.0,   # 3000 Hz
          0.5,   # 3200 Hz — passband edge
         -5.0,   # 4000 Hz — roll off
        -14.0,   # 6300 Hz
        -18.0,   # 8000 Hz
    ], dtype=float),
    description="Natural, warm, readable — everyday QSOs",
    passband_low=50.0,
    passband_high=3200.0,
)

# Contest-specific frequency axis — adds 2900 Hz passband edge point
CONTEST_FREQS = np.array([
    100, 200, 300, 400, 500, 630, 800, 1000, 1250, 1600,
    2000, 2500, 2900, 3000, 4000, 6300, 8000
], dtype=float)

# --- Contest -----------------------------------------------------------
# Tight passband (400–2900 Hz). Sacrifices low-end warmth entirely.
# Flat-to-rising in 400–2000 Hz to maximise Articulation Index. Hard brick
# walls outside the SSB passband. Expects downstream compression/limiting
# in SmartSDR to drive the processed signal to the TX ALC ceiling.
CONTEST = Profile(
    name="Contest",
    freqs=CONTEST_FREQS,
    levels=np.array([
        -20.0,   # 100 Hz  — cut completely
        -14.0,   # 200 Hz  — cut
         -7.0,   # 300 Hz  — roll in
          0.0,   # 400 Hz  — passband starts
          3.0,   # 500 Hz
          5.0,   # 630 Hz
          6.5,   # 800 Hz
          7.5,   # 1000 Hz — anchor of Articulation Index sweet spot
          8.0,   # 1250 Hz — peak intelligibility region
          8.0,   # 1600 Hz
          7.5,   # 2000 Hz
          6.5,   # 2500 Hz
          4.0,   # 2900 Hz — passband edge
         -3.0,   # 3000 Hz — sharp rolloff
        -12.0,   # 4000 Hz — hard cut
        -20.0,   # 6300 Hz
        -22.0,   # 8000 Hz
    ], dtype=float),
    description="Punchy, tight, cuts through pileups — contests",
    passband_low=400.0,
    passband_high=2900.0,
)

PROFILES: dict[str, Profile] = {
    "ragchew": RAGCHEW,
    "contest": CONTEST,
}
