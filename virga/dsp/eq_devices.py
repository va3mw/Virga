from __future__ import annotations

"""
EQ device definitions.

Each EQDevice describes the band layout, gain limits, and capabilities of one
physical or software EQ. Two devices are built-in; future custom devices can
be added to BUILTIN_DEVICES or loaded from JSON files in APPDATA.
"""

from dataclasses import dataclass, field
import numpy as np


@dataclass
class EQDevice:
    name: str
    bands: np.ndarray      # centre frequencies, Hz, ascending
    min_db: float
    max_db: float
    step_db: float         # finest gain step the hardware supports
    has_compressor: bool
    compressor_note: str   # shown in export when has_compressor is True
    description: str

    @property
    def band_labels(self) -> list[str]:
        labels = []
        for hz in self.bands:
            hz = int(hz)
            if hz >= 1000 and hz % 1000 == 0:
                labels.append(f"{hz // 1000}k")
            elif hz >= 1000:
                labels.append(f"{hz / 1000:.1f}k")
            else:
                labels.append(str(hz))
        return labels


SMARTSDR_TX_EQ = EQDevice(
    name="SmartSDR TX EQ",
    bands=np.array([63, 125, 250, 500, 1000, 2000, 4000, 8000], dtype=float),
    min_db=-10.0,
    max_db=10.0,
    step_db=1.0,
    has_compressor=False,
    compressor_note="",
    description="FlexRadio SmartSDR built-in 8-band TX graphic EQ",
)

UR6QW_EQ = EQDevice(
    name="UR6QW External EQ",
    bands=np.array([80, 160, 250, 900, 1500, 2500, 3200], dtype=float),
    min_db=-12.0,
    max_db=12.0,
    step_db=1.0,
    has_compressor=True,
    compressor_note=(
        "This device has an onboard compressor. "
        "Suggested starting point: ratio 3:1, attack 10 ms, release 200 ms, "
        "threshold set so gain reduction averages 6–8 dB on voice peaks."
    ),
    description="UR6QW 7-band external EQ with onboard compressor",
)

# Ordered list used to populate the device selector dropdown.
# Add new devices here — the UI picks them up automatically.
BUILTIN_DEVICES: list[EQDevice] = [SMARTSDR_TX_EQ, UR6QW_EQ]

DEVICES: dict[str, EQDevice] = {d.name: d for d in BUILTIN_DEVICES}
