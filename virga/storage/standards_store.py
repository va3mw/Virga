from __future__ import annotations

"""
Reference standard storage — named LTASS curves saved by the operator.

A standard is a measured spectrum saved as an EQ target so other operators
(or the same operator on different equipment) can calibrate to match it.
Stored as JSON files in %APPDATA%/Virga/standards/.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import numpy as np

from ..dsp.profiles import Profile


def _dir() -> Path:
    base = os.environ.get("APPDATA", Path.home())
    d = Path(base) / "Virga" / "standards"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(name: str, description: str,
         freqs: np.ndarray, levels: np.ndarray) -> None:
    data = {
        "name": name,
        "description": description,
        "created": datetime.now().isoformat(timespec="seconds"),
        "freqs": freqs.tolist(),
        "levels": levels.tolist(),
    }
    safe = name.replace(" ", "_").replace("/", "-")
    (_dir() / f"{safe}.json").write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )


def load_all() -> list[Profile]:
    """Return all saved standards as Profile objects, sorted by name."""
    profiles = []
    for p in sorted(_dir().glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            profiles.append(Profile(
                name=d["name"],
                freqs=np.array(d["freqs"]),
                levels=np.array(d["levels"]),
                description=d.get("description", ""),
                passband_low=200.0,
                passband_high=3000.0,
            ))
        except Exception:
            pass
    return profiles


def delete(name: str) -> None:
    safe = name.replace(" ", "_").replace("/", "-")
    p = _dir() / f"{safe}.json"
    if p.exists():
        p.unlink()


def list_names() -> list[str]:
    return [p.name for p in load_all()]
